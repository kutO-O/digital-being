"""
Digital Being — Hot Reloader
Система горячей перезагрузки Python модулей без остановки процесса.
"""

from __future__ import annotations

import importlib
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Set, Callable, Any

log = logging.getLogger("digital_being.hot_reloader")


class HotReloader:
    """
    Отслеживает изменения Python файлов и перезагружает модули.
    
    Возможности:
    - Автоматическое обнаружение изменений
    - Безопасная перезагрузка с откатом
    - Обработка зависимостей
    - Callback-и после перезагрузки
    - Blacklist для критичных модулей
    """
    
    def __init__(
        self,
        watch_dirs: list[str] | None = None,
        check_interval: float = 2.0,
        auto_reload: bool = True
    ):
        """
        Args:
            watch_dirs: Директории для отслеживания (default: ["core"])
            check_interval: Интервал проверки в секундах
            auto_reload: Автоматически перезагружать при изменениях
        """
        self._watch_dirs = watch_dirs or ["core"]
        self._check_interval = check_interval
        self._auto_reload = auto_reload
        
        # Хранение времени модификации файлов
        self._file_mtimes: Dict[str, float] = {}
        
        # Хранение резервных копий модулей
        self._module_backups: Dict[str, Any] = {}
        
        # Callback-и для выполнения после reload
        self._post_reload_callbacks: Dict[str, list[Callable]] = {}
        
        # Blacklist модулей (не перезагружать)
        self._blacklist: Set[str] = {
            "main",
            "config",
            "__main__",
        }
        
        # Статистика
        self._stats = {
            "total_reloads": 0,
            "successful_reloads": 0,
            "failed_reloads": 0,
            "last_reload": None,
        }
        
        self._last_check = 0.0
        
        log.info(
            f"HotReloader initialized: watching {self._watch_dirs}, "
            f"interval={check_interval}s"
        )
    
    def add_callback(self, module_name: str, callback: Callable) -> None:
        """
        Добавить callback для выполнения после reload модуля.
        
        Args:
            module_name: Имя модуля (например "core.emotions")
            callback: Функция для вызова после reload
        """
        if module_name not in self._post_reload_callbacks:
            self._post_reload_callbacks[module_name] = []
        self._post_reload_callbacks[module_name].append(callback)
        log.debug(f"Added callback for {module_name}")
    
    def blacklist_module(self, module_name: str) -> None:
        """Добавить модуль в blacklist (не будет перезагружаться)"""
        self._blacklist.add(module_name)
        log.info(f"Module blacklisted: {module_name}")
    
    def scan_files(self) -> Dict[str, float]:
        """
        Сканировать все Python файлы в watched директориях.
        
        Returns:
            Dict[file_path, modification_time]
        """
        files = {}
        
        for watch_dir in self._watch_dirs:
            path = Path(watch_dir)
            if not path.exists():
                log.warning(f"Watch directory does not exist: {watch_dir}")
                continue
            
            for py_file in path.rglob("*.py"):
                try:
                    mtime = py_file.stat().st_mtime
                    files[str(py_file)] = mtime
                except Exception as e:
                    log.debug(f"Cannot stat {py_file}: {e}")
        
        return files
    
    def detect_changes(self) -> list[str]:
        """
        Обнаружить изменённые файлы.
        
        Returns:
            Список путей к изменённым файлам
        """
        current_files = self.scan_files()
        changed_files = []
        
        for file_path, mtime in current_files.items():
            # Новый файл
            if file_path not in self._file_mtimes:
                self._file_mtimes[file_path] = mtime
                continue
            
            # Файл изменён
            if mtime > self._file_mtimes[file_path]:
                changed_files.append(file_path)
                self._file_mtimes[file_path] = mtime
        
        return changed_files
    
    def file_to_module(self, file_path: str) -> str | None:
        """
        Конвертировать путь файла в имя модуля.
        
        Args:
            file_path: Путь типа "core/emotions.py"
        
        Returns:
            Имя модуля типа "core.emotions" или None
        """
        try:
            path = Path(file_path)
            
            # Убираем .py
            if path.suffix == ".py":
                path = path.with_suffix("")
            
            # Конвертируем путь в module name
            parts = path.parts
            module_name = ".".join(parts)
            
            # Убираем __init__
            if module_name.endswith(".__init__"):
                module_name = module_name[:-9]
            
            return module_name
        except Exception as e:
            log.debug(f"Cannot convert {file_path} to module: {e}")
            return None
    
    def reload_module(self, module_name: str) -> bool:
        """
        Перезагрузить модуль.
        
        Args:
            module_name: Имя модуля для перезагрузки
        
        Returns:
            True если успешно
        """
        # Проверка blacklist
        if module_name in self._blacklist:
            log.debug(f"Module {module_name} is blacklisted, skipping")
            return False
        
        # Проверка что модуль загружен
        if module_name not in sys.modules:
            log.debug(f"Module {module_name} not loaded, skipping")
            return False
        
        log.info(f"🔄 Hot-reloading module: {module_name}")
        
        try:
            # Сохраняем backup
            module = sys.modules[module_name]
            self._module_backups[module_name] = module
            
            # RELOAD!
            importlib.reload(module)
            
            # Выполняем callbacks
            if module_name in self._post_reload_callbacks:
                for callback in self._post_reload_callbacks[module_name]:
                    try:
                        callback(module)
                    except Exception as e:
                        log.error(
                            f"Callback failed for {module_name}: {e}"
                        )
            
            # Статистика
            self._stats["total_reloads"] += 1
            self._stats["successful_reloads"] += 1
            self._stats["last_reload"] = time.time()
            
            log.info(f"✅ Successfully reloaded: {module_name}")
            return True
        
        except Exception as e:
            log.error(f"❌ Failed to reload {module_name}: {e}")
            
            # Откат
            if module_name in self._module_backups:
                sys.modules[module_name] = self._module_backups[module_name]
                log.info(f"Rolled back {module_name} to previous version")
            
            self._stats["failed_reloads"] += 1
            return False
    
    def check(self) -> Dict[str, bool]:
        """
        Проверить изменения и перезагрузить модули.
        
        Returns:
            Dict[module_name, reload_success]
        """
        # Throttling
        now = time.time()
        if now - self._last_check < self._check_interval:
            return {}
        
        self._last_check = now
        
        # Обнаружение изменений
        changed_files = self.detect_changes()
        
        if not changed_files:
            return {}
        
        log.info(f"Detected {len(changed_files)} changed file(s)")
        
        # Перезагрузка
        results = {}
        
        for file_path in changed_files:
            module_name = self.file_to_module(file_path)
            
            if not module_name:
                continue
            
            if self._auto_reload:
                success = self.reload_module(module_name)
                results[module_name] = success
            else:
                log.info(
                    f"Auto-reload disabled, skipping {module_name}"
                )
                results[module_name] = False
        
        return results
    
    def force_reload(self, module_name: str) -> bool:
        """Принудительно перезагрузить модуль (игнорируя mtime)"""
        return self.reload_module(module_name)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику перезагрузок"""
        return {
            **self._stats,
            "blacklist_size": len(self._blacklist),
            "watched_dirs": self._watch_dirs,
            "tracked_files": len(self._file_mtimes),
        }
    
    def enable_auto_reload(self) -> None:
        """Включить автоматическую перезагрузку"""
        self._auto_reload = True
        log.info("Auto-reload enabled")
    
    def disable_auto_reload(self) -> None:
        """Отключить автоматическую перезагрузку"""
        self._auto_reload = False
        log.info("Auto-reload disabled")
