"""
Add this to social_layer.py for inbox persistence.

Add _persist_inbox() method and call it in check_inbox().
"""

def _persist_inbox(self) -> None:
    """
    Atomically persist unread inbox messages to conversations.json.
    Prevents message loss on restart if LLM is unavailable.
    """
    if self._conversations_path is None:
        return
    
    tmp_path = self._conversations_path.with_suffix(".tmp")
    try:
        # Load existing conversations
        if self._conversations_path.exists():
            with self._conversations_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"incoming": [], "outgoing": [], "pending_inbox": []}
        
        # Update pending inbox
        data["pending_inbox"] = self._inbox_messages
        
        # Atomic write
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self._conversations_path)
        
        log.debug(f"Inbox persisted: {len(self._inbox_messages)} pending messages")
    except OSError as e:
        log.error(f"[_persist_inbox] Failed to persist: {e}")
        if tmp_path.exists():
            tmp_path.unlink()


def _load_pending_inbox(self) -> None:
    """
    Load pending inbox messages from conversations.json on startup.
    Call this in __init__() or load_conversations().
    """
    if not self._conversations_path.exists():
        return
    
    try:
        with self._conversations_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        pending = data.get("pending_inbox", [])
        self._inbox_messages.extend(pending)
        log.info(f"Loaded {len(pending)} pending inbox messages from last session")
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Could not load pending inbox: {e}")


# Modify check_inbox() method:
def check_inbox(self) -> list[dict]:
    # ... existing code ...
    
    # 🔴 ADD AT END:
    self._persist_inbox()  # Save unread messages
    
    return new_messages


# Modify __init__() or load_conversations():
# 🔴 ADD AFTER self._inbox_messages = []:
self._load_pending_inbox()  # Restore pending messages from last session
