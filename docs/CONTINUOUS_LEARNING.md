# Continuous Learning System

## Обзор

**Continuous Learning** — система обучения на опыте для Digital Being.

### Проблема

До этого система:
```
❌ Каждый раз декомпозировала цели с нуля (LLM)
❌ Не училась на успехах
❌ Не запоминала рабочие стратегии
```

### Решение

Теперь система **учится на опыте**:

```
1. Цель успешно выполнена
   → Извлекается паттерн
   → Сохраняется в базу паттернов

2. Похожая цель в будущем
   → Находится паттерн
   → Применяется без LLM!

3. Паттерн снова успешен
   → Confidence увеличивается
   → Чаще используется

→ Система становится умнее со временем! ✅
```

---

## Компоненты

### 1. **SuccessPattern**

Паттерн успешной декомпозиции:

```python
class SuccessPattern:
    id: str
    goal_type: str  # "learning", "analysis", "creation", etc.
    goal_keywords: List[str]  # Ключевые слова
    
    decomposition_strategy: str
    subgoals: List[Dict]  # Шаблоны подцелей
    
    success_count: int
    failure_count: int
    confidence: float  # 0.0 to 1.0
```

**Пример паттерна:**

```json
{
  "id": "abc-123",
  "goal_type": "learning",
  "goal_keywords": ["pandas", "изучить", "documentation"],
  "decomposition_strategy": "web_search → read_url → llm_query",
  "subgoals": [
    {
      "type": "action",
      "description_pattern": "Найти документацию",
      "action_type": "web_search",
      "estimated_ticks": 1
    },
    {
      "type": "action",
      "description_pattern": "Прочитать страницу",
      "action_type": "read_url",
      "estimated_ticks": 1
    }
  ],
  "success_count": 5,
  "failure_count": 0,
  "confidence": 0.95
}
```

---

### 2. **LearningEngine**

Движок обучения:

**Основные функции:**

```python
learning = LearningEngine(memory, storage_path)

# Обучение на успехе
learning.learn_from_goal(completed_goal, tree)

# Обучение на ошибке
learning.learn_from_failure(failed_goal, tree)

# Поиск паттернов
patterns = learning.find_patterns("Изучить pandas")

# Лучший паттерн
pattern = learning.get_best_pattern("Изучить pandas")
```

**Что делает:**

1. **Pattern Extraction:**
   - Анализирует завершённые цели
   - Извлекает ключевые слова
   - Классифицирует тип цели
   - Создаёт шаблоны подцелей

2. **Pattern Matching:**
   - Поиск по ключевым словам
   - Confidence-based ranking
   - Top-K выбор

3. **Reinforcement:**
   - Успех → confidence ↑
   - Неудача → confidence ↓

---

### 3. **PatternGuidedPlanner**

Планировщик с паттернами:

```python
planner = PatternGuidedPlanner(
    base_planner=goal_planner,
    learning_engine=learning,
    pattern_threshold=0.4
)

# Использование
subgoals = planner.decompose_goal(goal, tree)

# Автоматически:
# 1. Проверяет паттерны
# 2. Если нашёл → применяет
# 3. Иначе → использует LLM
```

**Логика работы:**

```
Вход: Цель = "Изучить pandas"

1. Поиск паттернов:
   find_patterns("Изучить pandas")
   → Нашёл: pattern #abc-123 (confidence=0.95)

2. Проверка порога:
   0.95 >= 0.4 → OK!

3. Применение паттерна:
   Создаются подцели по шаблону
   → web_search → read_url → llm_query

4. Результат:
   3 подцели созданы без LLM! ✅
```

---

## Интеграция

### С GoalExecutor

```python
# После завершения цели
if goal.is_completed():
    learning.learn_from_goal(goal, tree)
elif goal.is_failed():
    learning.learn_from_failure(goal, tree)
```

### С GoalPlanner

```python
# Замена обычного планнера на pattern-guided
planner = PatternGuidedPlanner(
    base_planner=original_planner,
    learning_engine=learning,
)

executor = GoalExecutor(
    tree=tree,
    planner=planner,  # Используем pattern-guided
    ...
)
```

---

## Пример работы

### Первый раз (без паттернов):

```
User: "Изучить pandas"

1. PatternGuidedPlanner:
   Паттернов нет → используем LLM
   LLM декомпозирует:
   → web_search
   → read_url
   → llm_query

2. GoalExecutor:
   Выполняет все шаги
   Цель завершена! ✅

3. LearningEngine:
   learn_from_goal()
   → Создан паттерн #abc-123
   → confidence = 0.5 (1 успех)
```

### Второй раз (с паттерном):

```
User: "Изучить NumPy"

1. PatternGuidedPlanner:
   Нашёл паттерн #abc-123 (похожие ключ. слова)
   confidence=0.5 >= 0.4 → применяем!
   → Без LLM создали подцели ✅

2. GoalExecutor:
   Выполняет
   Цель завершена! ✅

3. LearningEngine:
   Паттерн #abc-123:
   success_count = 2
   confidence = 0.75 ↑
```

### Пятый раз (устойчивый паттерн):

```
User: "Изучить TensorFlow"

1. PatternGuidedPlanner:
   Паттерн #abc-123
   confidence=0.95 → очень уверен!
   → Мгновенное создание подцелей ⚡

2-3. ...
```

---

## Преимущества

✅ **Ускорение** — паттерны быстрее LLM  
✅ **Экономия** — меньше LLM вызовов  
✅ **Надёжность** — проверенные стратегии  
✅ **Улучшение со временем** — реинфорсмент  
✅ **Fallback** — автоматический откат на LLM  

---

## Статистика

```python
# Learning Engine
stats = learning.get_statistics()
# {
#   "total_patterns": 12,
#   "total_successes": 45,
#   "total_failures": 3,
#   "overall_success_rate": 0.9375,
#   "avg_confidence": 0.78,
#   "by_type": {
#     "learning": {"count": 5, "avg_confidence": 0.85},
#     "analysis": {"count": 4, "avg_confidence": 0.72},
#     ...
#   }
# }

# Pattern-Guided Planner
stats = planner.get_statistics()
# {
#   "pattern_uses": 34,
#   "llm_uses": 8,
#   "pattern_rate": 0.81  # 81% используют паттерны!
# }
```

---

## Будущие улучшения

- [ ] **NLP-based matching** — семантический поиск паттернов
- [ ] **Pattern generalization** — обобщение шаблонов
- [ ] **Hierarchical patterns** — паттерны разных уровней
- [ ] **Transfer learning** — перенос паттернов между типами
- [ ] **Active learning** — запрос обратной связи