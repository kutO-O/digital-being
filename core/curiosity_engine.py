"""
Digital Being — CuriosityEngine
Stage 17: внутренний исследовательский импульс.

Система активно генерирует вопросы о том, что не понимает,
ставит их в очередь и постепенно ищет ответы в последующих тиках.

Файл состояния: memory/curiosity.json

Примечание: параметр memory_dir принимается в конструкторе и используется
для построения пути к файлу состояния curiosity.json.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.episodic import EpisodicMemory
    from core.memory.vector_memory import VectorMemory
    from core.ollama_client import OllamaClient
    from core.world_model import WorldModel

log = logging.getLogger("digital_being.curiosity_engine")

_MAX_QUESTIONS   = 50   # максимум записей в файле (answered + open)
_MAX_OPEN        = 20   # максимум вопросов в очереди
_SIMILARITY_WORDS = 3   # минимум общих слов (>4 символов) для признания дублем


class CuriosityEngine:
    """
    Генерирует вопросы, ставит их в очередь и ищет ответы через LLM + VectorMemory.

    Жизненный цикл:
        ce = CuriosityEngine(memory_dir=ROOT_DIR / "memory")
        ce.load()
        # в HeavyTick:
        if ce.should_ask(tick_count):
            for q in ce.generate_questions(episodes, world, ollama):
                ce.add_question(q, context="auto", priority=0.6)
        if ce.should_answer(tick_count):
            q = ce.get_next_question()
            if q:
                answer = ce.seek_answer(q, episodic, vector_memory, ollama)
                ce.answer_question(q["id"], answer)
    """

    def __init__(self, memory_dir: Path) -> None:
        # memory_dir используется для построения пути к файлу состояния
        self._path        = memory_dir / "curiosity.json"
        self._questions:  list[dict] = []
        self._total_asked    = 0
        self._total_answered = 0

    # ──────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────
    def load(self) -> None:
        """Загрузить состояние из файла. Создаёт файл при первом запуске."""
        if not self._path.exists():
            log.info("CuriosityEngine: state file not found, starting fresh.")
            self._save()
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._questions      = data.get("questions", [])
            self._total_asked    = data.get("total_asked", 0)
            self._total_answered = data.get("total_answered", 0)
            log.info(
                f"CuriosityEngine loaded: "
                f"open={self._count_open()} answered={self._total_answered} "
                f"total_asked={self._total_asked}"
            )
        except Exception as e:
            log.error(f"CuriosityEngine.load() failed: {e}. Starting fresh.")
            self._questions      = []
            self._total_asked    = 0
            self._total_answered = 0

    def _save(self) -> None:
        """Атомарная запись состояния на диск."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        data = {
            "questions":      self._questions,
            "total_asked":    self._total_asked,
            "total_answered": self._total_answered,
        }
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except Exception as e:
            log.error(f"CuriosityEngine._save() failed: {e}")

    # ──────────────────────────────────────────────────────────────
    # Core API
    # ──────────────────────────────────────────────────────────────
    def add_question(
        self,
        question: str,
        context:  str,
        priority: float = 0.5,
    ) -> bool:
        """
        Добавить вопрос в очередь.
        Возвращает True если добавлен, False если пропущен как дубль
        или очередь переполнена.
        """
        question = question.strip()
        if not question:
            return False

        # Проверка дублей по similarity
        if self._is_duplicate(question):
            log.debug(f"CuriosityEngine: duplicate question skipped: '{question[:80]}'")
            return False

        # Очистка: удалить старые answered если очередь достигла _MAX_OPEN
        open_count = self._count_open()
        if open_count >= _MAX_OPEN:
            self._evict_answered()
            if self._count_open() >= _MAX_OPEN:
                log.warning("CuriosityEngine: open questions limit reached, skipping.")
                return False

        entry: dict = {
            "id":          str(uuid.uuid4()),
            "question":    question,
            "context":     context,
            "priority":    float(priority),
            "status":      "open",
            "created_at":  _now_iso(),
            "answered_at": None,
            "answer":      None,
        }
        self._questions.append(entry)
        self._total_asked += 1
        self._trim()
        self._save()
        log.info(f"CuriosityEngine: new question added: '{question[:80]}'")
        return True

    def get_next_question(self) -> dict | None:
        """
        Вернуть самый приоритетный открытый вопрос.
        Сортировка: priority DESC, затем created_at ASC.
        """
        open_qs = [q for q in self._questions if q["status"] == "open"]
        if not open_qs:
            return None
        return sorted(
            open_qs,
            key=lambda q: (-q["priority"], q["created_at"]),
        )[0]

    def answer_question(self, question_id: str, answer: str) -> bool:
        """Пометить вопрос как answered, записать ответ и answered_at."""
        for q in self._questions:
            if q["id"] == question_id:
                q["status"]      = "answered"
                q["answer"]      = answer
                q["answered_at"] = _now_iso()
                self._total_answered += 1
                self._save()
                log.info(
                    f"CuriosityEngine: answered question id={question_id[:8]} "
                    f"'{q['question'][:60]}'"
                )
                return True
        log.warning(f"CuriosityEngine.answer_question(): id={question_id} not found.")
        return False

    def get_open_questions(self, limit: int = 5) -> list[dict]:
        """Список открытых вопросов, отсортированных по приоритету."""
        open_qs = [q for q in self._questions if q["status"] == "open"]
        sorted_qs = sorted(open_qs, key=lambda q: (-q["priority"], q["created_at"]))
        return sorted_qs[:limit]

    def get_stats(self) -> dict:
        return {
            "open":         self._count_open(),
            "answered":     self._total_answered,
            "total_asked":  self._total_asked,
        }

    # ──────────────────────────────────────────────────────────────
    # Tick control
    # ──────────────────────────────────────────────────────────────
    def should_ask(self, tick_count: int) -> bool:
        """True если tick_count % 7 == 0 и открытых вопросов < 10."""
        return tick_count % 7 == 0 and self._count_open() < 10

    def should_answer(self, tick_count: int) -> bool:
        """True если tick_count % 5 == 0 и есть открытые вопросы."""
        return tick_count % 5 == 0 and self._count_open() > 0

    # ──────────────────────────────────────────────────────────────
    # LLM integration
    # ──────────────────────────────────────────────────────────────
    def generate_questions(
        self,
        episodes:    list[dict],
        world_model: "WorldModel",
        ollama:      "OllamaClient",
    ) -> list[str]:
        """
        Синхронный. На основе последних эпизодов и состояния мира
        генерирует 1-3 новых вопроса через LLM.
        При ошибке LLM возвращает [].
        """
        try:
            events_summary = self._format_episodes(episodes)
            open_questions = [
                q["question"] for q in self.get_open_questions(5)
            ]
            open_q_str = "\n".join(f"- {q}" for q in open_questions) or "нет"

            prompt = (
                f"Ты — Digital Being. Проанализируй недавние события и сформулируй\n"
                f"1-3 конкретных вопроса которые тебя искренне интересуют.\n\n"
                f"Недавние события:\n{events_summary}\n\n"
                f"Уже открытые вопросы (не дублируй):\n{open_q_str}\n\n"
                f'Отвечай JSON: {{"questions": ["вопрос1", "вопрос2"]}}'
            )
            system = "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON без комментариев."

            raw = ollama.chat(prompt, system)
            if not raw:
                return []

            parsed = self._parse_json_questions(raw)
            return [q.strip() for q in parsed if q.strip()][:3]

        except Exception as e:
            log.error(f"CuriosityEngine.generate_questions() failed: {e}")
            return []

    def seek_answer(
        self,
        question:      dict,
        episodic:      "EpisodicMemory",
        vector_memory: "VectorMemory",
        ollama:        "OllamaClient",
    ) -> str:
        """
        Синхронный. Пытается найти ответ на вопрос:
        1. Семантический поиск в VectorMemory
        2. Формирует промпт с контекстами
        3. Вызывает LLM для генерации ответа
        При ошибке возвращает 'Ответ не найден'.
        """
        try:
            q_text = question["question"]

            # Семантический поиск
            contexts: list[str] = []
            try:
                embedding = ollama.embed(q_text[:1000])
                if embedding:
                    results = vector_memory.search(embedding, top_k=3)
                    for r in results:
                        contexts.append(
                            f"[{r.get('event_type','?')} sim={r.get('score',0):.2f}] "
                            f"{r.get('text','')[:200]}"
                        )
            except Exception as e:
                log.debug(f"CuriosityEngine.seek_answer() vector search failed: {e}")

            ctx_str = "\n".join(contexts) if contexts else "контекст не найден"

            prompt = (
                f"Вопрос: {q_text}\n\n"
                f"Контекст из памяти:\n{ctx_str}\n\n"
                f"Дай краткий ответ на вопрос основываясь на контексте. "
                f"Если ответа нет в контексте — честно скажи что не знаешь."
            )
            system = "Ты — Digital Being. Отвечай кратко и по делу."

            answer = ollama.chat(prompt, system)
            if not answer or not answer.strip():
                return "Ответ не найден"
            return answer.strip()

        except Exception as e:
            log.error(f"CuriosityEngine.seek_answer() failed: {e}")
            return "Ответ не найден"

    # ──────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────
    def _count_open(self) -> int:
        return sum(1 for q in self._questions if q["status"] == "open")

    def _is_duplicate(self, new_question: str) -> bool:
        """
        Проверить есть ли 3+ общих слова длиннее 4 символов
        с любым открытым вопросом.
        """
        new_words = _long_words(new_question)
        for q in self._questions:
            if q["status"] != "open":
                continue
            existing_words = _long_words(q["question"])
            common = new_words & existing_words
            if len(common) >= _SIMILARITY_WORDS:
                return True
        return False

    def _evict_answered(self) -> None:
        """Удалить самые старые answered-вопросы чтобы освободить место."""
        answered = [q for q in self._questions if q["status"] == "answered"]
        answered_sorted = sorted(answered, key=lambda q: q.get("answered_at", ""))
        to_remove = answered_sorted[:max(1, len(answered_sorted) // 2)]
        remove_ids = {q["id"] for q in to_remove}
        self._questions = [q for q in self._questions if q["id"] not in remove_ids]

    def _trim(self) -> None:
        """
        Держать не более _MAX_QUESTIONS записей.
        При превышении удалять старые answered-записи первыми.
        """
        if len(self._questions) <= _MAX_QUESTIONS:
            return
        # Сортируем: answered-старые сначала
        answered = sorted(
            [q for q in self._questions if q["status"] == "answered"],
            key=lambda q: q.get("answered_at", ""),
        )
        open_qs = [q for q in self._questions if q["status"] == "open"]
        # Обрезаем answered с начала
        excess = len(self._questions) - _MAX_QUESTIONS
        answered = answered[excess:]
        self._questions = answered + open_qs

    @staticmethod
    def _format_episodes(episodes: list[dict]) -> str:
        if not episodes:
            return "нет"
        lines = []
        for e in episodes[:10]:
            lines.append(
                f"- [{e.get('event_type','?')}] {e.get('description','')[:120]}"
            )
        return "\n".join(lines)

    @staticmethod
    def _parse_json_questions(raw: str) -> list[str]:
        """Попытаться распарсить JSON с вопросами из ответа LLM."""
        # Прямой парсинг
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data.get("questions", [])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        # Поиск JSON-блока внутри текста
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw[start:end + 1])
                if isinstance(data, dict):
                    return data.get("questions", [])
            except json.JSONDecodeError:
                pass
        log.debug(f"CuriosityEngine: could not parse questions JSON from: {raw[:200]}")
        return []


# ──────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _long_words(text: str) -> set[str]:
    """Набор слов длиннее 4 символов в нижнем регистре."""
    return {w.lower() for w in text.split() if len(w) > 4}
