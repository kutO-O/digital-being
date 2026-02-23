"""Message Bus for Inter-Agent Communication.

Enables asynchronous message passing between agents:
- Request/Response patterns
- Broadcast messages
- Topic-based subscriptions
- Priority messaging
- Delivery tracking

Phase 3 - Multi-Agent System
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Set

log = logging.getLogger("digital_being.multi_agent.message_bus")


class MessageType(Enum):
    """Types of messages in the system."""
    REQUEST = "request"              # Request for action/info
    RESPONSE = "response"            # Response to request
    BROADCAST = "broadcast"          # Message to all agents
    NOTIFICATION = "notification"    # Event notification
    COMMAND = "command"              # Direct command


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class Message:
    """Represents a message between agents."""
    message_id: str
    from_agent: str
    to_agent: Optional[str]  # None for broadcast
    message_type: MessageType
    priority: MessagePriority
    
    # Content
    topic: str
    payload: Dict[str, Any]
    
    # Metadata
    timestamp: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    requires_ack: bool = False
    in_reply_to: Optional[str] = None
    
    # Tracking
    delivered: bool = False
    acknowledged: bool = False
    delivered_at: Optional[float] = None
    acknowledged_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "requires_ack": self.requires_ack,
            "in_reply_to": self.in_reply_to,
            "delivered": self.delivered,
            "acknowledged": self.acknowledged,
        }
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class MessageBus:
    """
    Central message bus for agent communication.
    
    Features:
    - Asynchronous message delivery
    - Priority-based message queue
    - Topic subscriptions
    - Broadcast support
    - Message acknowledgments
    - History logging
    
    Example:
        bus = MessageBus()
        
        # Subscribe to topic
        async def handle_research(msg: Message):
            print(f"Research request: {msg.payload}")
        
        bus.subscribe("agent_1", "research", handle_research)
        
        # Send message
        msg = Message(
            message_id=str(uuid.uuid4()),
            from_agent="coordinator",
            to_agent="agent_1",
            message_type=MessageType.REQUEST,
            priority=MessagePriority.HIGH,
            topic="research",
            payload={"query": "AI safety"}
        )
        await bus.send(msg)
    """
    
    def __init__(self, max_history: int = 1000, message_timeout: float = 300.0):
        """
        Args:
            max_history: Maximum messages to keep in history
            message_timeout: Seconds before undelivered message expires
        """
        self._max_history = max_history
        self._message_timeout = message_timeout
        
        # Message storage
        self._pending: Dict[str, asyncio.PriorityQueue] = defaultdict(
            lambda: asyncio.PriorityQueue()
        )
        self._history: Deque[Message] = deque(maxlen=max_history)
        self._messages: Dict[str, Message] = {}  # All messages by ID
        
        # Subscriptions: agent_id -> topic -> handlers
        self._subscriptions: Dict[str, Dict[str, List[Callable]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # Broadcast subscriptions: topic -> handlers
        self._broadcast_subs: Dict[str, List[Callable]] = defaultdict(list)
        
        # Statistics
        self._stats = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_acknowledged": 0,
            "total_expired": 0,
            "total_failed": 0,
        }
        
        self._running = False
        self._delivery_task: Optional[asyncio.Task] = None
        
        log.info(
            f"MessageBus initialized (max_history={max_history}, "
            f"timeout={message_timeout}s)"
        )
    
    def subscribe(
        self,
        agent_id: str,
        topic: str,
        handler: Callable[[Message], Any]
    ) -> None:
        """Subscribe agent to topic."""
        self._subscriptions[agent_id][topic].append(handler)
        log.info(f"Agent {agent_id} subscribed to topic '{topic}'")
    
    def unsubscribe(
        self,
        agent_id: str,
        topic: str,
        handler: Optional[Callable] = None
    ) -> None:
        """Unsubscribe agent from topic."""
        if handler:
            try:
                self._subscriptions[agent_id][topic].remove(handler)
            except ValueError:
                pass
        else:
            self._subscriptions[agent_id][topic].clear()
        
        log.info(f"Agent {agent_id} unsubscribed from topic '{topic}'")
    
    def subscribe_broadcast(
        self,
        topic: str,
        handler: Callable[[Message], Any]
    ) -> None:
        """Subscribe to broadcast messages on topic."""
        self._broadcast_subs[topic].append(handler)
        log.debug(f"Broadcast subscription added for topic '{topic}'")
    
    async def send(
        self,
        message: Message,
        timeout: Optional[float] = None
    ) -> None:
        """Send a message."""
        # Set expiry if not set
        if message.expires_at is None:
            message.expires_at = time.time() + (
                timeout or self._message_timeout
            )
        
        # Store message
        self._messages[message.message_id] = message
        self._history.append(message)
        self._stats["total_sent"] += 1
        
        # Add to queue
        if message.to_agent:
            # Direct message
            await self._pending[message.to_agent].put(
                (-message.priority.value, message.message_id)
            )
            log.debug(
                f"Message {message.message_id} queued for {message.to_agent} "
                f"(topic={message.topic}, priority={message.priority.value})"
            )
        else:
            # Broadcast
            await self._deliver_broadcast(message)
    
    async def send_request(
        self,
        from_agent: str,
        to_agent: str,
        topic: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        requires_ack: bool = True,
        timeout: Optional[float] = None
    ) -> Message:
        """Send a request message."""
        message = Message(
            message_id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.REQUEST,
            priority=priority,
            topic=topic,
            payload=payload,
            requires_ack=requires_ack,
        )
        await self.send(message, timeout=timeout)
        return message
    
    async def send_response(
        self,
        from_agent: str,
        to_agent: str,
        in_reply_to: str,
        topic: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Message:
        """Send a response message."""
        message = Message(
            message_id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.RESPONSE,
            priority=priority,
            topic=topic,
            payload=payload,
            in_reply_to=in_reply_to,
        )
        await self.send(message)
        return message
    
    async def broadcast(
        self,
        from_agent: str,
        topic: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Message:
        """Broadcast a message to all subscribers."""
        message = Message(
            message_id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=None,  # Broadcast
            message_type=MessageType.BROADCAST,
            priority=priority,
            topic=topic,
            payload=payload,
        )
        await self.send(message)
        return message
    
    async def acknowledge(self, message_id: str, agent_id: str) -> bool:
        """Acknowledge message delivery."""
        message = self._messages.get(message_id)
        if not message:
            log.warning(f"Cannot acknowledge unknown message: {message_id}")
            return False
        
        if message.to_agent != agent_id:
            log.warning(
                f"Agent {agent_id} cannot acknowledge message "
                f"sent to {message.to_agent}"
            )
            return False
        
        message.acknowledged = True
        message.acknowledged_at = time.time()
        self._stats["total_acknowledged"] += 1
        
        log.debug(f"Message {message_id} acknowledged by {agent_id}")
        return True
    
    async def _deliver_broadcast(self, message: Message) -> None:
        """Deliver broadcast message to all subscribers."""
        handlers = self._broadcast_subs.get(message.topic, [])
        
        if not handlers:
            log.debug(f"No broadcast subscribers for topic '{message.topic}'")
            return
        
        message.delivered = True
        message.delivered_at = time.time()
        self._stats["total_delivered"] += 1
        
        log.info(
            f"Broadcasting message {message.message_id} to {len(handlers)} subscribers "
            f"(topic={message.topic})"
        )
        
        # Call all handlers
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                log.error(
                    f"Broadcast handler error for topic '{message.topic}': {e}"
                )
    
    async def _deliver_to_agent(self, agent_id: str, message: Message) -> None:
        """Deliver message to specific agent."""
        # Get handlers for topic
        handlers = self._subscriptions.get(agent_id, {}).get(message.topic, [])
        
        if not handlers:
            log.warning(
                f"No handlers for agent {agent_id} on topic '{message.topic}'"
            )
            self._stats["total_failed"] += 1
            return
        
        message.delivered = True
        message.delivered_at = time.time()
        self._stats["total_delivered"] += 1
        
        log.debug(
            f"Delivering message {message.message_id} to {agent_id} "
            f"(topic={message.topic})"
        )
        
        # Call all handlers
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                log.error(
                    f"Handler error for agent {agent_id}, topic '{message.topic}': {e}"
                )
    
    async def start(self) -> None:
        """Start message delivery loop."""
        if self._running:
            log.warning("MessageBus already running")
            return
        
        self._running = True
        self._delivery_task = asyncio.create_task(self._delivery_loop())
        log.info("MessageBus started")
    
    async def stop(self) -> None:
        """Stop message delivery loop."""
        self._running = False
        if self._delivery_task:
            self._delivery_task.cancel()
            try:
                await self._delivery_task
            except asyncio.CancelledError:
                pass
        log.info("MessageBus stopped")
    
    async def _delivery_loop(self) -> None:
        """Main message delivery loop."""
        while self._running:
            try:
                # Process messages for each agent
                for agent_id in list(self._pending.keys()):
                    queue = self._pending[agent_id]
                    
                    # Try to get message (non-blocking)
                    try:
                        _, message_id = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        continue
                    
                    message = self._messages.get(message_id)
                    if not message:
                        continue
                    
                    # Check expiry
                    if message.is_expired():
                        log.warning(
                            f"Message {message_id} expired before delivery"
                        )
                        self._stats["total_expired"] += 1
                        continue
                    
                    # Deliver
                    await self._deliver_to_agent(agent_id, message)
                
                # Small delay
                await asyncio.sleep(0.01)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Delivery loop error: {e}")
                await asyncio.sleep(0.1)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get message bus statistics."""
        return {
            **self._stats,
            "pending_count": sum(
                q.qsize() for q in self._pending.values()
            ),
            "history_size": len(self._history),
            "total_messages": len(self._messages),
            "delivery_rate": (
                self._stats["total_delivered"] / self._stats["total_sent"]
                if self._stats["total_sent"] > 0
                else 0.0
            ),
            "ack_rate": (
                self._stats["total_acknowledged"] / self._stats["total_delivered"]
                if self._stats["total_delivered"] > 0
                else 0.0
            ),
        }
    
    def get_message_history(
        self,
        agent_id: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 100
    ) -> List[Message]:
        """Get message history with optional filters."""
        messages = list(self._history)
        
        # Filter by agent
        if agent_id:
            messages = [
                m for m in messages
                if m.from_agent == agent_id or m.to_agent == agent_id
            ]
        
        # Filter by topic
        if topic:
            messages = [m for m in messages if m.topic == topic]
        
        # Limit
        return messages[-limit:]
