# Fault-Tolerant Architecture

## Обзор

Эта архитектура решает критическую проблему: **одна ошибка в любом шаге HeavyTick не должна ломать всю систему**.

### Проблема

В оригинальном `HeavyTick`:
- Если `goal_selection` таймаутит → весь tick умирает
- Если LLM недоступен → система зависает
- Нет защиты от каскадных ошибок
- Нет приоритетов → критичные и некритичные шаги равны

### Решение

Новая архитектура внедряет:

1. **Circuit Breaker** — автоматическое отключение сломанных компонентов
2. **Health Monitor** — мониторинг здоровья системы
3. **Priority System** — приоритеты для шагов (critical/important/optional)
4. **Graceful Degradation** — мягкая деградация с fallback'ами
5. **Result Caching** — кэширование результатов для восстановления
6. **Parallel Execution** — параллельное выполнение некритичных шагов

---

## Компоненты

### 1. **CircuitBreaker** (`core/circuit_breaker.py`)

Защищает от каскадных ошибок.

**Состояния:**
- `CLOSED` — нормальная работа
- `OPEN` — слишком много ошибок, блокирует вызовы
- `HALF_OPEN` — пробует восстановиться

**Логика:**
```python
# После 3 ошибок подряд → OPEN
# Через 60 секунд → HALF_OPEN
# Если вызов успешен → CLOSED
# Если опять ошибка → обратно в OPEN
```

**Пример:**
```python
breaker = CircuitBreaker("ollama_chat", failure_threshold=3, timeout_duration=60)

result = await breaker.call(
    func=ollama.chat,
    fallback=lambda: "Резервный ответ"
)
```

---

### 2. **HealthMonitor** (`core/health_monitor.py`)

Мониторит здоровье компонентов и автоматически переключает режимы.

**Режимы системы:**
- `NORMAL` — всё работает
- `DEGRADED` — часть компонентов недоступна, используются fallback'и
- `RECOVERY` — попытка восстановления
- `EMERGENCY` — критический сбой, минимальная работа

**Проверки:**
- Каждые 30 секунд проверяет Ollama, память, другие компоненты
- Если latency > 15 секунд → переход в DEGRADED
- После восстановления → RECOVERY → NORMAL

---

### 3. **PriorityExecutor** (`core/priority_system.py`)

Исполняет шаги с приоритетами.

**Приоритеты:**
- `CRITICAL` — **должны** выполниться (monologue, goal_selection, action)
- `IMPORTANT` — **желательно** выполнить (beliefs, contradictions, social)
- `OPTIONAL` — **выполнять, если есть время** (curiosity, meta_cognition)

**Budget System:**
```python
budgets = {
    Priority.CRITICAL: 15,    # секунд на critical шаги
    Priority.IMPORTANT: 8,    # секунд на important
    Priority.OPTIONAL: 3,     # секунд на optional
}
```

---

### 4. **Graceful Degradation** (`core/fallback_generators.py`)

Когда шаг падает, используется **fallback**.

**Иерархия fallback'ов:**
1. **Custom fallback** — заданная функция
2. **Cached result** — результат из предыдущего тика
3. **Default result** — безопасное значение по умолчанию

**Примеры:**
```python
# Monologue fallback
"Наблюдаю за текущим состоянием системы и окружающей средой."

# Goal fallback
{"goal": "наблюдать за средой", "action_type": "observe", "risk_level": "low"}

# Curiosity fallback
{"questions": [], "reason": "Curiosity engine unavailable"}
```

---

### 5. **ResilientOllamaClient** (`core/resilient_ollama.py`)

Обёртка над `OllamaClient` с защитой.

**Возможности:**
- Circuit Breaker для `chat()` и `embed()`
- Автоматический retry
- Отслеживание latency и success rate
- Интеграция с HealthMonitor

**Статистика:**
```python
stats = ollama.get_stats()
# {
#   "total_calls": 42,
#   "successful_calls": 39,
#   "success_rate": 92.86,
#   "avg_latency_ms": 1250,
#   "chat_breaker": {"state": "closed", ...}
# }
```

---

### 6. **FaultTolerantHeavyTick** (`core/fault_tolerant_heavy_tick.py`)

Новый orchestrator, который всё объединяет.

**Адаптивные timeout'ы:**
```python
STEP_TIMEOUTS = {
    "monologue": 30,         # Быстрый шаг
    "goal_selection": 90,    # Сложный шаг, несколько LLM-вызовов
    "action": 45,
    "curiosity": 30,
    ...
}
```

