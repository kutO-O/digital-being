"""
Digital Being — ShellExecutor
Stage 21: Safe shell command execution with whitelist validation.

Features:
- Whitelist of read-only commands
- Path traversal protection
- No pipe/redirect/chain allowed
- Timeout enforcement
- Stats tracking
"""

from __future__ import annotations

import json
import logging
import platform
import shlex
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.episodic import EpisodicMemory

log = logging.getLogger("digital_being.shell_executor")

ALLOWED_COMMANDS = {
    "ls": {"args": ["-la", "-lh", "-1", "-a", "-l"], "timeout": 5},
    "cat": {"args": [], "timeout": 5},
    "head": {"args": ["-n"], "timeout": 5},
    "tail": {"args": ["-n"], "timeout": 5},
    "wc": {"args": ["-l", "-w", "-c"], "timeout": 5},
    "du": {"args": ["-sh", "-h", "-s"], "timeout": 10},
    "find": {"args": ["-name", "-type", "-maxdepth"], "timeout": 10},
    "grep": {"args": ["-i", "-r", "-n"], "timeout": 10},
    "date": {"args": [], "timeout": 2},
    "pwd": {"args": [], "timeout": 2},
    "whoami": {"args": [], "timeout": 2},
    "echo": {"args": [], "timeout": 2},
}

DANGEROUS_CHARS = ["|", ">", "<", "&", ";", "&&", "||", "`", "$", "("]

FILE_COMMANDS = {"ls", "cat", "head", "tail", "find", "grep", "du"}


class ShellExecutor:
    def __init__(self, allowed_dir: Path, memory_dir: Path, max_output_chars: int = 2000) -> None:
        self._allowed_dir = allowed_dir.resolve()
        self._memory_dir = memory_dir
        self._max_output = max_output_chars
        self._stats_path = memory_dir / "shell_stats.json"
        self._stats = self._load_stats()
        
        # Check OS support
        self._os = platform.system()
        if self._os == "Windows":
            log.warning("ShellExecutor: Windows not fully supported. Only basic commands available.")

    def _load_stats(self) -> dict:
        if not self._stats_path.exists():
            return {"total_executed": 0, "total_rejected": 0, "total_errors": 0}
        try:
            return json.loads(self._stats_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Failed to load shell_stats.json: {e}")
            return {"total_executed": 0, "total_rejected": 0, "total_errors": 0}

    def _save_stats(self) -> None:
        try:
            self._stats_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._stats_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._stats, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._stats_path)
        except OSError as e:
            log.error(f"Failed to save shell_stats.json: {e}")

    def validate_command(self, cmd: str) -> tuple[bool, str]:
        """Validate that command is safe to execute."""
        if not cmd or not cmd.strip():
            return False, "Empty command"
        
        # Check for dangerous characters
        for char in DANGEROUS_CHARS:
            if char in cmd:
                return False, f"Forbidden character: {char}"
        
        # Parse command
        try:
            tokens = shlex.split(cmd)
        except ValueError as e:
            return False, f"Failed to parse command: {e}"
        
        if not tokens:
            return False, "No command found"
        
        command = tokens[0]
        args = tokens[1:]
        
        # Check if command is allowed
        if command not in ALLOWED_COMMANDS:
            return False, f"Command not in whitelist: {command}"
        
        allowed_cmd = ALLOWED_COMMANDS[command]
        
        # Validate arguments
        i = 0
        while i < len(args):
            arg = args[i]
            
            # If arg starts with -, it must be in allowed args
            if arg.startswith("-"):
                if arg not in allowed_cmd["args"]:
                    return False, f"Argument not allowed: {arg}"
            
            # For file commands, validate paths
            if command in FILE_COMMANDS and not arg.startswith("-"):
                # This is a path argument
                try:
                    # Resolve path relative to allowed_dir
                    if Path(arg).is_absolute():
                        path = Path(arg).resolve()
                    else:
                        path = (self._allowed_dir / arg).resolve()
                    
                    # Check if path is within allowed_dir
                    try:
                        path.relative_to(self._allowed_dir)
                    except ValueError:
                        return False, f"Path outside allowed directory: {arg}"
                except Exception as e:
                    return False, f"Invalid path: {arg} ({e})"
            
            i += 1
        
        return True, ""

    def execute(self, cmd: str) -> dict:
        """Execute command and return result. Never raises exceptions."""
        # Check OS support
        if self._os == "Windows":
            return {
                "success": False,
                "stdout": "",
                "stderr": "Windows not supported yet",
                "exit_code": -1,
                "execution_time_ms": 0,
            }
        
        try:
            tokens = shlex.split(cmd)
            command = tokens[0]
            timeout = ALLOWED_COMMANDS[command]["timeout"]
            
            start_time = time.time()
            
            # Execute with shell=False for security
            result = subprocess.run(
                tokens,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                cwd=self._allowed_dir,
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Truncate output if too long
            stdout = result.stdout
            stderr = result.stderr
            
            if len(stdout) > self._max_output:
                stdout = stdout[:self._max_output] + f"\n... (truncated, {len(result.stdout)} total chars)"
            
            if len(stderr) > self._max_output:
                stderr = stderr[:self._max_output] + f"\n... (truncated, {len(result.stderr)} total chars)"
            
            return {
                "success": True,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.returncode,
                "execution_time_ms": execution_time,
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "exit_code": -1,
                "execution_time_ms": timeout * 1000,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": -1,
                "execution_time_ms": 0,
            }

    def execute_safe(self, cmd: str, episodic_memory: "EpisodicMemory") -> dict:
        """Validate, execute and log command."""
        # Validate
        valid, reason = self.validate_command(cmd)
        
        if not valid:
            self._stats["total_rejected"] += 1
            self._save_stats()
            
            episodic_memory.add_episode(
                "shell.rejected",
                f"Command rejected: {cmd[:200]}\nReason: {reason}",
                outcome="rejected",
            )
            
            log.warning(f"Shell command rejected: {cmd[:80]} | Reason: {reason}")
            
            return {
                "success": False,
                "error": reason,
                "stdout": "",
                "stderr": reason,
                "exit_code": -1,
            }
        
        # Execute
        result = self.execute(cmd)
        
        if result["success"]:
            self._stats["total_executed"] += 1
        else:
            self._stats["total_errors"] += 1
        
        self._save_stats()
        
        # Log to episodic memory
        outcome = "success" if result["success"] and result["exit_code"] == 0 else "error"
        
        episodic_memory.add_episode(
            "shell.executed",
            f"Command: {cmd}\nExit code: {result['exit_code']}\nOutput: {result['stdout'][:300]}",
            outcome=outcome,
            data={
                "command": cmd,
                "exit_code": result["exit_code"],
                "execution_time_ms": result.get("execution_time_ms", 0),
            },
        )
        
        log.info(
            f"Shell command executed: {cmd[:80]} | "
            f"exit_code={result['exit_code']} time={result.get('execution_time_ms', 0)}ms"
        )
        
        return result

    def get_stats(self) -> dict:
        """Get execution statistics."""
        return dict(self._stats)

    def get_allowed_commands(self) -> list[str]:
        """Get list of allowed commands."""
        return list(ALLOWED_COMMANDS.keys())

    def get_allowed_dir(self) -> str:
        """Get allowed directory path."""
        return str(self._allowed_dir)
