"""
Digital Being - Message Broker
Stage 27: Message queue and routing between agents.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable, Optional

from core.message_protocol import Message, MessageType, Priority

log = logging.getLogger("digital_being.message_broker")


class MessageBroker:
    """Message broker for agent-to-agent communication."""
    
    def __init__(self, agent_id: str, storage_dir: Path):
        self._agent_id = agent_id
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Message queues per priority
        self._queues: dict[Priority, deque[Message]] = {
            Priority.CRITICAL: deque(),
            Priority.HIGH: deque(),
            Priority.NORMAL: deque(),
            Priority.LOW: deque()
        }
        
        # Message handlers by type
        self._handlers: dict[MessageType, list[Callable]] = defaultdict(list)
        
        # Sent messages (for tracking and replies)
        self._sent: dict[str, Message] = {}
        
        # Pending replies (msg_id -> future)
        self._pending_replies: dict[str, asyncio.Future] = {}
        
        # Track processed message IDs to avoid duplicates
        self._processed_ids: set[str] = set()
        
        self._load_queue()
        log.info(f"MessageBroker initialized for agent {agent_id}")
    
    def send(self, message: Message) -> str:
        """Send a message to another agent."""
        # Store in sent messages
        self._sent[message.msg_id] = message
        
        # If waiting for reply, create future
        if message.msg_type in (MessageType.QUERY, MessageType.TASK, MessageType.CONSENSUS):
            self._pending_replies[message.msg_id] = asyncio.Future()
        
        # Persist message
        self._persist_message(message, "sent")
        
        log.debug(
            f"[{self._agent_id}] Sent {message.msg_type.value} to {message.to_agent}: "
            f"{message.msg_id[:8]}"
        )
        
        return message.msg_id
    
    def receive(self, message: Message):
        """Receive a message from another agent."""
        # Skip if already processed
        if message.msg_id in self._processed_ids:
            return
        
        # Check if expired
        if message.is_expired():
            log.warning(f"Dropped expired message: {message.msg_id[:8]}")
            return
        
        # Add to appropriate queue
        self._queues[message.priority].append(message)
        self._processed_ids.add(message.msg_id)
        
        # Persist
        self._persist_message(message, "received")
        
        log.debug(
            f"[{self._agent_id}] Received {message.msg_type.value} from {message.from_agent}: "
            f"{message.msg_id[:8]}"
        )
        
        # If it's a reply to pending request, resolve future
        if message.reply_to and message.reply_to in self._pending_replies:
            future = self._pending_replies.pop(message.reply_to)
            if not future.done():
                future.set_result(message)
    
    async def wait_for_reply(self, msg_id: str, timeout: float = 30.0) -> Optional[Message]:
        """Wait for reply to a message."""
        if msg_id not in self._pending_replies:
            return None
        
        try:
            reply = await asyncio.wait_for(self._pending_replies[msg_id], timeout=timeout)
            return reply
        except asyncio.TimeoutError:
            log.warning(f"Timeout waiting for reply to {msg_id[:8]}")
            self._pending_replies.pop(msg_id, None)
            return None
    
    def get_next_message(self) -> Optional[Message]:
        """Get next message from queue (priority-based)."""
        # Check queues in priority order
        for priority in [Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW]:
            queue = self._queues[priority]
            if queue:
                return queue.popleft()
        return None
    
    def peek_queue(self, max_count: int = 10) -> list[Message]:
        """Peek at queue without removing messages."""
        messages = []
        for priority in [Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW]:
            for msg in self._queues[priority]:
                messages.append(msg)
                if len(messages) >= max_count:
                    return messages
        return messages
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register a handler for message type."""
        self._handlers[msg_type].append(handler)
        log.debug(f"Registered handler for {msg_type.value}")
    
    async def process_messages(self, batch_size: int = 5):
        """Process pending messages."""
        processed = 0
        
        while processed < batch_size:
            message = self.get_next_message()
            if not message:
                break
            
            # Call registered handlers
            handlers = self._handlers.get(message.msg_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    log.error(f"Handler error for {message.msg_type.value}: {e}")
            
            processed += 1
        
        return processed
    
    def get_queue_size(self) -> dict[str, int]:
        """Get queue sizes by priority."""
        return {
            priority.name: len(queue)
            for priority, queue in self._queues.items()
        }
    
    def get_stats(self) -> dict:
        """Get broker statistics."""
        total_queued = sum(len(q) for q in self._queues.values())
        return {
            "agent_id": self._agent_id,
            "total_sent": len(self._sent),
            "total_queued": total_queued,
            "pending_replies": len(self._pending_replies),
            "queue_sizes": self.get_queue_size()
        }
    
    def _persist_message(self, message: Message, direction: str):
        """Persist message to disk."""
        try:
            log_file = self._storage_dir / f"{direction}_messages.jsonl"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(message.to_json() + "\n")
        except Exception as e:
            log.error(f"Failed to persist message: {e}")
    
    def _load_queue(self):
        """Load received messages from disk on startup."""
        log_file = self._storage_dir / "received_messages.jsonl"
        if not log_file.exists():
            return
        
        try:
            with log_file.open("r", encoding="utf-8") as f:
                for line in f:
                    msg = Message.from_json(line.strip())
                    if not msg.is_expired() and msg.msg_id not in self._processed_ids:
                        self._queues[msg.priority].append(msg)
                        self._processed_ids.add(msg.msg_id)
            
            log.info(f"Loaded {sum(len(q) for q in self._queues.values())} messages from disk")
        except Exception as e:
            log.error(f"Failed to load queue: {e}")
    
    # Shared message delivery methods
    def _save_to_disk(self):
        """Save sent messages to shared storage."""
        if not self._sent:
            return
        
        try:
            shared_file = self._storage_dir / "shared_outbox.jsonl"
            with shared_file.open("a", encoding="utf-8") as f:
                for msg in self._sent.values():
                    f.write(msg.to_json() + "\n")
        except Exception as e:
            log.error(f"Failed to save to shared storage: {e}")
    
    def _load_from_disk(self):
        """Load messages from shared storage."""
        shared_file = self._storage_dir / "shared_outbox.jsonl"
        if not shared_file.exists():
            return
        
        try:
            with shared_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    msg = Message.from_json(line.strip())
                    
                    # Skip own messages
                    if msg.from_agent == self._agent_id:
                        continue
                    
                    # Skip if not for this agent and not broadcast
                    if msg.to_agent != self._agent_id and msg.to_agent != "*":
                        continue
                    
                    # Skip if already processed
                    if msg.msg_id in self._processed_ids:
                        continue
                    
                    # Receive the message
                    self.receive(msg)
        
        except Exception as e:
            log.error(f"Failed to load from shared storage: {e}")
