"""
Digital Being — ContradictionResolver
Stage 20: Detect and resolve contradictions between beliefs and principles.

Process:
  1. detect_contradictions() — find conflicting beliefs/principles via LLM
  2. add_contradiction() — add to pending queue
  3. resolve_contradiction() — run 3-step LLM dialogue:
       - Position A defense
       - Position B defense
       - Judge verdict (choose_a, choose_b, synthesis, both_valid)
  4. Apply verdict to confidence scores / create synthesis

State: memory/contradictions.json
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

log = logging.getLogger("digital_being.contradiction_resolver")

MAX_CONTRADICTIONS = 50


class ContradictionResolver:
    """
    Detects and resolves contradictions between beliefs and principles
    through LLM-based dialogue and reasoning.
    """

    def __init__(self, state_path: Path) -> None:
        self._path = state_path
        self._state = self.load()

    def load(self) -> dict:
        """Load state from disk."""
        if not self._path.exists():
            return {
                "contradictions": [],
                "total_detected": 0,
                "total_resolved": 0,
            }
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Failed to load {self._path}: {e}")
            return {
                "contradictions": [],
                "total_detected": 0,
                "total_resolved": 0,
            }

    def _save(self) -> None:
        """Atomic write to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._path)
        except OSError as e:
            log.error(f"Failed to save {self._path}: {e}")

    # ────────────────────────────────────────────────────────────────
    # Detection
    # ────────────────────────────────────────────────────────────────
    def detect_contradictions(
        self,
        beliefs: list[dict],
        principles: list[dict],
        ollama: "OllamaClient",
    ) -> list[dict]:
        """
        Detect contradictions between beliefs and principles via LLM.
        Returns list of detected contradictions (not saved automatically).
        
        If total items > 20, only check top 10 by confidence.
        """
        # Prepare items
        belief_items = [
            {"id": b["id"], "text": b["statement"], "type": "belief", "conf": b.get("confidence", 0.5)}
            for b in beliefs if b.get("status") == "active"
        ]
        principle_items = [
            {"id": p["id"], "text": p["principle"], "type": "principle", "conf": 1.0}
            for p in principles
        ]
        
        all_items = belief_items + principle_items
        
        # If too many, take top by confidence
        if len(all_items) > 20:
            all_items = sorted(all_items, key=lambda x: x["conf"], reverse=True)[:10]
            log.debug(f"detect_contradictions: limited to top 10 items by confidence")
        
        found = []
        checked_pairs = set()
        
        # Check all pairs
        for i, item_a in enumerate(all_items):
            for item_b in all_items[i + 1:]:
                pair_key = tuple(sorted([item_a["id"], item_b["id"]]))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)
                
                # Determine contradiction type
                if item_a["type"] == "belief" and item_b["type"] == "belief":
                    contr_type = "belief_belief"
                elif item_a["type"] == "principle" and item_b["type"] == "principle":
                    contr_type = "principle_principle"
                else:
                    contr_type = "belief_principle"
                
                # Ask LLM
                if self._check_contradiction_llm(item_a["text"], item_b["text"], ollama):
                    found.append({
                        "type": contr_type,
                        "item_a": {"id": item_a["id"], "text": item_a["text"], "type": item_a["type"]},
                        "item_b": {"id": item_b["id"], "text": item_b["text"], "type": item_b["type"]},
                    })
                    log.info(
                        f"Contradiction detected: [{contr_type}] "
                        f"{item_a['text'][:40]} vs {item_b['text'][:40]}"
                    )
        
        return found

    def _check_contradiction_llm(
        self, text_a: str, text_b: str, ollama: "OllamaClient"
    ) -> bool:
        """Ask LLM if two statements contradict."""
        prompt = (
            f"Проанализируй два утверждения. Противоречат ли они друг другу?\n\n"
            f"A) {text_a}\n"
            f"B) {text_b}\n\n"
            f"Отвечай JSON: {{\"contradicts\": true/false, \"explanation\": \"...\"}}"
        )
        system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."
        
        try:
            response = ollama.chat(prompt, system)
            if not response:
                return False
            data = json.loads(response)
            return bool(data.get("contradicts", False))
        except (json.JSONDecodeError, Exception) as e:
            log.debug(f"_check_contradiction_llm error: {e}")
            return False

    # ────────────────────────────────────────────────────────────────
    # Add
    # ────────────────────────────────────────────────────────────────
    def add_contradiction(
        self, contr_type: str, item_a: dict, item_b: dict
    ) -> bool:
        """
        Add contradiction to queue if not duplicate.
        Returns True if added, False if duplicate.
        """
        # Check duplicate
        pair_ids = set([item_a["id"], item_b["id"]])
        for c in self._state["contradictions"]:
            existing_ids = set([c["item_a"]["id"], c["item_b"]["id"]])
            if pair_ids == existing_ids:
                log.debug(f"Duplicate contradiction: {item_a['id']} vs {item_b['id']}")
                return False
        
        # Add
        contradiction = {
            "id": str(uuid.uuid4()),
            "type": contr_type,
            "item_a": item_a,
            "item_b": item_b,
            "detected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "pending",
            "resolution": None,
        }
        self._state["contradictions"].append(contradiction)
        self._state["total_detected"] += 1
        
        # Prune if too many
        if len(self._state["contradictions"]) > MAX_CONTRADICTIONS:
            # Remove oldest resolved
            resolved = [c for c in self._state["contradictions"] if c["status"] == "resolved"]
            if resolved:
                resolved.sort(key=lambda x: x.get("resolution", {}).get("resolved_at", ""))
                to_remove = resolved[0]
                self._state["contradictions"].remove(to_remove)
                log.debug(f"Pruned old resolved contradiction: {to_remove['id']}")
        
        self._save()
        log.info(f"Contradiction added: {contradiction['id']} [{contr_type}]")
        return True

    # ────────────────────────────────────────────────────────────────
    # Resolve
    # ────────────────────────────────────────────────────────────────
    def resolve_contradiction(
        self, contradiction_id: str, ollama: "OllamaClient"
    ) -> bool:
        """
        Resolve contradiction through 3-step LLM dialogue:
          1. Position A defense
          2. Position B defense
          3. Judge verdict
        
        Returns True if resolved, False on error.
        """
        # Find contradiction
        contradiction = None
        for c in self._state["contradictions"]:
            if c["id"] == contradiction_id:
                contradiction = c
                break
        
        if not contradiction:
            log.error(f"Contradiction not found: {contradiction_id}")
            return False
        
        if contradiction["status"] != "pending":
            log.warning(f"Contradiction already resolved: {contradiction_id}")
            return False
        
        item_a = contradiction["item_a"]
        item_b = contradiction["item_b"]
        
        log.info(f"Resolving contradiction: {contradiction_id}")
        
        try:
            # Step 1: Position A defense
            args_a = self._generate_defense(item_a["text"], item_b["text"], ollama)
            if not args_a:
                raise ValueError("Failed to generate defense for position A")
            
            # Step 2: Position B defense
            args_b = self._generate_defense(item_b["text"], item_a["text"], ollama)
            if not args_b:
                raise ValueError("Failed to generate defense for position B")
            
            # Step 3: Judge verdict
            verdict_data = self._judge_verdict(
                item_a["text"], args_a, item_b["text"], args_b, ollama
            )
            if not verdict_data:
                raise ValueError("Failed to get judge verdict")
            
            # Apply verdict
            resolution = {
                "verdict": verdict_data["verdict"],
                "reasoning": verdict_data["reasoning"],
                "synthesis_text": verdict_data.get("synthesis_text", ""),
                "resolved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            
            contradiction["resolution"] = resolution
            contradiction["status"] = "resolved"
            self._state["total_resolved"] += 1
            self._save()
            
            log.info(
                f"Contradiction resolved: {contradiction_id} "
                f"verdict={verdict_data['verdict']}"
            )
            return True
            
        except Exception as e:
            log.error(f"Failed to resolve contradiction {contradiction_id}: {e}")
            contradiction["status"] = "deferred"
            self._save()
            return False

    def _generate_defense(
        self, my_position: str, opposing_position: str, ollama: "OllamaClient"
    ) -> str:
        """Generate defense arguments for a position."""
        prompt = (
            f"Ты защищаешь позицию: \"{my_position}\"\n"
            f"Противоположная позиция: \"{opposing_position}\"\n\n"
            f"Приведи 2-3 сильных аргумента в свою пользу. Будь убедительным и конкретным."
        )
        system = "Ты — Digital Being. Защищай свою позицию логично и по делу."
        
        try:
            response = ollama.chat(prompt, system)
            return response.strip() if response else ""
        except Exception as e:
            log.error(f"_generate_defense error: {e}")
            return ""

    def _judge_verdict(
        self,
        text_a: str,
        args_a: str,
        text_b: str,
        args_b: str,
        ollama: "OllamaClient",
    ) -> dict | None:
        """Judge which position is correct or synthesize."""
        prompt = (
            f"Позиция A: {text_a}\n"
            f"Аргументы A: {args_a}\n\n"
            f"Позиция B: {text_b}\n"
            f"Аргументы B: {args_b}\n\n"
            f"Как разрешить это противоречие? Выбери:\n"
            f"- \"choose_a\" — A правильна, B отклонить\n"
            f"- \"choose_b\" — B правильна, A отклонить\n"
            f"- \"synthesis\" — создать новое утверждение объединяющее обе стороны\n"
            f"- \"both_valid\" — оба утверждения верны в разных контекстах\n\n"
            f"Отвечай JSON:\n"
            f'{{\n'
            f'  \"verdict\": \"choose_a\"|\"choose_b\"|\"synthesis\"|\"both_valid\",\n'
            f'  \"reasoning\": \"...\",\n'
            f'  \"synthesis_text\": \"...\"  // если synthesis\n'
            f'}}'
        )
        system = "Ты — Digital Being. Судья. Отвечай ТОЛЬКО валидным JSON."
        
        try:
            response = ollama.chat(prompt, system)
            if not response:
                return None
            
            # Try to parse JSON
            data = json.loads(response)
            verdict = data.get("verdict", "")
            if verdict not in ["choose_a", "choose_b", "synthesis", "both_valid"]:
                log.warning(f"Invalid verdict: {verdict}")
                return None
            
            return {
                "verdict": verdict,
                "reasoning": data.get("reasoning", ""),
                "synthesis_text": data.get("synthesis_text", ""),
            }
        except json.JSONDecodeError:
            # Try to extract from text
            log.debug("Failed to parse JSON, trying text extraction")
            response_lower = response.lower()
            if "choose_a" in response_lower or "choose a" in response_lower:
                return {"verdict": "choose_a", "reasoning": response[:500], "synthesis_text": ""}
            elif "choose_b" in response_lower or "choose b" in response_lower:
                return {"verdict": "choose_b", "reasoning": response[:500], "synthesis_text": ""}
            elif "synthesis" in response_lower:
                return {"verdict": "synthesis", "reasoning": response[:500], "synthesis_text": ""}
            elif "both_valid" in response_lower or "both valid" in response_lower:
                return {"verdict": "both_valid", "reasoning": response[:500], "synthesis_text": ""}
            return None
        except Exception as e:
            log.error(f"_judge_verdict error: {e}")
            return None

    # ────────────────────────────────────────────────────────────────
    # Query
    # ────────────────────────────────────────────────────────────────
    def get_pending(self) -> list[dict]:
        """Get all pending contradictions."""
        return [
            c for c in self._state["contradictions"]
            if c["status"] == "pending"
        ]

    def get_resolved(self, limit: int = 10) -> list[dict]:
        """Get last N resolved contradictions."""
        resolved = [
            c for c in self._state["contradictions"]
            if c["status"] == "resolved"
        ]
        # Sort by resolved_at descending
        resolved.sort(
            key=lambda x: x.get("resolution", {}).get("resolved_at", ""),
            reverse=True,
        )
        return resolved[:limit]

    def get_stats(self) -> dict:
        """Get statistics."""
        pending = len([c for c in self._state["contradictions"] if c["status"] == "pending"])
        resolved = len([c for c in self._state["contradictions"] if c["status"] == "resolved"])
        deferred = len([c for c in self._state["contradictions"] if c["status"] == "deferred"])
        
        return {
            "pending": pending,
            "resolved": resolved,
            "deferred": deferred,
            "total_detected": self._state["total_detected"],
            "total_resolved": self._state["total_resolved"],
        }

    # ────────────────────────────────────────────────────────────────
    # Scheduling
    # ────────────────────────────────────────────────────────────────
    def should_detect(self, tick_count: int) -> bool:
        """Should detect contradictions on this tick?"""
        if tick_count == 0:
            return False
        return tick_count % 30 == 0

    def should_resolve(self, tick_count: int) -> bool:
        """Should resolve contradictions on this tick?"""
        if tick_count == 0:
            return False
        pending = self.get_pending()
        return tick_count % 15 == 0 and len(pending) > 0
