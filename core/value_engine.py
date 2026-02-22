"""
Digital Being — ValueEngine
Stage 11: Added get_scores() alias and get_conflicts() for IntrospectionAPI.
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

_SCORE_NAMES = ("stability", "accuracy", "growth", "curiosity", "boredom")

_ALL_CONFLICTS = (
    "exploration_vs_stability",
    "growth_vs_accuracy",
    "action_vs_caution",
    "expansion_vs_control",
)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, round(v, 4)))


class ValueEngine:

    def __init__(self, cfg: dict, bus: "EventBus") -> None:
        self._cfg        = cfg
        self._bus        = bus
        self._state_path: Path | None = None
        self._drift_dir  = Path(cfg["scores"]["drift"]["snapshot_dir"])
        self._max_drift  = float(cfg["scores"]["drift"].get("max_weekly_change", 0.3))
        self._scores: dict[str, float] = {
            "stability": 0.7,
            "accuracy":  0.8,
            "growth":    0.5,
            "curiosity": 0.8,
            "boredom":   0.0,
        }
        self.locked_values: list[str] = []

    # ─ Lifecycle ─────────────────────────────────────────────────────────
    def load(self, state_path: Path, seed_path: Path) -> None:
        self._state_path = state_path
        self._drift_dir.mkdir(parents=True, exist_ok=True)
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
        self._bus.subscribe("world.updated", self._on_world_updated)
        log.debug("ValueEngine subscribed to world.updated.")

    # ─ Score read ───────────────────────────────────────────────────────
    def get(self, score_name: str) -> float:
        return self._scores.get(score_name, 0.0)

    def snapshot(self) -> dict:
        """Return all scores as a plain dict."""
        return dict(self._scores)

    def get_scores(self) -> dict:
        """Alias for snapshot(). Stage 11."""
        return self.snapshot()

    def get_mode(self) -> str:
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

    def get_conflicts(self) -> list[dict]:
        """
        Return all conflicts with their current winner.
        Stage 11: used by IntrospectionAPI /values endpoint.
        """
        conflicts = []
        for name in _ALL_CONFLICTS:
            risk = 0.25 if self.get_mode() in ("curious", "normal") else 0.5
            winner = self.get_conflict_winner(name, risk_score=risk)
            conflicts.append({"conflict": name, "winner": winner})
        return conflicts

    def get_conflict_winner(self, conflict: str, risk_score: float = 0.0) -> str:
        s = self._scores
        if conflict == "exploration_vs_stability":
            return "stability" if s["stability"] <= 0.8 else "exploration"
        if conflict == "growth_vs_accuracy":
            return "accuracy" if s["accuracy"] <= 0.9 else "growth"
        if conflict == "action_vs_caution":
            return "caution" if risk_score >= 0.2 else "action"
        if conflict == "expansion_vs_control":
            return "control"
        log.warning(f"[get_conflict_winner] Unknown conflict: '{conflict}'")
        return "unknown"

    # ─ Score write ──────────────────────────────────────────────────────
    def adjust(self, score_name: str, delta: float) -> float:
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
        if score_name not in _SCORE_NAMES:
            return
        old = self._scores[score_name]
        new = _clamp(old + delta)
        self._scores[score_name] = new
        sign = "+" if delta >= 0 else ""
        log.info(f"Score: {score_name}: {old:.2f} → {new:.2f} (Δ{sign}{delta:.2f})")

    def update_after_action(self, success: bool) -> None:
        if success:
            self._adjust_silent("accuracy",  +0.05)
            self._adjust_silent("stability", +0.02)
            self._adjust_silent("boredom",   -0.05)
        else:
            self._adjust_silent("accuracy",  -0.05)
            self._adjust_silent("stability", -0.03)
            self._adjust_silent("growth",    -0.02)
        self._persist_state()

    def update_boredom(self, novelty_score: float) -> None:
        if novelty_score > 0.7:
            self._adjust_silent("boredom",   -0.10)
            self._adjust_silent("curiosity", -0.05)
        elif novelty_score < 0.3:
            self._adjust_silent("boredom",   +0.10)
            self._adjust_silent("curiosity", +0.05)
        self._persist_state()

    # ─ Snapshot & prompt context ───────────────────────────────────
    def to_prompt_context(self) -> str:
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

    # ─ Drift ───────────────────────────────────────────────────────────
    def save_weekly_snapshot(self) -> None:
        self._drift_dir.mkdir(parents=True, exist_ok=True)
        date_str = time.strftime("%Y-%m-%d")
        out_path = self._drift_dir / f"{date_str}.json"
        tmp_path = out_path.with_suffix(".tmp")
        payload  = {"date": date_str, "scores": self.snapshot(), "mode": self.get_mode()}
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            tmp_path.replace(out_path)
            log.info(f"Weekly drift snapshot saved: {out_path.name}")
        except OSError as e:
            log.error(f"Failed to save weekly snapshot: {e}")
            if tmp_path.exists():
                tmp_path.unlink()

    def check_drift(self) -> list[str]:
        target_date   = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
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
            current  = self._scores.get(name, 0.0)
            previous = float(past_scores.get(name, current))
            delta    = abs(current - previous)
            if delta > self._max_drift:
                msg = (
                    f"DRIFT WARNING: {name} changed {previous:.2f} → {current:.2f} "
                    f"(Δ{delta:.2f} > max {self._max_drift:.2f}) over 7 days"
                )
                warnings.append(msg)
                log.warning(msg)
        return warnings

    # ─ EventBus ──────────────────────────────────────────────────────────
    async def _on_world_updated(self, data: dict) -> None:
        summary = data.get("summary", "")
        novelty = self._novelty_from_summary(summary)
        self.update_boredom(novelty)
        await self._publish_changed()

    async def _publish_changed(self) -> None:
        await self._bus.publish("value.changed", {
            "scores":  self.snapshot(),
            "mode":    self.get_mode(),
            "context": self.to_prompt_context(),
        })

    @staticmethod
    def _novelty_from_summary(summary: str) -> float:
        try:
            for part in summary.split():
                if part.startswith("changes_24h="):
                    n = int(part.split("=")[1])
                    if n == 0:    return 0.0
                    elif n <= 2:  return 0.3
                    elif n <= 5:  return 0.5
                    else:         return 0.8
        except (ValueError, IndexError):
            pass
        return 0.5

    # ─ Persistence ─────────────────────────────────────────────────────
    def _persist_state(self) -> None:
        """Atomically persist scores to state.json using .tmp + replace()."""
        if self._state_path is None or not self._state_path.exists():
            return
        tmp_path = self._state_path.with_suffix(".tmp")
        try:
            with self._state_path.open("r", encoding="utf-8") as f:
                state = json.load(f)
            state["scores"] = self.snapshot()
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self._state_path)  # atomic
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"[_persist_state] Failed to write state.json: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
