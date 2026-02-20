# Этапы 19-20: BeliefSystem и ContradictionResolver

## Обзор

Этапы 19-20 добавляют в Digital Being способность формировать убеждения о мире на основе наблюдений и разрешать противоречия между убеждениями и принципами через LLM-диалог.

## Этап 19: BeliefSystem

### Что сделано

#### 1. `core/belief_system.py`

**Основные компоненты:**

```python
class BeliefSystem:
    def form_beliefs(episodes, world, ollama) -> list[dict]
    def add_belief(statement, category, confidence) -> bool
    def validate_belief(belief_id, episodes, ollama) -> bool
    def get_beliefs(min_confidence, status) -> list[dict]
    def should_form(tick_count) -> bool  # каждые 20 тиков если < 30 активных
    def should_validate(tick_count) -> bool  # каждые 10 тиков
```

**Формирование убеждений:**
- LLM анализирует последние 15 эпизодов и world summary
- Генерирует 1-3 новых убеждения в формате JSON
- Категории: `pattern`, `cause_effect`, `world_state`
- Начальная confidence: 0.0-1.0

**Валидация убеждений:**
- LLM проверяет убеждение против последних 10 эпизодов
- Вердикт: `strengthen` / `weaken` / `neutral`
- Confidence delta: -0.3 до +0.3
- Автоматические статусы:
  - confidence ≥ 0.85 → `strong`
  - confidence < 0.2 → `rejected`

**Пример belief:**
```json
{
  "id": "uuid",
  "statement": "Частые изменения файлов указывают на активную разработку",
  "category": "pattern",
  "confidence": 0.7,
  "formed_at": "2026-02-21T01:00:00",
  "validation_count": 3,
  "status": "active"
}
```

#### 2. Интеграция в HeavyTick

**Step 7: Belief System**

```python
if self._beliefs.should_form(n):
    new_beliefs = self._beliefs.form_beliefs(recent_episodes, world, ollama)
    for b in new_beliefs:
        self._beliefs.add_belief(b["statement"], b["category"], b["confidence"])

if self._beliefs.should_validate(n):
    belief = random.choice(active_beliefs)
    self._beliefs.validate_belief(belief["id"], recent_episodes, ollama)
```

**Beliefs в монологе:**
```python
beliefs_ctx = self._beliefs.to_prompt_context(3)  # топ-3 убеждения
prompt += f"\n{beliefs_ctx}"
```

#### 3. IntrospectionAPI: `/beliefs`

```bash
curl http://localhost:8765/beliefs
```

**Ответ:**
```json
{
  "active": [
    {
      "id": "...",
      "statement": "...",
      "category": "pattern",
      "confidence": 0.65,
      "validation_count": 2,
      "status": "active"
    }
  ],
  "strong": [...],
  "stats": {
    "active": 12,
    "strong": 3,
    "rejected": 5,
    "total_beliefs_formed": 28,
    "total_beliefs_validated": 45,
    "total_beliefs_rejected": 5
  }
}
```

## Этап 20: ContradictionResolver

### Что сделано

#### 1. `core/contradiction_resolver.py`

**Основные компоненты:**

```python
class ContradictionResolver:
    def detect_contradictions(beliefs, principles, ollama) -> list[dict]
    def add_contradiction(type, item_a, item_b) -> bool
    def resolve_contradiction(contradiction_id, ollama) -> bool
    def should_detect(tick_count) -> bool  # каждые 30 тиков
    def should_resolve(tick_count) -> bool  # каждые 15 тиков если есть pending
```

**Обнаружение противоречий:**

1. Собирает все активные beliefs и principles
2. Если > 20 items, берёт топ-10 по confidence
3. Проверяет все пары через LLM:
   ```python
   prompt = "Противоречат ли эти два утверждения?\nA) ...\nB) ..."
   response = {"contradicts": true/false, "explanation": "..."}
   ```
4. Типы противоречий:
   - `belief_belief` — между двумя убеждениями
   - `principle_principle` — между принципами
   - `belief_principle` — убеждение vs принцип

**Разрешение через 3-step диалог:**

1. **Defense A:** LLM защищает позицию A, генерирует 2-3 аргумента
2. **Defense B:** LLM защищает позицию B, генерирует 2-3 аргумента
3. **Judge verdict:** LLM выбирает решение:
   - `choose_a` — A правильна, B отклонить
   - `choose_b` — B правильна, A отклонить
   - `synthesis` — создать новое утверждение, объединяющее обе стороны
   - `both_valid` — оба верны в разных контекстах

