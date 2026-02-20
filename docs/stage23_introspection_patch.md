# Stage 23: IntrospectionAPI Social Endpoints Patch

## Add to start() method after app.router.add_get("/time", self._handle_time):

```python
app.router.add_get("/social", self._handle_social)  # Stage 23
app.router.add_post("/social/send", self._handle_social_send)  # Stage 23
```

## Add social_layer import to TYPE_CHECKING:

```python
from core.social_layer import SocialLayer  # Stage 23
```

## Add two new handlers:

```python
async def _handle_social(self, request: web.Request) -> web.Response:
    """GET /social - Stage 23"""
    try:
        social = self._c.get("social_layer")
        if not social:
            return self._json({"error": "SocialLayer not available"})
        
        messages = social._state.get("messages", [])
        conversation_history = messages[-10:]  # Last 10 messages
        stats = social.get_stats()
        pending_response = social._state.get("pending_response", False)
        
        return self._json({
            "conversation_history": conversation_history,
            "stats": stats,
            "pending_response": pending_response,
        })
    except Exception as e:
        return self._error(e)

async def _handle_social_send(self, request: web.Request) -> web.Response:
    """POST /social/send - Stage 23
    
    Force add incoming message and generate response.
    Body: {"message": "text"}
    """
    try:
        social = self._c.get("social_layer")
        ollama = self._c.get("ollama")
        heavy = self._c.get("heavy_tick")
        
        if not social or not ollama:
            return self._json({"error": "SocialLayer or Ollama not available"})
        
        data = await request.json()
        message = data.get("message", "")
        
        if not message:
            return self._json({"error": "Missing message"})
        
        # Add incoming message
        tick = getattr(heavy, "_tick_count", 0) if heavy else 0
        msg = social.add_incoming(message, tick)
        
        # Generate response using build_social_context from heavy_tick
        context = ""
        if heavy and hasattr(heavy, "_build_social_context"):
            context = heavy._build_social_context()
        else:
            # Fallback simple context
            values = self._c.get("value_engine")
            self_model = self._c.get("self_model")
            if self_model:
                context = self_model.to_prompt_context()
            if values:
                context += "\n" + values.to_prompt_context()
        
        response = social.generate_response(msg, context, ollama)
        
        if response:
            outgoing = social.add_outgoing(response, tick, response_to=msg["id"])
            social.write_to_outbox(response)
            social.mark_responded(msg["id"])
            
            return self._json({
                "success": True,
                "message": message,
                "response": response,
                "outgoing_id": outgoing["id"],
            })
        else:
            return self._json({"error": "Failed to generate response"})
    
    except Exception as e:
        return self._error(e)
```
