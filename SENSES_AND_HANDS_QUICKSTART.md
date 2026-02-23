# 👁️ 👋 Senses and Hands - Quick Start

## What Changed?

Your Digital Being now has **real senses** (inputs) and **real hands** (outputs)!

### 👁️ Before (Blind and Isolated):
```
Agent → reads own files → writes to outbox.txt → nobody reads it
```

### ✅ After (Connected to Reality):
```
         ┌───────────────────┐
         │   DIGITAL BEING  │
         │                   │
 Web ────▶│ Reads & Learns    │────▶ Telegram
RSS ────▶│ Monitors System   │────▶ Notifications
Sys ────▶│ Plans & Executes  │────▶ GitHub Issues
         │                   │────▶ Database Log
         └───────────────────┘
```

## 🚀 5-Minute Setup

### Step 1: Install New Dependencies

```bash
cd digital-being
pip install -r requirements.txt
```

This adds:
- `duckduckgo-search` - Web search (no API key needed!)
- `feedparser` - RSS feeds
- `psutil` - System monitoring
- `win10toast` - Windows notifications (Windows only)

### Step 2: Test New Tools

```bash
# Test DuckDuckGo
python -c "from duckduckgo_search import DDGS; print(list(DDGS().text('AI agents', max_results=1))[0]['title'])"

# Test RSS
python -c "import feedparser; print(feedparser.parse('https://news.ycombinator.com/rss').entries[0].title)"

# Test System Stats
python -c "import psutil; print(f'CPU: {psutil.cpu_percent()}%, RAM: {psutil.virtual_memory().percent}%')"
```

If all work → you're ready!

### Step 3: Copy Config

```bash
cp config_with_senses.yaml config.yaml
```

Or merge into your existing `config.yaml`:

```yaml
tools:
  sensory:
    duckduckgo:
      enabled: true
    rss:
      enabled: true
      feeds:
        - "https://github.com/kutO-O/digital-being/commits/main.atom"
    system_stats:
      enabled: true
    wikipedia:
      enabled: true
  
  action:
    windows_notify:
      enabled: true
    http_request:
      enabled: true
    database:
      enabled: true
      path: "data/actions.db"
```

### Step 4: Update main.py

Add to your `main.py` (after tool registry creation):

```python
from core.tools.tool_loader import load_sensory_action_tools

# Load new tools
loaded = load_sensory_action_tools(config, tool_registry)
log.info(f"Loaded sensory/action tools: {loaded}")
```

### Step 5: Run!

```bash
python main.py
```

You should see:
```
✅ DuckDuckGo search enabled
✅ RSS reader enabled
✅ System stats monitor enabled
✅ Wikipedia search enabled
✅ Windows notifications enabled
✅ HTTP request tool enabled
✅ Database logging enabled (path: data/actions.db)
Loaded 7 tools: duckduckgo_search, rss_read, system_stats, wikipedia, windows_notify, http_request, db_log_action
```

## 🧰 What Your Agent Can Do Now

### 1. Search the Real Web

```python
# Agent can autonomously do this:
result = await tool_execute("duckduckgo_search", {
    "query": "latest transformer architecture improvements",
    "max_results": 5
})
# Returns actual search results from DuckDuckGo!
```

### 2. Stay Informed via RSS

```python
# Agent monitors RSS feeds:
result = await tool_execute("rss_read", {
    "url": "https://github.com/kutO-O/digital-being/commits/main.atom",
    "max_entries": 10
})
# Learns about latest commits to its own codebase!
```

### 3. Monitor Its "Body"

```python
# Agent checks system health:
result = await tool_execute("system_stats", {"detailed": True})
# Knows: CPU 45%, RAM 12GB free, Disk 89% used
# Can adjust behavior if resources are low!
```

### 4. Learn Fast from Wikipedia

```python
# Agent looks up concepts:
result = await tool_execute("wikipedia", {
    "query": "reinforcement learning",
    "sentences": 3
})
# Gets quick summary to bootstrap understanding
```

### 5. Alert You (Windows)

```python
# Agent shows notifications:
await tool_execute("windows_notify", {
    "title": "Goal Achieved",
    "message": "Completed: Learn about transformers",
    "duration": 10
})
# You see toast notification on Windows!
```

