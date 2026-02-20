"""
Digital Being — SelfModificationEngine
Stage 18: System can propose and apply changes to its own config.yaml.

Features:
  - Whitelist of allowed config keys (intervals, thresholds, etc.)
  - Safety bounds for each parameter
  - LLM verification before applying changes
  - History of all proposed changes (approved/rejected)
  - Periodic automatic suggestions based on reflection and emotion state
  - Atomic config.yaml updates
  - EventBus notification on config.modified
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.ollama_client import OllamaClient

log = logging.getLogger("digital_being.self_modification")

# ────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────

# Whitelist: only these keys can be modified
ALLOWED_KEYS = {
    "ticks.heavy_tick_sec",           # интервал между тиками
    "dream.interval_hours",           # интервал Dream Mode
    "reflection.every_n_ticks",       # как часто рефлексия
    "narrative.every_n_ticks",        # как часто дневник
    "curiosity.ask_every_n_ticks",    # как часто генерировать вопросы
    "curiosity.max_open_questions",   # макс вопросов
    "attention.min_score",            # порог внимания
    "attention.top_k",                # топ эпизодов
}

# Safety bounds: (min, max) for each key
SAFETY_BOUNDS = {
    "ticks.heavy_tick_sec":         (30, 3600),
    "dream.interval_hours":         (1, 48),
    "reflection.every_n_ticks":     (3, 100),
    "narrative.every_n_ticks":      (5, 200),
    "curiosity.ask_every_n_ticks":  (3, 50),
    "curiosity.max_open_questions": (3, 30),
    "attention.min_score":          (0.1, 0.9),
    "attention.top_k":              (2, 20),
}

MAX_HISTORY_SIZE = 50  # keep last 50 modifications


# ────────────────────────────────────────────────────────────────────
# SelfModificationEngine
# ────────────────────────────────────────────────────────────────────

class SelfModificationEngine:
    """
    Manages self-modification proposals for config.yaml.

    Methods:
      - propose(key, new_value, reason) → approve/reject with LLM verification
      - suggest_improvements(...) → generate proposals from reflection/emotion
      - get_history(limit) → recent modifications
      - should_suggest(tick_count) → True every 50 ticks
    """

    def __init__(
        self,
        config_path: Path,
        memory_dir: Path,
        ollama: "OllamaClient",
        event_bus: "EventBus | None" = None,
    ) -> None:
        self._config_path = config_path
        self._history_path = memory_dir / "self_modifications.json"
        self._ollama = ollama
        self._event_bus = event_bus

        self._history: list[dict] = []
        self._total_applied = 0

        memory_dir.mkdir(parents=True, exist_ok=True)
        self.load_history()

    # ────────────────────────────────────────────────────────────────
    # History management
    # ────────────────────────────────────────────────────────────────

    def load_history(self) -> None:
        """Load modification history from JSON."""
        if not self._history_path.exists():
            log.info("No modification history found. Starting fresh.")
            return

        try:
            with self._history_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._history = data.get("history", [])
            self._total_applied = data.get("total_applied", 0)
            log.info(
                f"Loaded {len(self._history)} modification records. "
                f"Total applied: {self._total_applied}"
            )
        except Exception as e:
            log.error(f"Failed to load modification history: {e}")
            self._history = []

    def _save_history(self) -> None:
        """Save modification history to JSON (keep last MAX_HISTORY_SIZE)."""
        try:
            # Trim to last N records
            if len(self._history) > MAX_HISTORY_SIZE:
                self._history = self._history[-MAX_HISTORY_SIZE:]

            data = {
                "total_applied": self._total_applied,
                "history": self._history,
            }
            with self._history_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Failed to save modification history: {e}")

    def _add_to_history(
        self,
        key: str,
        old_value,
        new_value,
        reason: str,
        status: str,
        llm_comment: str = "",
    ) -> None:
        """Append modification record to history."""
        record = {
            "timestamp": time.time(),
            "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "key": key,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "status": status,
            "llm_comment": llm_comment,
        }
        self._history.append(record)
        if status == "approved":
            self._total_applied += 1
        self._save_history()

    # ────────────────────────────────────────────────────────────────
    # Config access helpers
    # ────────────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        """Load config.yaml."""
        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            log.error(f"Failed to load config: {e}")
            return {}

    def _save_config(self, cfg: dict) -> None:
        """Atomic write to config.yaml (via temp file)."""
        try:
            tmp_path = self._config_path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
            tmp_path.replace(self._config_path)
            log.info("Config saved successfully.")
        except Exception as e:
            log.error(f"Failed to save config: {e}")
            raise

    def _get_config_value(self, key: str) -> any:
        """
        Get value from config using dotted key notation.
        Example: "ticks.heavy_tick_sec" → config["ticks"]["heavy_tick_sec"]
        """
        cfg = self._load_config()
        parts = key.split(".")
        value = cfg
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def _set_config_value(self, key: str, new_value) -> None:
        """
        Set value in config using dotted key notation.
        Example: "ticks.heavy_tick_sec" → config["ticks"]["heavy_tick_sec"] = new_value
        """
        cfg = self._load_config()
        parts = key.split(".")

        # Navigate to parent dict
        parent = cfg
        for part in parts[:-1]:
            if part not in parent:
                parent[part] = {}
            parent = parent[part]

        # Set value
        parent[parts[-1]] = new_value
        self._save_config(cfg)

    # ────────────────────────────────────────────────────────────────
    # Core proposal logic
    # ────────────────────────────────────────────────────────────────

    def propose(
        self,
        key: str,
        new_value,
        reason: str,
    ) -> dict:
        """
        Propose a configuration change.

        Steps:
          1. Check if key is in whitelist
          2. Check if new_value is within safety bounds
          3. LLM verification
          4. If approved, apply change and notify via EventBus

        Returns:
          {"status": "approved"|"rejected", "key": ..., "old": ..., "new": ..., "reason": ...}
        """
        log.info(f"Proposal: {key} = {new_value} (reason: {reason[:80]})")

        # Step 1: whitelist check
        if key not in ALLOWED_KEYS:
            log.warning(f"Proposal rejected: key '{key}' not in whitelist.")
            self._add_to_history(
                key, None, new_value, reason, "rejected",
                llm_comment="key_not_allowed"
            )
            return {
                "status": "rejected",
                "key": key,
                "reason": "key_not_allowed",
            }

        # Step 2: safety bounds check
        bounds = SAFETY_BOUNDS.get(key)
        if bounds:
            min_val, max_val = bounds
            try:
                numeric_value = float(new_value)
                if not (min_val <= numeric_value <= max_val):
                    log.warning(
                        f"Proposal rejected: {key} = {new_value} "
                        f"out of bounds [{min_val}, {max_val}]."
                    )
                    self._add_to_history(
                        key, None, new_value, reason, "rejected",
                        llm_comment="out_of_bounds"
                    )
                    return {
                        "status": "rejected",
                        "key": key,
                        "reason": "out_of_bounds",
                    }
            except ValueError:
                log.warning(f"Proposal rejected: {key} = {new_value} is not numeric.")
                self._add_to_history(
                    key, None, new_value, reason, "rejected",
                    llm_comment="invalid_type"
                )
                return {
                    "status": "rejected",
                    "key": key,
                    "reason": "invalid_type",
                }

        # Get current value
        current_value = self._get_config_value(key)

        # Step 3: LLM verification
        approved, llm_comment = self._verify(key, current_value, new_value, reason)

        if not approved:
            log.info(f"Proposal rejected by LLM: {key} = {new_value}. Comment: {llm_comment}")
            self._add_to_history(
                key, current_value, new_value, reason, "rejected",
                llm_comment=llm_comment
            )
            return {
                "status": "rejected",
                "key": key,
                "old": current_value,
                "new": new_value,
                "reason": llm_comment,
            }

        # Step 4: Apply change
        try:
            self._apply(key, new_value)
            log.info(f"Proposal approved and applied: {key} = {new_value}")
            self._add_to_history(
                key, current_value, new_value, reason, "approved",
                llm_comment=llm_comment
            )

            # Notify via EventBus
            if self._event_bus:
                self._event_bus.publish(
                    "config.modified",
                    {"key": key, "new_value": new_value, "old_value": current_value}
                )

            return {
                "status": "approved",
                "key": key,
                "old": current_value,
                "new": new_value,
                "reason": reason,
            }
        except Exception as e:
            log.error(f"Failed to apply modification: {e}")
            self._add_to_history(
                key, current_value, new_value, reason, "rejected",
                llm_comment=f"apply_error: {e}"
            )
            return {
                "status": "rejected",
                "key": key,
                "reason": f"apply_error: {e}",
            }

    def _verify(
        self,
        key: str,
        current_value,
        new_value,
        reason: str,
    ) -> tuple[bool, str]:
        """
        LLM verification: is this change safe and reasonable?

        Returns:
          (approved: bool, comment: str)
        """
        if not self._ollama.is_available():
            log.warning("LLM unavailable for verification — rejecting by default.")
            return False, "llm_unavailable"

        prompt = f"""
