"""
Digital Being — ShellExecutor
Stage 21: Safe shell command execution with whitelist.

Read-only commands: ls, cat, head, tail, wc, du, find, grep, date, pwd, whoami, echo
Strict validation: path traversal protection, no pipes/redirects, allowed_dir restriction
"""

from __future__ import annotations

import json
import logging
import platform
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.episodic import EpisodicMemory

log = logging.getLogger("digital_being.shell_executor")

ALLOWED_COMMANDS = {
    "ls": {"args": ["-la", "-lh", "-1", "-a", "-l", "-h"], "timeout": 5},
    "cat": {"args": [], "timeout": 5},
    "head": {"args": ["-n"], "timeout": 5},
    "tail": {"args": ["-n"], "timeout": 5},
    "wc": {"args": ["-l", "-w", "-c"], "timeout": 5},
    "du": {"args": ["-sh", "-h", "-s"], "timeout": 10},
    "find": {"args": ["-name", "-type", "-maxdepth"], "timeout": 10},
    "grep": {"args": ["-i", "-r", "-n", "-l"], "timeout": 10},
    "date": {"args": [], "timeout": 2},
    "pwd": {"args": [], "timeout": 2},
    "whoami": {"args": [], "timeout": 2},
    "echo": {"args": [], "timeout": 2},
}

DANGEROUS_CHARS = ["|", ">", "<", "&", ";", "&&", "||", "`", "$(", ")"]


class ShellExecutor:
    def __init__(self, allowed_dir: Path, memory_dir: Path, max_output_chars: int = 2000) -> None:
        self._allowed_dir = allowed_dir.resolve()
        self._memory_dir = memory_dir
        self._max_output = max_output_chars
        self._stats_path = memory_dir / "shell_stats.json"
        self._stats = self._load_stats()
        
        # Check if Windows
        self._is_windows = platform.system() == "Windows"
        
        log.info(f"ShellExecutor initialized. allowed_dir={self._allowed_dir}, windows={self._is_windows}")

    def _load_stats(self) -> dict:
        if not self._stats_path.exists():
            return {"total_executed": 0, "total_rejected": 0, "total_errors": 0}
        try:
            return json.loads(self._stats_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Failed to load {self._stats_path}: {e}")
            return {"total_executed": 0, "total_rejected": 0, "total_errors": 0}

    def _save_stats(self) -> None:
        try:
            self._memory_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._stats_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._stats, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._stats_path)
        except OSError as e:
            log.error(f"Failed to save {self._stats_path}: {e}")

    def validate_command(self, cmd: str) -> tuple[bool, str]:
        """Валидировать команду."""
        if not cmd or not cmd.strip():
            return False, "empty command"
        
        # Windows not supported yet
        if self._is_windows:
            return False, "Windows not supported yet"
        
        # Check for dangerous characters
        for char in DANGEROUS_CHARS:
            if char in cmd:
                return False, f"dangerous character '{char}' detected"
        
        # Parse command
        try:
            tokens = shlex.split(cmd)
        except ValueError as e:
            return False, f"failed to parse command: {e}"
        
        if not tokens:
            return False, "no tokens after parsing"
        
        command = tokens[0]
        args = tokens[1:]
        
        # Check if command is allowed
        if command not in ALLOWED_COMMANDS:
            return False, f"command '{command}' not in whitelist"
        
        allowed_args = ALLOWED_COMMANDS[command]["args"]
        
        # Validate arguments
        file_commands = ["ls", "cat", "head", "tail", "find", "grep", "wc", "du"]
        
        i = 0
        while i < len(args):
            arg = args[i]
            
            # Check if it's a flag
            if arg.startswith("-"):
                # For flags with values (like -n 10)
                if arg in ["-n", "-maxdepth", "-name", "-type"]:
                    if arg not in allowed_args:
                        return False, f"argument '{arg}' not allowed for '{command}'"
                    i += 2  # Skip flag and its value
                    continue
                else:
                    # Simple flag
                    if arg not in allowed_args:
                        return False, f"argument '{arg}' not allowed for '{command}'"
                    i += 1
                    continue
            
            # It's a file/directory path - validate if command works with files
            if command in file_commands:
                try:
                    path = Path(arg)
                    # If relative path, resolve against allowed_dir
                    if not path.is_absolute():
                        path = (self._allowed_dir / path).resolve()
                    else:
                        path = path.resolve()
                    
                    # Check if path is within allowed_dir
                    try:
                        path.relative_to(self._allowed_dir)
                    except ValueError:
                        return False, f"path '{arg}' is outside allowed directory"
                except Exception as e:
                    return False, f"invalid path '{arg}': {e}"
            
            i += 1
        
        return True, ""

    def execute(self, cmd: str) -> dict:
        """Выполнить команду без валидации (используй execute_safe)."""
        try:
            tokens = shlex.split(cmd)
            command = tokens[0]
            timeout = ALLOWED_COMMANDS.get(command, {}).get("timeout", 5)
            
            start_time = time.monotonic()
            result = subprocess.run(
                tokens,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._allowed_dir),
            )
            execution_time_ms = int((time.monotonic() - start_time) * 1000)
            
            stdout = result.stdout[:self._max_output] if result.stdout else ""
            stderr = result.stderr[:self._max_output] if result.stderr else ""
            
            return {
                "success": True,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.returncode,
                "execution_time_ms": execution_time_ms,
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timeout ({timeout}s)",
                "exit_code": -1,
                "execution_time_ms": timeout * 1000,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "execution_time_ms": 0,
            }

    def execute_safe(self, cmd: str, episodic_memory: "EpisodicMemory") -> dict:
        """Выполнить команду с валидацией и записью в память."""
        # Validate
        valid, reason = self.validate_command(cmd)
        
        if not valid:
            self._stats["total_rejected"] += 1
            self._save_stats()
            
            episodic_memory.add_episode(
                "shell.rejected",
                f"Command rejected: {cmd[:200]}. Reason: {reason}",
                outcome="error",
                data={"command": cmd, "reason": reason},
            )
            
            log.warning(f"Shell command rejected: {cmd[:80]} | {reason}")
            return {"success": False, "error": f"Rejected: {reason}", "command": cmd}
        
        # Execute
        result = self.execute(cmd)
        
        if result["success"]:
            self._stats["total_executed"] += 1
            self._save_stats()
            
            episodic_memory.add_episode(
                "shell.executed",
                f"Command: {cmd}\nOutput:\n{result['stdout'][:500]}",
                outcome="success",
                data={
                    "command": cmd,
                    "exit_code": result["exit_code"],
                    "execution_time_ms": result["execution_time_ms"],
                },
            )
            
            log.info(f"Shell command executed: {cmd[:80]} | exit_code={result['exit_code']}")
        else:
            self._stats["total_errors"] += 1
            self._save_stats()
            
            episodic_memory.add_episode(
                "shell.error",
                f"Command failed: {cmd[:200]}\nError: {result['stderr'][:200]}",
                outcome="error",
                data={"command": cmd, "stderr": result["stderr"]},
            )
            
            log.error(f"Shell command error: {cmd[:80]} | {result['stderr'][:100]}")
        
        return result

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_allowed_commands(self) -> list[str]:
        return list(ALLOWED_COMMANDS.keys())

    def get_allowed_dir(self) -> str:
        return str(self._allowed_dir)
