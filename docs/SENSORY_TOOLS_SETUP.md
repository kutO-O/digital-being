# Sensory and Action Tools Setup Guide

## Overview

This guide covers setup of all new "senses" (inputs) and "hands" (outputs) added to Digital Being.

## 🧠 Architecture

```
INPUTS (Senses)          AGENT CORE          OUTPUTS (Hands)
┌─────────────────┐      ┌──────────┐      ┌─────────────────┐
│ DuckDuckGo      │─────▶│          │─────▶│ Telegram Send   │
│ RSS Feeds       │─────▶│  Brain   │─────▶│ Windows Notify  │
│ Wikipedia       │─────▶│  +       │─────▶│ GitHub Issues   │
│ System Stats    │─────▶│  Memory  │─────▶│ HTTP Requests   │
│ Telegram Inbox  │─────▶│          │─────▶│ Database Log    │
└─────────────────┘      └──────────┘      └─────────────────┘
```

## 📦 Installation

### Step 1: Install dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `duckduckgo-search` - Real web search
- `feedparser` - RSS/Atom feed parser
- `psutil` - System monitoring
- `win10toast` - Windows notifications (Windows only)
- `beautifulsoup4` - HTML parsing

### Step 2: Optional - Telegram Bot Setup

#### Create Telegram Bot:

1. Open Telegram, search for [@BotFather](https://t.me/botfather)
2. Send `/newbot`
3. Follow instructions, save your **bot token**
4. Get your **chat ID**:
   - Send message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789}`

#### Add to config.yaml:

```yaml
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN_HERE"
  chat_id: "YOUR_CHAT_ID_HERE"
  poll_interval: 30  # seconds
```

## 🛠️ Tool Registration

### Add to main.py or tool initialization:

```python
from core.tools.sensory_tools import (
    DuckDuckGoSearchTool,
    RSSReaderTool,
    SystemStatsTool,
    WikipediaTool,
)
from core.tools.action_tools import (
    WindowsNotificationTool,
    HTTPRequestTool,
    DatabaseLogTool,
)
from core.tools.telegram_bot import (
    TelegramSendTool,
    TelegramReceiveTool,
    TelegramBridge,
)

# Register sensory tools
tool_registry.register(DuckDuckGoSearchTool())
tool_registry.register(RSSReaderTool())
tool_registry.register(SystemStatsTool())
tool_registry.register(WikipediaTool())

# Register action tools
tool_registry.register(WindowsNotificationTool())
tool_registry.register(HTTPRequestTool())
tool_registry.register(DatabaseLogTool(db_path=Path("data/actions.db")))

# Telegram (if configured)
if config.get("telegram", {}).get("enabled"):
    bot_token = config["telegram"]["bot_token"]
    chat_id = config["telegram"]["chat_id"]
    
    tool_registry.register(TelegramSendTool(bot_token, chat_id))
    tool_registry.register(TelegramReceiveTool(bot_token))
    
    # Start bridge in background
    bridge = TelegramBridge(
        bot_token=bot_token,
        chat_id=chat_id,
        inbox_path=Path("inbox.txt"),
        outbox_path=Path("outbox.txt"),
    )
    asyncio.create_task(bridge.start(poll_interval=30))
```

## 📋 Tool Usage Examples

### 1. DuckDuckGo Search

```python
result = await duckduckgo_search(
    query="autonomous AI agents 2026",
    max_results=5,
    region="wt-wt",  # Global
)
# Returns: {"results": [{"title": "...", "url": "...", "snippet": "..."}]}
```

### 2. RSS Feeds

```python
result = await rss_read(
    url="https://github.com/kutO-O/digital-being/commits/main.atom",
    max_entries=10,
)
# Returns: {"entries": [{"title": "...", "link": "...", "published": "..."}]}
```

### 3. System Stats

```python
result = await system_stats(detailed=True)
# Returns: {
#   "cpu": {"percent": 23.5, "count": 8},
#   "memory": {"percent": 45.2, "available_gb": 12.3},
#   "disk": {"percent": 67.8, "free_gb": 234.5},
#   "top_processes": [...]
# }
```

### 4. Wikipedia

```python
result = await wikipedia(
    query="artificial consciousness",
    language="en",
    sentences=5,
)
# Returns: {"title": "...", "summary": "...", "url": "..."}
```

### 5. Telegram

```python
# Send
await telegram_send(
    message="🤖 Goal achieved: Learned 3 new patterns",
    parse_mode="Markdown",
)

