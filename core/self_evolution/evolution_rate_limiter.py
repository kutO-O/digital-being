"""
Digital Being — Evolution Rate Limiter
Stage 30.7: Controls the rate of code evolution to prevent instability.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.evolution_rate_limiter")

class EvolutionRateLimiter:
    """
    Rate limiter for code evolution to prevent system instability.
    
    Features:
    - Time-based limits (changes per hour/day)
    - Module-specific limits
    - Cooling periods after failures
    - Burst protection
    - Dynamic rate adjustment
    """
    
    def __init__(
        self,
        storage_path: Path,
        max_per_hour: int = 5,
        max_per_day: int = 20,
        min_interval: int = 300  # 5 minutes
    ) -> None:
        self._storage_path = storage_path / "rate_limiter.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Global limits
        self._max_per_hour = max_per_hour
        self._max_per_day = max_per_day
        self._min_interval = min_interval  # seconds between changes
        
        # Tracking
        self._recent_changes: deque[float] = deque(maxlen=max_per_day)
        self._last_change_time: float = 0.0
        self._module_cooldowns: dict[str, float] = {}
        self._failure_counts: dict[str, int] = {}
        
        # Statistics
        self._total_allowed = 0
        self._total_blocked = 0
        
        self._load_state()
        
        log.info(
            f"EvolutionRateLimiter initialized: "
            f"{max_per_hour}/hour, {max_per_day}/day, min_interval={min_interval}s"
        )
    
    def _load_state(self) -> None:
        """Load limiter state from disk."""
        if self._storage_path.exists():
            try:
                with self._storage_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Restore timestamps
                self._recent_changes = deque(
                    data.get("recent_changes", []),
                    maxlen=self._max_per_day
                )
                self._last_change_time = data.get("last_change_time", 0.0)
                self._module_cooldowns = data.get("module_cooldowns", {})
                self._failure_counts = data.get("failure_counts", {})
                
                # Restore stats
                self._total_allowed = data.get("total_allowed", 0)
                self._total_blocked = data.get("total_blocked", 0)
                
                log.info("Loaded rate limiter state")
            except Exception as e:
                log.error(f"Failed to load rate limiter state: {e}")
    
    def _save_state(self) -> None:
        """Save limiter state to disk."""
        try:
            data = {
                "recent_changes": list(self._recent_changes),
                "last_change_time": self._last_change_time,
                "module_cooldowns": self._module_cooldowns,
                "failure_counts": self._failure_counts,
                "total_allowed": self._total_allowed,
                "total_blocked": self._total_blocked,
                "last_updated": time.time()
            }
            
            with self._storage_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Failed to save rate limiter state: {e}")
    
    def can_proceed(
        self,
        module_name: str,
        change_type: str = "update"
    ) -> dict[str, Any]:
        """
        Check if a change can proceed based on rate limits.
        
        Args:
            module_name: Module to change
            change_type: Type of change
        
        Returns:
            Result with allowed status and reason
        """
        now = time.time()
        
        # Clean up old timestamps
        self._cleanup_old_timestamps(now)
        
        # Check global minimum interval
        if self._last_change_time > 0:
            time_since_last = now - self._last_change_time
            if time_since_last < self._min_interval:
                wait_time = self._min_interval - time_since_last
                self._total_blocked += 1
                self._save_state()
                
                return {
                    "allowed": False,
                    "reason": "global_interval",
                    "message": f"Too soon since last change. Wait {wait_time:.0f}s.",
                    "wait_seconds": wait_time
                }
        
        # Check hourly limit
        changes_last_hour = self._count_recent_changes(now, 3600)
        if changes_last_hour >= self._max_per_hour:
            self._total_blocked += 1
            self._save_state()
            
            return {
                "allowed": False,
                "reason": "hourly_limit",
                "message": f"Hourly limit reached ({changes_last_hour}/{self._max_per_hour}).",
                "current_count": changes_last_hour,
                "limit": self._max_per_hour
            }
        
        # Check daily limit
        changes_last_day = len(self._recent_changes)
        if changes_last_day >= self._max_per_day:
            self._total_blocked += 1
            self._save_state()
            
            return {
                "allowed": False,
                "reason": "daily_limit",
                "message": f"Daily limit reached ({changes_last_day}/{self._max_per_day}).",
                "current_count": changes_last_day,
                "limit": self._max_per_day
            }
        
        # Check module-specific cooldown
        if module_name in self._module_cooldowns:
            cooldown_until = self._module_cooldowns[module_name]
            if now < cooldown_until:
                wait_time = cooldown_until - now
                self._total_blocked += 1
                self._save_state()
                
                return {
                    "allowed": False,
                    "reason": "module_cooldown",
                    "message": f"Module {module_name} is in cooldown. Wait {wait_time:.0f}s.",
                    "module_name": module_name,
                    "wait_seconds": wait_time
                }
        
        # All checks passed
        self._total_allowed += 1
        
        return {
            "allowed": True,
            "reason": "approved",
            "message": "Change can proceed.",
            "quota": {
                "hourly": f"{changes_last_hour + 1}/{self._max_per_hour}",
                "daily": f"{changes_last_day + 1}/{self._max_per_day}"
            }
        }
    
    def record_change(
        self,
        module_name: str,
        change_id: str,
        success: bool = True
    ) -> None:
        """
        Record a change (successful or failed).
        
        Args:
            module_name: Module that was changed
            change_id: Change ID
            success: Whether the change succeeded
        """
        now = time.time()
        
        # Record timestamp
        self._recent_changes.append(now)
        self._last_change_time = now
        
        if not success:
            # Increment failure count
            self._failure_counts[module_name] = self._failure_counts.get(module_name, 0) + 1
            
            # Apply cooldown based on failure count
            failure_count = self._failure_counts[module_name]
            cooldown_duration = self._calculate_cooldown(failure_count)
            self._module_cooldowns[module_name] = now + cooldown_duration
            
            log.warning(
                f"Failed change recorded for {module_name} "
                f"(failures={failure_count}, cooldown={cooldown_duration}s)"
            )
        else:
            # Reset failure count on success
            if module_name in self._failure_counts:
                del self._failure_counts[module_name]
            
            # Remove cooldown
            if module_name in self._module_cooldowns:
                del self._module_cooldowns[module_name]
            
            log.info(f"Successful change recorded for {module_name}")
        
        self._save_state()
    
    def set_limits(
        self,
        max_per_hour: int | None = None,
        max_per_day: int | None = None,
        min_interval: int | None = None
    ) -> None:
        """
        Update rate limits.
        
        Args:
            max_per_hour: Maximum changes per hour
            max_per_day: Maximum changes per day
            min_interval: Minimum seconds between changes
        """
        if max_per_hour is not None:
            self._max_per_hour = max_per_hour
        if max_per_day is not None:
            self._max_per_day = max_per_day
            # Update deque size
            self._recent_changes = deque(
                list(self._recent_changes),
                maxlen=max_per_day
            )
        if min_interval is not None:
            self._min_interval = min_interval
        
        self._save_state()
        
        log.info(
            f"Updated limits: {self._max_per_hour}/hour, "
            f"{self._max_per_day}/day, interval={self._min_interval}s"
        )
    
    def reset_module_cooldown(self, module_name: str) -> None:
        """Manually reset cooldown for a module."""
        if module_name in self._module_cooldowns:
            del self._module_cooldowns[module_name]
        if module_name in self._failure_counts:
            del self._failure_counts[module_name]
        
        self._save_state()
        log.info(f"Reset cooldown for {module_name}")
    
    def get_current_quota(self) -> dict[str, Any]:
        """
        Get current quota usage.
        
        Returns:
            Quota information
        """
        now = time.time()
        self._cleanup_old_timestamps(now)
        
        hourly_used = self._count_recent_changes(now, 3600)
        daily_used = len(self._recent_changes)
        
        time_since_last = 0.0
        if self._last_change_time > 0:
            time_since_last = now - self._last_change_time
        
        return {
            "hourly": {
                "used": hourly_used,
                "limit": self._max_per_hour,
                "remaining": self._max_per_hour - hourly_used,
                "percentage": (hourly_used / self._max_per_hour) * 100
            },
            "daily": {
                "used": daily_used,
                "limit": self._max_per_day,
                "remaining": self._max_per_day - daily_used,
                "percentage": (daily_used / self._max_per_day) * 100
            },
            "time_since_last_change": time_since_last,
            "can_change_now": time_since_last >= self._min_interval,
            "modules_in_cooldown": len(self._module_cooldowns)
        }
    
    def _cleanup_old_timestamps(self, now: float) -> None:
        """Remove timestamps older than 24 hours."""
        cutoff = now - 86400  # 24 hours
        
        while self._recent_changes and self._recent_changes[0] < cutoff:
            self._recent_changes.popleft()
        
        # Clean up expired module cooldowns
        expired = []
        for module, cooldown_until in self._module_cooldowns.items():
            if now >= cooldown_until:
                expired.append(module)
        
        for module in expired:
            del self._module_cooldowns[module]
    
    def _count_recent_changes(self, now: float, window: float) -> int:
        """Count changes within a time window (in seconds)."""
        cutoff = now - window
        return sum(1 for ts in self._recent_changes if ts >= cutoff)
    
    def _calculate_cooldown(self, failure_count: int) -> float:
        """
        Calculate cooldown duration based on failure count.
        
        Exponential backoff: 5min, 15min, 30min, 1h, 2h, 4h
        """
        base_cooldown = 300  # 5 minutes
        max_cooldown = 14400  # 4 hours
        
        cooldown = base_cooldown * (2 ** (failure_count - 1))
        return min(cooldown, max_cooldown)
    
    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        total_requests = self._total_allowed + self._total_blocked
        block_rate = 0.0
        
        if total_requests > 0:
            block_rate = self._total_blocked / total_requests
        
        return {
            "total_allowed": self._total_allowed,
            "total_blocked": self._total_blocked,
            "block_rate": block_rate,
            "modules_in_cooldown": len(self._module_cooldowns),
            "changes_last_24h": len(self._recent_changes),
            "limits": {
                "max_per_hour": self._max_per_hour,
                "max_per_day": self._max_per_day,
                "min_interval": self._min_interval
            }
        }
