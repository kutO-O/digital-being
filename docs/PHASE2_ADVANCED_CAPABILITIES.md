# Phase 2: Advanced Capabilities — Продвинутые возможности

**Статус:** ✅ Реализовано  
**Дата:** February 23, 2026  
**Branch:** `feature/phase2-advanced-capabilities`

## 🎯 Цель

Добавить агенту продвинутые способности: автоматизацию браузера, зрение, слух, граф знаний и полную интеграцию с Telegram.

---

## 📋 Что было добавлено

### 1. **Browser Automation** (🌐 Браузер)

**Файл:** `core/tools/advanced_tools.py`  
**Инструмент:** `browser`

**Возможности:**
- Автоматизация через Playwright (Chromium headless)
- Навигация по сайтам
- Клики по элементам (CSS селекторы)
- Заполнение форм
- Скриншоты страниц
- Полноценное управление браузером

**Пример использования:**
```python
# Navigate to website
await browser.execute(
    action="navigate",
    url="https://github.com/kutO-O/digital-being"
)

# Click on element
await browser.execute(
    action="click",
    selector="button.star-button"
)

# Fill form
await browser.execute(
    action="fill",
    selector="input[name='username']",
    text="digital_being"
)

# Take screenshot
await browser.execute(
    action="screenshot",
    save_path="sandbox/page.png"
)

# Close browser
await browser.execute(action="close")
```

**Установка:**
```bash
pip install playwright
playwright install chromium
```

---

### 2. **Vision Model Integration** (👁️ Зрение)

**Файл:** `core/tools/advanced_tools.py`  
**Инструмент:** `vision_analyze`

**Возможности:**
- Анализ изображений через LLaVA model (Ollama)
- Описание содержимого
- Обнаружение объектов
- Чтение текста на изображениях
- Ответы на вопросы об изображении

**Пример использования:**
```python
# Describe image
result = await vision_analyze.execute(
    image_path="sandbox/screenshot.png",
    prompt="Describe what you see in this image"
)

# result.data:
# {
#     "image": "sandbox/screenshot.png",
#     "prompt": "Describe what you see in this image",
#     "description": "This image shows a GitHub repository page...",
#     "model": "llava"
# }

# Detect specific objects
result = await vision_analyze.execute(
    image_path="photo.jpg",
    prompt="What animals do you see in this photo?"
)

# Read text from image
result = await vision_analyze.execute(
    image_path="document.jpg",
    prompt="Extract all text from this document"
)
```

**Установка:**
```bash
# Pull LLaVA model in Ollama
ollama pull llava
```

---

### 3. **Audio Transcription** (🎤 Слух)

**Файл:** `core/tools/advanced_tools.py`  
**Инструмент:** `audio_transcribe`

**Возможности:**
- Расшифровка аудио через Whisper
- Поддержка форматов: mp3, wav, m4a, ogg
- Автоматическое определение языка
- Сегментация по временным меткам

**Пример использования:**
```python
# Transcribe audio file
result = await audio_transcribe.execute(
    audio_path="recording.mp3",
    language="auto"  # or "ru", "en", etc.
)

# result.data:
# {
#     "audio": "recording.mp3",
#     "text": "Привет, это тестовая запись...",
#     "language": "ru",
#     "segments": 5
# }

# Transcribe with specific language
result = await audio_transcribe.execute(
    audio_path="speech.wav",
    language="en"
)
```

**Установка:**
```bash
pip install openai-whisper

# Also install ffmpeg (system package)
# Ubuntu/Debian:
sudo apt install ffmpeg

# macOS:
brew install ffmpeg

# Windows: download from https://ffmpeg.org/
```

---

### 4. **Knowledge Graph** (🕸️ Граф знаний)

**Файл:** `core/tools/advanced_tools.py`  
**Инструмент:** `knowledge_graph`

**Возможности:**
- Построение графа знаний через NetworkX
- Добавление концептов (nodes)
- Создание связей (edges)
- Поиск соседей концепта
- Персистентное хранение в JSON

**Пример использования:**
```python
# Add concepts
await knowledge_graph.execute(
    action="add_concept",
    concept="Python"
)

await knowledge_graph.execute(
    action="add_concept",
    concept="Machine Learning"
)

# Create relation
await knowledge_graph.execute(
    action="add_relation",
    from_concept="Python",
    to_concept="Machine Learning",
    relation_type="used_in"
)

# Get neighbors
result = await knowledge_graph.execute(
    action="get_neighbors",
    concept="Python"
)

# result.data:
# {
#     "concept": "Python",
#     "neighbors": ["Machine Learning", "Django", "FastAPI"],
#     "count": 3
# }

# Save graph
await knowledge_graph.execute(action="save")
```

