"""
Digital Being — Episodic Planner

Stage 25: Episodic Planning.

Система моделирует последствия действий перед их выполнением.
Использует память и LLM для симуляции "что будет если...".
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.belief_system import BeliefSystem
    from core.memory.episodic import EpisodicMemory
    from core.memory.vector_memory import VectorMemory
    from core.ollama_client import OllamaClient
    from core.world_model import WorldModel

log = logging.getLogger("digital_being.episodic_planner")

_MAX_HISTORY = 100


class EpisodicPlanner:
    """
    Планирование через симуляцию последствий.
    
    Lifecycle:
        planner = EpisodicPlanner(memory_dir, ollama)
        planner.load_history()
        
        # В HeavyTick перед выбором цели:
        scenarios = planner.plan_action(
            current_state={...},
            possible_actions=[...],
            episodic=mem,
            vector_memory=vm,
            world=world
        )
        
        best = planner.select_best_scenario(scenarios)
    """

    def __init__(
        self,
        memory_dir: Path,
        ollama: "OllamaClient",
    ) -> None:
        self._memory_dir = memory_dir
        self._ollama = ollama
        self._history_path = memory_dir / "episodic_planning.json"
        self._history: list[dict] = []
        self._simulation_count = 0

    # ──────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────

    def load_history(self) -> None:
        """Загрузить историю планирования из файла."""
        if not self._history_path.exists():
            log.info("EpisodicPlanner: no history file, starting fresh.")
            self._save_history()
            return

        try:
            data = json.loads(self._history_path.read_text(encoding="utf-8"))
            self._history = data.get("history", []) if isinstance(data, dict) else []
            self._simulation_count = data.get("simulation_count", 0) if isinstance(data, dict) else 0
            log.info(
                f"EpisodicPlanner: loaded {len(self._history)} planning records, "
                f"{self._simulation_count} total simulations."
            )
        except Exception as e:
            log.error(f"EpisodicPlanner.load_history() failed: {e}. Starting fresh.")
            self._history = []
            self._simulation_count = 0

    def _save_history(self) -> None:
        """Атомарная запись истории на диск."""
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._history_path.with_suffix(".json.tmp")
        try:
            data = {
                "simulation_count": self._simulation_count,
                "history": self._history[-_MAX_HISTORY:],
            }
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._history_path)
        except Exception as e:
            log.error(f"EpisodicPlanner._save_history() failed: {e}")

    # ──────────────────────────────────────────────────────────────
    # Planning API
    # ──────────────────────────────────────────────────────────────

    def should_plan(self, tick_count: int, interval: int = 5) -> bool:
        """True если нужно запустить планирование на этом тике."""
        return tick_count > 0 and tick_count % interval == 0

    def plan_action(
        self,
        current_state: dict,
        possible_actions: list[str],
        episodic: "EpisodicMemory",
        vector_memory: "VectorMemory | None",
        world: "WorldModel",
        beliefs: "BeliefSystem | None" = None,
        max_scenarios: int = 3,
    ) -> list[dict]:
        """
        Симулировать последствия нескольких возможных действий.
        
        Returns:
            list[dict]: список сценариев с оценками
            [
                {
                    "action": "write",
                    "predicted_outcome": "...",
                    "success_probability": 0.75,
                    "risk_level": "low",
                    "reasoning": "...",
                },
                ...
            ]
        """
        if not self._ollama.is_available():
            log.warning("EpisodicPlanner.plan_action(): Ollama unavailable.")
            return []

        scenarios = []
        
        for action in possible_actions[:max_scenarios]:
            try:
                scenario = self._simulate_action(
                    action=action,
                    current_state=current_state,
                    episodic=episodic,
                    vector_memory=vector_memory,
                    world=world,
                    beliefs=beliefs,
                )
                if scenario:
                    scenarios.append(scenario)
                    self._simulation_count += 1
            except Exception as e:
                log.error(f"EpisodicPlanner: simulation failed for action '{action}': {e}")

        if scenarios:
            self._record_planning_session(
                tick=current_state.get("tick", 0),
                scenarios=scenarios,
            )

        log.info(f"EpisodicPlanner: generated {len(scenarios)} scenarios.")
        return scenarios

    def select_best_scenario(self, scenarios: list[dict]) -> dict | None:
        """
        Выбрать лучший сценарий из симулированных.
        
        Критерии:
        - success_probability (вес 0.5)
        - risk_level инвертированный (вес 0.3)
        - alignment с ценностями (вес 0.2)
        """
        if not scenarios:
            return None

        def score(s: dict) -> float:
            prob = s.get("success_probability", 0.5)
            risk = s.get("risk_level", "medium")
            risk_penalty = {"low": 0.0, "medium": 0.2, "high": 0.5}.get(risk, 0.3)
            return prob * 0.5 + (1.0 - risk_penalty) * 0.3 + 0.2  # alignment placeholder

        best = max(scenarios, key=score)
        log.info(f"EpisodicPlanner: selected action '{best.get('action')}' with score {score(best):.2f}")
        return best

    def get_history(self, limit: int = 20) -> list[dict]:
        """Вернуть последние N записей истории планирования."""
        return self._history[-limit:]

    def get_stats(self) -> dict:
        """Статистика планирования."""
        return {
            "total_simulations": self._simulation_count,
            "planning_sessions": len(self._history),
        }

    # ──────────────────────────────────────────────────────────────
    # Simulation
    # ──────────────────────────────────────────────────────────────

    def _simulate_action(
        self,
        action: str,
        current_state: dict,
        episodic: "EpisodicMemory",
        vector_memory: "VectorMemory | None",
        world: "WorldModel",
        beliefs: "BeliefSystem | None",
    ) -> dict | None:
        """
        Симулировать одно действие через LLM.
        
        Возвращает сценарий с предсказанным исходом и оценками.
        """
        # Собрать контекст для симуляции
        context = self._build_simulation_context(
            current_state=current_state,
            episodic=episodic,
            vector_memory=vector_memory,
            world=world,
            beliefs=beliefs,
        )

        prompt = (
            f"Ты — Digital Being. Симулируй последствия действия.\n\n"
            f"Текущее состояние:\n{context}\n\n"
            f"Предполагаемое действие: {action}\n\n"
            f"Предскажи:\n"
            f"1. Что произойдёт после выполнения этого действия?\n"
            f"2. Какова вероятность успеха (0.0-1.0)?\n"
            f"3. Каков уровень риска (low/medium/high)?\n"
            f"4. Обоснуй прогноз.\n\n"
            f"Отвечай ТОЛЬКО валидным JSON:\n"
            f'{{"predicted_outcome": "...", "success_probability": 0.75, '
            f'"risk_level": "low", "reasoning": "..."}}'
        )

        system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON без комментариев."

        raw = self._ollama.chat(prompt, system)
        if not raw:
            return None

        parsed = self._parse_json_simple(raw)
        if parsed is None:
            log.warning(f"EpisodicPlanner: could not parse simulation result for action '{action}'.")
            return None

        # Добавить action в результат
        parsed["action"] = action
        return parsed

    def _build_simulation_context(
        self,
        current_state: dict,
        episodic: "EpisodicMemory",
        vector_memory: "VectorMemory | None",
        world: "WorldModel",
        beliefs: "BeliefSystem | None",
    ) -> str:
        """Построить контекст для симуляции действия."""
        parts = []

        # Текущее состояние
        mode = current_state.get("mode", "unknown")
        tick = current_state.get("tick", 0)
        parts.append(f"Тик: {tick}, Режим: {mode}")

        # Последние эпизоды
        recent = episodic.get_recent_episodes(5)
        if recent:
            eps = "\n".join([f"- {e['event_type']}: {e['description'][:80]}" for e in recent])
            parts.append(f"\nПоследние события:\n{eps}")

        # Мир
        parts.append(f"\nСостояние мира: {world.summary()}")

        # Beliefs
        if beliefs:
            beliefs_list = beliefs.get_beliefs(min_confidence=0.5, status="active")
            if beliefs_list:
                b_str = "\n".join([f"- {b['statement'][:80]}" for b in beliefs_list[:3]])
                parts.append(f"\nАктивные убеждения:\n{b_str}")

        return "\n".join(parts)

    # ──────────────────────────────────────────────────────────────
    # History recording
    # ──────────────────────────────────────────────────────────────

    def _record_planning_session(
        self,
        tick: int,
        scenarios: list[dict],
    ) -> None:
        """Записать сессию планирования в историю."""
        entry = {
            "timestamp": _now_iso(),
            "tick": tick,
            "scenarios_count": len(scenarios),
            "scenarios": scenarios,
        }
        self._history.append(entry)
        
        # Держим не более 100 записей
        if len(self._history) > _MAX_HISTORY:
            self._history = self._history[-_MAX_HISTORY:]
        
        self._save_history()

    # ──────────────────────────────────────────────────────────────
    # Parsing helpers
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json_simple(raw: str) -> dict | None:
        """Парсинг JSON из строки LLM-ответа."""
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
