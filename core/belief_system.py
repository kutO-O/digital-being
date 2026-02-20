"""
Digital Being — BeliefSystem
Stage 19: Form and validate beliefs based on observations.

Fix: Added update_confidence() method to avoid tight coupling.
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

MAX_BELIEFS = 100

class BeliefSystem:
    def __init__(self, state_path: Path) -> None:
        self._path = state_path
        self._state = self.load()

    def load(self) -> dict:
        if not self._path.exists():
            return {"beliefs": [], "total_beliefs_formed": 0, "total_beliefs_validated": 0, "total_beliefs_rejected": 0}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Failed to load {self._path}: {e}")
            return {"beliefs": [], "total_beliefs_formed": 0, "total_beliefs_validated": 0, "total_beliefs_rejected": 0}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as e:
            log.error(f"Failed to save {self._path}: {e}")

    def form_beliefs(self, recent_episodes: list[dict], world: "WorldModel", ollama: "OllamaClient") -> list[dict]:
        if not recent_episodes:
            return []
        episodes_str = "\n".join(f"- [{e.get('event_type','?')}] {e.get('description','')[:200]}" for e in recent_episodes[:15])
        world_summary = world.summary() if world else ""
        prompt = (f"Твои последние наблюдения:\n{episodes_str}\n\nМир: {world_summary}\n\n"
                  f"Сформулируй 1-3 новых убеждения о мире на основе этих наблюдений. JSON:\n"
                  f'{{"beliefs": [{{"statement": "...", "category": "pattern|cause_effect|world_state", "confidence": 0.0-1.0}}]}}')
        system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."
        try:
            response = ollama.chat(prompt, system)
            if not response:
                return []
            data = json.loads(response)
            beliefs = data.get("beliefs", [])
            result = []
            for b in beliefs:
                if b.get("statement") and b.get("category"):
                    result.append({"statement": b["statement"], "category": b["category"], "initial_confidence": b.get("confidence", 0.5)})
            return result
        except (json.JSONDecodeError, Exception) as e:
            log.debug(f"form_beliefs error: {e}")
            return []

    def add_belief(self, statement: str, category: str, initial_confidence: float = 0.5) -> bool:
        for b in self._state["beliefs"]:
            if b["statement"].lower() == statement.lower():
                log.debug(f"Duplicate belief: {statement[:60]}")
                return False
        belief = {"id": str(uuid.uuid4()), "statement": statement, "category": category, "confidence": max(0.0, min(1.0, initial_confidence)),
                  "formed_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "validation_count": 0, "status": "active"}
        self._state["beliefs"].append(belief)
        self._state["total_beliefs_formed"] += 1
        if len(self._state["beliefs"]) > MAX_BELIEFS:
            rejected = [b for b in self._state["beliefs"] if b["status"] == "rejected"]
            if rejected:
                rejected.sort(key=lambda x: x.get("last_updated", ""))
                to_remove = rejected[0]
                self._state["beliefs"].remove(to_remove)
                log.debug(f"Pruned old rejected belief: {to_remove['id']}")
        self._save()
        log.info(f"Belief added: [{category}] {statement[:80]}")
        return True

    def update_confidence(self, belief_id: str, delta: float) -> bool:
        """Update confidence of a belief by delta. Returns True if successful."""
        for b in self._state["beliefs"]:
            if b["id"] == belief_id:
                old_conf = b["confidence"]
                new_conf = max(0.0, min(1.0, old_conf + delta))
                b["confidence"] = new_conf
                b["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                
                # Update status based on confidence
                if new_conf >= 0.85 and b["status"] == "active":
                    b["status"] = "strong"
                elif new_conf < 0.2 and b["status"] != "rejected":
                    b["status"] = "rejected"
                    self._state["total_beliefs_rejected"] += 1
                
                self._save()
                log.info(f"Belief confidence updated: {b['statement'][:60]} | {old_conf:.2f} → {new_conf:.2f}")
                return True
        
        log.warning(f"Belief not found: {belief_id}")
        return False

    def validate_belief(self, belief_id: str, recent_episodes: list[dict], ollama: "OllamaClient") -> bool:
        belief = None
        for b in self._state["beliefs"]:
            if b["id"] == belief_id:
                belief = b
                break
        if not belief:
            log.error(f"Belief not found: {belief_id}")
            return False
        episodes_str = "\n".join(f"- [{e.get('event_type','?')}] {e.get('description','')[:200]}" for e in recent_episodes[:10]) if recent_episodes else "нет"
        prompt = (f"Убеждение: \"{belief['statement']}\"\nКатегория: {belief['category']}\nТекущая уверенность: {belief['confidence']:.2f}\n\n"
                  f"Последние наблюдения:\n{episodes_str}\n\nПодтверждается ли это убеждение наблюдениями? JSON:\n"
                  f'{{"verdict": "strengthen|weaken|neutral", "explanation": "...", "confidence_delta": -0.3 to +0.3}}')
        system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."
        try:
            response = ollama.chat(prompt, system)
            if not response:
                return False
            data = json.loads(response)
            verdict = data.get("verdict", "neutral")
            delta = float(data.get("confidence_delta", 0.0))
            delta = max(-0.3, min(0.3, delta))
            
            # Use update_confidence method
            self.update_confidence(belief_id, delta)
            belief["validation_count"] += 1
            self._state["total_beliefs_validated"] += 1
            self._save()
            
            log.info(f"Belief validated: {belief['statement'][:60]} | verdict={verdict}")
            return True
        except (json.JSONDecodeError, ValueError, Exception) as e:
            log.error(f"validate_belief error: {e}")
            return False

    def get_beliefs(self, min_confidence: float = 0.0, status: str | None = None) -> list[dict]:
        beliefs = [b for b in self._state["beliefs"] if b["confidence"] >= min_confidence]
        if status:
            beliefs = [b for b in beliefs if b["status"] == status]
        beliefs.sort(key=lambda x: x["confidence"], reverse=True)
        return beliefs

    def get_stats(self) -> dict:
        active = len([b for b in self._state["beliefs"] if b["status"] == "active"])
        strong = len([b for b in self._state["beliefs"] if b["status"] == "strong"])
        rejected = len([b for b in self._state["beliefs"] if b["status"] == "rejected"])
        return {"active": active, "strong": strong, "rejected": rejected,
                "total_beliefs_formed": self._state["total_beliefs_formed"],
                "total_beliefs_validated": self._state["total_beliefs_validated"],
                "total_beliefs_rejected": self._state["total_beliefs_rejected"]}

    def to_prompt_context(self, top_n: int = 3) -> str:
        beliefs = self.get_beliefs(min_confidence=0.5, status="active") + self.get_beliefs(min_confidence=0.85, status="strong")
        if not beliefs:
            return ""
        beliefs = sorted(beliefs, key=lambda x: x["confidence"], reverse=True)[:top_n]
        lines = ["Твои убеждения:"]
        for b in beliefs:
            lines.append(f"  • [{b['category']}] {b['statement']} (уверенность: {b['confidence']:.2f})")
        return "\n".join(lines)

    def should_form(self, tick_count: int) -> bool:
        if tick_count == 0:
            return False
        if tick_count % 20 != 0:
            return False
        active = len([b for b in self._state["beliefs"] if b["status"] in ("active", "strong")])
        return active < 30

    def should_validate(self, tick_count: int) -> bool:
        if tick_count == 0:
            return False
        return tick_count % 10 == 0
