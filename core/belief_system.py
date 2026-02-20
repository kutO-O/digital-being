"""
Digital Being — BeliefSystem
Stage 19: System forms beliefs about the world based on experience.

Features:
  - Forms beliefs through pattern recognition in episodes
  - Tracks confidence scores (0.0 - 1.0) that evolve with evidence
  - Validates beliefs against new experiences via LLM
  - Categorizes beliefs (file_patterns, time_patterns, cause_effect, etc.)
  - Rejects beliefs when confidence drops below threshold
  - Maximum 50 beliefs (auto-prune weakest rejected)

File: memory/beliefs.json
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.ollama_client import OllamaClient
    from core.world_model import WorldModel

log = logging.getLogger("digital_being.belief_system")

# ────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────

CATEGORIES = [
    "file_patterns",      # закономерности в файлах
    "time_patterns",      # закономерности по времени
    "cause_effect",       # причина-следствие
    "system_behavior",    # поведение системы
    "environment",        # окружающая среда
]

MAX_BELIEFS = 50
MAX_ACTIVE_BELIEFS = 30
MIN_CONFIDENCE_THRESHOLD = 0.2
STRONG_CONFIDENCE_THRESHOLD = 0.9


# ────────────────────────────────────────────────────────────────────
# BeliefSystem
# ────────────────────────────────────────────────────────────────────

class BeliefSystem:
    """
    Manages beliefs about the world based on episodic memory.

    Methods:
      - form_beliefs(episodes, world_model, ollama) → generate new beliefs
      - add_belief(statement, category, confidence) → add belief with duplicate check
      - validate_belief(belief_id, episodes, ollama) → verify belief against evidence
      - get_beliefs(...) → filter beliefs by criteria
      - to_prompt_context() → format beliefs for LLM prompts
    """

    def __init__(self, memory_dir: Path) -> None:
        self._memory_dir = Path(memory_dir)
        self._beliefs_path = self._memory_dir / "beliefs.json"

        self._beliefs: list[dict] = []
        self._total_formed = 0
        self._total_rejected = 0

        self._memory_dir.mkdir(parents=True, exist_ok=True)

    # ────────────────────────────────────────────────────────────────
    # Persistence
    # ────────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load beliefs from JSON file."""
        if not self._beliefs_path.exists():
            log.info("No beliefs file found. Starting fresh.")
            return

        try:
            with self._beliefs_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._beliefs = data.get("beliefs", [])
            self._total_formed = data.get("total_beliefs_formed", 0)
            self._total_rejected = data.get("total_beliefs_rejected", 0)
            
            log.info(
                f"Loaded {len(self._beliefs)} beliefs. "
                f"Total formed: {self._total_formed}, rejected: {self._total_rejected}"
            )
        except Exception as e:
            log.error(f"Failed to load beliefs: {e}")
            self._beliefs = []

    def _save(self) -> None:
        """Save beliefs to JSON file atomically."""
        try:
            # Prune if over limit
            if len(self._beliefs) > MAX_BELIEFS:
                self._prune_weakest_rejected()

            data = {
                "beliefs": self._beliefs,
                "total_beliefs_formed": self._total_formed,
                "total_beliefs_rejected": self._total_rejected,
            }
            
            # Atomic write: tmp file → replace
            tmp_path = self._beliefs_path.with_suffix(".json.tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self._beliefs_path)
        except Exception as e:
            log.error(f"Failed to save beliefs: {e}")

    def _prune_weakest_rejected(self) -> None:
        """Remove weakest rejected beliefs to stay under MAX_BELIEFS."""
        rejected = [b for b in self._beliefs if b["status"] == "rejected"]
        if not rejected:
            return
        
        # Sort by confidence (weakest first)
        rejected.sort(key=lambda b: b["confidence"])
        
        # Remove weakest until under limit
        to_remove = len(self._beliefs) - MAX_BELIEFS
        if to_remove > 0:
            removed_ids = {b["id"] for b in rejected[:to_remove]}
            self._beliefs = [b for b in self._beliefs if b["id"] not in removed_ids]
            log.info(f"Pruned {to_remove} weakest rejected beliefs.")

    # ────────────────────────────────────────────────────────────────
    # Core belief management
    # ────────────────────────────────────────────────────────────────

    def form_beliefs(
        self,
        episodes: list[dict],
        world_model: "WorldModel",
        ollama: "OllamaClient",
    ) -> list[dict]:
        """
        Generate 1-3 new beliefs based on recent episodes.
        Synchronous. Returns list of {"statement", "category", "initial_confidence"}.
        Never raises (returns [] on error).
        """
        if not ollama.is_available():
            log.debug("LLM unavailable for belief formation.")
            return []

        try:
            # Use last 15 episodes
            recent = episodes[-15:] if len(episodes) > 15 else episodes
            if not recent:
                return []

            # Format context
            events_summary = self._format_episodes(recent)
            world_summary = world_model.summary() if world_model else "нет данных"
            existing_beliefs = self._format_existing_beliefs()

            prompt = f"""
Ты — Digital Being. Проанализируй недавние события и сформулируй
1-3 убеждения о мире — закономерности которые ты заметил.

Недавние события:
{events_summary}

Текущее состояние мира:
{world_summary}

Уже существующие убеждения (не дублируй):
{existing_beliefs}

Категории: file_patterns, time_patterns, cause_effect, system_behavior, environment

Отвечай JSON:
{{
  "beliefs": [
    {{"statement": "...", "category": "file_patterns", "initial_confidence": 0.5}}
  ]
}}
"""
            system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."

            raw = ollama.chat(prompt, system)
            if not raw:
                return []

            # Parse JSON
            data = self._parse_json(raw)
            if not data or "beliefs" not in data:
                return []

            beliefs = data["beliefs"]
            if not isinstance(beliefs, list):
                return []

            # Validate and normalize
            valid = []
            for b in beliefs[:3]:  # max 3
                if not isinstance(b, dict):
                    continue
                if "statement" not in b or "category" not in b:
                    continue
                if b["category"] not in CATEGORIES:
                    continue
                
                # Cap initial confidence at 0.7
                conf = float(b.get("initial_confidence", 0.5))
                b["initial_confidence"] = min(conf, 0.7)
                valid.append(b)

            log.info(f"Generated {len(valid)} new belief(s).")
            return valid

        except Exception as e:
            log.error(f"form_beliefs() failed: {e}")
            return []

    def add_belief(
        self,
        statement: str,
        category: str,
        confidence: float = 0.5,
    ) -> bool:
        """
        Add new belief with duplicate check.
        Returns True if added, False if duplicate or invalid.
        """
        statement = statement.strip()
        if not statement or category not in CATEGORIES:
            return False

        # Cap initial confidence at 0.7
        confidence = min(max(confidence, 0.0), 0.7)

        # Check for duplicates
        if self._is_duplicate(statement):
            log.debug(f"Duplicate belief rejected: '{statement[:60]}'")
            return False

        # Check active belief limit
        active_count = len([b for b in self._beliefs if b["status"] == "active"])
        if active_count >= MAX_ACTIVE_BELIEFS:
            log.info(f"Max active beliefs reached ({MAX_ACTIVE_BELIEFS}). Skipping new belief.")
            return False

        # Create belief
        now = time.time()
        belief = {
            "id": str(uuid.uuid4()),
            "statement": statement,
            "category": category,
            "confidence": confidence,
            "evidence_for": 0,
            "evidence_against": 0,
            "created_at": now,
            "last_updated": now,
            "last_validated": now,
            "status": "active",
        }

        self._beliefs.append(belief)
        self._total_formed += 1
        self._save()

        log.info(
            f"Belief added: '{statement[:60]}' "
            f"[{category}] conf={confidence:.2f}"
        )
        return True

    def validate_belief(
        self,
        belief_id: str,
        episodes: list[dict],
        ollama: "OllamaClient",
    ) -> bool:
        """
        Validate belief against recent episodes via LLM.
        Updates confidence and evidence counters.
        Returns True if validation succeeded, False on error.
        """
        belief = self._find_belief(belief_id)
        if not belief:
            return False

        if not ollama.is_available():
            log.debug("LLM unavailable for belief validation.")
            return False

        try:
            # Use last 10 episodes
            recent = episodes[-10:] if len(episodes) > 10 else episodes
            events_summary = self._format_episodes(recent)

            prompt = f"""
Убеждение: "{belief['statement']}"
Недавние события:
{events_summary}

Подтверждают ли эти события убеждение, противоречат или нейтральны?
Отвечай JSON: {{"verdict": "confirm"|"contradict"|"neutral", "reasoning": "..."}}
"""
            system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."

            raw = ollama.chat(prompt, system)
            if not raw:
                return False

            # Parse verdict
            data = self._parse_json(raw)
            if not data or "verdict" not in data:
                return False

            verdict = data["verdict"]
            reasoning = data.get("reasoning", "")

            # Update belief based on verdict
            now = time.time()
            belief["last_validated"] = now

            if verdict == "confirm":
                belief["confidence"] = min(belief["confidence"] + 0.1, 1.0)
                belief["evidence_for"] += 1
                belief["last_updated"] = now
                log.info(
                    f"Belief CONFIRMED: '{belief['statement'][:60]}' "
                    f"conf={belief['confidence']:.2f}"
                )
            elif verdict == "contradict":
                belief["confidence"] = max(belief["confidence"] - 0.15, 0.0)
                belief["evidence_against"] += 1
                belief["last_updated"] = now
                log.info(
                    f"Belief CONTRADICTED: '{belief['statement'][:60]}' "
                    f"conf={belief['confidence']:.2f}"
                )
            else:  # neutral
                log.debug(
                    f"Belief validation neutral: '{belief['statement'][:60]}'"
                )

            # Update status based on confidence
            if belief["confidence"] < MIN_CONFIDENCE_THRESHOLD:
                belief["status"] = "rejected"
                self._total_rejected += 1
                log.info(f"Belief REJECTED: '{belief['statement'][:60]}'")
            elif belief["confidence"] > STRONG_CONFIDENCE_THRESHOLD:
                belief["status"] = "strong"
                log.info(f"Belief promoted to STRONG: '{belief['statement'][:60]}'")

            self._save()
            return True

        except Exception as e:
            log.error(f"validate_belief() failed: {e}")
            return False

    # ────────────────────────────────────────────────────────────────
    # Query interface
    # ────────────────────────────────────────────────────────────────

    def get_beliefs(
        self,
        category: str = None,
        min_confidence: float = 0.4,
        status: str = "active",
    ) -> list[dict]:
        """Get beliefs filtered by criteria."""
        result = [b for b in self._beliefs if b["status"] == status]
        
        if category:
            result = [b for b in result if b["category"] == category]
        
        result = [b for b in result if b["confidence"] >= min_confidence]
        
        return result

    def get_strongest_beliefs(self, limit: int = 5) -> list[dict]:
        """Get top beliefs by confidence."""
        active = [b for b in self._beliefs if b["status"] in ("active", "strong")]
        active.sort(key=lambda b: b["confidence"], reverse=True)
        return active[:limit]

    def to_prompt_context(self, limit: int = 3) -> str:
        """
        Format beliefs for LLM prompt context.
        Returns: "Мои убеждения: 1) ... [conf=0.8], 2) ... [conf=0.7]"
        """
        beliefs = self.get_strongest_beliefs(limit)
        if not beliefs:
            return ""
        
        lines = [
            f"{i}) {b['statement']} [conf={b['confidence']:.2f}]"
            for i, b in enumerate(beliefs, 1)
        ]
        return "Мои убеждения: " + ", ".join(lines)

    def get_stats(self) -> dict:
        """Get belief system statistics."""
        active = len([b for b in self._beliefs if b["status"] == "active"])
        strong = len([b for b in self._beliefs if b["status"] == "strong"])
        rejected = len([b for b in self._beliefs if b["status"] == "rejected"])
        
        return {
            "active": active,
            "strong": strong,
            "rejected": rejected,
            "total_formed": self._total_formed,
        }

    # ────────────────────────────────────────────────────────────────
    # Triggers
    # ────────────────────────────────────────────────────────────────

    def should_form(self, tick_count: int) -> bool:
        """True every 20 ticks if active beliefs < 30."""
        if tick_count % 20 != 0 or tick_count == 0:
            return False
        active_count = len([b for b in self._beliefs if b["status"] == "active"])
        return active_count < MAX_ACTIVE_BELIEFS

    def should_validate(self, tick_count: int) -> bool:
        """True every 10 ticks if there are active beliefs."""
        if tick_count % 10 != 0 or tick_count == 0:
            return False
        active = [b for b in self._beliefs if b["status"] == "active"]
        return len(active) > 0

    # ────────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────────

    def _find_belief(self, belief_id: str) -> dict | None:
        """Find belief by ID."""
        for b in self._beliefs:
            if b["id"] == belief_id:
                return b
        return None

    def _is_duplicate(self, statement: str) -> bool:
        """
        Check if belief is duplicate based on word overlap.
        Minimum 4 common words longer than 4 characters.
        """
        words = set(
            w.lower() for w in statement.split()
            if len(w) > 4 and w.isalpha()
        )
        
        if len(words) < 4:
            return False
        
        for b in self._beliefs:
            existing_words = set(
                w.lower() for w in b["statement"].split()
                if len(w) > 4 and w.isalpha()
            )
            common = words & existing_words
            if len(common) >= 4:
                return True
        
        return False

    @staticmethod
    def _format_episodes(episodes: list[dict]) -> str:
        """Format episodes for LLM prompt."""
        if not episodes:
            return "(нет событий)"
        
        lines = [
            f"- [{e.get('event_type', '?')}] {e.get('description', '')[:100]}"
            for e in episodes
        ]
        return "\n".join(lines)

    def _format_existing_beliefs(self) -> str:
        """Format existing beliefs for LLM prompt."""
        active = [b for b in self._beliefs if b["status"] in ("active", "strong")]
        if not active:
            return "(нет убеждений)"
        
        lines = [
            f"- [{b['category']}] {b['statement']}"
            for b in active[:10]  # show max 10
        ]
        return "\n".join(lines)

    @staticmethod
    def _parse_json(raw: str) -> dict | None:
        """Parse JSON from LLM response."""
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
