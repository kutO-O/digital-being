# Phase 1: Sensory Improvements — Органы чувств и руки

**Статус:** ✅ Реализовано  
**Дата:** February 23, 2026  
**Branch:** `feature/phase1-sensory-improvements`

## 🎯 Цель

Добавить агенту реальные органы чувств для восприятия внешнего мира и инструменты для взаимодействия с ним.

---

## 📋 Что было добавлено

### 1. **URL Reader Tool** (👁️ Органы чувств)

**Файл:** `core/tools/sensory_tools.py`  
**Инструмент:** `url_reader`

**Возможности:**
- Скачивание веб-страниц через `httpx`
- Парсинг HTML с помощью `BeautifulSoup`
- Извлечение чистого текста (без scripts, styles, nav)
- Опциональное извлечение ссылок
- Автоматическое следование редиректам

**Пример использования:**
```python
result = await url_reader.execute(
    url="https://github.com/kutO-O/digital-being",
    max_length=5000,
    extract_links=True
)

# result.data:
# {
#     "url": "https://github.com/kutO-O/digital-being",
#     "status_code": 200,
#     "title": "kutO-O/digital-being: Autonomous AI agent",
#     "text": "Digital Being\n\nАвтономная AI-система...",
#     "length": 4532,
#     "links": [{"text": "Documentation", "href": "/docs"}]
# }
```

**Зависимости:**
```bash
pip install httpx beautifulsoup4
```

---

### 2. **Python REPL Executor** (✋ Руки)

**Файл:** `core/tools/python_executor.py`  
**Инструмент:** `python_execute`

**Возможности:**
- Полноценный Python REPL с persistent namespace
- Песочница с whitelist безопасных модулей
- Захват stdout/stderr
- Timeout protection
- Автоматический возврат результата последнего выражения
- Статистика выполнения

**Безопасность:**
- Блокировка `__import__`, `eval`, `exec`, `open`, `subprocess`
- Whitelist модулей: `math`, `random`, `datetime`, `json`, `re`, etc.
- Изоляция от файловой системы
- Timeout по умолчанию: 5 секунд

**Пример использования:**
```python
# Первая команда - определяем функцию
result1 = await python_execute.execute(
    code="""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
)

# Вторая команда - используем функцию (namespace сохранён!)
result2 = await python_execute.execute(
    code="fibonacci(10)"
)

# result2.data:
# {
#     "success": True,
#     "stdout": "",
#     "result": "55",
#     "execution_time_ms": 12,
#     "namespace_vars": ["fibonacci"]
# }
```

**Сброс namespace:**
```python
result = await python_execute.execute(
    code="x = 42",
    reset_namespace=True  # Очистить все переменные
)
```

---

### 3. **Screenshot + OCR Tool** (👁️ Органы чувств)

**Файл:** `core/tools/sensory_tools.py`  
**Инструмент:** `screenshot_ocr`

**Возможности:**
- Захват скриншота экрана через `Pillow`
- Извлечение текста с помощью `Tesseract OCR`
- Сохранение скриншота в файл (опционально)
- Поддержка нескольких мониторов

**Пример использования:**
```python
result = await screenshot_ocr.execute(
    save_path="sandbox/screenshot.png",
    monitor=0
)

# result.data:
# {
#     "text": "Extracted text from screen...",
#     "size": [1920, 1080],
#     "saved_to": "sandbox/screenshot.png",
#     "length": 542
# }
```

**Системные требования:**
```bash
# Python packages
pip install pillow pytesseract

# System package (Ubuntu/Debian)
sudo apt install tesseract-ocr tesseract-ocr-rus

# System package (macOS)
brew install tesseract tesseract-lang

# System package (Windows)
# Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
```

---

### 4. **PDF Reader Tool** (👁️ Органы чувств)

**Файл:** `core/tools/sensory_tools.py`  
**Инструмент:** `pdf_read`

**Возможности:**
- Извлечение текста из PDF через `pdfplumber`
- Чтение метаданных (автор, название, subject)
- Извлечение таблиц (опционально)
- Обработка по страницам с ограничением

**Пример использования:**
```python
result = await pdf_read.execute(
    file_path="sandbox/document.pdf",
    max_pages=10,
    extract_structure=True
)

# result.data:
# {
#     "metadata": {
#         "title": "Digital Being Architecture",
#         "author": "kutO-O",
#         "total_pages": 15,
#         "processed_pages": 10
#     },
#     "text": "Full text from all pages...",
#     "pages": [
#         {"page": 1, "text": "Page 1 content..."},
#         {"page": 2, "text": "Page 2 content..."}
#     ],
#     "tables": [
#         {"page": 3, "rows": 5, "preview": [["Col1", "Col2"], ["Data1", "Data2"]]}
#     ],
#     "length": 8432
# }
```

