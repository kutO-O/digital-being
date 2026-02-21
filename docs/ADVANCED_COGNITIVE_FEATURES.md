# Advanced Cognitive Features (Layers 4-8)

## Обзор

Это руководство описывает **продвинутые когнитивные возможности** Digital Being.

---

## 💤 Layer 4: Memory Consolidation

### Что это?

**Sleep Cycle** для обработки опыта:
- Episode replay (повтор важных событий)
- Pattern extraction (извлечение паттернов)
- Memory pruning (удаление дублей)
- Belief consolidation (укрепление убеждений)

### Использование:

```python
from core.memory_consolidation import MemoryConsolidation

consolidator = MemoryConsolidation(
    memory=episodic_memory,
    ollama=ollama_client,
    beliefs=belief_system,
    consolidation_interval=24 * 3600,  # 24 часа
)

# В главном цикле
if consolidator.should_consolidate():
    result = await consolidator.consolidate()
    # result = {
    #   "episodes_processed": 100,
    #   "episodes_pruned": 15,
    #   "patterns_formed": 3
    # }
```

### Что происходит:

```
1. Episode Replay:
   - Берёт 100 последних эпизодов
   - Выбирает 20 самых важных (по emotional salience)
   - Анализирует через LLM
   - Извлекает паттерны

2. Memory Pruning:
   - Находит повторяющиеся эпизоды
   - Удаляет дубликаты
   - Экономит память

3. Belief Consolidation:
   - Усиливает подтверждённые убеждения
   - Ослабляет противоречивые
```

---

## 🧠 Layer 5: Theory of Mind

### Что это?

**Модель пользователя** с отслеживанием:
- Знаний (по темам)
- Предпочтений
- Текущего контекста
- Целей

### Использование:

```python
from core.theory_of_mind import UserModel

user_model = UserModel(storage_path=Path("data/user_model.json"))

# Обновление знаний
user_model.update_knowledge("pandas", "intermediate")
user_model.update_knowledge("numpy", "beginner")

# Контекст
user_model.update_context("working_on", "data analysis project")
user_model.update_context("mood", "focused")

# Предпочтения
user_model.set_preference("explanation_style", "step-by-step")
user_model.set_preference("code_examples", True)

# Цели
user_model.add_goal("learn machine learning")

# Использование в планировании
level = user_model.get_knowledge_level("pandas")
if level == "beginner":
    # Добавить объяснение основ
    pass
```

### Интеграция с GoalPlanner:

```python
# В decompose_goal()
user_knowledge = user_model.get_knowledge_level(topic)

prompt = f"""
User knowledge level: {user_knowledge}
Preferred style: {user_model.get_preference('explanation_style')}

Разбей цель с учётом уровня пользователя...
"""
```

---

## 🎭 Layer 6: Emotional Intelligence 2.0

### Что это?

**Адаптация под эмоции:**
- Sentiment analysis (анализ настроения)
- Tone adaptation (адаптация тона)
- Long-term emotional memory

### Использование:

```python
# В UserModel уже есть mood tracking
user_model.update_context("mood", "frustrated")

# В генерации ответов
mood = user_model.get_context().get("mood", "neutral")

if mood == "frustrated":
    tone = "supportive, patient"
    detail_level = "step-by-step"
elif mood == "excited":
    tone = "enthusiastic, encouraging"
    detail_level = "overview with deep-dive options"
else:
    tone = "professional, clear"
    detail_level = "balanced"

system_prompt = f"Отвечай в {tone} тоне. Уровень детализации: {detail_level}."
```

### Автоматическое определение:

```python
# Простой sentiment analysis (TODO: улучшить)
def detect_sentiment(user_message: str) -> str:
    frustrated_words = ["не работает", "ошибка", "помоги", "не понимаю"]
    excited_words = ["отлично", "круто", "получилось", "спасибо"]
    
    msg_lower = user_message.lower()
    
    if any(w in msg_lower for w in frustrated_words):
        return "frustrated"
    elif any(w in msg_lower for w in excited_words):
        return "excited"
    else:
        return "neutral"
```

---

## 🚀 Layer 7: Proactive Behavior

### Что это?

**Проактивные действия:**
- Temporal triggers (по времени)
- Pattern-based triggers (по паттернам)
- Opportunity triggers (новая информация)
- Prevention triggers (предупреждение проблем)

### Использование:

```python
from core.proactive_behavior import ProactiveBehaviorEngine, ProactiveTrigger

proactive = ProactiveBehaviorEngine(
    user_model=user_model,
    memory=episodic_memory,
)

# Проверка триггеров
actions = proactive.check_triggers()
# actions = ["suggest_automation", "suggest_related_info"]

for action in actions:
    if action == "suggest_automation":
        proactive.suggest(
            "automation",
            "Заметил, что ты часто делаешь это. Автоматизировать?"
        )
    elif action == "suggest_related_info":
        proactive.suggest(
            "info",
            "Нашёл статью по теме, над которой ты работаешь"
        )
```

### Добавление своих триггеров:

```python
# Кастомный триггер
custom_trigger = ProactiveTrigger(
    name="morning_summary",
    condition=lambda ctx: ctx.get("time_of_day") == "morning",
    action="provide_morning_summary",
    cooldown=24 * 3600,
)

proactive._triggers.append(custom_trigger)
```

