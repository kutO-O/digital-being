"""
Digital Being — Priority Queue
Stage 30.6: Manages prioritized queue of code changes.
"""

from __future__ import annotations

import heapq
import json
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.priority_queue")

class ChangeRequest:
    """
    Represents a single change request with priority.
    """
    
    def __init__(
        self,
        change_id: str,
        module_name: str,
        change_type: str,
        description: str,
        priority: float,
        urgency: str = "normal",
        metadata: dict[str, Any] | None = None
    ) -> None:
        self.change_id = change_id
        self.module_name = module_name
        self.change_type = change_type
        self.description = description
        self.priority = priority  # Higher = more important
        self.urgency = urgency
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.scheduled_for: float | None = None
        self.status = "pending"
    
    def __lt__(self, other: ChangeRequest) -> bool:
        """Compare for priority queue (higher priority first)."""
        # Negative because heapq is min-heap
        return -self.priority < -other.priority
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "change_id": self.change_id,
            "module_name": self.module_name,
            "change_type": self.change_type,
            "description": self.description,
            "priority": self.priority,
            "urgency": self.urgency,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "scheduled_for": self.scheduled_for,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeRequest:
        """Create from dictionary."""
        req = cls(
            change_id=data["change_id"],
            module_name=data["module_name"],
            change_type=data["change_type"],
            description=data["description"],
            priority=data["priority"],
            urgency=data.get("urgency", "normal"),
            metadata=data.get("metadata", {})
        )
        req.created_at = data.get("created_at", time.time())
        req.scheduled_for = data.get("scheduled_for")
        req.status = data.get("status", "pending")
        return req