**Фазы выполнения:**

**Phase 1: Critical Sequential Steps**
1. Monologue (обязательно)
2. Semantic Context
3. Goal Selection (обязательно)
4. Action (обязательно)
5. After Action (обязательно)

**Phase 2: Optional Parallel Steps** (выполняются параллельно)
- Curiosity
- Self Modification
- Belief System
- Contradiction Resolver
- Time Perception
- Social Interaction
- Meta-Cognition

---

## Интеграция

### Поставьте в `main.py`:

```python
# Было:
# from core.heavy_tick import HeavyTick

# Стало:
from core.fault_tolerant_heavy_tick import FaultTolerantHeavyTick

# ...

heavy_tick = FaultTolerantHeavyTick(
    cfg=config,
    ollama=ollama_client,
    world=world_model,
    values=value_engine,
    self_model=self_model,
    mem=episodic_memory,
    milestones=milestones,
    log_dir=Path("data/logs"),
    sandbox_dir=Path("data/sandbox"),
    # ... все остальные компоненты
)

await heavy_tick.start()
```

**Это всё!** Drop-in replacement, никаких изменений в остальном коде.

---

## Преимущества

### 1. **Устойчивость к ошибкам**
Пример: `goal_selection` таймаутит → используется цель из предыдущего тика или дефолтная.

### 2. **Автоматическое восстановление**
LLM недоступен → Circuit Breaker OPEN → через 60 секунд система пробует снова.

### 3. **Приоритетное выполнение**
Критичные шаги всегда выполняются, некритичные — только если есть время.

### 4. **Мягкая деградация**
Система не падает целиком, а деградирует мягко:
- `curiosity` не работает → просто пропускается
- `monologue` не работает → используется шаблон

### 5. **Параллельное выполнение**
7 некритичных шагов выполняются параллельно → **сокращение времени тика**.

### 6. **Мониторинг**
Полная статистика каждого тика:
```
[HeavyTick #42] Completed.
Critical: 5, Important: 4, Optional: 3, Fallbacks: 2, Skipped: 0
Ollama: 15/17 calls, 88.24% success, 1420ms avg latency
```

---

## Trade-offs

### Плюсы
✅ Не ломается от одной ошибки  
✅ Автоматическое восстановление  
✅ Приоритеты  
✅ Мониторинг  
✅ Observability  

### Минусы
⚠️ Немного больше кода (~1500 строк нового кода)  
⚠️ Немного сложнее понять (но документировано)  
⚠️ Fallback'и могут скрывать реальные проблемы (но логируются)  

---

## Статистика

### Настройка логирования

В `config.yaml`:
```yaml
logging:
  level: INFO
  # Для отладки можно DEBUG
```

### Пример логов

```
[FaultTolerantHeavyTick] Started. Interval: 60s, max timeout: 120s
[HeavyTick #1] Starting (fault-tolerant mode)
[HeavyTick #1] Executing critical step 'monologue' (timeout=30s)
[HeavyTick #1] Step 'monologue' completed successfully (1250ms)
[HeavyTick #1] Executing critical step 'goal_selection' (timeout=90s)
[CircuitBreaker:ollama_chat] Call succeeded
[HeavyTick #1] Goal (StrategyEngine): 'исследовать файлы' action=analyze risk=low
[HeavyTick #1] Starting parallel optional steps
[HeavyTick #1] Completed. Critical: 5, Important: 4, Optional: 3, Fallbacks: 1, Skipped: 0
[HeavyTick #1] Ollama: 12/13 calls, 92.31% success, 1180ms avg latency
```

---

## Будущие улучшения

### 1. **Celery Integration** (опционально)
Каждый шаг — отдельная Celery task → можно запускать на разных машинах.

### 2. **Checkpointing**
Сохранять состояние тика → при краше восстановление с места остановки.

### 3. **Adaptive Timeouts**
Автоматическая подстройка timeout'ов на основе latency.

### 4. **Prometheus Metrics**
Интеграция с Prometheus для мониторинга.

### 5. **Rate Limiting**
Ограничение частоты LLM-вызовов для экономии ресурсов.

---

## Заключение

Эта архитектура — **production-ready** решение для автономных систем.

**Ключевые принципы:**
1. Одна ошибка не ломает всю систему
2. Автоматическое восстановление
3. Приоритеты важнее скорости
4. Observability — не роскошь, а необходимость

**Результат:** система, которая **работает**, а не падает от первой же ошибки.