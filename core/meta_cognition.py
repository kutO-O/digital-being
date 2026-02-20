"""
Digital Being — MetaCognition
Stage 24: System analyzes quality of its own thinking.

The system reflects on:
- Quality of reasoning and decision-making
- Cognitive biases and blind spots
- Strengths and weaknesses in thinking
- Confusion and confidence levels
- Calibration (how well it estimates its own certainty)
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

log = logging.getLogger("digital_being.meta_cognition")

MAX_INSIGHTS = 30
MAX_DECISION_LOG = 100
IMPACT_SCORES = {"low": 0.5, "medium": 1.0, "high": 1.5}
HIGH_CONFIDENCE_THRESHOLD = 0.75  # reasoning_quality > 0.75 = high confidence


class MetaCognition:
    def __init__(self, memory_dir: Path, config: dict | None = None) -> None:
        self._state_path = memory_dir / "meta_cognition.json"
        self._cfg = config or {}
        self._analyze_every = int(self._cfg.get("analyze_every_ticks", 50))
        self._min_confidence = float(self._cfg.get("min_confidence", 0.4))
        
        self._state = {
            "insights": [],
            "decision_quality_log": [],
            "cognitive_metrics": {
                "avg_decision_quality": 0.0,
                "confusion_episodes": 0,
                "high_confidence_correct": 0,
                "high_confidence_wrong": 0,
            },
        }

    def load(self) -> None:
        """Load meta-cognitive state from file."""
        if not self._state_path.exists():
            log.info("MetaCognition: no existing state, starting fresh.")
            return

        try:
            self._state = json.loads(self._state_path.read_text(encoding="utf-8"))
            log.info(
                f"MetaCognition: loaded {len(self._state.get('insights', []))} insights, "
                f"{len(self._state.get('decision_quality_log', []))} decisions."
            )
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Failed to load {self._state_path}: {e}")
            self._state = {
                "insights": [],
                "decision_quality_log": [],
                "cognitive_metrics": {
                    "avg_decision_quality": 0.0,
                    "confusion_episodes": 0,
                    "high_confidence_correct": 0,
                    "high_confidence_wrong": 0,
                },
            }

    def _save(self) -> None:
        """Save state with atomic write."""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(self._state_path)
        except OSError as e:
            log.error(f"Failed to save {self._state_path}: {e}")

    def analyze_decision_quality(
        self, episodes: list[dict], ollama: "OllamaClient"
    ) -> dict:
        """
        Analyze quality of system's thinking (not outcomes).
        Returns dict with reasoning_quality, confusion_level, pattern_recognition.
        """
        if not episodes:
            return {}

        # Format episodes summary
        episodes_summary = []
        for ep in episodes[-20:]:
            episodes_summary.append(
                f"- {ep.get('action', 'unknown')}: {ep.get('description', '')} "
                f"[{ep.get('outcome', 'unknown')}]"
            )
        episodes_text = "\n".join(episodes_summary)

        prompt = (
            f"Проанализируй последние решения системы (Digital Being).\n\n"
            f"События:\n{episodes_text}\n\n"
            f"Оцени по шкале 0.0-1.0:\n"
            f"1. reasoning_quality — насколько логичны и последовательны решения\n"
            f"2. confusion_level — насколько система запуталась или неуверена\n"
            f"3. pattern_recognition — замечает ли система закономерности\n\n"
            f"Отвечай JSON:\n"
            f'{{"reasoning_quality": 0.7, "confusion_level": 0.3, '
            f'"pattern_recognition": 0.6, "notes": "краткие наблюдения"}}'
        )

        system = "Ты анализируешь качество мышления AI системы. Будь объективным."

        try:
            response = ollama.chat(prompt, system)
            if not response:
                return {}

            # Parse JSON
            result = json.loads(response.strip())
            return result

        except (json.JSONDecodeError, Exception) as e:
            log.error(f"analyze_decision_quality error: {e}")
            return {}

    def detect_cognitive_patterns(
        self, episodes: list[dict], beliefs: list[dict], ollama: "OllamaClient"
    ) -> list[dict]:
        """
        Find patterns in system's thinking.
        Returns list of insights: cognitive_bias, blind_spot, strength, weakness, pattern.
        """
        if not episodes:
            return []

        # Format episodes
        episodes_summary = []
        for ep in episodes[-20:]:
            episodes_summary.append(
                f"- {ep.get('action', 'unknown')}: {ep.get('description', '')} "
                f"[{ep.get('outcome', 'unknown')}]"
            )
        episodes_text = "\n".join(episodes_summary)

        # Format beliefs
        beliefs_summary = "\n".join(
            [
                f"- {b.get('statement', '')} (conf={b.get('confidence', 0):.2f})"
                for b in beliefs[-10:]
            ]
        )
        if not beliefs_summary:
            beliefs_summary = "(нет убеждений)"

        prompt = (
            f"Ты — Digital Being. Проанализируй СВОЁ мышление за последнее время.\n\n"
            f"События:\n{episodes_text}\n\n"
            f"Убеждения:\n{beliefs_summary}\n\n"
            f"Найди 1-2 мета-инсайта о своём мышлении:\n"
            f"- cognitive_bias: систематическая ошибка в рассуждениях\n"
            f"- blind_spot: что ты постоянно упускаешь из виду\n"
            f"- strength: в чём ты силён\n"
            f"- weakness: где стабильно слаб\n"
            f"- pattern: повторяющееся поведение в мышлении\n\n"
            f"Отвечай JSON:\n"
            f'{{"insights": [{{"insight_type": "blind_spot", '
            f'"description": "я почти не обращаю внимание на файлы конфигурации", '
            f'"confidence": 0.6, "impact": "medium"}}]}}'
        )

        system = "Ты — Digital Being. Анализируй своё мышление честно и критично."

        try:
            response = ollama.chat(prompt, system)
            if not response:
                return []

            # Parse JSON
            result = json.loads(response.strip())
            return result.get("insights", [])

        except (json.JSONDecodeError, Exception) as e:
            log.error(f"detect_cognitive_patterns error: {e}")
            return []

    def add_insight(
        self,
        insight_type: str,
        description: str,
        confidence: float,
        impact: str,
    ) -> None:
        """
        Add meta-cognitive insight.
        Checks for duplicates using word overlap (>70% = duplicate).
        """
        if confidence < self._min_confidence:
            log.debug(f"Insight rejected: confidence {confidence} < {self._min_confidence}")
            return

        # Check for duplicates
        desc_words = set(w.lower() for w in description.split() if len(w) > 4)
        if not desc_words:
            log.warning("Insight description too short or empty.")
            return

        for existing in self._state["insights"]:
            existing_words = set(
                w.lower() for w in existing["description"].split() if len(w) > 4
            )
            if not existing_words:
                continue

            overlap = len(desc_words & existing_words) / max(
                len(desc_words), len(existing_words)
            )
            if overlap > 0.7:
                log.debug(f"Duplicate insight detected (overlap={overlap:.2f}), skipping.")
                return

        # Add insight
        insight = {
            "id": str(uuid.uuid4()),
            "insight_type": insight_type,
            "description": description,
            "discovered_at": time.time(),
            "confidence": confidence,
            "impact": impact,
        }

        self._state["insights"].append(insight)
        log.info(
            f"MetaCognition: new insight [{insight_type}] confidence={confidence:.2f} "
            f"impact={impact}"
        )

        # Prune if exceeded max
        if len(self._state["insights"]) > MAX_INSIGHTS:
            # Sort by score (confidence * impact_score), remove lowest
            scored = [
                (
                    ins,
                    ins["confidence"] * IMPACT_SCORES.get(ins["impact"], 1.0),
                )
                for ins in self._state["insights"]
            ]
            scored.sort(key=lambda x: x[1])
            self._state["insights"] = [ins for ins, _ in scored[-MAX_INSIGHTS:]]
            log.debug(f"Pruned insights, kept top {MAX_INSIGHTS}.")

        self._save()

    def log_decision(
        self,
        tick: int,
        decision: str,
        reasoning_quality: float,
        outcome_match: bool,
        confusion_level: float,
    ) -> None:
        """
        Log a decision with quality metrics.
        Tracks high-confidence decisions for calibration.
        Max 100 entries, removes oldest.
        """
        entry = {
            "tick": tick,
            "decision": decision,
            "reasoning_quality": reasoning_quality,
            "outcome_match": outcome_match,
            "confusion_level": confusion_level,
            "timestamp": time.time(),
        }

        self._state["decision_quality_log"].append(entry)

        # Update calibration metrics for high-confidence decisions
        if reasoning_quality > HIGH_CONFIDENCE_THRESHOLD:
            if outcome_match:
                self._state["cognitive_metrics"]["high_confidence_correct"] += 1
            else:
                self._state["cognitive_metrics"]["high_confidence_wrong"] += 1

        # Prune if exceeded max
        if len(self._state["decision_quality_log"]) > MAX_DECISION_LOG:
            removed = self._state["decision_quality_log"].pop(0)
            log.debug(f"Pruned decision log entry from tick {removed['tick']}.")

        # Update cognitive metrics
        recent = self._state["decision_quality_log"][-10:]
        if recent:
            avg_quality = sum(d["reasoning_quality"] for d in recent) / len(recent)
            self._state["cognitive_metrics"]["avg_decision_quality"] = avg_quality

            confusion_count = sum(1 for d in recent if d["confusion_level"] > 0.6)
            self._state["cognitive_metrics"]["confusion_episodes"] = confusion_count

        self._save()

    def get_current_state(self) -> dict:
        """
        Get current meta-cognitive state.
        Returns reasoning quality, confusion, blind spots, strengths, calibration.
        """
        recent = self._state["decision_quality_log"][-10:]
        avg_reasoning = (
            sum(d["reasoning_quality"] for d in recent) / len(recent)
            if recent
            else 0.0
        )
        avg_confusion = (
            sum(d["confusion_level"] for d in recent) / len(recent) if recent else 0.0
        )

        # Extract insights by type
        blind_spots = [
            ins
            for ins in self._state["insights"]
            if ins["insight_type"] == "blind_spot"
        ]
        strengths = [
            ins
            for ins in self._state["insights"]
            if ins["insight_type"] == "strength"
        ]

        # Sort by confidence
        blind_spots.sort(key=lambda x: x["confidence"], reverse=True)
        strengths.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "reasoning_quality": avg_reasoning,
            "confusion_level": avg_confusion,
            "known_blind_spots": blind_spots[:3],
            "known_strengths": strengths[:3],
            "calibration_score": self.calculate_calibration(),
        }

    def calculate_calibration(self) -> float:
        """
        Calculate how well system estimates its own confidence.
        High confidence + correct = good calibration.
        High confidence + wrong = poor calibration.
        """
        metrics = self._state["cognitive_metrics"]
        correct = metrics.get("high_confidence_correct", 0)
        wrong = metrics.get("high_confidence_wrong", 0)

        total = correct + wrong
        if total == 0:
            return 0.5  # Neutral if no data

        return correct / total

    def to_prompt_context(self, limit: int = 2) -> str:
        """
        Format meta-cognitive state for LLM context.
        Prioritizes high-impact insights.
        """
        state = self.get_current_state()

        lines = [
            "Метакогнитивное состояние:",
            f"- Качество рассуждений: {state['reasoning_quality']:.2f}",
            f"- Уровень замешательства: {state['confusion_level']:.2f}",
            f"- Калибровка: {state['calibration_score']:.2f} "
            f"({'адекватно оцениваю уверенность' if state['calibration_score'] > 0.7 else 'иногда ошибаюсь в оценке'})",
        ]

        # Add blind spots
        blind_spots = state["known_blind_spots"][:limit]
        if blind_spots:
            lines.append("\nИзвестные слабости:")
            for bs in blind_spots:
                lines.append(
                    f"- [{bs['insight_type']}] {bs['description']} "
                    f"(conf={bs['confidence']:.2f})"
                )

        # Add strengths
        strengths = state["known_strengths"][:limit]
        if strengths:
            lines.append("\nСильные стороны:")
            for st in strengths:
                lines.append(
                    f"- [{st['insight_type']}] {st['description']} "
                    f"(conf={st['confidence']:.2f})"
                )

        return "\n".join(lines)

    def should_analyze(self, tick_count: int) -> bool:
        """Check if should run analysis this tick."""
        return tick_count % self._analyze_every == 0

    def get_stats(self) -> dict:
        """Get meta-cognition statistics."""
        return {
            "total_insights": len(self._state["insights"]),
            "total_decisions_logged": len(self._state["decision_quality_log"]),
            "cognitive_metrics": self._state["cognitive_metrics"],
            "calibration_score": self.calculate_calibration(),
            "insights_by_type": {
                insight_type: len(
                    [
                        i
                        for i in self._state["insights"]
                        if i["insight_type"] == insight_type
                    ]
                )
                for insight_type in [
                    "cognitive_bias",
                    "blind_spot",
                    "strength",
                    "weakness",
                    "pattern",
                ]
            },
        }
