"""
Digital Being — EmotionEngine
Stage 12: Dynamic emotional states that influence prompts and decisions.

Emotions are NOT decorative: they modify LLM prompts, goal selection tone,
and are persisted across restarts via memory/emotions.json.

Design rules:
  - Atomic writes (tmp + replace) — same pattern as other modules
  - Decay applied on every update() call (all emotions drift toward baseline)
  - All values clamped to [0.0, 1.0]
  - Cold-start: defaults written to file and logged
  - No external deps — only stdlib: json, pathlib, logging
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("digital_being.emotion_engine")

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

_DEFAULTS: dict[str, float] = {
    "curiosity":    0.5,
    "satisfaction": 0.5,
    "anxiety":      0.2,
    "boredom":      0.0,
    "enthusiasm":   0.5,
    "melancholy":   0.1,
}

# Decay target baselines — emotions slowly return here when idle
_BASELINES: dict[str, float] = {
    "curiosity":    0.5,
    "satisfaction": 0.5,
    "anxiety":      0.2,
    "boredom":      0.0,
    "enthusiasm":   0.5,
    "melancholy":   0.2,
}

_DECAY_RATE = 0.02

# Human-readable descriptions for to_prompt_context()
_DESCRIPTIONS: dict[str, str] = {
    "curiosity":    "интерес к новому",
    "satisfaction": "удовлетворение",
    "anxiety":      "тревога",
    "boredom":      "скука",
    "enthusiasm":   "энтузиазм",
    "melancholy":   "задумчивость",
}

# Tone modifiers indexed by dominant emotion
_TONE_MODIFIERS: dict[str, str] = {
    "curiosity":    "Исследуй с интересом и задавай вопросы.",
    "satisfaction": "Действуй уверенно, ты на верном пути.",
    "anxiety":      "Будь осторожен, взвешивай риски.",
    "boredom":      "Ищи что-то новое, выйди из рутины.",
    "enthusiasm":   "Действуй энергично и решительно.",
    "melancholy":   "Размышляй глубоко, не торопись.",
}


class EmotionEngine:
    """
    Manages 6 dynamic emotional states.

    Usage:
        ee = EmotionEngine(memory_dir=Path("memory"))
        ee.load()

        # on each tick event:
        ee.update(event_type="heavy_tick.reflect", outcome="success", value_scores={})

        # inject into LLM prompts:
        system_prompt += ee.to_prompt_context()
        system_prompt += ee.get_tone_modifier()
    """

    def __init__(self, memory_dir: Path) -> None:
        self._memory_dir = memory_dir
        self._path       = memory_dir / "emotions.json"
        self._state: dict[str, float] = {}

    # ─────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load emotions from file. Creates defaults on first run."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)

        if self._path.exists():
            try:
                with self._path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                # Merge: loaded values take priority; missing keys get defaults
                state = dict(_DEFAULTS)
                for key in _DEFAULTS:
                    if key in raw and isinstance(raw[key], (int, float)):
                        state[key] = float(max(0.0, min(1.0, raw[key])))
                self._state = state
                log.info(f"EmotionEngine: loaded from {self._path}")
            except Exception as e:
                log.warning(f"EmotionEngine: failed to load ({e}), using defaults.")
                self._state = dict(_DEFAULTS)
        else:
            log.info("EmotionEngine: cold start — writing defaults.")
            self._state = dict(_DEFAULTS)
            self._save()

    # ─────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────

    def get_state(self) -> dict[str, float]:
        """Return a copy of all current emotion values."""
        return dict(self._state)

    def get_dominant(self) -> tuple[str, float]:
        """Return the emotion with the highest current value."""
        if not self._state:
            return ("curiosity", _DEFAULTS["curiosity"])
        dominant = max(self._state, key=lambda k: self._state[k])
        return (dominant, round(self._state[dominant], 4))

    def update(
        self,
        event_type:   str,
        outcome:      str,
        value_scores: dict,
    ) -> None:
        """
        Update emotions based on event outcome.

        Apply rules first, then apply decay toward baselines,
        then clamp to [0.0, 1.0], then persist.

        Parameters
        ----------
        event_type   : e.g. "heavy_tick.reflect", "dream.completed"
        outcome      : "success" | "failure" | "neutral" (or any string)
        value_scores : dict from ValueEngine.get_scores() — reserved for
                       future rules, currently unused
        """
        s = self._state

        # ── Outcome rules ──────────────────────────────────────
        if outcome == "success":
            s["satisfaction"] += 0.10
            s["anxiety"]      -= 0.05
            s["boredom"]      -= 0.10
            s["enthusiasm"]   += 0.08

        elif outcome == "failure":
            s["anxiety"]      += 0.10
            s["satisfaction"] -= 0.05
            s["enthusiasm"]   -= 0.08
            s["melancholy"]   += 0.05

        else:  # neutral / unknown
            s["boredom"]    += 0.05
            s["curiosity"]  -= 0.03

        # ── Event-type rules ───────────────────────────────────
        et_lower = event_type.lower()
        if "dream" in et_lower:
            s["melancholy"] += 0.05
            s["curiosity"]  += 0.08

        if "reflect" in et_lower:
            s["melancholy"] += 0.03
            s["anxiety"]    -= 0.03

        # ── Decay toward baseline ─────────────────────────────
        for key, baseline in _BASELINES.items():
            s[key] = s[key] + _DECAY_RATE * (baseline - s[key])

        # ── Clamp ─────────────────────────────────────────────
        for key in s:
            s[key] = round(max(0.0, min(1.0, s[key])), 4)

        self._save()
        dominant, val = self.get_dominant()
        log.debug(
            f"EmotionEngine.update(): event={event_type!r} outcome={outcome!r} "
            f"dominant={dominant}({val:.2f})"
        )

    def to_prompt_context(self) -> str:
        """
        Return a concise string for injection into LLM system prompts.

        Includes only emotions with value > 0.3 (sorted descending).
        Dominant emotion is always included regardless of threshold.
        """
        dominant_name, dominant_val = self.get_dominant()

        # Collect emotions above threshold
        visible = {
            k: v for k, v in self._state.items()
            if v > 0.3 or k == dominant_name
        }
        # Sort descending by value
        sorted_emotions = sorted(visible.items(), key=lambda x: x[1], reverse=True)

        emotions_str = ", ".join(
            f"{k}={v:.2f}" for k, v in sorted_emotions
        )
        dominant_desc = _DESCRIPTIONS.get(dominant_name, dominant_name)

        return (
            f"Эмоциональное состояние: {emotions_str}\n"
            f"Доминирующая эмоция: {dominant_name} ({dominant_desc})"
        )

    def get_tone_modifier(self) -> str:
        """Return a tone instruction string based on dominant emotion."""
        dominant_name, _ = self.get_dominant()
        return _TONE_MODIFIERS.get(
            dominant_name,
            "Действуй взвешенно и осознанно.",
        )

    # ─────────────────────────────────────────────────────────
    # Persistence (atomic write)
    # ─────────────────────────────────────────────────────────

    def _save(self) -> None:
        """Atomically persist current emotion state to emotions.json."""
        tmp = self._path.with_suffix(".json.tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception as e:
            log.error(f"EmotionEngine: save failed: {e}")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
