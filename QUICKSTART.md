# Quick Start Guide

Быстрый запуск Digital Being за 5 минут.

---

## Предварительные требования

### Обязательно:
- **Python 3.11+**
- **Ollama** (установлен и запущен)
- **Git**

### Опционально:
- **prometheus_client** (для metrics)
- **aiohttp** (для async mode)

---

## Установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/kutO-O/digital-being.git
cd digital-being
```

### 2. Создать виртуальное окружение

#### Windows (PowerShell):
```powershell
python -m venv venv
venv\Scripts\activate
```

#### Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Установить зависимости

```bash
# Основные зависимости
pip install -r requirements.txt

# Опционально: метрики + async
pip install prometheus-client aiohttp

# Опционально: тесты
pip install -r requirements-test.txt
```

### 4. Установить Ollama

#### Windows:
```powershell
# Скачать с https://ollama.ai
# Установить OllamaSetup.exe

# Запустить
ollama serve

# Скачать модель
ollama pull llama3.2
ollama pull nomic-embed-text
```

#### Linux:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
ollama pull llama3.2
ollama pull nomic-embed-text
```

#### macOS:
```bash
brew install ollama
ollama serve &
ollama pull llama3.2
ollama pull nomic-embed-text
```

### 5. Проверить Ollama

```bash
curl http://localhost:11434/api/tags

# Должно вернуть JSON с моделями
```

---

## Запуск

### Базовый запуск

```bash
python main.py
```

### С кастомным config

```bash
python main.py --config my_config.yaml
```

### Запуск в фоне (Linux/macOS)

```bash
nohup python main.py &
```

### Windows (фоновый режим)

```powershell
Start-Process python -ArgumentList "main.py" -WindowStyle Hidden
```

---

## Проверка работы

### 1. Health Check

```bash
curl http://localhost:8766/health

# Ожидаемый ответ:
{
  "status": "healthy",
  "components": {
    "ollama": "ok",
    "database": "ok",
    "memory": "ok"
  }
}
```

### 2. Metrics (если установлен prometheus-client)

```bash
curl http://localhost:8766/metrics

# Покажет Prometheus метрики
```

### 3. WebSocket

```python
import websockets
import asyncio
import json

async def test():
    uri = "ws://localhost:8766/ws"
    async with websockets.connect(uri) as ws:
        # Отправить сообщение
        await ws.send(json.dumps({
            "type": "user_input",
            "content": "Hello!"
        }))
        
        # Получить ответ
        response = await ws.recv()
        print(response)

asyncio.run(test())
```

---

## Распространённые проблемы

### Проблема 1: Ollama не запускается

**Симптом:**
```
Connection refused to localhost:11434
```

**Решение:**
```bash
# Проверить запущен ли Ollama
curl http://localhost:11434/api/tags

# Если нет - запустить
ollama serve
```

### Проблема 2: Модель не найдена

**Симптом:**
```
model 'llama3.2' not found
```

**Решение:**
```bash
# Скачать модель
ollama pull llama3.2
ollama pull nomic-embed-text

# Проверить
ollama list
```

### Проблема 3: Port занят

**Симптом:**
```
Address already in use: 8766
```

**Решение:**
```yaml
# Изменить config.yaml
api:
  port: 8767  # Другой порт
```

### Проблема 4: ModuleNotFoundError

**Симптом:**
```
ModuleNotFoundError: No module named 'prometheus_client'
```

**Решение:**
```bash
# Установить недостающие пакеты
pip install prometheus-client aiohttp
```

### Проблема 5: Windows signal handler (FIXED)

**Симптом:**
```
NotImplementedError: add_signal_handler
```

**Решение:**
✅ **Уже исправлено!** `shutdown_handler.py` теперь использует `signal.signal()` (cross-platform).

---

## Тестирование

### Запустить тесты

```bash
# Установить test dependencies
pip install -r requirements-test.txt

# Запустить все тесты
pytest

# С coverage
pytest --cov=core --cov-report=html

# Открыть отчёт
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

### Быстрые тесты (unit only)

```bash
pytest tests/unit -v
```

---

## Мониторинг

### Prometheus + Grafana (опционально)

```bash
# 1. Установить Prometheus
# Скачать с https://prometheus.io/download/

# 2. Конфигурировать prometheus.yml
scrape_configs:
  - job_name: 'digital-being'
    static_configs:
      - targets: ['localhost:8766']

# 3. Запустить
./prometheus --config.file=prometheus.yml

# 4. Открыть
http://localhost:9090
```

---

## Конфигурация

### Минимальный config.yaml

```yaml
ollama:
  base_url: "http://localhost:11434"
  strategy_model: "llama3.2"
  embed_model: "nomic-embed-text"

api:
  host: "0.0.0.0"
  port: 8766

logging:
  level: "INFO"
  dir: "logs"
```

### Полный config см. в `config.yaml`

---

## Следующие шаги

1. ✅ **Запустить систему** - `python main.py`
2. ✅ **Проверить health** - `curl localhost:8766/health`
3. ✅ **Подключиться по WebSocket**
4. ✅ **Настроить мониторинг** (опционально)
5. ✅ **Прочитать docs/**

---

## Документация

- **`docs/fault-tolerance.md`** - Circuit breaker, retry, cache
- **`docs/metrics-monitoring.md`** - Prometheus metrics
- **`docs/production-deployment.md`** - Production setup
- **`docs/performance-optimization.md`** - Performance tuning
- **`docs/testing-guide.md`** - Testing

---

## Помощь

### Проблемы?

1. Проверь **logs/** папку
2. Запусти с `--debug`
3. Проверь **Issues** на GitHub

### Контакты

- GitHub Issues: https://github.com/kutO-O/digital-being/issues
- Discussions: https://github.com/kutO-O/digital-being/discussions

---

**Система готова к работе!** 🚀
