"""
Digital Being - Message Protocol for Multi-Agent Communication
Stage 27: Structured messaging between agents.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Optional


class MessageType(Enum):
    """Types of messages agents can exchange."""
    QUERY = "query"              # Ask another agent for information
    RESPONSE = "response"        # Response to a query
    TASK = "task"                # Delegate a task
    STATUS = "status"            # Status update
    SKILL_SHARE = "skill_share"  # Share a skill
    CONSENSUS = "consensus"      # Request consensus vote
    VOTE = "vote"                # Cast a vote
    BROADCAST = "broadcast"      # Broadcast to all
    HEARTBEAT = "heartbeat"      # Agent alive signal


class Priority(Enum):
    """Message priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    """Structured message for agent-to-agent communication."""
    
    msg_id: str
    msg_type: MessageType
    from_agent: str
    to_agent: str  # or "*" for broadcast
    payload: dict[str, Any]
    priority: Priority = Priority.NORMAL
    timestamp: float = 0.0
    reply_to: Optional[str] = None  # For threading
    ttl: int = 3600  # Time-to-live in seconds
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "payload": self.payload,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to,
            "ttl": self.ttl
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Message:
        """Parse from dict."""
        return cls(
            msg_id=data["msg_id"],
            msg_type=MessageType(data["msg_type"]),
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            payload=data["payload"],
            priority=Priority(data["priority"]),
            timestamp=data["timestamp"],
            reply_to=data.get("reply_to"),
            ttl=data.get("ttl", 3600)
        )
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> Message:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def is_expired(self) -> bool:
        """Check if message TTL expired."""
        return (time.time() - self.timestamp) > self.ttl
    
    def is_broadcast(self) -> bool:
        """Check if message is broadcast."""
        return self.to_agent == "*"


class MessageBuilder:
    """Helper to construct messages easily."""
    
    @staticmethod
    def query(
        from_agent: str,
        to_agent: str,
        question: str,
        context: dict[str, Any] | None = None,
        priority: Priority = Priority.NORMAL
    ) -> Message:
        """Create a query message."""
        return Message(
            msg_id=str(uuid.uuid4()),
            msg_type=MessageType.QUERY,
            from_agent=from_agent,
            to_agent=to_agent,
            payload={"question": question, "context": context or {}},
            priority=priority
        )
    
    @staticmethod
    def response(
        from_agent: str,
        to_agent: str,
        answer: Any,
        reply_to: str,
        success: bool = True
    ) -> Message:
        """Create a response message."""
        return Message(
            msg_id=str(uuid.uuid4()),
            msg_type=MessageType.RESPONSE,
            from_agent=from_agent,
            to_agent=to_agent,
            payload={"answer": answer, "success": success},
            reply_to=reply_to
        )
    
    @staticmethod
    def delegate_task(
        from_agent: str,
        to_agent: str,
        task_description: str,
        context: dict[str, Any] | None = None,
        priority: Priority = Priority.NORMAL
    ) -> Message:
        """Create a task delegation message."""
        return Message(
            msg_id=str(uuid.uuid4()),
            msg_type=MessageType.TASK,
            from_agent=from_agent,
            to_agent=to_agent,
            payload={
                "task": task_description,
                "context": context or {},
                "status": "pending"
            },
            priority=priority
        )
    
    @staticmethod
    def share_skill(
        from_agent: str,
        skill_data: dict[str, Any],
        to_agent: str = "*"  # Default broadcast
    ) -> Message:
        """Create a skill-sharing message."""
        return Message(
            msg_id=str(uuid.uuid4()),
            msg_type=MessageType.SKILL_SHARE,
            from_agent=from_agent,
            to_agent=to_agent,
            payload=skill_data,
            priority=Priority.HIGH
        )
    
    @staticmethod
    def broadcast(
        from_agent: str,
        announcement: str,
        data: dict[str, Any] | None = None
    ) -> Message:
        """Create a broadcast message."""
        return Message(
            msg_id=str(uuid.uuid4()),
            msg_type=MessageType.BROADCAST,
            from_agent=from_agent,
            to_agent="*",
            payload={"announcement": announcement, "data": data or {}}
        )
    
    @staticmethod
    def consensus_request(
        from_agent: str,
        question: str,
        options: list[str],
        timeout: int = 30
    ) -> Message:
        """Create a consensus request."""
        return Message(
            msg_id=str(uuid.uuid4()),
            msg_type=MessageType.CONSENSUS,
            from_agent=from_agent,
            to_agent="*",
            payload={
                "question": question,
                "options": options,
                "timeout": timeout,
                "votes": {}
            },
            priority=Priority.HIGH,
            ttl=timeout
        )
    
    @staticmethod
    def vote(
        from_agent: str,
        to_agent: str,
        reply_to: str,
        choice: str,
        reasoning: str = ""
    ) -> Message:
        """Cast a vote in consensus."""
        return Message(
            msg_id=str(uuid.uuid4()),
            msg_type=MessageType.VOTE,
            from_agent=from_agent,
            to_agent=to_agent,
            payload={"choice": choice, "reasoning": reasoning},
            reply_to=reply_to
        )
