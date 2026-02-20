"""
Digital Being — TimePerception
Stage 22: Temporal pattern detection and awareness.

Detects patterns like:
- "morning: files .py are edited more often"
- "friday: activity is higher"
- "night: low activity"

Provides temporal context for decision making and prediction.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.ollama_client import OllamaClient

log = logging.getLogger("digital_being.time_perception")

MAX_PATTERNS = 50
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
TIMES_OF_DAY = {
    "night": (0, 6),
    "morning": (6, 12),
    "afternoon": (12, 18),
    "evening": (18, 24),
}


class TimePerception:
    def __init__(self, memory_dir: Path, max_patterns: int = MAX_PATTERNS, min_confidence: float = 0.4) -> None:
        self._path = memory_dir / "time_patterns.json"
        self._max_patterns = max_patterns
        self._min_confidence = min_confidence
        self._state = {"patterns": [], "current_context": self._build_context()}

    def load(self) -> None:
        """Load state from file."""
        if not self._path.exists():
            log.info("TimePerception: no existing state, starting fresh.")
            return
        try:
            self._state = json.loads(self._path.read_text(encoding="utf-8"))
            log.info(f"TimePerception: loaded {len(self._state.get('patterns', []))} patterns.")
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Failed to load {self._path}: {e}")
            self._state = {"patterns": [], "current_context": self._build_context()}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as e:
            log.error(f"Failed to save {self._path}: {e}")

    def _build_context(self) -> dict:
        """Build current time context from time.localtime()."""
        lt = time.localtime()
        hour = lt.tm_hour
        minute = lt.tm_min
        day_of_week = DAYS[lt.tm_wday]
        is_weekend = lt.tm_wday >= 5  # Saturday=5, Sunday=6
        
        # Determine time_of_day
        time_of_day = "night"
        for tod, (start, end) in TIMES_OF_DAY.items():
            if start <= hour < end:
                time_of_day = tod
                break
        
        return {
            "time_of_day": time_of_day,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "hour": hour,
            "minute": minute,
        }

    def update_context(self) -> None:
        """Update current_context. Fast, no I/O."""
        self._state["current_context"] = self._build_context()

    def detect_patterns(self, episodes: list[dict], ollama: "OllamaClient") -> list[dict]:
        """
        Analyze episodes and detect temporal patterns using LLM.
        Returns list of patterns (not saved automatically).
        """
        if not episodes:
            return []
        
        # Format episodes with timestamps
        lines = []
        for ep in episodes[-50:]:
            ts = ep.get("timestamp", 0)
            if not ts:
                continue
            
            lt = time.localtime(ts)
            day = DAYS[lt.tm_wday]
            hour = lt.tm_hour
            minute = lt.tm_min
            
            # Determine time_of_day
            tod = "night"
            for t, (start, end) in TIMES_OF_DAY.items():
                if start <= hour < end:
                    tod = t
                    break
            
            event_type = ep.get("event_type", "?")
            desc = ep.get("description", "")[:100]
            lines.append(f"- [{day} {hour:02d}:{minute:02d} | {tod}] {event_type}: {desc}")
        
        if not lines:
            return []
        
        episodes_str = "\n".join(lines)
        ctx = self._state["current_context"]
        current_time_info = f"{ctx['time_of_day']}, {ctx['day_of_week']} (hour={ctx['hour']})"
        
        prompt = (
            f"Проанализируй события за разное время суток/дни недели.\n"
            f"Найди 1-3 временных паттерна — что обычно происходит когда.\n\n"
            f"События с временными метками:\n{episodes_str}\n\n"
            f"Текущее время: {current_time_info}\n\n"
            f'Отвечай JSON:\n{{"patterns": [{{"pattern_type": "time_of_day|day_of_week|hour_of_day", '
            f'"condition": "morning|monday|14:00-15:00", "observation": "краткое описание", '
            f'"confidence": 0.5-0.8}}]}}'
        )
        system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."
        
        try:
            response = ollama.chat(prompt, system)
            if not response:
                return []
            
            data = json.loads(response)
            patterns = data.get("patterns", [])
            result = []
            
            for p in patterns:
                if p.get("pattern_type") and p.get("condition") and p.get("observation"):
                    result.append({
                        "pattern_type": p["pattern_type"],
                        "condition": p["condition"],
                        "observation": p["observation"],
                        "confidence": float(p.get("confidence", 0.5)),
                    })
            
            return result
        
        except (json.JSONDecodeError, Exception) as e:
            log.debug(f"detect_patterns error: {e}")
            return []

    def add_pattern(
        self, pattern_type: str, condition: str, observation: str, confidence: float
    ) -> bool:
        """Add pattern or update existing one."""
        # Check for duplicates
        for p in self._state["patterns"]:
            if p["pattern_type"] == pattern_type and p["condition"] == condition:
                # Update existing
                old_conf = p["confidence"]
                p["confidence"] = (old_conf + confidence) / 2
                p["occurrences"] += 1
                p["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                p["observation"] = observation  # Update with latest observation
                self._save()
                log.info(
                    f"Pattern updated: [{pattern_type}:{condition}] conf={old_conf:.2f}→{p['confidence']:.2f} occ={p['occurrences']}"
                )
                return True
        
        # Add new pattern
        pattern = {
            "id": str(uuid.uuid4()),
            "pattern_type": pattern_type,
            "condition": condition,
            "observation": observation,
            "occurrences": 1,
            "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "confidence": max(0.0, min(1.0, confidence)),
        }
        
        self._state["patterns"].append(pattern)
        
        # Prune if exceeded max
        if len(self._state["patterns"]) > self._max_patterns:
            # Sort by confidence * occurrences (score)
            self._state["patterns"].sort(key=lambda x: x["confidence"] * x["occurrences"])
            removed = self._state["patterns"].pop(0)
            log.debug(f"Pruned pattern: {removed['id']} (score={removed['confidence']*removed['occurrences']:.2f})")
        
        self._save()
        log.info(f"Pattern added: [{pattern_type}:{condition}] {observation[:60]}")
        return True

    def get_patterns(
        self, pattern_type: str | None = None, min_confidence: float = 0.4
    ) -> list[dict]:
        """Get patterns with optional filtering."""
        patterns = [
            p for p in self._state["patterns"] if p["confidence"] >= min_confidence
        ]
        
        if pattern_type:
            patterns = [p for p in patterns if p["pattern_type"] == pattern_type]
        
        patterns.sort(key=lambda x: x["confidence"] * x["occurrences"], reverse=True)
        return patterns

    def get_current_patterns(self, min_confidence: float = 0.5) -> list[dict]:
        """Get patterns relevant to current time."""
        ctx = self._state["current_context"]
        current_tod = ctx["time_of_day"]
        current_dow = ctx["day_of_week"]
        current_hour = ctx["hour"]
        
        patterns = []
        for p in self._state["patterns"]:
            if p["confidence"] < min_confidence:
                continue
            
            pt = p["pattern_type"]
            cond = p["condition"]
            
            if pt == "time_of_day" and cond == current_tod:
                patterns.append(p)
            elif pt == "day_of_week" and cond == current_dow:
                patterns.append(p)
            elif pt == "hour_of_day":
                # Parse hour range like "14:00-15:00"
                if "-" in cond:
                    try:
                        start_str, end_str = cond.split("-")
                        start_hour = int(start_str.split(":")[0])
                        end_hour = int(end_str.split(":")[0])
                        if start_hour <= current_hour < end_hour:
                            patterns.append(p)
                    except (ValueError, IndexError):
                        pass
        
        patterns.sort(key=lambda x: x["confidence"] * x["occurrences"], reverse=True)
        return patterns

    def to_prompt_context(self, limit: int = 3) -> str:
        """Format temporal context for LLM prompt."""
        ctx = self._state["current_context"]
        tod = ctx["time_of_day"]
        dow = ctx["day_of_week"]
        is_weekend = ctx["is_weekend"]
        
        # Days until weekend
        days_until_weekend = 0
        if not is_weekend:
            # Monday=0, ..., Friday=4
            dow_idx = DAYS.index(dow)
            days_until_weekend = 5 - dow_idx  # Days until Saturday
        
        lines = [
            f"Сейчас: {tod}, {dow} {'(выходные)' if is_weekend else f'(выходные через {days_until_weekend} дня/дней)'}"
        ]
        
        current_patterns = self.get_current_patterns(min_confidence=0.5)
        if current_patterns:
            lines.append("Временные паттерны:")
            for p in current_patterns[:limit]:
                lines.append(
                    f"  - [{p['condition']}] {p['observation']} (conf={p['confidence']:.2f})"
                )
        
        return "\n".join(lines)

    def predict_next_event(self, event_type: str) -> str | None:
        """
        Simple heuristic prediction: when is event_type most likely to occur?
        Based on patterns.
        """
        # Find patterns mentioning this event_type
        relevant = []
        for p in self._state["patterns"]:
            if event_type.lower() in p["observation"].lower():
                relevant.append(p)
        
        if not relevant:
            return None
        
        # Sort by score
        relevant.sort(key=lambda x: x["confidence"] * x["occurrences"], reverse=True)
        best = relevant[0]
        
        return (
            f"вероятно в {best['condition']} "
            f"(conf={best['confidence']:.2f}, occ={best['occurrences']})"
        )

    def should_detect(self, tick_count: int) -> bool:
        """Should detect patterns on this tick? Every ~40 ticks (~3-4 hours)."""
        return tick_count > 0 and tick_count % 40 == 0

    def get_stats(self) -> dict:
        """Get statistics."""
        patterns = self._state["patterns"]
        by_type = defaultdict(int)
        for p in patterns:
            by_type[p["pattern_type"]] += 1
        
        ctx = self._state["current_context"]
        return {
            "total_patterns": len(patterns),
            "patterns_by_type": dict(by_type),
            "current_time_of_day": ctx["time_of_day"],
            "current_day_of_week": ctx["day_of_week"],
            "is_weekend": ctx["is_weekend"],
        }
