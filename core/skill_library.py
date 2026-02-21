"""
Digital Being — Skill Library

Stage 26: Skill Library.

Система накопления и переиспользования успешных паттернов действий.
Навыки сохраняются, обобщаются и могут комбинироваться для решения сложных задач.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.episodic import EpisodicMemory
    from core.ollama_client import OllamaClient

log = logging.getLogger("digital_being.skill_library")

_MAX_SKILLS = 200
_MAX_EXECUTIONS_HISTORY = 50


class SkillLibrary:
    """
    Библиотека переиспользуемых навыков.
    
    Навык (Skill) — это последовательность действий которая:
    - Была успешно выполнена
    - Может быть применена в похожих контекстах
    - Улучшается с каждым использованием
    
    Lifecycle:
        library = SkillLibrary(memory_dir, ollama)
        library.load()
        
        # После успешного действия:
        library.record_action(
            action_type="write",
            context={...},
            outcome="success",
            episode_id=123
        )
        
        # Периодически обобщать в навыки:
        if library.should_extract_skills(tick):
            new_skills = library.extract_skills(episodic_memory)
        
        # Поиск подходящего навыка:
        skills = library.find_applicable_skills(current_context)
        if skills:
            best_skill = skills[0]
            # Использовать best_skill для генерации плана
    """

    def __init__(
        self,
        memory_dir: Path,
        ollama: "OllamaClient",
    ) -> None:
        self._memory_dir = memory_dir
        self._ollama = ollama
        self._skills_path = memory_dir / "skills.json"
        self._actions_path = memory_dir / "skill_actions_log.json"
        
        self._skills: list[dict] = []  # Библиотека навыков
        self._actions_log: list[dict] = []  # Лог действий для обучения
        self._total_extractions = 0
        self._total_skill_uses = 0

    # ────────────────────────────────────────────────────────────────
    # Persistence
    # ────────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Загрузить библиотеку навыков из файла."""
        if not self._skills_path.exists():
            log.info("SkillLibrary: no skills file, starting fresh.")
            self._save()
            return

        try:
            data = json.loads(self._skills_path.read_text(encoding="utf-8"))
            self._skills = data.get("skills", []) if isinstance(data, dict) else []
            self._total_extractions = data.get("total_extractions", 0) if isinstance(data, dict) else 0
            self._total_skill_uses = data.get("total_skill_uses", 0) if isinstance(data, dict) else 0
            log.info(f"SkillLibrary: loaded {len(self._skills)} skills.")
        except Exception as e:
            log.error(f"SkillLibrary.load() failed: {e}. Starting fresh.")
            self._skills = []

        # Load actions log
        if self._actions_path.exists():
            try:
                actions_data = json.loads(self._actions_path.read_text(encoding="utf-8"))
                self._actions_log = actions_data.get("actions", []) if isinstance(actions_data, dict) else []
                log.info(f"SkillLibrary: loaded {len(self._actions_log)} action records.")
            except Exception as e:
                log.error(f"SkillLibrary: failed to load actions log: {e}")
                self._actions_log = []

    def _save(self) -> None:
        """Атомарная запись библиотеки на диск."""
        self._skills_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._skills_path.with_suffix(".json.tmp")
        try:
            data = {
                "total_extractions": self._total_extractions,
                "total_skill_uses": self._total_skill_uses,
                "skills": self._skills[-_MAX_SKILLS:],
            }
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._skills_path)
        except Exception as e:
            log.error(f"SkillLibrary._save() failed: {e}")

    def _save_actions_log(self) -> None:
        """Сохранить лог действий."""
        self._actions_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._actions_path.with_suffix(".json.tmp")
        try:
            data = {
                "actions": self._actions_log[-_MAX_EXECUTIONS_HISTORY:],
            }
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._actions_path)
        except Exception as e:
            log.error(f"SkillLibrary._save_actions_log() failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Recording Actions
    # ────────────────────────────────────────────────────────────────

    def record_action(
        self,
        action_type: str,
        context: dict,
        outcome: str,
        episode_id: int | None = None,
        tick: int | None = None,
    ) -> None:
        """
        Записать выполненное действие для последующего обучения.
        
        Args:
            action_type: Тип действия (observe, analyze, write, shell, etc.)
            context: Контекст действия (monologue, mode, etc.)
            outcome: Результат (success, error, skipped)
            episode_id: ID эпизода в памяти
            tick: Номер тика
        """
        record = {
            "timestamp": _now_iso(),
            "action_type": action_type,
            "context": context,
            "outcome": outcome,
            "episode_id": episode_id,
            "tick": tick,
        }
        self._actions_log.append(record)
        
        # Keep only recent actions
        if len(self._actions_log) > _MAX_EXECUTIONS_HISTORY:
            self._actions_log = self._actions_log[-_MAX_EXECUTIONS_HISTORY:]
        
        self._save_actions_log()

    # ────────────────────────────────────────────────────────────────
    # Skill Extraction
    # ────────────────────────────────────────────────────────────────

    def should_extract_skills(self, tick_count: int, interval: int = 20) -> bool:
        """True если пора извлекать навыки из истории действий."""
        return tick_count > 0 and tick_count % interval == 0 and len(self._actions_log) >= 3

    def extract_skills(
        self,
        episodic: "EpisodicMemory",
        min_success_rate: float = 0.7,
    ) -> list[dict]:
        """
        Извлечь навыки из истории успешных действий.
        
        Анализирует последовательности действий и обобщает их в навыки.
        
        Returns:
            list[dict]: Новые извлечённые навыки
        """
        if not self._ollama.is_available():
            log.warning("SkillLibrary.extract_skills(): Ollama unavailable.")
            return []

        # Фильтруем успешные действия
        successful_actions = [
            a for a in self._actions_log
            if a.get("outcome") == "success"
        ]
        
        if len(successful_actions) < 3:
            log.info("SkillLibrary: not enough successful actions to extract skills.")
            return []

        # Группируем по типу действия
        action_groups = {}
        for action in successful_actions:
            action_type = action.get("action_type", "unknown")
            if action_type not in action_groups:
                action_groups[action_type] = []
            action_groups[action_type].append(action)

        new_skills = []
        for action_type, actions in action_groups.items():
            if len(actions) < 2:
                continue
            
            # Извлечь общие паттерны
            skill = self._generalize_actions(action_type, actions, episodic)
            if skill:
                new_skills.append(skill)
                self._skills.append(skill)
                self._total_extractions += 1

        if new_skills:
            # Очищаем лог после извлечения
            self._actions_log = []
            self._save()
            self._save_actions_log()
            log.info(f"SkillLibrary: extracted {len(new_skills)} new skills.")

        return new_skills

    def _generalize_actions(
        self,
        action_type: str,
        actions: list[dict],
        episodic: "EpisodicMemory",
    ) -> dict | None:
        """
        Обобщить последовательность действий в навык через LLM.
        
        Returns:
            Skill dict или None если не удалось обобщить
        """
        # Построить описание действий
        actions_desc = []
        for i, action in enumerate(actions[:5]):
            ctx = action.get("context", {})
            actions_desc.append(
                f"{i+1}. Контекст: {str(ctx)[:100]}, Результат: {action.get('outcome')}"
            )

        prompt = (
            f"Ты — Digital Being. Проанализируй серию успешных действий типа '{action_type}'.\n\n"
            f"Действия:\n" + "\n".join(actions_desc) + "\n\n"
            f"Обобщи эти действия в переиспользуемый навык. Опиши:\n"
            f"1. Название навыка (краткое)\n"
            f"2. Описание: что делает этот навык\n"
            f"3. Условия применения: когда его использовать\n"
            f"4. Ожидаемый результат\n\n"
            f"Отвечай ТОЛЬКО валидным JSON:\n"
            f'{{"name": "...", "description": "...", '
            f'"applicability": "...", "expected_outcome": "..."}}'
        )

        system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON без комментариев."

        raw = self._ollama.chat(prompt, system)
        if not raw:
            return None

        parsed = self._parse_json_simple(raw)
        if parsed is None:
            log.warning(f"SkillLibrary: could not parse skill extraction for '{action_type}'.")
            return None

        # Создать навык
        skill = {
            "id": f"skill_{int(time.time())}_{action_type}",
            "name": parsed.get("name", f"Unnamed {action_type}"),
            "action_type": action_type,
            "description": parsed.get("description", ""),
            "applicability": parsed.get("applicability", ""),
            "expected_outcome": parsed.get("expected_outcome", ""),
            "created_at": _now_iso(),
            "use_count": 0,
            "success_count": 0,
            "confidence": 0.5,  # Initial confidence
        }

        return skill

    # ────────────────────────────────────────────────────────────────
    # Skill Search & Usage
    # ────────────────────────────────────────────────────────────────

    def find_applicable_skills(
        self,
        context: dict,
        action_type: str | None = None,
        min_confidence: float = 0.3,
        top_k: int = 3,
    ) -> list[dict]:
        """
        Найти навыки применимые в данном контексте.
        
        Args:
            context: Текущий контекст (monologue, mode, etc.)
            action_type: Фильтр по типу действия (опционально)
            min_confidence: Минимальная уверенность навыка
            top_k: Количество навыков для возврата
        
        Returns:
            list[dict]: Список подходящих навыков, отсортированных по релевантности
        """
        if not self._skills:
            return []

        # Фильтрация
        candidates = []
        for skill in self._skills:
            # Фильтр по типу действия
            if action_type and skill.get("action_type") != action_type:
                continue
            
            # Фильтр по уверенности
            if skill.get("confidence", 0) < min_confidence:
                continue
            
            candidates.append(skill)

        # Сортировка по успешности и использованию
        def score(s: dict) -> float:
            confidence = s.get("confidence", 0.5)
            use_count = s.get("use_count", 0)
            success_rate = (
                s.get("success_count", 0) / use_count
                if use_count > 0 else 0.5
            )
            return confidence * 0.5 + success_rate * 0.3 + min(use_count / 10, 1.0) * 0.2

        candidates.sort(key=score, reverse=True)
        return candidates[:top_k]

    def mark_skill_used(
        self,
        skill_id: str,
        success: bool,
    ) -> None:
        """
        Отметить использование навыка и обновить статистику.
        
        Args:
            skill_id: ID навыка
            success: Был ли навык успешно применён
        """
        for skill in self._skills:
            if skill.get("id") == skill_id:
                skill["use_count"] = skill.get("use_count", 0) + 1
                if success:
                    skill["success_count"] = skill.get("success_count", 0) + 1
                
                # Обновить confidence на основе успешности
                use_count = skill["use_count"]
                success_count = skill["success_count"]
                skill["confidence"] = success_count / use_count if use_count > 0 else 0.5
                
                self._total_skill_uses += 1
                self._save()
                break

    def get_skill(self, skill_id: str) -> dict | None:
        """Получить навык по ID."""
        for skill in self._skills:
            if skill.get("id") == skill_id:
                return skill
        return None

    def get_all_skills(
        self,
        min_confidence: float = 0.0,
        action_type: str | None = None,
    ) -> list[dict]:
        """Получить все навыки с фильтрацией."""
        filtered = []
        for skill in self._skills:
            if skill.get("confidence", 0) < min_confidence:
                continue
            if action_type and skill.get("action_type") != action_type:
                continue
            filtered.append(skill)
        return filtered

    def get_stats(self) -> dict:
        """Статистика библиотеки."""
        return {
            "total_skills": len(self._skills),
            "total_extractions": self._total_extractions,
            "total_skill_uses": self._total_skill_uses,
            "pending_actions": len(self._actions_log),
        }

    # ────────────────────────────────────────────────────────────────
    # Parsing helpers
    # ────────────────────────────────────────────────────────────────

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


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
