"""Telegram bot integration for messaging."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.tools.base_tool import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
)

log = logging.getLogger("digital_being.tools.telegram")


class TelegramSendTool(BaseTool):
    """Send messages via Telegram bot."""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        super().__init__()
        self._bot_token = bot_token
        self._chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "telegram_send"
    
    @property
    def description(self) -> str:
        return "Send message to Telegram chat"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMMUNICATION
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="message",
                type="string",
                description="Message text",
                required=True,
                validation={"max_length": 4096},  # Telegram limit
            ),
            ToolParameter(
                name="parse_mode",
                type="string",
                description="Message format: Markdown or HTML",
                required=False,
                default="Markdown",
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Send Telegram message."""
        message = kwargs["message"]
        parse_mode = kwargs.get("parse_mode", "Markdown")
        
        if not self._bot_token or not self._chat_id:
            return ToolResult(
                success=False,
                data=None,
                error="Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in config",
                cost=0,
            )
        
        try:
            import urllib.parse
            import urllib.request
            
            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            
            data = urllib.parse.urlencode({
                "chat_id": self._chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }).encode()
            
            loop = asyncio.get_event_loop()
            
            def _send():
                req = urllib.request.Request(url, data=data, method="POST")
                response = urllib.request.urlopen(req, timeout=10).read()
                return json.loads(response)
            
            result = await loop.run_in_executor(None, _send)
            
            if not result.get("ok"):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Telegram API error: {result.get('description', 'Unknown')}",
                    cost=1,
                )
            
            return ToolResult(
                success=True,
                data={
                    "message_id": result["result"]["message_id"],
                    "chat_id": self._chat_id,
                    "sent_at": datetime.now().isoformat(),
                },
                metadata={"platform": "telegram"},
                cost=1,
            )
        
        except Exception as e:
            log.error(f"Telegram send failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Send error: {str(e)}",
                cost=0,
            )


class TelegramReceiveTool(BaseTool):
    """Receive new messages from Telegram."""
    
    def __init__(self, bot_token: Optional[str] = None):
        super().__init__()
        self._bot_token = bot_token
        self._last_update_id = 0
    
    @property
    def name(self) -> str:
        return "telegram_receive"
    
    @property
    def description(self) -> str:
        return "Get new messages from Telegram"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMMUNICATION
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="limit",
                type="int",
                description="Maximum messages to fetch",
                required=False,
                default=10,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Get new Telegram messages."""
        limit = kwargs.get("limit", 10)
        
        if not self._bot_token:
            return ToolResult(
                success=False,
                data=None,
                error="Telegram not configured. Set TELEGRAM_BOT_TOKEN in config",
                cost=0,
            )
        
        try:
            import urllib.parse
            import urllib.request
            
            url = f"https://api.telegram.org/bot{self._bot_token}/getUpdates"
            params = {
                "offset": self._last_update_id + 1,
                "limit": limit,
                "timeout": 5,
            }
            url_with_params = f"{url}?{urllib.parse.urlencode(params)}"
            
            loop = asyncio.get_event_loop()
            
            def _receive():
                req = urllib.request.Request(url_with_params)
                response = urllib.request.urlopen(req, timeout=10).read()
                return json.loads(response)
            
            result = await loop.run_in_executor(None, _receive)
            
            if not result.get("ok"):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Telegram API error: {result.get('description', 'Unknown')}",
                    cost=1,
                )
            
            messages = []
            updates = result.get("result", [])
            
            for update in updates:
                update_id = update.get("update_id", 0)
                if update_id > self._last_update_id:
                    self._last_update_id = update_id
                
                msg = update.get("message", {})
                if msg:
                    messages.append({
                        "message_id": msg.get("message_id"),
                        "from_user": msg.get("from", {}).get("username", "Unknown"),
                        "from_id": msg.get("from", {}).get("id"),
                        "chat_id": msg.get("chat", {}).get("id"),
                        "text": msg.get("text", ""),
                        "date": msg.get("date"),
                    })
            
            return ToolResult(
                success=True,
                data={
                    "messages": messages,
                    "count": len(messages),
                },
                metadata={"platform": "telegram", "last_update_id": self._last_update_id},
                cost=1,
            )
        
        except Exception as e:
            log.error(f"Telegram receive failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Receive error: {str(e)}",
                cost=0,
            )


# ============================================================================
# INBOX/OUTBOX FILE BRIDGE
# ============================================================================

class TelegramBridge:
    """Bridge between inbox.txt/outbox.txt and Telegram."""
    
    def __init__(
        self,
        bot_token: Optional[str],
        chat_id: Optional[str],
        inbox_path: Path,
        outbox_path: Path,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.inbox_path = inbox_path
        self.outbox_path = outbox_path
        self.send_tool = TelegramSendTool(bot_token, chat_id)
        self.receive_tool = TelegramReceiveTool(bot_token)
        self._running = False
        self._last_outbox_size = 0
    
    async def start(self, poll_interval: int = 30):
        """Start bidirectional bridge."""
        self._running = True
        log.info(f"Starting Telegram bridge (poll interval: {poll_interval}s)")
        
        # Initialize outbox size
        if self.outbox_path.exists():
            self._last_outbox_size = self.outbox_path.stat().st_size
        
        while self._running:
            try:
                # 1. Check for new outgoing messages
                await self._process_outbox()
                
                # 2. Check for new incoming messages
                await self._process_inbox()
                
                await asyncio.sleep(poll_interval)
            
            except Exception as e:
                log.error(f"Bridge error: {e}")
                await asyncio.sleep(poll_interval)
    
    def stop(self):
        """Stop bridge."""
        self._running = False
        log.info("Stopping Telegram bridge")
    
    async def _process_outbox(self):
        """Send new messages from outbox.txt to Telegram."""
        if not self.outbox_path.exists():
            return
        
        current_size = self.outbox_path.stat().st_size
        
        # Check if file grew
        if current_size > self._last_outbox_size:
            # Read only new content
            with open(self.outbox_path, "r", encoding="utf-8") as f:
                f.seek(self._last_outbox_size)
                new_content = f.read().strip()
            
            if new_content:
                # Send to Telegram
                result = await self.send_tool.execute(
                    message=f"🤖 **Digital Being**\n\n{new_content}"
                )
                
                if result.success:
                    log.info(f"Sent outbox message to Telegram (len={len(new_content)})")
                else:
                    log.error(f"Failed to send outbox: {result.error}")
            
            self._last_outbox_size = current_size
    
    async def _process_inbox(self):
        """Fetch new Telegram messages and append to inbox.txt."""
        result = await self.receive_tool.execute(limit=10)
        
        if not result.success:
            return
        
        messages = result.data.get("messages", [])
        
        if messages:
            with open(self.inbox_path, "a", encoding="utf-8") as f:
                for msg in messages:
                    timestamp = datetime.fromtimestamp(msg["date"]).isoformat()
                    text = msg["text"]
                    user = msg["from_user"]
                    
                    f.write(f"[{timestamp}] @{user}: {text}\n")
                    log.info(f"Received message from @{user}: {text[:50]}...")
