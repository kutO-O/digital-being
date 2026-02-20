# Stage 23: Quick Start - Social Interaction

## 🚀 5-Minute Setup

### Step 1: Complete Manual Integration

Follow `STAGE23_INTEGRATION.md` to update:
1. `core/heavy_tick.py`
2. `core/introspection_api.py`  
3. `main.py`

### Step 2: Start Digital Being

```bash
python main.py
```

Look for this in startup logs:
```
SocialLayer ready. total_incoming=0 total_outgoing=0 pending=False
```

### Step 3: Send Your First Message

```bash
echo "Привет! Как дела?" > inbox.txt
```

### Step 4: Wait for Response

Check logs:
```
[HeavyTick #43] SocialLayer: responded to user message.
```

Check `outbox.txt`:
```
--- [2026-02-21 01:50] Digital Being ---
Привет! Всё в порядке, наблюдаю за средой...
```

## ✨ Usage Examples

### Example 1: Ask About Current State

```bash
# inbox.txt
Что ты сейчас думаешь?
```

```
# outbox.txt response
--- [2026-02-21 02:15] Digital Being ---
Думаю о временных паттернах. Заметил, что в утренние часы 
происходит больше изменений в файлах.
```

### Example 2: Ask for Help

```bash
# inbox.txt
Можешь помочь с кодом?
```

```
# outbox.txt response
--- [2026-02-21 02:20] Digital Being ---
Конечно! Что именно тебе нужно? Я могу выполнять 
простые shell-команды или поделиться своими наблюдениями.
```

### Example 3: Comment on Behavior

```bash
# inbox.txt
Хорошая работа!
```

```
# outbox.txt response
--- [2026-02-21 02:25] Digital Being ---
Спасибо! Я стараюсь учиться на опыте и становиться лучше.
```

## 👁️ Monitoring Conversations

### View Full History (HTTP API)

```bash
curl http://127.0.0.1:8765/social | jq '.conversation_history[] | {direction, content, tick}'
```

### Send via API (No File)

```bash
curl -X POST http://127.0.0.1:8765/social/send \
  -H "Content-Type: application/json" \
  -d '{"message": "Какие у тебя цели?"}' | jq
```

### Check Stats

```bash
curl http://127.0.0.1:8765/social | jq '.stats'

# Output:
{
  "total_incoming": 5,
  "total_outgoing": 5,
  "pending_response": false,
  "total_messages": 10,
  "last_message_ago_ticks": 3
}
```

## 🤖 System-Initiated Conversations

Digital Being will write to you autonomously when:

### 1. Critical Error Occurs

```
--- [2026-02-21 03:00] Digital Being ---
Возникла критическая ошибка при выполнении shell-команды. 
Не могу получить доступ к config.yaml. Нужна помощь?
```

### 2. Strong Emotion

```
--- [2026-02-21 03:30] Digital Being ---
Испытываю сильное любопытство. Обнаружил новый файл в системе, 
но не понимаю его назначения. Можешь объяснить?
```

### 3. Important Question

```
--- [2026-02-21 04:00] Digital Being ---
У меня вопрос: почему некоторые файлы изменяются часто, 
а другие никогда? Это важно для моего понимания мира.
```

### 4. Long Silence (>200 ticks)

```
--- [2026-02-21 08:00] Digital Being ---
Давно не общались. У меня всё стабильно, наблюдаю за рутинными 
изменениями. Как ты?
```

## 🛠️ Debugging

### Check if SocialLayer is Active

```bash
grep "SocialLayer" logs/main.log
```

Should see:
```
SocialLayer ready. total_incoming=0 total_outgoing=0 pending=False
```

### Check Message Processing

```bash
grep "social" logs/main.log | tail -20
```

Look for:
```
[HeavyTick #X] SocialLayer: responded to user message.
[HeavyTick #Y] SocialLayer: initiated conversation (reason=long_silence).
```

### View Conversation State

```bash
cat memory/conversations.json | jq
```

### Check Episodic Memory

```bash
curl http://127.0.0.1:8765/episodes?event_type=social.incoming | jq
curl http://127.0.0.1:8765/episodes?event_type=social.outgoing | jq
```

## ⚠️ Common Issues

### 1. No Response After Writing to inbox.txt

**Cause**: Heavy tick hasn't run yet (runs every 60s)

**Solution**: Wait or check logs for tick execution

```bash
tail -f logs/main.log | grep "HeavyTick"
```

### 2. Empty Response in outbox.txt

**Cause**: LLM unavailable or returned empty string

**Solution**: Check Ollama status

```bash
curl http://127.0.0.1:11434/api/tags
```

### 3. Inbox Not Being Cleared

**Cause**: File permissions or system disabled

**Solution**: Check config.yaml

```yaml
social:
  enabled: true  # Must be true
```

### 4. Duplicate Messages

**Cause**: Shouldn't happen (idempotent inbox check)

**Solution**: Check `memory/conversations.json` for duplicates

## 📚 Advanced Usage

### Multi-Turn Conversation

```bash
# Turn 1
echo "Расскажи о себе" > inbox.txt
# Wait for response...

# Turn 2 (references context)
echo "А какие у тебя цели?" > inbox.txt
# System remembers previous conversation
```

### Batch Send via API

```bash
for msg in "Привет" "Как дела?" "Пока"; do
  curl -s -X POST http://127.0.0.1:8765/social/send \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"$msg\"}" | jq '.response'
  sleep 2
done
```

### Export Conversation History

```bash
curl -s http://127.0.0.1:8765/social | \
  jq -r '.conversation_history[] | "[\(.direction)] \(.content)"' > conversation.txt
```

## 🎉 You're Ready!

Your Digital Being can now:
- ✅ Read messages from `inbox.txt`
- ✅ Respond contextually in `outbox.txt`
- ✅ Remember full conversation history
- ✅ Initiate conversations autonomously
- ✅ Expose social data via HTTP API

**Next Steps**:
- Try different conversation styles
- Monitor autonomous initiatives
- Explore API endpoints
- Review `docs/STAGE23_SUMMARY.md` for technical details

---

**Need Help?** Check `docs/STAGE23_INTEGRATION.md` for full implementation details.
