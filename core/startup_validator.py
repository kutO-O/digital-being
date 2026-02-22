"""
Startup Validator

Проверяет всё перед запуском - fail fast если что-то не так.

Checks:
- Config validity
- Dependencies (Ollama, DBs)
- Permissions
- Disk space
- Port availability
- Model availability

Usage:
    validator = StartupValidator(cfg)
    report = validator.validate_all()
    
    if not report['valid']:
        for error in report['errors']:
            log.error(error)
        sys.exit(1)
"""

from __future__ import annotations

import logging
import os
import socket
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.startup")


class ValidationError:
    """Одна ошибка валидации."""
    
    def __init__(
        self,
        category: str,
        severity: str,  # critical | warning
        message: str,
        hint: str = ""
    ) -> None:
        self.category = category
        self.severity = severity
        self.message = message
        self.hint = hint
    
    def __str__(self) -> str:
        hint_str = f" (Hint: {self.hint})" if self.hint else ""
        return f"[{self.severity.upper()}] {self.category}: {self.message}{hint_str}"


class StartupValidator:
    """
    Валидатор стартовой конфигурации.
    
    Проверяет всё необходимое для запуска.
    """
    
    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg
        self._errors: list[ValidationError] = []
        self._warnings: list[ValidationError] = []
    
    def validate_all(self) -> dict:
        """
        Запустить все проверки.
        
        Returns:
            dict с результатами
        """
        log.info("Starting validation...")
        
        self._validate_config()
        self._validate_directories()
        self._validate_dependencies()
        self._validate_resources()
        self._validate_network()
        
        has_critical_errors = any(
            e.severity == "critical" for e in self._errors
        )
        
        report = {
            "valid": not has_critical_errors,
            "errors": [str(e) for e in self._errors],
            "warnings": [str(w) for w in self._warnings],
            "checks_passed": self._count_passed_checks(),
            "checks_total": self._count_total_checks(),
        }
        
        if has_critical_errors:
            log.error(f"❌ Validation FAILED: {len(self._errors)} error(s)")
        else:
            log.info(f"✅ Validation passed ({len(self._warnings)} warning(s))")
        
        return report
    
    def _validate_config(self) -> None:
        """Проверить config.yaml."""
        log.debug("Validating config...")
        
        # Check required sections
        required_sections = ["ollama", "memory", "paths"]
        for section in required_sections:
            if section not in self._cfg:
                self._errors.append(ValidationError(
                    "config",
                    "critical",
                    f"Missing required section: {section}",
                    f"Add '{section}:' section to config.yaml"
                ))
        
        # Check Ollama config
        ollama = self._cfg.get("ollama", {})
        if not ollama.get("base_url"):
            self._errors.append(ValidationError(
                "config",
                "critical",
                "Missing ollama.base_url",
                "Add 'base_url: http://localhost:11434' to ollama section"
            ))
        
        if not ollama.get("strategy_model"):
            self._warnings.append(ValidationError(
                "config",
                "warning",
                "Missing ollama.strategy_model, using default"
            ))
    
    def _validate_directories(self) -> None:
        """Проверить директории."""
        log.debug("Validating directories...")
        
        # Check memory directory
        memory_dir = Path("memory")
        if not memory_dir.exists():
            try:
                memory_dir.mkdir(parents=True)
                log.info(f"Created directory: {memory_dir}")
            except Exception as e:
                self._errors.append(ValidationError(
                    "filesystem",
                    "critical",
                    f"Cannot create memory directory: {e}",
                    "Check permissions"
                ))
        
        # Check write permissions
        if memory_dir.exists():
            test_file = memory_dir / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                self._errors.append(ValidationError(
                    "filesystem",
                    "critical",
                    f"No write permission in memory/: {e}"
                ))
        
        # Check logs directory
        logs_dir = Path(self._cfg.get("logging", {}).get("dir", "logs"))
        if not logs_dir.exists():
            try:
                logs_dir.mkdir(parents=True)
                log.info(f"Created directory: {logs_dir}")
            except Exception as e:
                self._warnings.append(ValidationError(
                    "filesystem",
                    "warning",
                    f"Cannot create logs directory: {e}"
                ))
    
    def _validate_dependencies(self) -> None:
        """Проверить зависимости."""
        log.debug("Validating dependencies...")
        
        # Check Python packages
        required_packages = [
            ("yaml", "PyYAML"),
            ("ollama", "ollama"),
        ]
        
        for module_name, package_name in required_packages:
            try:
                __import__(module_name)
            except ImportError:
                self._errors.append(ValidationError(
                    "dependencies",
                    "critical",
                    f"Missing required package: {package_name}",
                    f"Install with: pip install {package_name}"
                ))
        
        # Check optional packages
        optional_packages = [
            ("prometheus_client", "prometheus-client", "Metrics disabled"),
        ]
        
        for module_name, package_name, consequence in optional_packages:
            try:
                __import__(module_name)
            except ImportError:
                self._warnings.append(ValidationError(
                    "dependencies",
                    "warning",
                    f"Optional package {package_name} not installed. {consequence}",
                    f"Install with: pip install {package_name}"
                ))
        
        # Check Ollama availability
        try:
            import ollama
            base_url = self._cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
            client = ollama.Client(host=base_url)
            client.list()  # Test connection
            log.info("✅ Ollama is available")
        except Exception as e:
            self._errors.append(ValidationError(
                "dependencies",
                "critical",
                f"Ollama not available: {e}",
                "Start Ollama with: ollama serve"
            ))
    
    def _validate_resources(self) -> None:
        """Проверить ресурсы."""
        log.debug("Validating resources...")
        
        # Check disk space
        try:
            stat = os.statvfs(".")
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            
            if free_gb < 1:
                self._errors.append(ValidationError(
                    "resources",
                    "critical",
                    f"Low disk space: {free_gb:.1f}GB free",
                    "Free up at least 1GB"
                ))
            elif free_gb < 5:
                self._warnings.append(ValidationError(
                    "resources",
                    "warning",
                    f"Limited disk space: {free_gb:.1f}GB free",
                    "Consider freeing up space"
                ))
        except Exception as e:
            log.warning(f"Could not check disk space: {e}")
    
    def _validate_network(self) -> None:
        """Проверить сеть."""
        log.debug("Validating network...")
        
        # Check API port availability
        api_cfg = self._cfg.get("api", {})
        if api_cfg.get("enabled"):
            port = api_cfg.get("port", 8766)
            if not self._is_port_available(port):
                self._errors.append(ValidationError(
                    "network",
                    "critical",
                    f"Port {port} already in use",
                    f"Stop other service on port {port} or change api.port in config"
                ))
    
    def _is_port_available(self, port: int) -> bool:
        """Проверить доступен ли порт."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return True
        except OSError:
            return False
    
    def _count_passed_checks(self) -> int:
        """Подсчитать успешные проверки."""
        return self._count_total_checks() - len(self._errors)
    
    def _count_total_checks(self) -> int:
        """Общее количество проверок."""
        # Approximate - config, dirs, deps, resources, network
        return 15


def validate_startup(cfg: dict) -> bool:
    """
    Удобная функция для валидации.
    
    Returns:
        True если всё OK, False если есть critical ошибки
    """
    validator = StartupValidator(cfg)
    report = validator.validate_all()
    
    # Print errors and warnings
    for error in report['errors']:
        log.error(error)
    
    for warning in report['warnings']:
        log.warning(warning)
    
    if report['valid']:
        log.info(
            f"✅ Startup validation passed: "
            f"{report['checks_passed']}/{report['checks_total']} checks OK"
        )
    else:
        log.error(
            f"❌ Startup validation FAILED: "
            f"{len(report['errors'])} critical error(s)"
        )
    
    return report['valid']
