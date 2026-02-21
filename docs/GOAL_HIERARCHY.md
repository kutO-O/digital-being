# Goal Hierarchy & Planning System

## Обзор

**Goal Hierarchy** — это система многоуровневого планирования для Digital Being.

### Проблема

До этого система могла выполнять **только одношаговые действия**:
```
Goal: "Изучить pandas и сделать анализ data.csv"
→ ONE tick: observe / analyze / write
→ Не хватает для сложных задач
```

### Решение

Теперь система разбивает сложные цели на шаги:
```
Root Goal: "Изучить pandas и сделать анализ data.csv"
├─ Subgoal 1: "Найти документацию pandas" (1 tick)
│  └─ Action: llm_query("где найти pandas docs")
├─ Subgoal 2: "Изучить основы" (2 ticks)
│  ├─ Action: read_file("pandas_intro.md")
│  └─ Action: write_file("notes.md", summary)
├─ Subgoal 3: "Понять data.csv" (1 tick)
│  └─ Action: shell("head data.csv")
└─ Subgoal 4: "Написать код анализа" (3 ticks)
   ├─ Action: llm_query("напиши код")
   ├─ Action: write_file("analyze.py", code)
   └─ Action: shell("python analyze.py")

→ Общее время: 7 ticks вместо 1
→ Каждый шаг выполняется самостоятельно
→ Автоматическое восстановление при ошибках
```

---

## Компоненты

### 1. **GoalNode**

Узел в дереве целей.

**Типы:**
- `ROOT` — корневая цель пользователя
- `SUBGOAL` — промежуточная подцель
- `ACTION` — конкретное действие

**Статусы:**
- `PENDING` — ещё не начато
- `ACTIVE` — выполняется
- `COMPLETED` — завершено
- `FAILED` — провалено

**Метаданные:**
- `estimated_ticks` — ожидаемое время
- `actual_ticks` — фактическое время
- `success_criteria` — критерии успеха

---

### 2. **GoalTree**

Иерархическое дерево целей.

**Функции:**
- `add_node()` / `remove_node()`
- `add_child()` / `get_children()`
- `get_active_goals()` — все активные
- `get_pending_actions()` — готовые к выполнению
- `get_subtree()` — всё поддерево
- `save()` / `load()` — персистентность

---

### 3. **GoalPlanner**

LLM-планировщик.

**Что делает:**
- Декомпозиция целей через LLM
- Генерация success_criteria
- Оценка сложности
- Контекстное планирование

**Пример промпта:**
```
Цель: "Изучить pandas"
Разбей на 3-7 шагов с:
- Конкретным описанием
- Критериями успеха
- Оценкой времени
```

---

### 4. **GoalExecutor**

Исполнитель целей.

**Возможности:**
- Выполнение action nodes
- Валидация success_criteria
- Progress tracking
- **Adaptive replanning** при ошибках

**Типы action:**
- `shell` — команды shell
- `llm_query` — запрос к LLM
- `read_file` — чтение файла
- `write_file` — запись файла

---

## Интеграция

### Автоматическое переключение режимов

**Reactive mode** (оригинальное поведение):
- Нет активных целей
- Реагирует на изменения среды
- Одношаговые действия

**Goal-oriented mode** (новое):
- Есть активные или pending цели
- Последовательное выполнение плана
- Многошаговое достижение

---

## Пример использования

```python
from core.goal_integration import GoalOrientedBehavior

# Инициализация
goal_behavior = GoalOrientedBehavior(
    ollama=ollama_client,
    world=world_model,
    memory=episodic_memory,
    storage_dir=Path("data/goals"),
    shell_executor=shell_executor,
)

# Добавить цель
goal_id = goal_behavior.add_user_goal(
    "Изучить pandas и проанализировать data.csv"
)

# В HeavyTick
if goal_behavior.should_use_goal_mode():
    result = await goal_behavior.execute_tick(tick_number)
else:
    # Обычное поведение
    pass

# Прогресс
print(goal_behavior.get_progress_summary())
# → "• Изучить pandas...: 42% (3/7)"

# Статистика
stats = goal_behavior.get_statistics()
# → {mode: "goal_oriented", tree: {...}, execution: {...}}
```

---

## Преимущества

✅ **Многошаговое планирование** — сложные цели делятся на шаги  
✅ **Adaptive replanning** — автоматическое восстановление при ошибках  
✅ **Progress tracking** — отслеживание прогресса  
✅ **Context-aware** — учитывает world model и memory  
✅ **Автоматическое переключение** reactive ↔ goal-oriented  
✅ **Backward compatible** — работает с существующим кодом  

---

## Будущие улучшения

- [ ] **Parallel goal execution** — несколько целей одновременно
- [ ] **Goal priorities** — приоритеты между целями
- [ ] **Learning from success** — успешные планы запоминаются
- [ ] **Tool discovery** — автоматическое обнаружение доступных инструментов
- [ ] **Conditional goals** — цели с условиями
- [ ] **Resource constraints** — учёт ресурсов