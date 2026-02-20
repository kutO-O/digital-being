# Stage 23: Social Interaction Layer - Integration Guide

## ✅ Completed

1. **core/social_layer.py** - Full implementation [cite:51]
2. **docs/stage23_introspection_patch.md** - API endpoints patch [cite:56]
3. **docs/stage23_heavy_tick_full.py** - HeavyTick integration reference [cite:55]
4. **config.yaml** - Updated with social section [cite:56]
5. **README.md** - Stage 23 documentation [cite:56]

## ⚠️ Manual Steps Required

### 1. Fix heavy_tick.py

The file was too large to update automatically. You need to:

```python
# 1. Add import at top (in TYPE_CHECKING block):
from core.social_layer import SocialLayer  # Stage 23

# 2. Add parameter to __init__():
def __init__(
    ...
    time_perception: "TimePerception | None" = None,
    social_layer: "SocialLayer | None" = None,  # Stage 23
) -> None:

# 3. Add instance variable in __init__():
self._social = social_layer  # Stage 23

# 4. Add call in _run_tick() after await self._step_time_perception(n):
await self._step_social_interaction(n)  # Stage 23

# 5. Add two new methods (copy from commit bdf3b8ef or see below):
```

```python
async def _step_social_interaction(self, n: int) -> None:
    if self._social is None:
        return
    
    loop = asyncio.get_event_loop()
    
    # Check for incoming messages
    new_messages = await loop.run_in_executor(None, self._social.check_inbox)
    
    if new_messages:
        for msg in new_messages:
            # Update tick in message
            msg["tick"] = n
            
            # Add to memory
            self._mem.add_episode(
                "social.incoming",
                f"Пользователь написал: {msg['content'][:200]}",
                outcome="success",
                data={"message_id": msg["id"]}
            )
            
            # Generate response
            context = self._build_social_context()
            response = await loop.run_in_executor(
                None,
                lambda: self._social.generate_response(msg, context, self._ollama)
            )
            
            if response:
                # Send response
                outgoing = self._social.add_outgoing(response, n, response_to=msg["id"])
                await loop.run_in_executor(None, lambda: self._social.write_to_outbox(response))
                self._social.mark_responded(msg["id"])
                
                self._mem.add_episode(
                    "social.outgoing",
                    f"Ответил пользователю: {response[:200]}",
                    outcome="success"
                )
                
                log.info(f"[HeavyTick #{n}] SocialLayer: responded to user message.")
            else:
                # LLM unavailable
                self._mem.add_episode(
                    "social.llm_unavailable",
                    "Не удалось сгенерировать ответ — LLM недоступен",
                    outcome="error"
                )
                log.warning(f"[HeavyTick #{n}] SocialLayer: failed to generate response (LLM unavailable).")
    
    # Check if should initiate conversation
    should_write, reason = await loop.run_in_executor(
        None,
        lambda: self._social.should_initiate(
            n, self._world, self._emotions, self._curiosity
        )
    )
    
    if should_write:
        context = self._build_social_context()
        message = await loop.run_in_executor(
            None,
            lambda: self._social.generate_initiative(reason, context, self._ollama)
        )
        
        if message:
            outgoing = self._social.add_outgoing(message, n)
            await loop.run_in_executor(None, lambda: self._social.write_to_outbox(message))
            
            self._mem.add_episode(
                "social.initiative",
                f"Написал пользователю (reason={reason}): {message[:200]}",
                outcome="success"
            )
            
            log.info(f"[HeavyTick #{n}] SocialLayer: initiated conversation (reason={reason}).")
        else:
            log.warning(f"[HeavyTick #{n}] SocialLayer: failed to generate initiative message.")

def _build_social_context(self) -> str:
    """Построить контекст для social interaction."""
    parts = [
        self._self_model.to_prompt_context(),
        self._values.to_prompt_context(),
    ]
    
    if self._emotions:
        parts.append(self._emotions.to_prompt_context())
    
    if self._beliefs:
        parts.append(self._beliefs.to_prompt_context(3))
    
    if self._time_perc:
        parts.append(self._time_perc.to_prompt_context(2))
    
    return "\n".join(parts)
```

```python
# 6. Update docstring:
"""
Digital Being — HeavyTick
Stage 23: SocialLayer integration for async user communication.

Note: TimePerception hour_of_day parsing only uses HH:00 from "14:00-15:00" format.
Minutes are intentionally ignored as a reasonable simplification for current version.
"""
```

### 2. Update introspection_api.py

Follow instructions in `docs/stage23_introspection_patch.md`:

1. Add import in TYPE_CHECKING block
2. Add two routes in `start()` method
3. Add `_handle_social()` method
4. Add `_handle_social_send()` method

### 3. Update main.py

Add SocialLayer initialization:

```python
# Add import at top
from core.social_layer import SocialLayer

# Add after time_perception initialization (around line 450):
social_cfg = cfg.get("social", {})
social_enabled = bool(social_cfg.get("enabled", True))
social_layer = None
if social_enabled:
    social_layer = SocialLayer(
        inbox_path=ROOT_DIR / "inbox.txt",
        outbox_path=ROOT_DIR / "outbox.txt",
        memory_dir=ROOT_DIR / "memory"
    )
    social_layer.load()
    social_stats = social_layer.get_stats()
    logger.info(
        f"SocialLayer ready. total_incoming={social_stats['total_incoming']} "
        f"total_outgoing={social_stats['total_outgoing']} pending={social_stats['pending_response']}"
    )
else:
    logger.info("SocialLayer disabled.")

# Add social_layer parameter to HeavyTick (around line 480):
heavy = HeavyTick(
    ...
    time_perception=time_perc,
    social_layer=social_layer,  # Stage 23
)

# Add to IntrospectionAPI components (around line 500):
api = IntrospectionAPI(
    ...
    components={
        ...
        "time_perception": time_perc,
        "social_layer": social_layer,  # Stage 23
    },
    ...
)

# Add to startup summary (around line 530):
if social_layer:
    social_stats = social_layer.get_stats()
    logger.info(
        f"  SocialLayer  : messages={social_stats['total_messages']} "
        f"pending={social_stats['pending_response']}"
    )
```

## Testing

1. Start the system: `python main.py`
2. Write message in `inbox.txt`: "Hello! How are you?"
3. Save the file
4. Wait for next heavy tick (~60s)
5. Check `outbox.txt` for response
6. Test API: `curl http://127.0.0.1:8765/social | jq`

## Files Structure

```
digital-being/
├── core/
│   └── social_layer.py          ✅ Created
├── memory/
│   └── conversations.json        ✅ Auto-created on first run
├── inbox.txt                     ✅ Already exists
├── outbox.txt                    ✅ Already exists
├── config.yaml                   ✅ Updated
├── README.md                     ✅ Updated
└── docs/
    ├── stage23_introspection_patch.md  ✅ Created
    └── stage23_heavy_tick_full.py      ✅ Created
```

## Stage 23 Complete! 🎉

Once manual steps are done, the system will be able to:
- Read messages from `inbox.txt` asynchronously
- Generate contextual responses using LLM
- Write responses to `outbox.txt` with timestamps
- Initiate conversations on critical events
- Remember conversation history
- Expose conversation data via HTTP API