**Зависимости:**
```bash
pip install pdfplumber
```

---

## 🔧 Интеграция с проектом

### Автоматическая регистрация инструментов

Все новые инструменты автоматически регистрируются через систему `ToolRegistry`:

```python
# В core/tools/__init__.py уже есть автоматическая регистрация
from core.tools.sensory_tools import (
    DuckDuckGoSearchTool,
    URLReaderTool,
    RSSReaderTool,
    SystemStatsTool,
    WikipediaTool,
    ScreenshotOCRTool,
    PDFReaderTool,
)
from core.tools.python_executor import PythonExecutorTool

# Инструменты доступны в heavy_tick через tool_executor
```

### Использование в агенте

Агент автоматически получает доступ ко всем инструментам через LLM tool calling:

```python
# В heavy_tick агент может сделать:
# "Я хочу узнать о последних новостях в AI"

# LLM автоматически вызовет:
await duckduckgo_search.execute(query="latest AI news 2026")

# Затем может прочитать статью:
await url_reader.execute(url="https://...")

# И проанализировать данные в Python:
await python_execute.execute(code="""
import json
data = {...}
result = sum(data['values'])
print(f'Total: {result}')
""")
```

---

## 📊 Статистика инструментов

Все инструменты ведут статистику выполнения в `memory/`:

- `python_executor_stats.json` — статистика Python выполнения
- `shell_stats.json` — статистика shell команд (уже было)

**Пример статистики:**
```json
{
  "total_executed": 142,
  "total_errors": 8,
  "total_timeouts": 2
}
```

**Просмотр статистики через API:**
```bash
curl http://127.0.0.1:8765/tools/stats
```

---

## 🚀 Что дальше (Phase 2)

### Следующие улучшения:

1. **Telegram Integration** — связать `telegram_bot.py` с `social_layer.py`
2. **Browser Automation** — Playwright для взаимодействия с сайтами
3. **Knowledge Graph** — NetworkX для связей между концептами
4. **Vision Model** — LLaVA через Ollama для анализа изображений
5. **Whisper Audio** — расшифровка аудио через Ollama

---

## 📝 Changelog

### Added
- ✅ **URLReaderTool** — чтение веб-страниц (httpx + BeautifulSoup)
- ✅ **PythonExecutorTool** — sandboxed Python REPL с persistent namespace
- ✅ **ScreenshotOCRTool** — захват экрана + Tesseract OCR
- ✅ **PDFReaderTool** — чтение PDF с извлечением таблиц

### Updated
- ✅ `requirements.txt` — добавлены `httpx`, `pdfplumber`, `pytesseract`, `pillow`
- ✅ `sensory_tools.py` — расширен набор сенсорных инструментов

---

## 🧪 Тестирование

### Быстрый тест всех инструментов:

```python
import asyncio
from pathlib import Path
from core.tools.sensory_tools import URLReaderTool, PDFReaderTool, ScreenshotOCRTool
from core.tools.python_executor import PythonExecutorTool

async def test_tools():
    # Test URL Reader
    url_reader = URLReaderTool()
    result = await url_reader.execute(url="https://example.com")
    assert result.success
    print(f"✅ URL Reader: {result.data['title']}")
    
    # Test Python Executor
    py_exec = PythonExecutorTool(Path("sandbox"), Path("memory"))
    result = await py_exec.execute(code="print('Hello, World!')")
    assert result.success
    print(f"✅ Python Executor: {result.data['stdout']}")
    
    # Test Screenshot OCR (requires display)
    # screenshot = ScreenshotOCRTool()
    # result = await screenshot.execute()
    # print(f"✅ Screenshot OCR: {result.data['length']} chars")
    
    # Test PDF Reader (requires PDF file)
    # pdf_reader = PDFReaderTool()
    # result = await pdf_reader.execute(file_path="test.pdf")
    # print(f"✅ PDF Reader: {result.data['metadata']['title']}")

asyncio.run(test_tools())
```

---

## 📚 Ссылки

- **Branch:** [feature/phase1-sensory-improvements](https://github.com/kutO-O/digital-being/tree/feature/phase1-sensory-improvements)
- **Issues:** [Phase 1 Tracking Issue](#) (TODO: create)
- **Related PRs:** [PR #XXX](#) (TODO: create)

---

**Автор:** AI Assistant + kutO-O  
**Последнее обновление:** February 23, 2026
