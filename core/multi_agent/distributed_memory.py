"""Distributed Memory System for Multi-Agent Knowledge Sharing.

Enables agents to share knowledge while maintaining local context:
- Shared semantic memory (global facts)
- Local episodic memory (agent-specific experiences)
- Memory synchronization
- Conflict resolution
- Memory partitioning

Phase 3 - Multi-Agent System
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger("digital_being.multi_agent.memory")


class MemoryScope(Enum):
    """Scope of memory entry."""
    LOCAL = "local"        # Agent-specific
    SHARED = "shared"      # Available to all agents
    TEAM = "team"          # Available to specific team
    GLOBAL = "global"      # System-wide facts


class MemoryType(Enum):
    """Type of memory."""
    EPISODIC = "episodic"      # Event-based memories
    SEMANTIC = "semantic"      # Factual knowledge
    PROCEDURAL = "procedural"  # How-to knowledge


@dataclass
class MemoryEntry:
    """Single memory entry."""
    entry_id: str
    agent_id: str  # Owner
    
    # Content
    content: str
    memory_type: MemoryType
    scope: MemoryScope
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5  # 0.0 to 1.0
    confidence: float = 1.0  # How confident
    
    # Access control
    shared_with: Set[str] = field(default_factory=set)  # Agent IDs
    
    # Versioning
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # Relations
    related_to: List[str] = field(default_factory=list)  # Entry IDs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "agent_id": self.agent_id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "scope": self.scope.value,
            "tags": self.tags,
            "importance": self.importance,
            "confidence": self.confidence,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DistributedMemory:
    """
    Manages distributed memory across multiple agents.
    
    Features:
    - Shared semantic memory for global facts
    - Local episodic memory for agent experiences
    - Memory synchronization
    - Conflict-free updates
    - Query interface
    
    Example:
        memory = DistributedMemory()
        
        # Add local memory
        memory.add_memory(
            agent_id="agent_1",
            content="Completed task XYZ successfully",
            memory_type=MemoryType.EPISODIC,
            scope=MemoryScope.LOCAL
        )
        
        # Add shared knowledge
        memory.add_memory(
            agent_id="agent_1",
            content="Python is a programming language",
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.SHARED
        )
        
        # Query memories
        results = memory.query(
            agent_id="agent_2",
            query="Python",
            include_shared=True
        )
    """
    
    def __init__(self, max_local_memories: int = 1000):
        """
        Args:
            max_local_memories: Max local memories per agent
        """
        self._max_local_memories = max_local_memories
        
        # Memory storage
        self._shared_memory: Dict[str, MemoryEntry] = {}  # Shared across all
        self._local_memory: Dict[str, Dict[str, MemoryEntry]] = defaultdict(dict)  # Per agent
        
        # Indexes for fast search
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)  # tag -> entry_ids
        self._type_index: Dict[MemoryType, Set[str]] = defaultdict(set)
        
        # Sync tracking
        self._last_sync: Dict[str, float] = {}  # agent_id -> timestamp
        
        log.info(
            f"DistributedMemory initialized (max_local={max_local_memories})"
        )
    
    def add_memory(
        self,
        agent_id: str,
        content: str,
        memory_type: MemoryType,
        scope: MemoryScope,
        entry_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
        confidence: float = 1.0,
        related_to: Optional[List[str]] = None
    ) -> MemoryEntry:
        """Add a new memory entry."""
        import uuid
        
        if entry_id is None:
            entry_id = str(uuid.uuid4())
        
        entry = MemoryEntry(
            entry_id=entry_id,
            agent_id=agent_id,
            content=content,
            memory_type=memory_type,
            scope=scope,
            tags=tags or [],
            importance=importance,
            confidence=confidence,
            related_to=related_to or [],
        )
        
        # Store based on scope
        if scope in (MemoryScope.SHARED, MemoryScope.GLOBAL):
            self._shared_memory[entry_id] = entry
        else:
            self._local_memory[agent_id][entry_id] = entry
            
            # Cleanup old local memories if needed
            self._cleanup_local_memories(agent_id)
        
        # Update indexes
        self._update_indexes(entry)
        
        log.debug(
            f"Memory added: {entry_id[:8]} by {agent_id} "
            f"(scope={scope.value}, type={memory_type.value})"
        )
        
        return entry
    
    def _cleanup_local_memories(self, agent_id: str) -> None:
        """Remove old local memories if over limit."""
        local_mem = self._local_memory[agent_id]
        
        if len(local_mem) <= self._max_local_memories:
            return
        
        # Sort by importance and age
        entries = sorted(
            local_mem.values(),
            key=lambda e: (e.importance, -e.created_at)
        )
        
        # Remove least important, oldest
        to_remove = len(local_mem) - self._max_local_memories
        for entry in entries[:to_remove]:
            del local_mem[entry.entry_id]
            log.debug(f"Cleaned up old memory: {entry.entry_id[:8]}")
    
    def _update_indexes(self, entry: MemoryEntry) -> None:
        """Update search indexes."""
        # Tag index
        for tag in entry.tags:
            self._tag_index[tag].add(entry.entry_id)
        
        # Type index
        self._type_index[entry.memory_type].add(entry.entry_id)
    
    def get_memory(self, entry_id: str, agent_id: str) -> Optional[MemoryEntry]:
        """Get memory by ID with access control."""
        # Check shared first
        if entry_id in self._shared_memory:
            return self._shared_memory[entry_id]
        
        # Check local
        if entry_id in self._local_memory.get(agent_id, {}):
            return self._local_memory[agent_id][entry_id]
        
        return None
    
    def update_memory(
        self,
        entry_id: str,
        agent_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update existing memory (Last-Write-Wins)."""
        entry = self.get_memory(entry_id, agent_id)
        if not entry:
            return False
        
        # Check permissions (can only update own memories)
        if entry.agent_id != agent_id and entry.scope == MemoryScope.LOCAL:
            log.warning(
                f"Agent {agent_id} cannot update memory owned by {entry.agent_id}"
            )
            return False
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        entry.version += 1
        entry.updated_at = time.time()
        
        log.debug(f"Memory updated: {entry_id[:8]} v{entry.version}")
        return True
    
    def query(
        self,
        agent_id: str,
        query: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        tags: Optional[List[str]] = None,
        include_shared: bool = True,
        min_importance: float = 0.0,
        limit: int = 100
    ) -> List[MemoryEntry]:
        """Query memories with filters."""
        results = []
        
        # Search local memories
        for entry in self._local_memory.get(agent_id, {}).values():
            if self._matches_query(entry, query, memory_type, tags, min_importance):
                results.append(entry)
        
        # Search shared memories
        if include_shared:
            for entry in self._shared_memory.values():
                if self._matches_query(entry, query, memory_type, tags, min_importance):
                    results.append(entry)
        
        # Sort by importance and recency
        results.sort(
            key=lambda e: (e.importance, e.updated_at),
            reverse=True
        )
        
        return results[:limit]
    
    def _matches_query(
        self,
        entry: MemoryEntry,
        query: Optional[str],
        memory_type: Optional[MemoryType],
        tags: Optional[List[str]],
        min_importance: float
    ) -> bool:
        """Check if entry matches query criteria."""
        # Type filter
        if memory_type and entry.memory_type != memory_type:
            return False
        
        # Importance filter
        if entry.importance < min_importance:
            return False
        
        # Tag filter
        if tags:
            if not any(tag in entry.tags for tag in tags):
                return False
        
        # Content search
        if query:
            if query.lower() not in entry.content.lower():
                return False
        
        return True
    
    def share_memory(self, entry_id: str, agent_id: str, with_agents: List[str]) -> bool:
        """Share local memory with specific agents."""
        entry = self.get_memory(entry_id, agent_id)
        if not entry:
            return False
        
        if entry.agent_id != agent_id:
            return False
        
        # Update shared_with
        entry.shared_with.update(with_agents)
        
        log.info(
            f"Memory {entry_id[:8]} shared with {len(with_agents)} agents"
        )
        return True
    
    def sync_agent_memories(
        self,
        agent_id: str,
        since: Optional[float] = None
    ) -> List[MemoryEntry]:
        """Get memories updated since timestamp."""
        if since is None:
            since = self._last_sync.get(agent_id, 0.0)
        
        synced = []
        
        # Get updated shared memories
        for entry in self._shared_memory.values():
            if entry.updated_at > since:
                synced.append(entry)
        
        # Get memories shared with this agent
        for other_agent_memories in self._local_memory.values():
            for entry in other_agent_memories.values():
                if (
                    entry.updated_at > since and
                    agent_id in entry.shared_with
                ):
                    synced.append(entry)
        
        self._last_sync[agent_id] = time.time()
        
        log.debug(
            f"Synced {len(synced)} memories for {agent_id} since {since}"
        )
        
        return synced
    
    def get_statistics(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Get memory statistics."""
        if agent_id:
            # Agent-specific stats
            local_count = len(self._local_memory.get(agent_id, {}))
            
            return {
                "agent_id": agent_id,
                "local_memories": local_count,
                "shared_accessible": len(self._shared_memory),
                "last_sync": self._last_sync.get(agent_id),
            }
        else:
            # Global stats
            total_local = sum(
                len(memories) for memories in self._local_memory.values()
            )
            
            type_dist = {}
            for mem_type in MemoryType:
                type_dist[mem_type.value] = len(self._type_index[mem_type])
            
            return {
                "total_agents": len(self._local_memory),
                "total_local_memories": total_local,
                "total_shared_memories": len(self._shared_memory),
                "total_memories": total_local + len(self._shared_memory),
                "type_distribution": type_dist,
                "total_tags": len(self._tag_index),
            }
    
    def clear_agent_memories(self, agent_id: str, local_only: bool = True) -> int:
        """Clear memories for an agent."""
        count = 0
        
        if agent_id in self._local_memory:
            count = len(self._local_memory[agent_id])
            self._local_memory[agent_id].clear()
        
        if not local_only:
            # Also remove from shared if owned
            to_remove = [
                entry_id for entry_id, entry in self._shared_memory.items()
                if entry.agent_id == agent_id
            ]
            for entry_id in to_remove:
                del self._shared_memory[entry_id]
                count += 1
        
        log.info(f"Cleared {count} memories for agent {agent_id}")
        return count