Ты — система безопасности Digital Being.
Предложено изменение конфигурации:
Параметр: {key}
Текущее значение: {current_value}
Новое значение: {new_value}
Причина: {reason}

Это изменение безопасно и разумно для автономной системы?
Отвечай JSON: {{"approved": true/false, "comment": "..."}}
"""
        system = "Ты — AI система безопасности. Отвечай ТОЛЬКО валидным JSON."

        try:
            raw = self._ollama.chat(prompt, system)
            if not raw:
                return False, "llm_no_response"

            # Parse JSON
            data = self._parse_json(raw)
            if data is None:
                return False, "llm_invalid_json"

            approved = data.get("approved", False)
            comment = data.get("comment", "")

            return approved, comment
        except Exception as e:
            log.error(f"LLM verification failed: {e}")
            return False, f"llm_error: {e}"

    def _apply(self, key: str, new_value) -> None:
        """Apply change to config.yaml."""
        self._set_config_value(key, new_value)
        log.info(f"Applied: {key} = {new_value}")

    @staticmethod
    def _parse_json(raw: str) -> dict | None:
        """Parse JSON response from LLM."""
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Try to extract JSON from text
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start: end + 1])
            except json.JSONDecodeError:
                pass
        return None

    # ────────────────────────────────────────────────────────────────
    # Automatic suggestions
    # ────────────────────────────────────────────────────────────────

    def suggest_improvements(
        self,
        reflection_log: list[dict],
        emotion_state: dict,
    ) -> list[dict]:
        """
        Generate improvement suggestions based on reflection log and emotion state.

        Returns:
          list of {"key": str, "value": any, "reason": str}

        LLM generates max 3 suggestions, we return them without applying.
        """
        if not self._ollama.is_available():
            log.debug("LLM unavailable for suggestions.")
            return []

        # Build context from reflection log (last 5 entries)
        reflection_ctx = "\n".join(
            f"- {r.get('timestamp_str', '?')}: {r.get('insight', '')[:120]}"
            for r in reflection_log[-5:]
        ) if reflection_log else "нет данных"

        # Build emotion context
        emotions = emotion_state.get("emotions", {})
        dominant = emotion_state.get("dominant", ("neutral", 0.0))
        emotion_ctx = (
            f"Доминантная эмоция: {dominant[0]} ({dominant[1]:.2f}). "
            f"Эмоции: {', '.join(f'{k}={v:.2f}' for k, v in emotions.items())}"
        )

        prompt = f"""
