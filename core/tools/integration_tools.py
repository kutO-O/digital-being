"""External integration tools for Phase 3: Email, Calendar, Files, Web APIs."""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import shutil
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.tools.base_tool import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
)

log = logging.getLogger("digital_being.tools.integration")


# ============================================================================
# EMAIL INTEGRATION
# ============================================================================

class EmailTool(BaseTool):
    """Send and receive emails via SMTP/IMAP."""
    
    def __init__(
        self,
        smtp_server: Optional[str] = None,
        smtp_port: int = 587,
        imap_server: Optional[str] = None,
        imap_port: int = 993,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ):
        super().__init__()
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.email = email
        self.password = password
    
    @property
    def name(self) -> str:
        return "email"
    
    @property
    def description(self) -> str:
        return "Send and receive emails via SMTP/IMAP"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMMUNICATION
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action: send, check_inbox, read",
                required=True,
            ),
            ToolParameter(
                name="to",
                type="string",
                description="Recipient email (for send)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="subject",
                type="string",
                description="Email subject (for send)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="body",
                type="string",
                description="Email body (for send)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="limit",
                type="int",
                description="Max emails to fetch (for check_inbox)",
                required=False,
                default=10,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute email operation."""
        action = kwargs["action"].lower()
        
        if not self.email or not self.password:
            return ToolResult(
                success=False,
                data=None,
                error="Email not configured. Set email credentials in config.",
                cost=0,
            )
        
        try:
            if action == "send":
                return await self._send_email(
                    to=kwargs.get("to", ""),
                    subject=kwargs.get("subject", ""),
                    body=kwargs.get("body", ""),
                )
            
            elif action == "check_inbox":
                return await self._check_inbox(
                    limit=kwargs.get("limit", 10)
                )
            
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Unknown action: {action}",
                    cost=0,
                )
        
        except Exception as e:
            log.error(f"Email action '{action}' failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )
    
    async def _send_email(self, to: str, subject: str, body: str) -> ToolResult:
        """Send email via SMTP."""
        if not to:
            return ToolResult(
                success=False,
                data=None,
                error="Recipient email required",
                cost=0,
            )
        
        try:
            import smtplib
            
            loop = asyncio.get_event_loop()
            
            def _send():
                msg = MIMEMultipart()
                msg["From"] = self.email
                msg["To"] = to
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))
                
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.email, self.password)
                    server.send_message(msg)
            
            await loop.run_in_executor(None, _send)
            
            return ToolResult(
                success=True,
                data={
                    "to": to,
                    "subject": subject,
                    "sent_at": datetime.now().isoformat(),
                },
                metadata={"action": "send"},
                cost=2,
            )
        
        except Exception as e:
            log.error(f"Failed to send email: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Send failed: {str(e)}",
                cost=1,
            )
    
    async def _check_inbox(self, limit: int) -> ToolResult:
        """Check inbox via IMAP."""
        try:
            import imaplib
            import email
            from email.header import decode_header
            
            loop = asyncio.get_event_loop()
            
            def _check():
                imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
                imap.login(self.email, self.password)
                imap.select("INBOX")
                
                # Search for unread emails
                status, messages = imap.search(None, "UNSEEN")
                email_ids = messages[0].split()
                
                emails = []
                for email_id in email_ids[-limit:]:
                    status, msg_data = imap.fetch(email_id, "(RFC822)")
                    
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Decode subject
                            subject = decode_header(msg["Subject"])[0][0]
                            if isinstance(subject, bytes):
                                subject = subject.decode()
                            
                            # Get body
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode()
                                        break
                            else:
                                body = msg.get_payload(decode=True).decode()
                            
                            emails.append({
                                "id": email_id.decode(),
                                "from": msg["From"],
                                "subject": subject,
                                "body": body[:500],  # Truncate
                                "date": msg["Date"],
                            })
                
                imap.close()
                imap.logout()
                
                return emails
            
            emails = await loop.run_in_executor(None, _check)
            
            return ToolResult(
                success=True,
                data={
                    "emails": emails,
                    "count": len(emails),
                },
                metadata={"action": "check_inbox"},
                cost=3,
            )
        
        except Exception as e:
            log.error(f"Failed to check inbox: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Check failed: {str(e)}",
                cost=1,
            )


# ============================================================================
# CALENDAR INTEGRATION
# ============================================================================

class CalendarTool(BaseTool):
    """Manage calendar events (local JSON-based calendar)."""
    
    def __init__(self, calendar_path: Path):
        super().__init__()
        self._calendar_path = calendar_path
        self._events = []
    
    @property
    def name(self) -> str:
        return "calendar"
    
    @property
    def description(self) -> str:
        return "Manage calendar: create events, list upcoming, check availability"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PRODUCTIVITY
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action: create, list, upcoming, delete",
                required=True,
            ),
            ToolParameter(
                name="title",
                type="string",
                description="Event title (for create)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="start_time",
                type="string",
                description="Start time ISO format (for create)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="end_time",
                type="string",
                description="End time ISO format (for create)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="description",
                type="string",
                description="Event description (for create)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="days",
                type="int",
                description="Days ahead to list (for upcoming)",
                required=False,
                default=7,
            ),
        ]
    
    async def _load_calendar(self):
        """Load calendar from file."""
        if self._calendar_path.exists():
            self._events = json.loads(self._calendar_path.read_text(encoding="utf-8"))
        else:
            self._events = []
    
    async def _save_calendar(self):
        """Save calendar to file."""
        self._calendar_path.parent.mkdir(parents=True, exist_ok=True)
        self._calendar_path.write_text(
            json.dumps(self._events, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute calendar operation."""
        action = kwargs["action"].lower()
        
        try:
            await self._load_calendar()
            
            if action == "create":
                title = kwargs.get("title", "")
                start_time = kwargs.get("start_time", "")
                end_time = kwargs.get("end_time", "")
                description = kwargs.get("description", "")
                
                if not title or not start_time:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Title and start_time required",
                        cost=0,
                    )
                
                event = {
                    "id": len(self._events) + 1,
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time or start_time,
                    "description": description,
                    "created_at": datetime.now().isoformat(),
                }
                
                self._events.append(event)
                await self._save_calendar()
                
                return ToolResult(
                    success=True,
                    data=event,
                    metadata={"action": "create"},
                    cost=1,
                )
            
            elif action == "upcoming":
                days = kwargs.get("days", 7)
                now = datetime.now()
                future = now + timedelta(days=days)
                
                upcoming = []
                for event in self._events:
                    start = datetime.fromisoformat(event["start_time"])
                    if now <= start <= future:
                        upcoming.append(event)
                
                # Sort by start time
                upcoming.sort(key=lambda e: e["start_time"])
                
                return ToolResult(
                    success=True,
                    data={
                        "events": upcoming,
                        "count": len(upcoming),
                        "days": days,
                    },
                    metadata={"action": "upcoming"},
                    cost=1,
                )
            
            elif action == "list":
                return ToolResult(
                    success=True,
                    data={
                        "events": self._events,
                        "count": len(self._events),
                    },
                    metadata={"action": "list"},
                    cost=1,
                )
            
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Unknown action: {action}",
                    cost=0,
                )
        
        except Exception as e:
            log.error(f"Calendar action '{action}' failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )


# ============================================================================
# ADVANCED FILE OPERATIONS
# ============================================================================

class FileOperationsTool(BaseTool):
    """Advanced file operations: copy, move, archive, search."""
    
    def __init__(self, allowed_dir: Path):
        super().__init__()
        self._allowed_dir = allowed_dir.resolve()
    
    @property
    def name(self) -> str:
        return "file_ops"
    
    @property
    def description(self) -> str:
        return "Advanced file operations: copy, move, archive, search content"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action: copy, move, archive, search, get_info",
                required=True,
            ),
            ToolParameter(
                name="source",
                type="string",
                description="Source path (for copy, move, archive, get_info)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="destination",
                type="string",
                description="Destination path (for copy, move)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="Search pattern (for search)",
                required=False,
                default="",
            ),
        ]
    
    def _validate_path(self, path: Path) -> bool:
        """Validate path is within allowed_dir."""
        try:
            resolved = path.resolve()
            resolved.relative_to(self._allowed_dir)
            return True
        except (ValueError, OSError):
            return False
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute file operation."""
        action = kwargs["action"].lower()
        
        try:
            if action == "copy":
                source = Path(kwargs.get("source", ""))
                dest = Path(kwargs.get("destination", ""))
                
                if not source or not dest:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Source and destination required",
                        cost=0,
                    )
                
                # Make absolute if relative
                if not source.is_absolute():
                    source = self._allowed_dir / source
                if not dest.is_absolute():
                    dest = self._allowed_dir / dest
                
                if not self._validate_path(source) or not self._validate_path(dest):
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Path outside allowed directory",
                        cost=0,
                    )
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, shutil.copy2, source, dest)
                
                return ToolResult(
                    success=True,
                    data={
                        "source": str(source),
                        "destination": str(dest),
                        "size": dest.stat().st_size,
                    },
                    metadata={"action": "copy"},
                    cost=2,
                )
            
            elif action == "move":
                source = Path(kwargs.get("source", ""))
                dest = Path(kwargs.get("destination", ""))
                
                if not source or not dest:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Source and destination required",
                        cost=0,
                    )
                
                if not source.is_absolute():
                    source = self._allowed_dir / source
                if not dest.is_absolute():
                    dest = self._allowed_dir / dest
                
                if not self._validate_path(source) or not self._validate_path(dest):
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Path outside allowed directory",
                        cost=0,
                    )
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, shutil.move, source, dest)
                
                return ToolResult(
                    success=True,
                    data={
                        "source": str(source),
                        "destination": str(dest),
                    },
                    metadata={"action": "move"},
                    cost=2,
                )
            
            elif action == "get_info":
                source = Path(kwargs.get("source", ""))
                
                if not source:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Source path required",
                        cost=0,
                    )
                
                if not source.is_absolute():
                    source = self._allowed_dir / source
                
                if not self._validate_path(source):
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Path outside allowed directory",
                        cost=0,
                    )
                
                if not source.exists():
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"File not found: {source}",
                        cost=0,
                    )
                
                stats = source.stat()
                
                return ToolResult(
                    success=True,
                    data={
                        "path": str(source),
                        "name": source.name,
                        "size": stats.st_size,
                        "is_file": source.is_file(),
                        "is_dir": source.is_dir(),
                        "modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                        "created": datetime.fromtimestamp(stats.st_ctime).isoformat(),
                    },
                    metadata={"action": "get_info"},
                    cost=1,
                )
            
            elif action == "search":
                pattern = kwargs.get("pattern", "")
                
                if not pattern:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Search pattern required",
                        cost=0,
                    )
                
                loop = asyncio.get_event_loop()
                
                def _search():
                    matches = []
                    for path in self._allowed_dir.rglob(pattern):
                        if self._validate_path(path):
                            matches.append({
                                "path": str(path.relative_to(self._allowed_dir)),
                                "name": path.name,
                                "is_file": path.is_file(),
                                "size": path.stat().st_size if path.is_file() else 0,
                            })
                    return matches
                
                matches = await loop.run_in_executor(None, _search)
                
                return ToolResult(
                    success=True,
                    data={
                        "pattern": pattern,
                        "matches": matches[:50],  # Limit to 50
                        "count": len(matches),
                    },
                    metadata={"action": "search"},
                    cost=2,
                )
            
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Unknown action: {action}",
                    cost=0,
                )
        
        except Exception as e:
            log.error(f"File operation '{action}' failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )


# ============================================================================
# WEB API CLIENT
# ============================================================================

class WebAPITool(BaseTool):
    """Make HTTP requests to REST APIs."""
    
    @property
    def name(self) -> str:
        return "web_api"
    
    @property
    def description(self) -> str:
        return "Make HTTP requests to REST APIs: GET, POST, PUT, DELETE"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="method",
                type="string",
                description="HTTP method: GET, POST, PUT, DELETE",
                required=True,
            ),
            ToolParameter(
                name="url",
                type="string",
                description="API endpoint URL",
                required=True,
            ),
            ToolParameter(
                name="headers",
                type="dict",
                description="HTTP headers as JSON object",
                required=False,
                default={},
            ),
            ToolParameter(
                name="body",
                type="dict",
                description="Request body as JSON object",
                required=False,
                default={},
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Make HTTP request."""
        method = kwargs["method"].upper()
        url = kwargs["url"]
        headers = kwargs.get("headers", {})
        body = kwargs.get("body", {})
        
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=body)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, json=body)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Unsupported method: {method}",
                        cost=0,
                    )
                
                # Try to parse as JSON
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                return ToolResult(
                    success=response.is_success,
                    data={
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": response_data,
                    },
                    metadata={"method": method, "url": url},
                    cost=2,
                )
        
        except Exception as e:
            log.error(f"Web API request failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Request error: {str(e)}",
                cost=1,
            )