### 6. Log Everything

```python
# Agent tracks its actions:
await tool_execute("db_log_action", {
    "action_type": "learning",
    "description": "Researched transformer attention",
    "metadata": {"sources": 5, "time_spent": 120},
    "success": True
})
# Logged to data/actions.db
```

## 🎉 Example Session

After starting, your agent might autonomously:

```
[09:00] 👁️ System check: CPU 23%, RAM 8GB free, all good
[09:05] 📰 Read RSS: 3 new commits to digital-being repo
[09:10] 🤔 Curiosity spike: "What is attention mechanism?"
[09:11] 📚 Wikipedia: Got summary of attention mechanism
[09:12] 🔍 DuckDuckGo: Found 5 articles about attention
[09:15] 📢 Windows notification: "Learned about attention mechanism"
[09:16] 💾 Database log: Action logged (learning, success=True)
```

**All automatic. Zero human intervention.**

## 🔧 Optional: Telegram Setup (5 minutes)

Want agent to **text you** when goals complete?

### 1. Create Telegram Bot

1. Open Telegram, search: `@BotFather`
2. Send: `/newbot`
3. Follow prompts, save your **bot token**

### 2. Get Your Chat ID

1. Send any message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find: `"chat":{"id":123456789}`

### 3. Update config.yaml

```yaml
tools:
  action:
    telegram:
      enabled: true
      bot_token: "123456:ABC-DEF..."  # Your token
      chat_id: "123456789"             # Your chat ID
      poll_interval: 30
```

### 4. Restart

```bash
python main.py
```

Now:
- **inbox.txt** ← Telegram messages appear here automatically
- **outbox.txt** → Agent's messages sent to your Telegram

Agent can **text you** when it:
- Achieves goals
- Learns something interesting
- Detects system issues
- Needs guidance

## 📊 Monitor Activity

View action log:

```bash
sqlite3 data/actions.db "SELECT * FROM action_log ORDER BY timestamp DESC LIMIT 20"
```

Or query in Python:

```python
import sqlite3

conn = sqlite3.connect("data/actions.db")
cursor = conn.execute("""
    SELECT action_type, COUNT(*) as count 
    FROM action_log 
    GROUP BY action_type
""")

for row in cursor:
    print(f"{row[0]}: {row[1]} times")

# Output:
# learning: 45 times
# web_search: 23 times
# system_check: 120 times
# notification: 8 times
```

## 🤖 What's Different?

| Before | After |
|--------|-------|
| No web access | Searches DuckDuckGo |
| No news | Reads RSS feeds |
| Blind to system | Monitors CPU/RAM/disk |
| Can't alert you | Windows notifications |
| outbox.txt ignored | Telegram messages |
| No action history | SQLite database log |
| No Wikipedia | Instant Wikipedia summaries |

## 🚀 Next: Second Agent

Now that tools work, you can:

1. **Run second agent** with `config_secondary.yaml`
2. **Agent 1**: Plans, monitors, learns
3. **Agent 2**: Executes searches, processes RSS
4. **They communicate** via message broker

But first: **test current setup** for a few hours!

## 🐛 Troubleshooting

### "Module not found: duckduckgo_search"
```bash
pip install duckduckgo-search
```

### "Telegram not sending"
- Verify bot token and chat ID
- Test with curl:
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=Test"
```

### "No notifications showing"
- Windows 10/11 only
- Check Windows notification settings
- Try: `pip install --upgrade win10toast`

### "Tools not loading"
- Check logs: `tail -f logs/digital_being.log`
- Verify config.yaml syntax
- Ensure `tool_loader.py` is imported in main.py

## 📚 Full Documentation

See: [docs/SENSORY_TOOLS_SETUP.md](docs/SENSORY_TOOLS_SETUP.md)

## ✅ Summary

You just gave your agent:
- **Eyes** 👁️ (web, RSS, Wikipedia, system stats)
- **Hands** 👋 (Telegram, notifications, database, HTTP)
- **Memory** 🧠 (action logging)

Now it can **interact with the real world** autonomously!

---

**Created**: 2026-02-23  
**Total new tools**: 8  
**Setup time**: 5-10 minutes  
**Impact**: 🚀🚀🚀