class PriorityQueue:
    """
    Manages prioritized queue of code changes.
    
    Features:
    - Priority-based scheduling
    - Urgency levels (critical, high, normal, low)
    - Dynamic priority adjustment
    - Queue persistence
    - Time-based scheduling
    - Conflict detection
    """
    
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path / "priority_queue.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._queue: list[ChangeRequest] = []
        self._requests_by_id: dict[str, ChangeRequest] = {}
        self._completed: list[dict[str, Any]] = []
        self._rejected: list[dict[str, Any]] = []
        
        self._load_queue()
        
        log.info(f"PriorityQueue initialized with {len(self._queue)} pending requests")
    
    def _load_queue(self) -> None:
        """Load queue from disk."""
        if self._storage_path.exists():
            try:
                with self._storage_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Restore pending requests
                for req_data in data.get("pending", []):
                    req = ChangeRequest.from_dict(req_data)
                    self._queue.append(req)
                    self._requests_by_id[req.change_id] = req
                
                # Restore history
                self._completed = data.get("completed", [])
                self._rejected = data.get("rejected", [])
                
                # Re-heapify queue
                heapq.heapify(self._queue)
                
                log.info(f"Loaded queue: {len(self._queue)} pending, {len(self._completed)} completed")
            except Exception as e:
                log.error(f"Failed to load queue: {e}")
    
    def _save_queue(self) -> None:
        """Save queue to disk."""
        try:
            data = {
                "pending": [req.to_dict() for req in self._queue],
                "completed": self._completed,
                "rejected": self._rejected,
                "last_updated": time.time()
            }
            
            with self._storage_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Failed to save queue: {e}")
    
    def enqueue(
        self,
        change_id: str,
        module_name: str,
        change_type: str,
        description: str,
        urgency: str = "normal",
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Add change request to queue.
        
        Args:
            change_id: Unique change ID
            module_name: Module to change
            change_type: Type of change
            description: Change description
            urgency: Urgency level (critical, high, normal, low)
            metadata: Additional metadata
        
        Returns:
            Result with priority info
        """
        # Check for duplicates
        if change_id in self._requests_by_id:
            return {
                "success": False,
                "error": "Change request already in queue"
            }
        
        # Calculate priority
        priority = self._calculate_priority(
            change_type=change_type,
            urgency=urgency,
            metadata=metadata or {}
        )
        
        # Create request
        request = ChangeRequest(
            change_id=change_id,
            module_name=module_name,
            change_type=change_type,
            description=description,
            priority=priority,
            urgency=urgency,
            metadata=metadata
        )
        
        # Add to queue
        heapq.heappush(self._queue, request)
        self._requests_by_id[change_id] = request
        
        self._save_queue()
        
        position = self._get_queue_position(change_id)
        
        log.info(
            f"Enqueued {change_id}: priority={priority:.2f}, "
            f"urgency={urgency}, position={position}"
        )
        
        return {
            "success": True,
            "change_id": change_id,
            "priority": priority,
            "urgency": urgency,
            "queue_position": position,
            "queue_size": len(self._queue)
        }
    
    def dequeue(self) -> ChangeRequest | None:
        """
        Get next change request from queue.
        
        Returns:
            Next change request or None if queue empty
        """
        if not self._queue:
            return None
        
        request = heapq.heappop(self._queue)
        request.status = "processing"
        
        # Remove from lookup
        if request.change_id in self._requests_by_id:
            del self._requests_by_id[request.change_id]
        
        self._save_queue()
        
        log.info(f"Dequeued {request.change_id} (priority={request.priority:.2f})")
        
        return request
    
    def peek(self, count: int = 1) -> list[ChangeRequest]:
        """
        Peek at next N requests without removing.
        
        Args:
            count: Number of requests to peek
        
        Returns:
            List of next requests
        """
        return heapq.nsmallest(count, self._queue)
    
    def adjust_priority(
        self,
        change_id: str,
        new_priority: float | None = None,
        urgency: str | None = None
    ) -> dict[str, Any]:
        """
        Adjust priority of a pending request.
        
        Args:
            change_id: Change ID
            new_priority: New priority value
            urgency: New urgency level
        
        Returns:
            Result with updated info
        """
        if change_id not in self._requests_by_id:
            return {
                "success": False,
                "error": "Request not found in queue"
            }
        
        request = self._requests_by_id[change_id]
        old_priority = request.priority
        
        # Update priority
        if new_priority is not None:
            request.priority = new_priority
        
        # Update urgency
        if urgency is not None:
            request.urgency = urgency
            # Recalculate priority based on new urgency
            request.priority = self._calculate_priority(
                change_type=request.change_type,
                urgency=urgency,
                metadata=request.metadata
            )
        
        # Re-heapify queue
        heapq.heapify(self._queue)
        
        self._save_queue()
        
        log.info(
            f"Adjusted priority for {change_id}: "
            f"{old_priority:.2f} → {request.priority:.2f}"
        )
        
        return {
            "success": True,
            "change_id": change_id,
            "old_priority": old_priority,
            "new_priority": request.priority,
            "queue_position": self._get_queue_position(change_id)
        }
    
    def complete(
        self,
        change_id: str,
        result: dict[str, Any] | None = None
    ) -> None:
        """Mark a request as completed."""
        if change_id in self._requests_by_id:
            request = self._requests_by_id[change_id]
            self._queue.remove(request)
            del self._requests_by_id[change_id]
        
        self._completed.append({
            "change_id": change_id,
            "completed_at": time.time(),
            "result": result
        })
        
        self._save_queue()
        log.info(f"Marked {change_id} as completed")
    
    def reject(
        self,
        change_id: str,
        reason: str
    ) -> None:
        """Mark a request as rejected."""
        if change_id in self._requests_by_id:
            request = self._requests_by_id[change_id]
            self._queue.remove(request)
            del self._requests_by_id[change_id]
        
        self._rejected.append({
            "change_id": change_id,
            "rejected_at": time.time(),
            "reason": reason
        })
        
        self._save_queue()
        log.info(f"Rejected {change_id}: {reason}")
    
    def _calculate_priority(
        self,
        change_type: str,
        urgency: str,
        metadata: dict[str, Any]
    ) -> float:
        """
        Calculate priority score (0.0 - 1.0).
        
        Higher priority = processed first
        """
        # Base priority from change type
        type_priority = {
            "bug_fix": 0.8,
            "security_fix": 1.0,
            "optimization": 0.6,
            "new_feature": 0.4,
            "module_update": 0.5,
            "module_creation": 0.3
        }.get(change_type, 0.5)
        
        # Urgency multiplier
        urgency_multiplier = {
            "critical": 1.5,
            "high": 1.2,
            "normal": 1.0,
            "low": 0.7
        }.get(urgency, 1.0)
        
        # Adjust for risk score (lower risk = higher priority)
        risk_score = metadata.get("risk_score", 0.5)
        risk_factor = 1.0 - (risk_score * 0.3)
        
        # Adjust for impact (higher impact = higher priority)
        impact_score = metadata.get("impact_score", 0.5)
        impact_factor = 1.0 + (impact_score * 0.2)
        
        # Calculate final priority
        priority = type_priority * urgency_multiplier * risk_factor * impact_factor
        
        return min(priority, 1.0)
    
    def _get_queue_position(self, change_id: str) -> int:
        """Get position of request in queue (1-indexed)."""
        if change_id not in self._requests_by_id:
            return -1
        
        request = self._requests_by_id[change_id]
        
        # Sort queue by priority
        sorted_queue = sorted(self._queue, reverse=True)
        
        for i, req in enumerate(sorted_queue):
            if req.change_id == change_id:
                return i + 1
        
        return -1
    
    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status."""
        return {
            "pending": len(self._queue),
            "completed": len(self._completed),
            "rejected": len(self._rejected),
            "next_changes": [
                req.to_dict() for req in self.peek(5)
            ]
        }
    
    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        total_processed = len(self._completed) + len(self._rejected)
        success_rate = 0.0
        
        if total_processed > 0:
            success_rate = len(self._completed) / total_processed
        
        return {
            "pending_requests": len(self._queue),
            "completed": len(self._completed),
            "rejected": len(self._rejected),
            "success_rate": success_rate
        }