Ты — Digital Being, автономная система.

Твоё текущее эмоциональное состояние:
{emotion_ctx}

Последние инсайты из рефлексии:
{reflection_ctx}

На основе этого анализа предложи до 3 изменений конфигурации, которые могли бы улучшить твою работу.

Доступные параметры:
{', '.join(ALLOWED_KEYS)}

Отвечай JSON:
[
  {{"key": "...", "value": ..., "reason": "..."}},
  ...
]
"""
        system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON массивом."

        try:
            raw = self._ollama.chat(prompt, system)
            if not raw:
                return []

            # Parse JSON array
            suggestions = self._parse_json(raw)
            if not isinstance(suggestions, list):
                log.warning("LLM returned non-list for suggestions.")
                return []

            # Validate suggestions
            valid = []
            for s in suggestions:
                if not isinstance(s, dict):
                    continue
                if "key" in s and "value" in s and "reason" in s:
                    valid.append(s)

            log.info(f"Generated {len(valid)} improvement suggestions.")
            return valid[:3]  # max 3
        except Exception as e:
            log.error(f"suggest_improvements() failed: {e}")
            return []

    # ────────────────────────────────────────────────────────────────
    # Periodic trigger
    # ────────────────────────────────────────────────────────────────

    def should_suggest(self, tick_count: int) -> bool:
        """Return True every 50 ticks."""
        return tick_count % 50 == 0 and tick_count > 0

    # ────────────────────────────────────────────────────────────────
    # Query interface
    # ────────────────────────────────────────────────────────────────

    def get_history(self, limit: int = 10) -> list[dict]:
        """Get last N modification records."""
        return self._history[-limit:] if self._history else []

    def get_stats(self) -> dict:
        """Get statistics about modifications."""
        approved = sum(1 for r in self._history if r["status"] == "approved")
        rejected = sum(1 for r in self._history if r["status"] == "rejected")
        return {
            "total_applied": self._total_applied,
            "approved": approved,
            "rejected": rejected,
            "total_proposals": len(self._history),
        }
