"""Goal Hierarchy & Planning Engine.

Hierarchical goal decomposition with:
- Multi-level goal trees
- Automatic decomposition via LLM
- Execution tracking
- Adaptive replanning on failures
- Success criteria validation
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

log = logging.getLogger("digital_being.goal_hierarchy")


class GoalStatus(Enum):
    """Goal execution status."""
    PENDING = "pending"      # Not started yet
    ACTIVE = "active"        # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"        # Failed to complete
    CANCELLED = "cancelled"  # Cancelled by system
    BLOCKED = "blocked"      # Blocked by dependencies


class GoalType(Enum):
    """Type of goal node."""
    ROOT = "root"           # Top-level user goal
    SUBGOAL = "subgoal"     # Intermediate subgoal
    ACTION = "action"       # Concrete action to execute


@dataclass
class GoalNode:
    """Individual goal in the hierarchy."""
    
    id: str
    type: GoalType
    description: str
    status: GoalStatus = GoalStatus.PENDING
    
    # Hierarchy
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    
    # Execution
    estimated_ticks: int = 1
    actual_ticks: int = 0
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    failure_reason: Optional[str] = None
    
    # Action details (for ACTION type)
    action_type: Optional[str] = None  # "shell", "tool_call", "llm_query", etc.
    action_params: Dict[str, Any] = field(default_factory=dict)
    action_result: Optional[Any] = None
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Metadata
    priority: int = 5  # 1-10, higher = more important
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        d = asdict(self)
        d["type"] = self.type.value
        d["status"] = self.status.value
        return d
    
    @staticmethod
    def from_dict(data: dict) -> "GoalNode":
        """Create from dictionary."""
        data = data.copy()
        data["type"] = GoalType(data["type"])
        data["status"] = GoalStatus(data["status"])
        return GoalNode(**data)
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (no children)."""
        return len(self.children_ids) == 0
    
    def is_completed(self) -> bool:
        """Check if goal is completed."""
        return self.status == GoalStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """Check if goal failed."""
        return self.status == GoalStatus.FAILED
    
    def is_terminal(self) -> bool:
        """Check if goal is in terminal state."""
        return self.status in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED)
    
    def can_execute(self) -> bool:
        """Check if goal can be executed now."""
        return self.status in (GoalStatus.PENDING, GoalStatus.ACTIVE)


class GoalTree:
    """Hierarchical goal tree structure."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self._nodes: Dict[str, GoalNode] = {}
        self._storage_path = storage_path
        self._root_ids: Set[str] = set()
        
        if storage_path and storage_path.exists():
            self.load()
    
    def add_node(self, node: GoalNode) -> None:
        """Add node to tree."""
        self._nodes[node.id] = node
        if node.type == GoalType.ROOT:
            self._root_ids.add(node.id)
        log.debug(f"Added goal node: {node.id} ({node.type.value})")
    
    def get_node(self, node_id: str) -> Optional[GoalNode]:
        """Get node by ID."""
        return self._nodes.get(node_id)
    
    def remove_node(self, node_id: str) -> None:
        """Remove node and its subtree."""
        node = self.get_node(node_id)
        if not node:
            return
        
        # Remove children recursively
        for child_id in node.children_ids:
            self.remove_node(child_id)
        
        # Remove from parent
        if node.parent_id:
            parent = self.get_node(node.parent_id)
            if parent and node_id in parent.children_ids:
                parent.children_ids.remove(node_id)
        
        # Remove node
        del self._nodes[node_id]
        self._root_ids.discard(node_id)
        log.debug(f"Removed goal node: {node_id}")
    
    def add_child(self, parent_id: str, child: GoalNode) -> None:
        """Add child to parent node."""
        parent = self.get_node(parent_id)
        if not parent:
            raise ValueError(f"Parent node {parent_id} not found")
        
        child.parent_id = parent_id
        self.add_node(child)
        parent.children_ids.append(child.id)
    
    def get_children(self, node_id: str) -> List[GoalNode]:
        """Get all children of node."""
        node = self.get_node(node_id)
        if not node:
            return []
        return [self._nodes[cid] for cid in node.children_ids if cid in self._nodes]
    
    def get_parent(self, node_id: str) -> Optional[GoalNode]:
        """Get parent of node."""
        node = self.get_node(node_id)
        if not node or not node.parent_id:
            return None
        return self.get_node(node.parent_id)
    
    def get_root_nodes(self) -> List[GoalNode]:
        """Get all root nodes."""
        return [self._nodes[rid] for rid in self._root_ids if rid in self._nodes]
    
    def get_active_goals(self) -> List[GoalNode]:
        """Get all goals with ACTIVE status."""
        return [n for n in self._nodes.values() if n.status == GoalStatus.ACTIVE]
    
    def get_pending_actions(self) -> List[GoalNode]:
        """Get all ACTION nodes that are pending."""
        return [
            n for n in self._nodes.values()
            if n.type == GoalType.ACTION and n.status == GoalStatus.PENDING
        ]
    
    def get_subtree(self, node_id: str) -> List[GoalNode]:
        """Get node and all its descendants."""
        node = self.get_node(node_id)
        if not node:
            return []
        
        result = [node]
        for child_id in node.children_ids:
            result.extend(self.get_subtree(child_id))
        return result
    
    def get_path_to_root(self, node_id: str) -> List[GoalNode]:
        """Get path from node to root."""
        path = []
        current = self.get_node(node_id)
        while current:
            path.append(current)
            current = self.get_parent(current.id)
        return list(reversed(path))
    
    def count_nodes(self) -> int:
        """Count total nodes in tree."""
        return len(self._nodes)
    
    def save(self) -> None:
        """Save tree to storage."""
        if not self._storage_path:
            return
        
        data = {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "root_ids": list(self._root_ids),
            "saved_at": time.time()
        }
        
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        log.info(f"Goal tree saved: {self.count_nodes()} nodes")
    
    def load(self) -> None:
        """Load tree from storage."""
        if not self._storage_path or not self._storage_path.exists():
            return
        
        data = json.loads(self._storage_path.read_text(encoding="utf-8"))
        self._nodes = {n["id"]: GoalNode.from_dict(n) for n in data["nodes"]}
        self._root_ids = set(data["root_ids"])
        log.info(f"Goal tree loaded: {self.count_nodes()} nodes")
    
    def clear(self) -> None:
        """Clear all nodes."""
        self._nodes.clear()
        self._root_ids.clear()
        log.info("Goal tree cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tree statistics."""
        total = len(self._nodes)
        if total == 0:
            return {"total": 0}
        
        by_status = {}
        by_type = {}
        completed = 0
        failed = 0
        avg_ticks = 0
        
        for node in self._nodes.values():
            by_status[node.status.value] = by_status.get(node.status.value, 0) + 1
            by_type[node.type.value] = by_type.get(node.type.value, 0) + 1
            if node.is_completed():
                completed += 1
                avg_ticks += node.actual_ticks
            elif node.is_failed():
                failed += 1
        
        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / (completed + failed) if (completed + failed) > 0 else 0,
            "avg_ticks_per_goal": avg_ticks / completed if completed > 0 else 0,
        }