# Skill Library (Stage 26)

Автоматическое извлечение, хранение и применение навыков агента.

## 🎯 Обзор

**SkillLibrary** — система, которая:

1. **Записывает действия** агента через `record_action()`
2. **Извлекает навыки** из повторяющихся паттернов через LLM
3. **Ищет применимые навыки** по контексту
4. **Адаптирует confidence** на основе успеха/провала

## 📚 Структура навыка

```python
{
    "id": "skill_1740182400_write",
    "name": "Навык написания файлов",
    "action_type": "write",                  # Тип действия
    "description": "Создание файлов с кодом",
    "applicability": "Когда нужно создать файл",  # Когда применять
    "expected_outcome": "Файл создан успешно",
    "implementation_hints": "Использовать Path().write_text()",
    "use_count": 12,                        # Сколько раз использован
    "success_count": 10,                    # Сколько успешно
    "confidence": 0.83,                     # 10/12 = 0.83
    "created_at": "2026-02-22T02:00:00"
}
```

## 🚀 Использование

### 1. Конфигурация

```yaml
# config.yaml
skills:
  enabled: true
  extract_every_n_ticks: 20  # Извлекать навыки каждые 20 тиков
```

### 2. Запись действий

После выполнения действия:

```python
if skill_library:
    skill_library.record_action(
        action_type="write",
        context="Создание Python скрипта hello.py",
        implementation="Path('hello.py').write_text('print(\"Hello\")')",
        outcome="success",
        result="Файл создан успешно"
    )
```

### 3. Автоматическое извлечение

Каждые N тиков HeavyTick автоматически вызывает:

```python
result = skill_library.extract_skills()
# {
#     "extracted": True,
#     "skills": [...],
#     "prompt_tokens": 450,
#     "completion_tokens": 280
# }
```

### 4. Поиск применимых навыков

```python
applicable = skill_library.find_applicable_skills(
    context="Нужно создать новый файл config.yaml",
    min_confidence=0.5
)
# [
#     {
#         "id": "skill_1740182400_write",
#         "name": "Навык написания файлов",
#         "confidence": 0.83,
#         ...
#     }
# ]
```

### 5. Использование навыка

```python
skill_library.use_skill(skill_id="skill_1740182400_write", success=True)
# Confidence: 0.83 -> 0.84 (при успехе)
```

## 🔌 API

### Endpoint: `GET /skills`

```bash
curl http://127.0.0.1:8765/skills
```

**Response**:
```json
{
  "skills": [
    {
      "id": "skill_1740182400_write",
      "name": "Навык написания файлов",
      "action_type": "write",
      "description": "Создание файлов с кодом",
      "applicability": "Когда нужно создать новый файл",
      "expected_outcome": "Файл создан успешно",
      "use_count": 12,
      "success_count": 10,
      "confidence": 0.83,
      "created_at": "2026-02-22T02:00:00"
    }
  ],
  "stats": {
    "total_skills": 5,
    "total_extractions": 3,
    "total_skill_uses": 47
  }
}
```

## 🧠 LLM Prompt

Для извлечения навыков используется промпт:

```python
ANALYZE_ACTIONS_PROMPT = """
You are analyzing repeated patterns in an AI agent's actions to extract reusable skills.

RECENT ACTIONS:
{actions}

Identify 1-3 distinct skills that the agent has demonstrated through these actions.

For each skill, provide:
- **name**: Short descriptive name
- **action_type**: Type of action (e.g., 'write', 'read', 'analyze')
- **description**: What the skill accomplishes
- **applicability**: When this skill should be used
- **expected_outcome**: What result to expect
- **implementation_hints**: How to execute this skill

Return ONLY valid JSON array:
[
  {
    "name": "...",
    "action_type": "...",
    "description": "...",
    "applicability": "...",
    "expected_outcome": "...",
    "implementation_hints": "..."
  }
]
"""
```

## 📈 Adaptive Learning

Система автоматически обновляет `confidence`:

```python
def use_skill(self, skill_id: str, success: bool) -> dict:
    skill["use_count"] += 1
    if success:
        skill["success_count"] += 1
    
    # Recalculate confidence
    skill["confidence"] = skill["success_count"] / skill["use_count"]
```

**Пример**:
- Начальный confidence: `0.8` (8/10)
- После успеха: `0.82` (9/11)
- После провала: `0.75` (9/12)

## 💾 Хранение

Навыки хранятся в:

```
memory/
  skills.json          # Извлечённые навыки
  skill_actions.json   # Записанные действия (max 50)
```

## 🕰️ Timeline

```
HeavyTick #1-19:  Запись действий (record_action)
HeavyTick #20:    Извлечение навыков (extract_skills)
HeavyTick #21-39: Запись действий
HeavyTick #40:    Извлечение новых навыков
...
```

## ✅ Integration Checklist

- [x] `SkillLibrary` class implementation
- [x] `main.py` initialization
- [x] API endpoint `/skills`
- [x] Pass to `FaultTolerantHeavyTick`
- [ ] Manual changes to `fault_tolerant_heavy_tick.py` (see PR comments)
- [ ] Add `record_action()` calls in action handlers

## 💡 Future Enhancements

1. **Skill Transfer**: Сохранять навыки между перезапусками
2. **Skill Composition**: Комбинировать простые навыки в сложные
3. **Skill Versioning**: Хранить версии навыков
4. **Skill Recommendations**: Предлагать навыки перед действием
5. **Skill Export/Import**: Совместное использование навыков

---

✅ **Stage 26 Complete** | 👨‍💻 See [PR #7](https://github.com/kutO-O/digital-being/pull/7)
