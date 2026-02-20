"""
Digital Being — ValueEngine
Phase 5: Score management, mode detection, conflict resolution, drift tracking.

Rules:
  - All scores are float clamped to [0.0, 1.0]
  - Every change is logged: "stability: 0.70 → 0.75 (Δ+0.05)"
  - state.json is updated on every score change
  - anchor_values are read-only, never modified
  - Drift detection compares current scores to weekly snapshot
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.event_bus import EventBus

log = logging.getLogger("digital_being.value_engine")

# All score names in canonical order
_SCORE_NAMES = ("stability", "accuracy", "growth", "curiosity", "boredom")


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, round(v, 4)))


class ValueEngine:
    """
    Manages all system scores and drives behavioural mode.

    Lifecycle:
        ve = ValueEngine(cfg, bus)
        ve.load(state_path, seed_path)   # call once at startup
        # ... runs via EventBus events
    """

    def __init__(self, cfg: dict, bus: "EventBus") -> None:
        self._cfg          = cfg
        self._bus          = bus
        self._state_path:  Path | None = None
        self._drift_dir:   Path = Path(
            cfg["scores"]["drift"]["snapshot_dir"]
        )
        self._max_drift:   float = float(
            cfg["scores"]["drift"].get("max_weekly_change", 0.3)
        )

        # Scores live here
        self._scores: dict[str, float] = {
            "stability": 0.7,
            "accuracy":  0.8,
            "growth":    0.5,
            "curiosity": 0.8,
            "boredom":   0.0,
        }

        # Read-only anchor values from seed
        self.locked_values: list[str] = []

    # ────────────────────────────────────────────────────────────
    # Lifecycle
    # ────────────────────────────────────────────────────────────
    def load(self, state_path: Path, seed_path: Path) -> None:
        """
        Load scores from state.json (if it exists).
        Load anchor_values from seed.yaml.
        """
        self._state_path = state_path
        self._drift_dir.mkdir(parents=True, exist_ok=True)

        # Load scores from state.json
        if state_path.exists():
            try:
                with state_path.open("r", encoding="utf-8") as f:
                    state = json.load(f)
                saved = state.get("scores", {})
                for name in _SCORE_NAMES:
                    if name in saved:
                        self._scores[name] = _clamp(float(saved[name]))
                log.info(f"Scores loaded from state.json: {self._fmt_scores()}")
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Could not load scores from state.json: {e}. Using defaults.")

        # Load anchor values from seed.yaml
        if seed_path.exists():
            try:
                import yaml
                with seed_path.open("r", encoding="utf-8") as f:
                    seed = yaml.safe_load(f)
                anchors = seed.get("anchor_values", {})
                self.locked_values = anchors.get("values", [])
                log.info(f"Anchor values loaded ({len(self.locked_values)} rules, locked=True).")
            except Exception as e:
                log.warning(f"Could not load anchor values from seed.yaml: {e}")

    def subscribe(self) -> None:
        """Wire EventBus handlers."""
        self._bus.subscribe("world.updated", self._on_world_updated)
        log.debug("ValueEngine subscribed to world.updated.")

    # ────────────────────────────────────────────────────────────
    # Core score API
    # ────────────────────────────────────────────────────────────
    def get(self, score_name: str) -> float:
        """Return current value of a score. Returns 0.0 for unknown names."""
        return self._scores.get(score_name, 0.0)

    def adjust(self, score_name: str, delta: float) -> float:
        """
        Adjust a score by delta. Clamps result to [0.0, 1.0].
        Logs the change and persists to state.json.
        Returns the new value.
        """
        if score_name not in _SCORE_NAMES:
            log.warning(f"[adjust] Unknown score name: '{score_name}'")
            return 0.0

        old = self._scores[score_name]
        new = _clamp(old + delta)
        self._scores[score_name] = new

        sign = "+" if delta >= 0 else ""
        log.info(f"Score: {score_name}: {old:.2f} → {new:.2f} (Δ{sign}{delta:.2f})")

        self._persist_state()
        return new

    def _adjust_silent(self, score_name: str, delta: float) -> None:
        """Adjust without triggering persistence — used for batch updates."""
        if score_name not in _SCORE_NAMES:
            return
        old = self._scores[score_name]
        new = _clamp(old + delta)
        self._scores[score_name] = new
        sign = "+" if delta >= 0 else ""
        log.info(f"Score: {score_name}: {old:.2f} → {new:.2f} (Δ{sign}{delta:.2f})")

    # ────────────────────────────────────────────────────────────
    # Composite updates
    # ────────────────────────────────────────────────────────────
    def update_after_action(self, success: bool) -> None:
        """
        Update scores after any action completes.
          success=True:  accuracy+0.05, stability+0.02, boredom-0.05
          success=False: accuracy-0.05, stability-0.03, growth-0.02
        Batched: one persist + one bus event at the end.
        """
        if success:
            self._adjust_silent("accuracy",  +0.05)
            self._adjust_silent("stability", +0.02)
            self._adjust_silent("boredom",   -0.05)
        else:
            self._adjust_silent("accuracy",  -0.05)
            self._adjust_silent("stability", -0.03)
            self._adjust_silent("growth",    -0.02)

        self._persist_state()
        # publish is scheduled by caller via asyncio if needed — see _publish_changed

    def update_boredom(self, novelty_score: float) -> None:
        """
        Update boredom and curiosity based on action novelty.
          high novelty (>0.7): boredom-0.1, curiosity-0.05
          low  novelty (<0.3): boredom+0.1, curiosity+0.05
        """
        if novelty_score > 0.7:
            self._adjust_silent("boredom",   -0.10)
            self._adjust_silent("curiosity", -0.05)
        elif novelty_score < 0.3:
            self._adjust_silent("boredom",   +0.10)
            self._adjust_silent("curiosity", +0.05)
        # mid-range: no change

        self._persist_state()

    # ────────────────────────────────────────────────────────────
    # Mode & conflict
    # ────────────────────────────────────────────────────────────
    def get_mode(self) -> str:
        """
        Returns the system’s current behavioural mode.
        Priority order (first match wins):
          defensive → passive → curious → normal
        """
        s = self._scores
        thresholds = self._cfg["scores"]["thresholds"]

        if (s["stability"] < thresholds["stability_warn"]
                or s["accuracy"] < thresholds["accuracy_warn"]):
            return "defensive"

        if s["boredom"] > 0.7 and s["growth"] < thresholds["growth_warn"]:
            return "passive"

        if s["curiosity"] > 0.7 and s["stability"] >= thresholds["stability_warn"]:
            return "curious"

        return "normal"

    def get_conflict_winner(
        self,
        conflict: str,
        risk_score: float = 0.0,
    ) -> str:
        """
        Resolve a named conflict.

        Supported conflicts:
          exploration_vs_stability  → stability (unless stability > 0.8)
          growth_vs_accuracy        → accuracy  (unless accuracy > 0.9)
          action_vs_caution         → caution   if risk_score >= 0.2, else action
          expansion_vs_control      → always control (Phase 1)
        """
        s = self._scores

        if conflict == "exploration_vs_stability":
            return "stability" if s["stability"] <= 0.8 else "exploration"

        if conflict == "growth_vs_accuracy":
            return "accuracy" if s["accuracy"] <= 0.9 else "growth"

        if conflict == "action_vs_caution":
            return "caution" if risk_score >= 0.2 else "action"

        if conflict == "expansion_vs_control":
            return "control"  # Phase 1: always conservative

        log.warning(f"[get_conflict_winner] Unknown conflict: '{conflict}'")
        return "unknown"

    # ────────────────────────────────────────────────────────────
    # Snapshot & prompt context
    # ────────────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        """Return all scores as a plain dict."""
        return dict(self._scores)

    def to_prompt_context(self) -> str:
        """Short string for insertion into an LLM prompt."""
        s = self._scores
        return (
            f"stability={s['stability']:.2f} "
            f"accuracy={s['accuracy']:.2f} "
            f"growth={s['growth']:.2f} "
            f"curiosity={s['curiosity']:.2f} "
            f"boredom={s['boredom']:.2f} "
            f"mode={self.get_mode()}"
        )

    def _fmt_scores(self) -> str:
        s = self._scores
        return (f"stability={s['stability']:.2f} accuracy={s['accuracy']:.2f} "
                f"growth={s['growth']:.2f} curiosity={s['curiosity']:.2f} "
                f"boredom={s['boredom']:.2f}")

    # ────────────────────────────────────────────────────────────
    # Drift detection
    # ────────────────────────────────────────────────────────────
    def save_weekly_snapshot(self) -> None:
        """Save current scores to memory/drift_snapshots/YYYY-MM-DD.json."""
        self._drift_dir.mkdir(parents=True, exist_ok=True)
        date_str  = time.strftime("%Y-%m-%d")
        out_path  = self._drift_dir / f"{date_str}.json"
        payload   = {
            "date":   date_str,
            "scores": self.snapshot(),
            "mode":   self.get_mode(),
        }
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        log.info(f"Weekly drift snapshot saved: {out_path.name}")

    def check_drift(self) -> list[str]:
        """
        Compare current scores to the snapshot from 7 days ago.
        Returns list of warning strings for any score that changed > max_weekly_change.
        Returns [] if no snapshot found or all scores are stable.
        """
        target_date = time.strftime(
            "%Y-%m-%d",
            time.localtime(time.time() - 7 * 86400),
        )
        snapshot_path = self._drift_dir / f"{target_date}.json"

        if not snapshot_path.exists():
            log.debug(f"[check_drift] No snapshot for {target_date}, skipping.")
            return []

        try:
            with snapshot_path.open("r", encoding="utf-8") as f:
                past = json.load(f)
            past_scores = past.get("scores", {})
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"[check_drift] Could not read snapshot {target_date}: {e}")
            return []

        warnings: list[str] = []
        for name in _SCORE_NAMES:
            current = self._scores.get(name, 0.0)
            previous = float(past_scores.get(name, current))
            delta = abs(current - previous)
            if delta > self._max_drift:
                msg = (
                    f"DRIFT WARNING: {name} changed {previous:.2f} → {current:.2f} "
                    f"(Δ{delta:.2f} > max {self._max_drift:.2f}) over 7 days"
                )
                warnings.append(msg)
                log.warning(msg)

        return warnings

    # ────────────────────────────────────────────────────────────
    # EventBus handlers
    # ────────────────────────────────────────────────────────────
    async def _on_world_updated(self, data: dict) -> None:
        """
        Called on world.updated.
        Extracts novelty from the summary string (changes_24h count),
        maps it to a 0.0–1.0 novelty_score, then updates boredom.
        """
        summary = data.get("summary", "")
        novelty = self._novelty_from_summary(summary)
        self.update_boredom(novelty)
        await self._publish_changed()

    async def _publish_changed(self) -> None:
        """Publish value.changed event with current snapshot."""
        await self._bus.publish("value.changed", {
            "scores": self.snapshot(),
            "mode":   self.get_mode(),
            "context": self.to_prompt_context(),
        })

    @staticmethod
    def _novelty_from_summary(summary: str) -> float:
        """
        Parse 'changes_24h=N' from world.updated summary string.
        Map N to a novelty score:
          0 changes   → 0.0  (boring)
          1–2 changes  → 0.3  (low)
          3–5 changes  → 0.5  (medium)
          6+ changes   → 0.8  (high novelty)
        """
        try:
            for part in summary.split():
                if part.startswith("changes_24h="):
                    n = int(part.split("=")[1])
                    if n == 0:       return 0.0
                    elif n <= 2:     return 0.3
                    elif n <= 5:     return 0.5
                    else:            return 0.8
        except (ValueError, IndexError):
            pass
        return 0.5  # neutral default

    # ────────────────────────────────────────────────────────────
    # State persistence
    # ────────────────────────────────────────────────────────────
    def _persist_state(self) -> None:
        """
        Update the 'scores' field in state.json without touching other fields.
        """
        if self._state_path is None or not self._state_path.exists():
            return
        try:
            with self._state_path.open("r", encoding="utf-8") as f:
                state = json.load(f)
            state["scores"] = self.snapshot()
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"[_persist_state] Could not write state.json: {e}")