**Типы связей:**
- `related_to` — общая связь
- `is_a` — наследование
- `part_of` — композиция
- `used_in` — использование
- `causes` — причинно-следственная связь
- `requires` — зависимость

**Установка:**
```bash
pip install networkx
```

---

### 5. **Telegram Integration** (✈️ Telegram)

**Файлы:** 
- `core/telegram_integration.py` — сервис интеграции
- `core/tools/telegram_bot.py` — инструменты (уже было)

**Возможности:**
- Автоматическая двусторонняя синхронизация
- Incoming: Telegram → inbox.txt → social_layer
- Outgoing: social_layer → outbox.txt → Telegram
- Polling каждые 30 секунд (настраивается)
- Автозапуск вместе с агентом

**Как работает:**

1. **Входящие сообщения:**
   ```
   User (Telegram) → [Bot] → inbox.txt → SocialLayer → Agent
   ```

2. **Исходящие сообщения:**
   ```
   Agent → SocialLayer → outbox.txt → [Bot] → User (Telegram)
   ```

**Настройка:**

1. Создай бота через [@BotFather](https://t.me/BotFather)
2. Получи `bot_token` и свой `chat_id`
3. Добавь в `config.yaml`:

```yaml
telegram:
  enabled: true
  bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
  chat_id: "987654321"
  poll_interval: 30  # seconds
```

**Использование в коде:**

```python
from core.telegram_integration import (
    initialize_telegram_service,
    start_telegram_service,
    get_telegram_service,
)

# Initialize
service = initialize_telegram_service(
    bot_token=config["telegram"]["bot_token"],
    chat_id=config["telegram"]["chat_id"],
    inbox_path=Path("inbox.txt"),
    outbox_path=Path("outbox.txt"),
    poll_interval=30,
)

# Start (в main.py при запуске агента)
if service.is_configured():
    await start_telegram_service()
    print("✅ Telegram integration started")

# Check status
status = service.get_status()
print(status)
# {
#     "configured": True,
#     "enabled": True,
#     "running": True,
#     "poll_interval": 30,
#     ...
# }

# Stop (при завершении)
await stop_telegram_service()
```

**Формат сообщений в Telegram:**

```
🤖 **Digital Being**

Привет! Я закончил анализ данных. Вот что я нашёл:

- Всего записей: 1542
- Аномалий: 3
- Средняя оценка: 8.7/10

Хочешь подробный отчёт?
```

---

## 🔧 Интеграция с проектом

### Автоматическая регистрация инструментов

```python
# В core/tools/__init__.py
from core.tools.advanced_tools import (
    BrowserTool,
    VisionTool,
    AudioTranscribeTool,
    KnowledgeGraphTool,
)

# Инструменты автоматически доступны в heavy_tick
```

### Использование в агенте

Агент получает доступ ко всем инструментам через LLM tool calling:

```python
# В heavy_tick агент может:
# "Открой GitHub и найди мой репозиторий"

# 1. Открыть браузер
await browser.execute(action="navigate", url="https://github.com")

# 2. Сделать скриншот
await browser.execute(action="screenshot", save_path="github.png")

# 3. Проанализировать скриншот
await vision_analyze.execute(
    image_path="github.png",
    prompt="Find the link to kutO-O/digital-being repository"
)

# 4. Кликнуть по найденной ссылке
await browser.execute(action="click", selector="a[href='/kutO-O/digital-being']")

# 5. Сохранить связь в граф знаний
await knowledge_graph.execute(
    action="add_relation",
    from_concept="GitHub",
    to_concept="digital-being repo",
    relation_type="contains"
)
```

---

## 📊 Сравнение Phase 1 vs Phase 2

| Возможность | Phase 1 | Phase 2 |
|------------|---------|--------|
| Веб-поиск | ✅ DuckDuckGo | ✅ + Browser automation |
| Чтение страниц | ✅ URL reader | ✅ + Interactive browsing |
| Зрение | ✅ Screenshot OCR | ✅ + Vision AI (LLaVA) |
| Слух | ❌ | ✅ Whisper transcription |
| Python | ✅ REPL sandbox | ✅ Same |
| PDF | ✅ Text + tables | ✅ Same |
| Telegram | ⚠️ Manual | ✅ Auto bidirectional |
| Граф знаний | ❌ | ✅ NetworkX graph |
| Мультимодальность | ⚠️ Basic | ✅ Full (text, vision, audio) |

---

## 🚀 Примеры использования

### 📰 Автоматический мониторинг новостей

```python
# 1. Найти новости
results = await duckduckgo_search.execute(query="AI news 2026")

# 2. Открыть статью в браузере
await browser.execute(action="navigate", url=results['results'][0]['url'])

# 3. Сделать скриншот
await browser.execute(action="screenshot", save_path="news.png")

# 4. Проанализировать визуально
vision = await vision_analyze.execute(
    image_path="news.png",
    prompt="Summarize the main points of this article"
)

# 5. Добавить в граф знаний
await knowledge_graph.execute(
    action="add_concept",
    concept=vision['description'][:50]
)

# 6. Отправить в Telegram
# (автоматически через outbox.txt)
```

### 🎤 Обработка голосовых сообщений

```python
# 1. Получить аудио из Telegram
# (сохраняется автоматически при получении)

# 2. Расшифровать
text = await audio_transcribe.execute(
    audio_path="voice_message.ogg",
    language="auto"
)

# 3. Обработать как текстовое сообщение
# (через standard pipeline)

# 4. Ответить в Telegram
# (автоматически через outbox.txt)
```

### 🕸️ Построение базы знаний

```python
# Агент автоматически строит граф знаний при обучении:

# Прочитал статью о Python
await knowledge_graph.execute(
    action="add_concept",
    concept="Python"
)

# Нашёл связь с ML
await knowledge_graph.execute(
    action="add_relation",
    from_concept="Python",
    to_concept="Machine Learning",
    relation_type="used_in"
)

# Сохранить граф
await knowledge_graph.execute(action="save")

# Потом может спросить:
# "Что я знаю о Python?"
neighbors = await knowledge_graph.execute(
    action="get_neighbors",
    concept="Python"
)
```

---

## 🧪 Тестирование

### Quick test всех инструментов:

```python
import asyncio
from pathlib import Path
from core.tools.advanced_tools import (
    BrowserTool,
    VisionTool,
    AudioTranscribeTool,
    KnowledgeGraphTool,
)

async def test_phase2():
    # Test Browser
    browser = BrowserTool()
    result = await browser.execute(action="navigate", url="https://example.com")
    assert result.success
    print(f"✅ Browser: {result.data['title']}")
    await browser.execute(action="close")
    
    # Test Vision (requires LLaVA + image)
    # vision = VisionTool()
    # result = await vision.execute(
    #     image_path="test.jpg",
    #     prompt="What is in this image?"
    # )
    # print(f"✅ Vision: {result.data['description'][:50]}...")
    
    # Test Audio (requires audio file)
    # audio = AudioTranscribeTool()
    # result = await audio.execute(audio_path="test.mp3")
    # print(f"✅ Audio: {result.data['text'][:50]}...")
    
    # Test Knowledge Graph
    kg = KnowledgeGraphTool(Path("memory/knowledge_graph.json"))
    result = await kg.execute(action="add_concept", concept="Testing")
    assert result.success
    print(f"✅ Knowledge Graph: {result.data['nodes_count']} nodes")
    await kg.execute(action="save")

asyncio.run(test_phase2())
```

---

## 📚 Зависимости

```bash
# Install all Phase 2 dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Pull LLaVA model for vision
ollama pull llava

# Install ffmpeg for audio (system package)
# Ubuntu/Debian:
sudo apt install ffmpeg

# macOS:
brew install ffmpeg
```

---

## 🎯 Что дальше (Phase 3)

### Потенциальные улучшения:

1. **Email Integration** — чтение/отправка писем
2. **Calendar Integration** — управление расписанием
3. **File Sync** — синхронизация с облачными хранилищами
4. **Code Execution** — запуск кода на удалённых серверах
5. **Advanced Vision** — распознавание эмоций, жестов
6. **Speech Synthesis** — генерация голосовых сообщений
7. **Multi-agent** — взаимодействие с другими AI агентами

---

## 📝 Changelog

### Added
- ✅ **BrowserTool** — автоматизация браузера через Playwright
- ✅ **VisionTool** — анализ изображений через LLaVA
- ✅ **AudioTranscribeTool** — расшифровка аудио через Whisper
- ✅ **KnowledgeGraphTool** — граф знаний через NetworkX
- ✅ **TelegramIntegrationService** — автоматическая двусторонняя синхронизация

### Updated
- ✅ `requirements.txt` — добавлены `playwright`, `openai-whisper`, `networkx`
- ✅ `telegram_bot.py` — используется в TelegramBridge

---

## 📖 Ссылки

- **Branch:** [feature/phase2-advanced-capabilities](https://github.com/kutO-O/digital-being/tree/feature/phase2-advanced-capabilities)
- **Playwright Docs:** https://playwright.dev/python/
- **LLaVA Model:** https://ollama.com/library/llava
- **Whisper:** https://github.com/openai/whisper
- **NetworkX:** https://networkx.org/

---

**Автор:** AI Assistant + kutO-O  
**Последнее обновление:** February 23, 2026