---

## 🔬 Layer 8: Meta-Learning

### Что это?

**Самооптимизация:**
- A/B testing промптов
- Strategy optimization
- Self-reflection
- Hyperparameter tuning

### Использование:

```python
from core.meta_learning import MetaOptimizer

meta = MetaOptimizer(storage_path=Path("data/meta_learning.json"))

# Регистрация A/B теста
meta.register_ab_test(
    "system_prompt",
    variants=[
        {"prompt": "Ты — Digital Being. Помогай пользователю."},
        {"prompt": "Ты — автономный агент. Достигай целей."},
        {"prompt": "Ты — ассистент с расширенной памятью."},
    ]
)

# Получение варианта
variant = meta.get_variant("system_prompt")
system_prompt = variant["config"]["prompt"]

# Использование
response = ollama.chat(user_query, system_prompt)

# Запись результата
success = validate_response(response)
meta.record_result(
    "system_prompt",
    variant["index"],
    success,
    metric_value=calculate_quality(response)
)

# Получение лучшего
best_config = meta.get_best_config("system_prompt")
```

### Self-Reflection:

```python
# При неудаче
if goal.is_failed():
    hypothesis = meta.self_reflect(
        f"Goal failed: {goal.description}, reason: {goal.failure_reason}"
    )
    # hypothesis = "Try breaking down the task into smaller steps"
    
    # Применить гипотезу в следующий раз
```

### Метрики:

```python
# Запись метрик
meta.record_metric("goal_completion_time", 45.2)
meta.record_metric("llm_calls_per_goal", 3)

# Статистика
stats = meta.get_metric_stats("goal_completion_time")
# {
#   "count": 50,
#   "mean": 42.5,
#   "recent_avg": 38.2  # Улучшение!
# }
```

---

## 🎯 Полная Интеграция

### В FaultTolerantHeavyTick:

```python
class EnhancedHeavyTick:
    def __init__(self, ...):
        # Layers 1-3
        self.goal_behavior = GoalOrientedBehavior(...)
        self.tool_registry = ToolRegistry()
        self.learning = LearningEngine(...)
        
        # Layers 4-8
        self.consolidator = MemoryConsolidation(...)
        self.user_model = UserModel(...)
        self.proactive = ProactiveBehaviorEngine(...)
        self.meta = MetaOptimizer(...)
    
    async def tick(self):
        # 1. Check proactive triggers
        proactive_actions = self.proactive.check_triggers()
        for action in proactive_actions:
            await self.execute_proactive(action)
        
        # 2. Goal-oriented behavior
        if self.goal_behavior.should_use_goal_mode():
            result = await self.goal_behavior.execute_tick(tick_number)
            
            # Learn from result
            if result.get("status") == "completed":
                self.learning.learn_from_goal(goal, tree)
        
        # 3. Memory consolidation (periodic)
        if self.consolidator.should_consolidate():
            await self.consolidator.consolidate()
        
        # 4. Meta-learning (record metrics)
        self.meta.record_metric("tick_duration", duration)
        
        # 5. Update user model
        self.user_model.record_interaction(topic=current_topic)
        self.user_model.save()
```

---

## 📊 Пример Полного Цикла

```
User: "Изучить pandas и проанализировать sales.csv"

1. Theory of Mind:
   user_model.get_knowledge_level("pandas") = "beginner"
   user_model.update_context("working_on", "data analysis")

2. Goal Planning (с учётом уровня):
   Pattern найден → применён
   Создано 5 подцелей

3. Tool Registry:
   web_search → read_url → file_read → python_execute

4. Continuous Learning:
   Паттерн усилен (confidence 0.8 → 0.85)

5. Proactive Behavior:
   Trigger: "suggest_related_info"
   → "Нашёл продвинутый tutorial по pandas, хочешь?"

6. Meta-Learning:
   Метрика: goal_completion_time = 12 минут
   A/B test: system_prompt variant #2 сработал лучше

7. Memory Consolidation (ночью):
   100 эпизодов обработано
   Паттерн "data analysis workflow" извлечён
   15 дублей удалено

8. User Model Update:
   knowledge["pandas"] = "beginner" → "intermediate"
   goals.add("learn advanced pandas")

→ Система стала умнее! ✨
```

---

## 🎖️ Преимущества

✅ **Персонализация** — учитывает уровень и предпочтения  
✅ **Проактивность** — предлагает помощь до запроса  
✅ **Самообучение** — улучшается со временем  
✅ **Оптимизация** — A/B тестирование стратегий  
✅ **Долгосрочная память** — consolidation и pruning  
✅ **Эмоциональный интеллект** — адаптация под настроение  

---

## 🚀 Будущие Улучшения

### Memory Consolidation:
- [ ] Более сложный pattern extraction (NLP)
- [ ] Hierarchical memory (short-term → long-term)
- [ ] Dream-like replay для креативности

### Theory of Mind:
- [ ] Multi-user support
- [ ] Deeper intent inference
- [ ] Social context modeling

### Proactive Behavior:
- [ ] ML-based prediction
- [ ] Context-aware timing
- [ ] Multi-modal triggers

### Meta-Learning:
- [ ] Automated hyperparameter search
- [ ] Transfer learning между задачами
- [ ] Causal analysis failures