**Пример contradiction:**
```json
{
  "id": "uuid",
  "type": "belief_principle",
  "item_a": {
    "id": "belief-123",
    "text": "Быстрые изменения — признак прогресса",
    "type": "belief"
  },
  "item_b": {
    "id": "principle-456",
    "text": "Стабильность важнее скорости",
    "type": "principle"
  },
  "detected_at": "2026-02-21T01:15:00",
  "status": "resolved",
  "resolution": {
    "verdict": "synthesis",
    "reasoning": "Обе позиции имеют ценность в разных контекстах...",
    "synthesis_text": "Быстрые изменения полезны при условии сохранения стабильного ядра",
    "resolved_at": "2026-02-21T01:20:00"
  }
}
```

#### 2. Применение вердиктов в HeavyTick

**Step 8: Contradiction Resolver**

```python
# Detection
if self._contradictions.should_detect(n):
    contradictions = self._contradictions.detect_contradictions(beliefs, principles, ollama)
    for c in contradictions[:2]:  # max 2 per cycle
        self._contradictions.add_contradiction(c["type"], c["item_a"], c["item_b"])

# Resolution + verdict application
if self._contradictions.should_resolve(n):
    pending = self._contradictions.get_pending()
    if pending:
        c = pending[0]  # resolve oldest
        resolved = self._contradictions.resolve_contradiction(c["id"], ollama)
        if resolved:
            await self._apply_verdict(c["id"], n)
```

**Применение вердикта:**

```python
async def _apply_verdict(contradiction_id, tick):
    resolution = get_resolution(contradiction_id)
    verdict = resolution["verdict"]
    
    if verdict == "choose_a":
        # Снизить confidence item_b на -0.3
        modify_confidence(item_b, -0.3)
        
    elif verdict == "choose_b":
        # Снизить confidence item_a на -0.3
        modify_confidence(item_a, -0.3)
        
    elif verdict == "synthesis":
        # Создать новое убеждение/принцип
        create_synthesis(synthesis_text)
        # Снизить оба на -0.2
        modify_confidence(item_a, -0.2)
        modify_confidence(item_b, -0.2)
        
    elif verdict == "both_valid":
        # Без изменений
        pass
```

**Автоматическое отклонение:**
- Если confidence < 0.2 после применения вердикта → status = `rejected`

#### 3. IntrospectionAPI: `/contradictions`

```bash
curl http://localhost:8765/contradictions
```

**Ответ:**
```json
{
  "pending": [
    {
      "id": "...",
      "type": "belief_belief",
      "item_a": {...},
      "item_b": {...},
      "detected_at": "2026-02-21T01:10:00",
      "status": "pending"
    }
  ],
  "resolved": [
    {
      "id": "...",
      "type": "belief_principle",
      "item_a": {...},
      "item_b": {...},
      "resolution": {
        "verdict": "synthesis",
        "reasoning": "...",
        "synthesis_text": "...",
        "resolved_at": "2026-02-21T01:20:00"
      },
      "status": "resolved"
    }
  ],
  "stats": {
    "pending": 2,
    "resolved": 8,
    "deferred": 1,
    "total_detected": 15,
    "total_resolved": 8
  }
}
```

## Исправления

### Bug Fix: `should_*()` методы

**Проблема:** `should_form()`, `should_validate()`, `should_detect()`, `should_resolve()` могли срабатывать на tick 0

**Решение:**
```python
def should_form(self, tick_count: int) -> bool:
    if tick_count == 0:
        return False
    if tick_count % 20 != 0:
        return False
    active = len([b for b in self._state["beliefs"] if b["status"] in ("active", "strong")])
    return active < 30
```

Теперь все `should_*()` методы возвращают `False` на tick 0.

## Архитектура

### Жизненный цикл belief

```
formed (confidence=0.5)
    ↓
  [валидация каждые 10 тиков]
    ↓
active (0.2 ≤ conf < 0.85)
    ↓
[достигла conf ≥ 0.85]
    ↓
strong

или

[упала до conf < 0.2]
    ↓
rejected
```

### Жизненный цикл contradiction

```
detected (каждые 30 тиков)
    ↓
pending
    ↓
[resolution каждые 15 тиков]
    ↓
3-step dialogue:
  1. Defense A
  2. Defense B
  3. Judge verdict
    ↓
resolved + apply verdict
```