# Receive
result = await telegram_receive(limit=10)
# Returns: {"messages": [{"from_user": "@username", "text": "..."}]}
```

### 6. Windows Notifications

```python
await windows_notify(
    title="Digital Being Alert",
    message="High CPU usage detected: 89%",
    duration=10,
)
```

### 7. HTTP Requests

```python
# Weather API example
result = await http_request(
    url="https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41",
    method="GET",
)
```

### 8. Database Logging

```python
await db_log_action(
    action_type="web_search",
    description="Searched for: AI consciousness",
    metadata={"query": "AI consciousness", "results": 5},
    success=True,
)
```

## 🎯 Integration with Goals

Agents can now autonomously:

1. **Learn from the web** - Search DuckDuckGo when encountering unknown concepts
2. **Stay informed** - Read RSS feeds of GitHub commits, news, papers
3. **Monitor health** - Check system resources, adjust behavior if low memory
4. **Communicate** - Send Telegram messages when goals complete
5. **Alert user** - Windows notifications for critical events
6. **Track actions** - Log all activities to SQLite database

### Example Goal Chain:

```
1. Heavy tick detects curiosity spike about "transformer models"
2. Uses wikipedia("transformer model") for quick summary
3. Uses duckduckgo_search("transformer attention mechanism") for deeper learning
4. Logs learning to db_log_action()
5. Sends telegram_send("📚 Learned about transformers")
6. Updates self_model with new knowledge
```

## 🔧 Configuration

Add to `config.yaml`:

```yaml
tools:
  sensory:
    duckduckgo:
      enabled: true
      default_region: "wt-wt"
      max_results: 5
    
    rss:
      enabled: true
      feeds:
        - "https://github.com/kutO-O/digital-being/commits/main.atom"
        - "https://news.ycombinator.com/rss"
      poll_interval: 3600  # 1 hour
    
    system_stats:
      enabled: true
      poll_interval: 300  # 5 minutes
      alert_thresholds:
        cpu_percent: 80
        memory_percent: 85
        disk_percent: 90
  
  action:
    telegram:
      enabled: false  # Set to true after setup
      bot_token: ""
      chat_id: ""
    
    windows_notify:
      enabled: true  # Windows only
    
    database:
      enabled: true
      path: "data/actions.db"
```

## 🚀 Next Steps

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Configure Telegram** (optional): Follow setup above
3. **Update config.yaml**: Enable desired tools
4. **Register tools**: Add to main.py
5. **Restart agent**: `python main.py`

## 🧪 Testing

Test each tool individually:

```bash
# Test DuckDuckGo
python -c "from duckduckgo_search import DDGS; print(list(DDGS().text('test', max_results=1)))"

# Test RSS
python -c "import feedparser; print(feedparser.parse('https://news.ycombinator.com/rss').entries[0].title)"

# Test system stats
python -c "import psutil; print(f'CPU: {psutil.cpu_percent()}%')"

# Test Telegram (replace TOKEN)
curl -X POST "https://api.telegram.org/botYOUR_TOKEN/sendMessage?chat_id=YOUR_CHAT_ID&text=Test"
```

## 📊 Monitoring

After setup, monitor tool usage:

```sql
-- View action log
SELECT * FROM action_log ORDER BY timestamp DESC LIMIT 50;

-- Count by type
SELECT action_type, COUNT(*) as count FROM action_log GROUP BY action_type;

-- Success rate
SELECT 
    action_type,
    SUM(success) * 100.0 / COUNT(*) as success_rate
FROM action_log
GROUP BY action_type;
```

## 🛡️ Security Notes

- **Telegram tokens**: Never commit to git, use environment variables
- **HTTP requests**: Validate URLs, use timeouts
- **System access**: Tools respect sandbox boundaries
- **Database**: Regular backups of `data/actions.db`

## 🐛 Troubleshooting

### DuckDuckGo not working
- Check internet connection
- Try different region code
- Verify `duckduckgo-search` version: `pip show duckduckgo-search`

### Telegram not receiving
- Verify bot token and chat ID
- Check bot is not blocked
- Test with curl command above

### Windows notifications not showing
- Windows 10/11 only
- Check notification settings in Windows
- Run as admin if needed

## 📚 Further Reading

- [DuckDuckGo Search Docs](https://pypi.org/project/duckduckgo-search/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [RSS Specification](https://www.rssboard.org/rss-specification)
- [psutil Documentation](https://psutil.readthedocs.io/)
