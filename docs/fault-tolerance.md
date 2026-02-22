# Fault Tolerance & Monitoring

Документация по системе защиты от сбоев и мониторингу.

## Обзор

Система использует **трёхуровневую защиту**:

### 1. Retry Logic (TD-006)
- Повторяет временные сбои (network, timeout)
- Exponential backoff (1s, 2s, 4s)
- Максимум 3 попытки

### 2. Circuit Breaker (TD-016)
- Блокирует вызовы к недоступным сервисам
- Автоматическое восстановление
- Защищает от каскадных сбоев

### 3. Error Boundaries (TD-018)
- Изолирует ошибки критичных операций
- Fallback стратегии
- Система продолжает работу

---

## Circuit Breaker

### Состояния

```
CLOSED (closed)     → Нормальная работа
OPEN (open)         → Сервис недоступен, запросы блокируются
HALF_OPEN (half_open) → Тестирование восстановления
```

### Переходы

```
CLOSED → OPEN
  • После 5 последовательных ошибок
  • Запросы блокируются на 30 секунд

OPEN → HALF_OPEN
  • Через 30 секунд
  • Разрешается тестовый запрос

HALF_OPEN → CLOSED
  • После 2 успешных запросов
  • Сервис восстановлен

HALF_OPEN → OPEN
  • Если тест провалился
  • Возвращаемся к OPEN
```

### Пример использования

```python
from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

# Создать circuit breaker
breaker = CircuitBreaker(
    name="my_service",
    failure_threshold=5,      # Ошибок до OPEN
    recovery_timeout=30.0,    # Секунд до попытки восстановления
    success_threshold=2,      # Успехов до CLOSED
)

# Использовать
try:
    result = breaker.call(lambda: risky_operation())
except CircuitBreakerOpen:
    # Сервис недоступен
    result = fallback_value

# Проверить состояние
state = breaker.get_state()  # "closed", "open", "half_open"
stats = breaker.get_stats()
```

### Конфигурация

Текущие настройки для **Ollama**:

```python
CircuitBreaker(
    name="ollama",
    failure_threshold=5,       # 5 ошибок → OPEN
    recovery_timeout=30.0,     # 30с timeout
    success_threshold=2,       # 2 успеха → CLOSED
)
```

**Рекомендации:**
- `failure_threshold`: 3-7 (чем меньше, тем быстрее открывается)
- `recovery_timeout`: 10-60с (зависит от сервиса)
- `success_threshold`: 1-3 (чем больше, тем надёжнее)

---

## Health Checks

### Компоненты

Система проверяет:

1. **Ollama** - доступность LLM
2. **Episodic Memory** - работа БД
3. **Vector Memory** - эмбеддинги и поиск
4. **Event Bus** - обработка событий
5. **Circuit Breakers** - состояние всех breakers

### Пример использования

```python
from core.health_check import HealthChecker
from core.circuit_breaker import get_registry

# Инициализировать
health = HealthChecker(
    ollama=ollama,
    episodic_mem=episodic_mem,
    vector_mem=vector_mem,
    event_bus=event_bus,
    circuit_registry=get_registry()
)

# Проверить всё
report = health.check_all()

if report['healthy']:
    print("✅", report['summary'])
else:
    print("⚠️", report['summary'])
    for issue in report['issues']:
        print(f"  - {issue}")

# Быстрая проверка
if health.is_healthy():
    proceed_with_operation()
else:
    log.warning("System unhealthy:", health.get_issues())
```

### Формат репорта

```json
{
  "healthy": true,
  "timestamp": 1708630800.0,
  "components": {
    "ollama": {
      "name": "ollama",
      "healthy": true,
      "message": "Ollama is healthy",
      "details": {"available": true, "tick_count": 42}
    },
    "episodic_memory": {
      "name": "episodic_memory",
      "healthy": true,
      "message": "Episodic memory is healthy",
      "details": {"db_size_mb": 12.5}
    }
  },
  "issues": [],
  "summary": "✅ All 5 components healthy"
}
```

### Мониторинг

Рекомендуется проверять здоровье:

1. **Периодически** - каждые 10-30 секунд
2. **Перед критичными операциями**
3. **После ошибок** - чтобы понять причину

```python
# В heavy_tick
async def _run_tick(self):
    # Проверить здоровье перед тиком
    if not self._health.is_healthy():
        log.warning(f"[Tick #{n}] System unhealthy: {self._health.get_issues()}")
        # Можно перейти в defensive mode
    
    # Продолжить работу...
```

