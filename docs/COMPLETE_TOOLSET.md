# Complete Toolset — Полный набор инструментов

**Digital Being** — полноценный автономный AI-агент с 20+ инструментами.

**Дата:** February 23, 2026  
**Версия:** Phase 1-3 Complete

---

## 📊 Обзор по категориям

### 🌐 Web & Internet (7 tools)
1. **duckduckgo_search** — поиск в интернете
2. **url_reader** — чтение веб-страниц
3. **rss_read** — чтение RSS/Atom лент
4. **wikipedia** — поиск в Wikipedia
5. **browser** — автоматизация браузера (Playwright)
6. **web_api** — HTTP API клиент (REST)
7. **telegram_send/receive** — Telegram бот

### 👁️ Vision & Multimodal (3 tools)
8. **screenshot_ocr** — скриншот + OCR
9. **vision_analyze** — анализ изображений (LLaVA)
10. **pdf_read** — чтение PDF с таблицами

### 🎤 Audio (1 tool)
11. **audio_transcribe** — расшифровка аудио (Whisper)

### 💻 Computation (1 tool)
12. **python_execute** — Python REPL с персистентным namespace

### 💾 File Operations (2 tools)
13. **shell commands** — безопасные shell команды (ls, cat, grep)
14. **file_ops** — продвинутые операции (copy, move, search)

### 🕸️ Memory & Knowledge (1 tool)
15. **knowledge_graph** — граф знаний (NetworkX)

### ✉️ Communication (2 tools)
16. **email** — отправка/получение писем (SMTP/IMAP)
17. **telegram** — автоматическая интеграция

### 📅 Productivity (2 tools)
18. **calendar** — управление событиями
19. **system_stats** — мониторинг системы (CPU, RAM, disk)

### 👋 Action Tools (1 tool)
20. **notifications** — системные уведомления

---

## 📝 Полный список инструментов

### Phase 1: Sensory Tools (Органы чувств)

#### 1. duckduckgo_search
```python
# Поиск в интернете без API key
await duckduckgo_search.execute(
    query="latest AI news 2026",
    max_results=5,
    region="ru-ru"
)
```
**Возможности:** Поиск, фильтр по региону, SafeSearch

#### 2. url_reader
```python
# Полное чтение веб-страницы
await url_reader.execute(
    url="https://example.com",
    max_length=5000,
    extract_links=True
)
```
**Возможности:** httpx + BeautifulSoup, чистый текст, экстракция ссылок

#### 3. rss_read
```python
# Чтение RSS/Atom лент
await rss_read.execute(
    url="https://news.ycombinator.com/rss",
    max_entries=10
)
```
**Возможности:** feedparser, парсинг RSS/Atom, метаданные

#### 4. wikipedia
```python
# Поиск в Wikipedia
await wikipedia.execute(
    query="Artificial Intelligence",
    language="en",
    sentences=5
)
```
**Возможности:** Поиск, summary, мультиязычность

#### 5. screenshot_ocr
```python
# Скриншот экрана + OCR
await screenshot_ocr.execute(
    save_path="screen.png",
    monitor=0
)
```
**Возможности:** Pillow + Tesseract, мультимонитор

#### 6. pdf_read
```python
# Чтение PDF с таблицами
await pdf_read.execute(
    file_path="document.pdf",
    max_pages=10,
    extract_structure=True
)
```
**Возможности:** pdfplumber, текст + таблицы, метаданные

#### 7. python_execute
```python
# Python REPL с персистентным namespace
await python_execute.execute(
    code="x = 42; print(x * 2)",
    timeout=5
)
```
**Возможности:** Sandbox, persistent namespace, timeout, stdout/stderr

---

### Phase 2: Advanced Capabilities (Продвинутые)

#### 8. browser
```python
# Автоматизация браузера
await browser.execute(action="navigate", url="https://github.com")
await browser.execute(action="click", selector=".star-button")
await browser.execute(action="screenshot", save_path="page.png")
```
**Возможности:** Playwright, Chromium, клики, формы, скриншоты

