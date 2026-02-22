"""
Graceful Shutdown Handler

Гарантирует чистое завершение работы без потери данных.

Features:
- Signal handling (SIGTERM, SIGINT, SIGQUIT)
- Graceful timeout (30s default)
- Shutdown hooks system
- State preservation
- Resource cleanup

Usage:
    handler = ShutdownHandler(timeout=30)
    handler.register_hook(lambda: save_state())
    handler.start()
    
    # On SIGTERM/SIGINT:
    # 1. Stops accepting new work
    # 2. Completes in-flight operations
    # 3. Runs shutdown hooks
    # 4. Exits cleanly
"""

from __future__ import annotations

import atexit
import logging
import signal
import sys
import threading
import time
from typing import Callable, Any

log = logging.getLogger("digital_being.shutdown")


class ShutdownHandler:
    """
    Управляет graceful shutdown системы.
    
    Features:
    - Обработка сигналов
    - Shutdown hooks
    - Timeout protection
    - Сохранение состояния
    """
    
    def __init__(self, timeout: float = 30.0) -> None:
        """
        Args:
            timeout: Максимальное время на shutdown (секунды)
        """
        self._timeout = timeout
        self._shutdown_requested = False
        self._shutdown_complete = False
        self._hooks: list[tuple[str, Callable[[], None]]] = []
        self._lock = threading.Lock()
        
        log.info(f"ShutdownHandler initialized with {timeout}s timeout")
    
    def register_hook(self, name: str, hook: Callable[[], None]) -> None:
        """
        Зарегистрировать shutdown hook.
        
        Hooks выполняются в порядке регистрации.
        
        Args:
            name: Имя hook для логов
            hook: Функция без аргументов
        """
        with self._lock:
            self._hooks.append((name, hook))
            log.debug(f"Registered shutdown hook: {name}")
    
    def start(self) -> None:
        """Запустить обработчик signal handlers."""
        # Handle common termination signals
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # SIGQUIT on Unix only
        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT, self._signal_handler)
        
        # Also register atexit for normal exits
        atexit.register(self._run_shutdown_hooks)
        
        log.info("Shutdown handler started. Press Ctrl+C for graceful shutdown.")
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Обработчик сигналов."""
        signal_name = signal.Signals(signum).name
        log.warning(f"\n\nReceived {signal_name} - initiating graceful shutdown...")
        
        with self._lock:
            if self._shutdown_requested:
                log.warning("Shutdown already in progress...")
                return
            self._shutdown_requested = True
        
        # Run shutdown in separate thread to avoid blocking signal handler
        shutdown_thread = threading.Thread(
            target=self._execute_shutdown,
            name="shutdown-thread"
        )
        shutdown_thread.start()
        
        # Wait for shutdown with timeout
        shutdown_thread.join(timeout=self._timeout)
        
        if shutdown_thread.is_alive():
            log.error(
                f"Shutdown timeout ({self._timeout}s) exceeded! "
                f"Forcing exit..."
            )
            sys.exit(1)
        else:
            log.info("✅ Graceful shutdown complete")
            sys.exit(0)
    
    def _execute_shutdown(self) -> None:
        """Выполнить shutdown sequence."""
        log.info("Starting shutdown sequence...")
        start_time = time.time()
        
        self._run_shutdown_hooks()
        
        elapsed = time.time() - start_time
        log.info(f"Shutdown completed in {elapsed:.2f}s")
        
        with self._lock:
            self._shutdown_complete = True
    
    def _run_shutdown_hooks(self) -> None:
        """Запустить все shutdown hooks."""
        if self._shutdown_complete:
            return  # Already ran
        
        log.info(f"Running {len(self._hooks)} shutdown hooks...")
        
        for name, hook in self._hooks:
            try:
                log.info(f"  ↳ Executing: {name}")
                start = time.time()
                hook()
                elapsed = time.time() - start
                log.info(f"    ✓ {name} completed in {elapsed:.2f}s")
            except Exception as e:
                log.error(f"    ✗ {name} failed: {e}", exc_info=True)
        
        log.info("✅ All shutdown hooks completed")
    
    def is_shutdown_requested(self) -> bool:
        """Проверить запрошен ли shutdown."""
        with self._lock:
            return self._shutdown_requested
    
    def request_shutdown(self) -> None:
        """Запросить shutdown программно (без signal)."""
        log.info("Programmatic shutdown requested")
        with self._lock:
            self._shutdown_requested = True
        self._execute_shutdown()


class ShutdownManager:
    """
    High-level manager для graceful shutdown.
    
    Автоматически регистрирует стандартные cleanup операции.
    """
    
    def __init__(self, timeout: float = 30.0) -> None:
        self._handler = ShutdownHandler(timeout)
        self._components: dict[str, Any] = {}
    
    def register_component(self, name: str, component: Any) -> None:
        """
        Зарегистрировать компонент для cleanup.
        
        Автоматически вызовет методы:
        - close()
        - shutdown()
        - cleanup()
        если они существуют.
        """
        self._components[name] = component
        
        # Auto-register cleanup methods
        if hasattr(component, 'close'):
            self._handler.register_hook(
                f"{name}.close",
                component.close
            )
        if hasattr(component, 'shutdown'):
            self._handler.register_hook(
                f"{name}.shutdown",
                component.shutdown
            )
        if hasattr(component, 'cleanup'):
            self._handler.register_hook(
                f"{name}.cleanup",
                component.cleanup
            )
    
    def register_hook(self, name: str, hook: Callable[[], None]) -> None:
        """Зарегистрировать custom shutdown hook."""
        self._handler.register_hook(name, hook)
    
    def start(self) -> None:
        """Запустить shutdown handler."""
        self._handler.start()
    
    def is_shutdown_requested(self) -> bool:
        """Проверить запрошен ли shutdown."""
        return self._handler.is_shutdown_requested()
    
    def request_shutdown(self) -> None:
        """Запросить shutdown."""
        self._handler.request_shutdown()


# Global shutdown manager
_shutdown_manager: ShutdownManager | None = None


def get_shutdown_manager() -> ShutdownManager:
    """Получить глобальный shutdown manager."""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = ShutdownManager()
    return _shutdown_manager


def register_shutdown_hook(name: str, hook: Callable[[], None]) -> None:
    """Удобная функция для регистрации hook."""
    get_shutdown_manager().register_hook(name, hook)


def is_shutdown_requested() -> bool:
    """Проверить запрошен ли shutdown."""
    return get_shutdown_manager().is_shutdown_requested()