### Применение вердикта

```
verdict → modify confidence
    ↓
if conf < 0.2 → status = rejected
    ↓
if conf ≥ 0.85 → status = strong
```

## Файлы состояния

### `memory/beliefs.json`
```json
{
  "beliefs": [
    {
      "id": "uuid",
      "statement": "...",
      "category": "pattern|cause_effect|world_state",
      "confidence": 0.0-1.0,
      "formed_at": "2026-02-21T01:00:00",
      "last_updated": "2026-02-21T01:10:00",
      "validation_count": 3,
      "status": "active|strong|rejected"
    }
  ],
  "total_beliefs_formed": 28,
  "total_beliefs_validated": 45,
  "total_beliefs_rejected": 5
}
```

### `memory/contradictions.json`
```json
{
  "contradictions": [
    {
      "id": "uuid",
      "type": "belief_belief|principle_principle|belief_principle",
      "item_a": {"id": "...", "text": "...", "type": "belief|principle"},
      "item_b": {"id": "...", "text": "...", "type": "belief|principle"},
      "detected_at": "2026-02-21T01:10:00",
      "status": "pending|resolved|deferred",
      "resolution": {
        "verdict": "choose_a|choose_b|synthesis|both_valid",
        "reasoning": "...",
        "synthesis_text": "...",
        "resolved_at": "2026-02-21T01:20:00"
      }
    }
  ],
  "total_detected": 15,
  "total_resolved": 8
}
```

## Использование

### Запуск
```bash
python main.py
```

### Логи
```
[BeliefSystem] Belief added: [pattern] Частые изменения файлов...
[BeliefSystem] Belief validated: ... | 0.50 → 0.65 (strengthen)
[ContradictionResolver] Contradiction detected: [belief_principle] ...
[ContradictionResolver] Resolving contradiction: uuid
[ContradictionResolver] Contradiction resolved: uuid verdict=synthesis
[HeavyTick] Applying verdict 'synthesis' to contradiction...
[HeavyTick] Updated belief confidence: ... 0.65 → 0.45
[HeavyTick] Created synthesis belief: ...
```

### API проверка

**Beliefs:**
```bash
curl http://localhost:8765/beliefs | jq .
```

**Contradictions:**
```bash
curl http://localhost:8765/contradictions | jq .
```

**Status (включает stats):**
```bash
curl http://localhost:8765/status | jq .
```

## Тестирование

### Ручной тест формирования beliefs

1. Создайте разнообразные эпизоды (изменения файлов, взаимодействия)
2. Подождите 20 тиков
3. Проверьте `memory/beliefs.json` или `/beliefs`
4. Убедитесь, что beliefs формируются на основе паттернов

### Ручной тест detection contradictions

1. Создайте противоречащие beliefs/principles вручную в JSON
2. Подождите 30 тиков
3. Проверьте `memory/contradictions.json` или `/contradictions`
4. Убедитесь, что противоречие обнаружено

### Ручной тест resolution + verdict

1. После detection подождите 15 тиков
2. Проверьте logs: "Resolving contradiction", "verdict=..."
3. Проверьте beliefs.json: confidence должна измениться
4. Если verdict=synthesis, должно появиться новое убеждение

## Известные ограничения

1. **Масштабируемость detection:** При > 20 beliefs+principles берётся только топ-10 по confidence
2. **LLM качество:** Качество вердиктов зависит от модели (рекомендуется llama3.2:3b или лучше)
3. **Principles modification:** Principles не имеют confidence scores, поэтому вердикт не может их ослабить
4. **Дублирование:** Детектор может пропустить дубликаты при разной формулировке

## Будущие улучшения

1. **Confidence scores для principles:** Добавить weight/strength к принципам
2. **Semantic deduplication:** Использовать embeddings для обнаружения дубликатов
3. **Multi-belief reasoning:** Анализировать группы из 3+ противоречащих beliefs
4. **Evidence tracking:** Хранить ссылки на episodes, подтверждающие belief
5. **Belief hierarchy:** Создавать связи между parent/child beliefs

## Заключение

Этапы 19-20 добавляют в Digital Being способность:
- **Обучаться из опыта**, формируя убеждения о мире
- **Самокорректироваться**, обнаруживая и разрешая противоречия
- **Эволюционировать**, изменяя confidence на основе новых наблюдений

Система теперь может строить динамическую модель мира и корректировать её при обнаружении несоответствий через LLM-диалог.