---

## Интеграция в main.py

```python
from core.health_check import HealthChecker
from core.circuit_breaker import get_registry

# В main()
health_checker = HealthChecker(
    ollama=ollama,
    episodic_mem=episodic_mem,
    vector_mem=vector_mem,
    event_bus=event_bus,
    circuit_registry=get_registry()
)

# Передать в HeavyTick
heavy_tick = HeavyTick(
    cfg=cfg,
    ollama=ollama,
    # ... other dependencies
    health_checker=health_checker  # Добавить этот параметр
)

# Проверять периодически
async def monitor_health():
    while True:
        await asyncio.sleep(30)  # Каждые 30с
        report = health_checker.check_all(force=True)
        if not report['healthy']:
            log.warning(f"Health issues: {report['issues']}")

# Запустить мониторинг
asyncio.create_task(monitor_health())
```

---

## Troubleshooting

### Circuit Breaker открыт (OPEN)

**Проблема:** `CircuitBreakerOpen: Circuit breaker 'ollama' is OPEN`

**Причины:**
- Ollama недоступен (service down)
- Сетевые проблемы
- Перегрузка сервера

**Решение:**
1. Проверьте `ollama list` - работает ли Ollama
2. Подождите 30 секунд - breaker автоматически попробует восстановиться
3. Вручную перезагрузка: `breaker.reset()`

### Health check показывает unhealthy

**Проблема:** `System unhealthy: ['Ollama is not available']`

**Диагностика:**
```python
report = health.check_all(force=True)
for comp_name, comp_data in report['components'].items():
    if not comp_data['healthy']:
        print(f"{comp_name}: {comp_data['message']}")
        print(f"  Details: {comp_data['details']}")
```

**Решение:**
- Проверьте каждый компонент отдельно
- Посмотрите логи компонента
- Проверьте DB файлы (permissions, disk space)

### Частые транзиции OPEN/CLOSED

**Проблема:** Circuit breaker постоянно меняет состояние

**Причина:** Нестабильное соединение с Ollama

**Решение:**
1. Увеличьте `failure_threshold` (5 → 7)
2. Увеличьте `recovery_timeout` (30с → 60с)
3. Увеличьте `success_threshold` (2 → 3)

---

## Metrics & Monitoring

### Что мониторить

1. **Circuit Breaker состояние**
   - Сколько времени в каждом состоянии
   - Частота переходов

2. **Health Check результаты**
   - % здоровых проверок
   - Какие компоненты чаще падают

3. **Error Boundary статистика**
   - Сколько ошибок поймано
   - Сколько fallback использовано

### Логи

Важные лог сообщения:

```
WARNING: CircuitBreaker 'ollama': closed -> OPEN. Failures: 5. Will retry in 30s
INFO: CircuitBreaker 'ollama': open -> HALF_OPEN. Testing recovery...
INFO: CircuitBreaker 'ollama': half_open -> CLOSED. Service recovered!
WARNING: Health check FAILED: 2 issue(s)
```

---

## Best Practices

### 1. Настройки Circuit Breaker

- ✅ Критичные сервисы: низкий `failure_threshold` (3-5)
- ✅ Некритичные: высокий `failure_threshold` (7-10)
- ✅ Быстрые сервисы: короткий `recovery_timeout` (10-20с)
- ✅ Медленные: длинный `recovery_timeout` (30-60с)

### 2. Health Checks

- ✅ Проверяйте периодически (10-30с)
- ✅ Кэшируйте результаты (10с)
- ✅ Проверяйте перед критичными операциями
- ❌ Не проверяйте слишком часто (<5с)

### 3. Graceful Degradation

- ✅ Всегда имейте fallback значения
- ✅ Продолжайте работу при частичной недоступности
- ✅ Логируйте degraded состояния
- ❌ Не падайте при одной ошибке

---

## Связанные файлы

- `core/circuit_breaker.py` - Circuit breaker implementation
- `core/health_check.py` - Health check system
- `core/error_boundary.py` - Error boundary pattern
- `core/ollama_client.py` - Ollama client with circuit breaker
- `docs/audits/phase-1-complete-audit.md` - Полный аудит

## Issues Resolved

- ✅ TD-006: Retry logic
- ✅ TD-012: Health checks
- ✅ TD-016: Circuit breaker
- ✅ TD-018: Error boundaries