#### 9. vision_analyze
```python
# Анализ изображений через LLaVA
await vision_analyze.execute(
    image_path="photo.jpg",
    prompt="What objects do you see?"
)
```
**Возможности:** LLaVA (Ollama), описание, объекты, текст на изображении

#### 10. audio_transcribe
```python
# Расшифровка аудио
await audio_transcribe.execute(
    audio_path="recording.mp3",
    language="auto"
)
```
**Возможности:** Whisper, mp3/wav/m4a/ogg, автоопределение языка

#### 11. knowledge_graph
```python
# Граф знаний
await knowledge_graph.execute(action="add_concept", concept="Python")
await knowledge_graph.execute(
    action="add_relation",
    from_concept="Python",
    to_concept="ML",
    relation_type="used_in"
)
await knowledge_graph.execute(action="get_neighbors", concept="Python")
```
**Возможности:** NetworkX, nodes, edges, связи, персистентность

#### 12. telegram (integration)
```yaml
# config.yaml
telegram:
  enabled: true
  bot_token: "YOUR_TOKEN"
  chat_id: "YOUR_CHAT_ID"
  poll_interval: 30
```
**Возможности:** Автосинхронизация inbox/outbox, двусторонняя

---

### Phase 3: External Integrations (Внешние сервисы)

#### 13. email
```python
# Отправка письма
await email.execute(
    action="send",
    to="user@example.com",
    subject="Report",
    body="Analysis complete"
)

# Проверка входящих
await email.execute(
    action="check_inbox",
    limit=10
)
```
**Возможности:** SMTP/IMAP, отправка/получение, вложения

#### 14. calendar
```python
# Создание события
await calendar.execute(
    action="create",
    title="Team meeting",
    start_time="2026-02-24T14:00:00",
    end_time="2026-02-24T15:00:00",
    description="Weekly sync"
)

# Ближайшие события
await calendar.execute(action="upcoming", days=7)
```
**Возможности:** Создание, просмотр, удаление, JSON-based

#### 15. file_ops
```python
# Копирование файла
await file_ops.execute(
    action="copy",
    source="data.csv",
    destination="backup/data.csv"
)

# Поиск файлов
await file_ops.execute(
    action="search",
    pattern="*.pdf"
)

# Информация о файле
await file_ops.execute(
    action="get_info",
    source="document.pdf"
)
```
**Возможности:** copy, move, search, info, безопасность

#### 16. web_api
```python
# GET запрос
await web_api.execute(
    method="GET",
    url="https://api.github.com/repos/kutO-O/digital-being"
)

# POST запрос
await web_api.execute(
    method="POST",
    url="https://api.example.com/data",
    headers={"Authorization": "Bearer token"},
    body={"key": "value"}
)
```
**Возможности:** GET, POST, PUT, DELETE, headers, JSON body

#### 17. system_stats
```python
# Мониторинг системы
await system_stats.execute(detailed=True)
```
**Возможности:** CPU, RAM, disk, network, процессы

---

## 🚀 Реальные сценарии

### 📰 Автоматический мониторинг новостей

```python
# 1. Поиск новостей
results = await duckduckgo_search.execute(query="AI breakthrough 2026")

# 2. Открыть в браузере
await browser.execute(action="navigate", url=results['results'][0]['url'])

# 3. Скриншот страницы
await browser.execute(action="screenshot", save_path="news.png")

# 4. Анализ с помощью Vision AI
vision = await vision_analyze.execute(
    image_path="news.png",
    prompt="Summarize the key points of this article"
)

# 5. Добавить в граф знаний
await knowledge_graph.execute(
    action="add_concept",
    concept=vision['description'][:50]
)
await knowledge_graph.execute(action="save")

# 6. Отправить отчёт по email
await email.execute(
    action="send",
    to="user@example.com",
    subject="AI News Digest",
    body=f"Summary:\n{vision['description']}"
)

# 7. Уведомить в Telegram (автоматически через outbox.txt)
```

