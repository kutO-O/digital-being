"""
Digital Being — AttentionSystem
Stage 16: Attention System.

Responsibility:
  Compute per-event attention scores and filter / format episodic context
  before it reaches the LLM.

Design notes:
  - Stateless: no persistence, no disk I/O.
  - score() is NOT cached — called fresh for every episode.
  - emotion_engine / value_engine may be None → multipliers silently skipped.
  - metadata param in score() is reserved for future use, currently ignored.

Weights:
  BASE_WEIGHTS define the starting score per event_type.
  Emotion and value multipliers are applied on top.
  A novelty bonus is added for text containing specific keywords.
  Final score is clamped to [0.0, 1.0] and rounded to 3 decimal places.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.emotion_engine import EmotionEngine
    from core.value_engine import ValueEngine

log = logging.getLogger("digital_being.attention_system")

BASE_WEIGHTS: dict[str, float] = {
    "file_created":  0.6,
    "file_modified": 0.4,
    "file_deleted":  0.8,
    "reflection":    0.9,
    "contradiction": 1.0,
    "dream_insight": 0.85,
    "diary_entry":   0.3,
    "heavy_tick":    0.2,
    "milestone":     1.0,
    "monologue":     0.3,
    "goal_selected": 0.5,
    "error":         0.9,
    "default":       0.3,
}

NOVELTY_KEYWORDS: list[str] = [
    "впервые",
    "новый",
    "неожиданно",
    "strange",
    "unusual",
    "first",
]


class AttentionSystem:
    """
    Stateless attention scoring and context-building helper.

    Usage:
        attn = AttentionSystem(
            memory_dir=Path("memory"),
            emotion_engine=emotion_engine,  # may be None
            value_engine=value_engine,      # may be None
        )
        score = attn.score("reflection", "Заметил противоречие...")
        top   = attn.filter_episodes(episodes, top_k=5)
        ctx   = attn.build_context(top)
        focus = attn.get_focus_summary()
    """

    def __init__(
        self,
        memory_dir:     Path,
        emotion_engine: "EmotionEngine | None" = None,
        value_engine:   "ValueEngine | None"   = None,
    ) -> None:
        self._memory_dir = memory_dir
        self._emotions   = emotion_engine
        self._values     = value_engine

    # ──────────────────────────────────────────────────────────────
    # Core scoring
    # ──────────────────────────────────────────────────────────────
    def score(
        self,
        event_type: str,
        text:       str,
        metadata:   dict | None = None,  # reserved, currently unused
    ) -> float:
        """
        Compute attention weight for a single event.

        Pipeline:
          1. Base weight from BASE_WEIGHTS (or "default" fallback).
          2. Emotion multiplier (curiosity → file events ×1.2;
                                 anxiety  → error events ×1.3).
          3. Value multiplier   (curiosity score >0.7 → reflect events ×1.15).
          4. Novelty bonus      (+0.1 if text contains a NOVELTY_KEYWORD).
          5. Clamp to [0.0, 1.0] and round to 3 decimal places.
        """
        # 1. Base
        base = BASE_WEIGHTS.get(event_type, BASE_WEIGHTS["default"])
        weight = base

        # 2. Emotion multiplier
        dominant_name = self._get_dominant_emotion()
        if dominant_name == "curiosity" and "file" in event_type:
            weight *= 1.2
        elif dominant_name == "anxiety" and "error" in event_type:
            weight *= 1.3

        # 3. Value multiplier
        curiosity_value = self._get_value_score("curiosity")
        if curiosity_value > 0.7 and "reflect" in event_type:
            weight *= 1.15

        # 4. Novelty bonus
        text_lower = text.lower()
        if any(kw in text_lower for kw in NOVELTY_KEYWORDS):
            weight += 0.1

        # 5. Clamp and round
        return round(min(max(weight, 0.0), 1.0), 3)

    # ──────────────────────────────────────────────────────────────
    # Episode filtering
    # ──────────────────────────────────────────────────────────────
    def filter_episodes(
        self,
        episodes:  list[dict],
        top_k:     int   = 5,
        min_score: float = 0.4,
    ) -> list[dict]:
        """
        Score every episode, keep those with score >= min_score,
        sort descending, return top_k.

        Each episode dict gains an "attention_score" field (float).
        The original list is NOT mutated — shallow-copied episodes are returned.
        """
        scored: list[dict] = []
        for ep in episodes:
            ep_copy = dict(ep)  # shallow copy — do not mutate caller's data
            s = self.score(
                event_type=ep_copy.get("event_type", "default"),
                text=ep_copy.get("description", ""),
            )
            ep_copy["attention_score"] = s
            if s >= min_score:
                scored.append(ep_copy)

        scored.sort(key=lambda e: e["attention_score"], reverse=True)
        return scored[:top_k]

    # ──────────────────────────────────────────────────────────────
    # Context building
    # ──────────────────────────────────────────────────────────────
    def build_context(
        self,
        episodes:  list[dict],
        max_chars: int = 1500,
    ) -> str:
        """
        Build a compact string for LLM injection from filtered episodes.

        Format per line:
            [{score:.2f}] {event_type}: {text[:200]}

        The total output is truncated to max_chars characters.
        Returns "(нет значимых событий)" if the list is empty.
        """
        if not episodes:
            return "(нет значимых событий)"

        lines: list[str] = []
        total = 0
        for ep in episodes:
            s         = ep.get("attention_score", 0.0)
            etype     = ep.get("event_type", "unknown")
            desc      = ep.get("description", "")[:200]
            line      = f"[{s:.2f}] {etype}: {desc}"
            line_len  = len(line) + 1  # +1 for newline
            if total + line_len > max_chars:
                break
            lines.append(line)
            total += line_len

        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────
    # Focus summary
    # ──────────────────────────────────────────────────────────────
    def get_focus_summary(self) -> str:
        """
        Return a one-line focus summary for system prompts.

        Shows the top-3 event types ranked by BASE_WEIGHTS (descending).
        Ties are broken alphabetically for determinism.

        Example:
            "Фокус внимания: contradiction(1.0), milestone(1.0), reflection(0.9)"
        """
        top3 = sorted(
            ((etype, w) for etype, w in BASE_WEIGHTS.items() if etype != "default"),
            key=lambda x: (-x[1], x[0]),
        )[:3]
        parts = ", ".join(f"{etype}({w})" for etype, w in top3)
        return f"Фокус внимания: {parts}"

    # ──────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────
    def _get_dominant_emotion(self) -> str | None:
        """Return the name of the dominant emotion, or None if unavailable."""
        if self._emotions is None:
            return None
        try:
            name, _ = self._emotions.get_dominant()
            return name
        except Exception as e:
            log.debug(f"AttentionSystem._get_dominant_emotion(): {e}")
            return None

    def _get_value_score(self, key: str) -> float:
        """Return a single value score by key, defaulting to 0.5 if unavailable."""
        if self._values is None:
            return 0.5
        try:
            scores = self._values.get_scores()
            return float(scores.get(key, 0.5))
        except Exception as e:
            log.debug(f"AttentionSystem._get_value_score({key!r}): {e}")
            return 0.5
