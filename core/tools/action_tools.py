"""Action tools for output and external interactions."""

from __future__ import annotations

import asyncio
import json
import logging
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.tools.base_tool import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
)

log = logging.getLogger("digital_being.tools.actions")


# ============================================================================
# WINDOWS NOTIFICATIONS
# ============================================================================

class WindowsNotificationTool(BaseTool):
    """Send Windows 10/11 toast notifications."""
    
    @property
    def name(self) -> str:
        return "windows_notify"
    
    @property
    def description(self) -> str:
        return "Show Windows toast notification"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="title",
                type="string",
                description="Notification title",
                required=True,
            ),
            ToolParameter(
                name="message",
                type="string",
                description="Notification message",
                required=True,
            ),
            ToolParameter(
                name="duration",
                type="int",
                description="Duration in seconds",
                required=False,
                default=10,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Show notification."""
        title = kwargs["title"]
        message = kwargs["message"]
        duration = kwargs.get("duration", 10)
        
        if platform.system() != "Windows":
            return ToolResult(
                success=False,
                data=None,
                error="Windows notifications only work on Windows",
                cost=0,
            )
        
        try:
            try:
                from win10toast import ToastNotifier
            except ImportError:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Install win10toast: pip install win10toast",
                    cost=0,
                )
            
            toaster = ToastNotifier()
            
            loop = asyncio.get_event_loop()
            
            def _show():
                toaster.show_toast(
                    title,
                    message,
                    duration=duration,
                    threaded=True,
                )
            
            await loop.run_in_executor(None, _show)
            
            return ToolResult(
                success=True,
                data={
                    "title": title,
                    "shown_at": datetime.now().isoformat(),
                },
                cost=0,
            )
        
        except Exception as e:
            log.error(f"Windows notification failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Notification error: {str(e)}",
                cost=0,
            )


# ============================================================================
# GITHUB INTEGRATION (using MCP server)
# ============================================================================

class GitHubIssueTool(BaseTool):
    """Create GitHub issues using MCP server."""
    
    def __init__(self, mcp_client=None):
        super().__init__()
        self._mcp_client = mcp_client
    
    @property
    def name(self) -> str:
        return "github_create_issue"
    
    @property
    def description(self) -> str:
        return "Create issue in GitHub repository"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.INTEGRATION
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="title",
                type="string",
                description="Issue title",
                required=True,
            ),
            ToolParameter(
                name="body",
                type="string",
                description="Issue description",
                required=True,
            ),
            ToolParameter(
                name="labels",
                type="list",
                description="List of labels",
                required=False,
                default=[],
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Create GitHub issue."""
        title = kwargs["title"]
        body = kwargs["body"]
        labels = kwargs.get("labels", [])
        
        if not self._mcp_client:
            return ToolResult(
                success=False,
                data=None,
                error="MCP client not configured",
                cost=0,
            )
        
        try:
            # Call MCP GitHub server to create issue
            # This is a placeholder - actual implementation depends on MCP setup
            result = await self._mcp_client.call_tool(
                "github_mcp_direct_issue_write",
                {
                    "owner": "kutO-O",
                    "repo": "digital-being",
                    "method": "create",
                    "title": title,
                    "body": body,
                    "labels": labels,
                }
            )
            
            return ToolResult(
                success=True,
                data={
                    "title": title,
                    "created_at": datetime.now().isoformat(),
                },
                metadata={"platform": "github"},
                cost=2,
            )
        
        except Exception as e:
            log.error(f"GitHub issue creation failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"GitHub error: {str(e)}",
                cost=1,
            )


# ============================================================================
# HTTP REQUEST TOOL
# ============================================================================

class HTTPRequestTool(BaseTool):
    """Make HTTP requests to external APIs."""
    
    @property
    def name(self) -> str:
        return "http_request"
    
    @property
    def description(self) -> str:
        return "Make HTTP GET/POST request"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="Request URL",
                required=True,
            ),
            ToolParameter(
                name="method",
                type="string",
                description="HTTP method (GET, POST, PUT, DELETE)",
                required=False,
                default="GET",
            ),
            ToolParameter(
                name="headers",
                type="dict",
                description="Request headers",
                required=False,
                default={},
            ),
            ToolParameter(
                name="body",
                type="string",
                description="Request body (JSON string)",
                required=False,
                default=None,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Make HTTP request."""
        url = kwargs["url"]
        method = kwargs.get("method", "GET").upper()
        headers = kwargs.get("headers", {})
        body = kwargs.get("body")
        
        try:
            import urllib.request
            import urllib.error
            
            # Prepare request
            req_headers = {"User-Agent": "DigitalBeing/1.0"}
            req_headers.update(headers)
            
            data = None
            if body:
                data = body.encode() if isinstance(body, str) else body
            
            req = urllib.request.Request(
                url,
                data=data,
                headers=req_headers,
                method=method,
            )
            
            loop = asyncio.get_event_loop()
            
            def _request():
                try:
                    response = urllib.request.urlopen(req, timeout=15)
                    content = response.read().decode("utf-8")
                    status = response.status
                    return content, status, None
                except urllib.error.HTTPError as e:
                    return None, e.code, str(e)
                except Exception as e:
                    return None, 0, str(e)
            
            content, status, error = await loop.run_in_executor(None, _request)
            
            if error:
                return ToolResult(
                    success=False,
                    data={"status": status},
                    error=error,
                    cost=1,
                )
            
            # Try to parse JSON
            parsed_content = None
            try:
                parsed_content = json.loads(content)
            except:
                parsed_content = content
            
            return ToolResult(
                success=True,
                data={
                    "status": status,
                    "content": parsed_content,
                    "content_length": len(content),
                },
                metadata={"url": url, "method": method},
                cost=2,
            )
        
        except Exception as e:
            log.error(f"HTTP request failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Request error: {str(e)}",
                cost=1,
            )


# ============================================================================
# DATABASE LOGGING
# ============================================================================

class DatabaseLogTool(BaseTool):
    """Log actions to SQLite database."""
    
    def __init__(self, db_path: Path):
        super().__init__()
        self._db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create action_log table if not exists."""
        import sqlite3
        
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                description TEXT,
                metadata TEXT,
                success INTEGER NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    
    @property
    def name(self) -> str:
        return "db_log_action"
    
    @property
    def description(self) -> str:
        return "Log action to database"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.DATA
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action_type",
                type="string",
                description="Type of action",
                required=True,
            ),
            ToolParameter(
                name="description",
                type="string",
                description="Action description",
                required=True,
            ),
            ToolParameter(
                name="metadata",
                type="dict",
                description="Additional metadata",
                required=False,
                default={},
            ),
            ToolParameter(
                name="success",
                type="bool",
                description="Whether action succeeded",
                required=True,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Log to database."""
        action_type = kwargs["action_type"]
        description = kwargs["description"]
        metadata = kwargs.get("metadata", {})
        success = kwargs["success"]
        
        try:
            import sqlite3
            
            loop = asyncio.get_event_loop()
            
            def _log():
                conn = sqlite3.connect(str(self._db_path))
                conn.execute(
                    "INSERT INTO action_log (timestamp, action_type, description, metadata, success) VALUES (?, ?, ?, ?, ?)",
                    (
                        datetime.now().isoformat(),
                        action_type,
                        description,
                        json.dumps(metadata),
                        1 if success else 0,
                    )
                )
                conn.commit()
                row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.close()
                return row_id
            
            row_id = await loop.run_in_executor(None, _log)
            
            return ToolResult(
                success=True,
                data={"id": row_id, "logged_at": datetime.now().isoformat()},
                cost=1,
            )
        
        except Exception as e:
            log.error(f"Database log failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"DB error: {str(e)}",
                cost=0,
            )
