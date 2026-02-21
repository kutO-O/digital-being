"""Fallback cache for graceful degradation."""

import time
from typing import Any, Optional, Dict, Callable
from dataclasses import dataclass
import logging
import json

logger = logging.getLogger('digital_being.fallback_cache')


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    timestamp: float
    ttl: Optional[float]
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl
    
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.timestamp


class FallbackCache:
    """
    Cache for graceful degradation with fallback strategies.
    
    When a component fails:
    1. Try to use cached result from previous success
    2. If cache expired, try default value
    3. If no default, raise exception
    
    Example:
        cache = FallbackCache()
        
        # Store successful result
        cache.set("goal_selection", {"goal": "analyze files"}, ttl=300)
        
        # Later, when service fails
        try:
            result = await risky_operation()
            cache.set("goal_selection", result)
        except Exception:
            # Use cached result
            result = cache.get(
                "goal_selection",
                default={"goal": "wait"},  # Fallback if cache expired
            )
    """
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize fallback cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._defaults: Dict[str, Any] = {}
        logger.info(f"[FallbackCache] Initialized (default_ttl={default_ttl}s)")
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ):
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = use default)
        """
        ttl = ttl if ttl is not None else self.default_ttl
        
        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            ttl=ttl,
        )
        
        self._cache[key] = entry
        logger.debug(f"[FallbackCache] Set '{key}' (ttl={ttl}s)")
    
    def get(
        self,
        key: str,
        default: Optional[Any] = None,
        allow_expired: bool = True,
    ) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if not found or expired
            allow_expired: If True, return expired values (with warning)
            
        Returns:
            Cached value, default value, or registered default for key
        """
        entry = self._cache.get(key)
        
        if entry is None:
            logger.debug(f"[FallbackCache] Miss '{key}' (not found)")
            return default if default is not None else self._defaults.get(key)
        
        # Update hit count
        entry.hit_count += 1
        
        # Check expiration
        if entry.is_expired():
            if allow_expired:
                logger.warning(
                    f"[FallbackCache] Using EXPIRED cache for '{key}' "
                    f"(age={entry.age_seconds():.0f}s, ttl={entry.ttl}s)"
                )
                return entry.value
            else:
                logger.debug(f"[FallbackCache] Miss '{key}' (expired)")
                return default if default is not None else self._defaults.get(key)
        
        logger.debug(
            f"[FallbackCache] Hit '{key}' "
            f"(age={entry.age_seconds():.0f}s, hits={entry.hit_count})"
        )
        return entry.value
    
    def set_default(self, key: str, value: Any):
        """
        Register default value for key.
        
        This value is used when cache miss and no explicit default provided.
        
        Args:
            key: Cache key
            value: Default value
        """
        self._defaults[key] = value
        logger.info(f"[FallbackCache] Registered default for '{key}'")
    
    def has(self, key: str, allow_expired: bool = False) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            allow_expired: If True, count expired entries
            
        Returns:
            True if key exists (and not expired if allow_expired=False)
        """
        entry = self._cache.get(key)
        if entry is None:
            return False
        return allow_expired or not entry.is_expired()
    
    def invalidate(self, key: str):
        """Remove key from cache."""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"[FallbackCache] Invalidated '{key}'")
    
    def clear(self):
        """Clear all cached values (keeps defaults)."""
        self._cache.clear()
        logger.info("[FallbackCache] Cleared all entries")
    
    def cleanup_expired(self):
        """Remove all expired entries."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(
                f"[FallbackCache] Cleaned up {len(expired_keys)} expired entries"
            )
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_entries = len(self._cache)
        expired_entries = sum(1 for e in self._cache.values() if e.is_expired())
        total_hits = sum(e.hit_count for e in self._cache.values())
        
        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "active_entries": total_entries - expired_entries,
            "total_hits": total_hits,
            "registered_defaults": len(self._defaults),
        }


class FallbackStrategy:
    """
    Wrapper for executing functions with automatic fallback.
    
    Example:
        cache = FallbackCache()
        strategy = FallbackStrategy(cache)
        
        # Set default for when everything fails
        strategy.set_default("monologue", "Размышляю...")
        
        # Execute with auto-fallback
        result = await strategy.execute(
            key="monologue",
            func=generate_monologue,
            args=(context,),
            ttl=300,
        )
    """
    
    def __init__(self, cache: FallbackCache):
        self.cache = cache
        self.logger = logging.getLogger('digital_being.fallback_strategy')
    
    async def execute(
        self,
        key: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        ttl: Optional[int] = None,
        use_expired: bool = True,
    ) -> Any:
        """
        Execute function with automatic fallback on failure.
        
        Args:
            key: Cache key for results
            func: Async function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            ttl: Cache TTL for successful result
            use_expired: Use expired cache on failure
            
        Returns:
            Function result or cached fallback
        """
        kwargs = kwargs or {}
        
        try:
            # Try to execute function
            result = await func(*args, **kwargs)
            
            # Cache successful result
            self.cache.set(key, result, ttl=ttl)
            
            return result
            
        except Exception as e:
            self.logger.warning(
                f"[FallbackStrategy] Function '{key}' failed: {e}. "
                f"Attempting fallback..."
            )
            
            # Try to get cached result
            fallback = self.cache.get(key, allow_expired=use_expired)
            
            if fallback is not None:
                self.logger.info(
                    f"[FallbackStrategy] Using cached fallback for '{key}'"
                )
                return fallback
            
            # No fallback available - re-raise
            self.logger.error(
                f"[FallbackStrategy] No fallback available for '{key}'"
            )
            raise
    
    def set_default(self, key: str, value: Any):
        """Register default value for key."""
        self.cache.set_default(key, value)