### 📅 Автоматическое управление расписанием

```python
# Ежедневно в 8:00
# 1. Проверить события на сегодня
events = await calendar.execute(action="upcoming", days=1)

# 2. Проверить email
emails = await email.execute(action="check_inbox", limit=10)

# 3. Создать отчёт с Python
await python_execute.execute(code="""
import json
events_count = {len(events['events'])}
emails_count = {len(emails['emails'])}
report = f'Today: {events_count} events, {emails_count} new emails'
print(report)
""")

# 4. Отправить в Telegram
# (автоматически через social_layer)
```

### 🔍 Интеллектуальный поиск и анализ

```python
# Пользователь: "Найди информацию о quantum computing и сохрани в базу знаний"

# Агент автоматически:

# 1. Поиск
results = await duckduckgo_search.execute(query="quantum computing basics")

# 2. Чтение статьи
for result in results['results'][:3]:
    content = await url_reader.execute(url=result['url'])
    
    # 3. Анализ с помощью Python
    await python_execute.execute(code=f"""
text = '''{content['text']}'''
words = len(text.split())
print(f'Analyzed {words} words')
""")
    
    # 4. Сохранение в граф знаний
    await knowledge_graph.execute(
        action="add_concept",
        concept="Quantum Computing"
    )
    await knowledge_graph.execute(
        action="add_relation",
        from_concept="Quantum Computing",
        to_concept="Physics",
        relation_type="part_of"
    )

# 5. Сохранение
await knowledge_graph.execute(action="save")

# 6. Отправка ответа через Telegram
```

---

## 📊 Статистика по категориям

| Категория | Инструменты | Возможности |
|-----------|-------------|---------------|
| 🌐 Web | 7 | Поиск, чтение, браузер, API |
| 👁️ Vision | 3 | OCR, Vision AI, PDF |
| 🎤 Audio | 1 | Whisper transcription |
| 💻 Compute | 1 | Python REPL |
| 💾 Files | 2 | Shell + Advanced ops |
| 🕸️ Memory | 1 | Knowledge graph |
| ✉️ Comm | 2 | Email + Telegram |
| 📅 Productivity | 2 | Calendar + Stats |
| **Всего** | **20** | **Full autonomy** |

---

## 🛠️ Установка

### Базовые зависимости

```bash
pip install -r requirements.txt
```

### Дополнительные зависимости

```bash
# Playwright для browser
playwright install chromium

# LLaVA для vision_analyze
ollama pull llava

# Tesseract для screenshot_ocr
sudo apt install tesseract-ocr tesseract-ocr-rus  # Ubuntu/Debian
brew install tesseract tesseract-lang              # macOS

# ffmpeg для audio_transcribe
sudo apt install ffmpeg  # Ubuntu/Debian
brew install ffmpeg      # macOS
```

### Конфигурация

```yaml
# config.yaml

# Telegram
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
  poll_interval: 30

# Email
email:
  enabled: true
  address: "your@email.com"
  password: "your_password"
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  imap_server: "imap.gmail.com"
  imap_port: 993
```

---

## 📚 Документация

- [PHASE1_SENSORY_TOOLS.md](PHASE1_SENSORY_TOOLS.md) — органы чувств
- [PHASE2_ADVANCED_CAPABILITIES.md](PHASE2_ADVANCED_CAPABILITIES.md) — продвинутые возможности
- [PHASE3_EXTERNAL_INTEGRATIONS.md](PHASE3_EXTERNAL_INTEGRATIONS.md) — внешние интеграции

---

**Автор:** kutO-O + AI Assistant  
**Версия:** 1.0.0 (Complete Toolset)  
**Дата:** February 23, 2026
