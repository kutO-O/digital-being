"""Telegram integration service for Digital Being.

Automatic bidirectional sync between Telegram and social_layer:
- Incoming messages from Telegram → inbox.txt → social_layer
- Outgoing messages from social_layer → outbox.txt → Telegram
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from core.tools.telegram_bot import TelegramBridge

log = logging.getLogger("digital_being.telegram_integration")


class TelegramIntegrationService:
    """Service to run Telegram bridge in background."""
    
    def __init__(
        self,
        bot_token: Optional[str],
        chat_id: Optional[str],
        inbox_path: Path,
        outbox_path: Path,
        poll_interval: int = 30,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.inbox_path = inbox_path
        self.outbox_path = outbox_path
        self.poll_interval = poll_interval
        
        self.bridge: Optional[TelegramBridge] = None
        self._task: Optional[asyncio.Task] = None
        self._enabled = False
    
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.chat_id)
    
    async def start(self) -> bool:
        """Start Telegram integration service."""
        if not self.is_configured():
            log.warning("Telegram not configured (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
            return False
        
        if self._task is not None:
            log.warning("Telegram service already running")
            return False
        
        try:
            # Create bridge
            self.bridge = TelegramBridge(
                bot_token=self.bot_token,
                chat_id=self.chat_id,
                inbox_path=self.inbox_path,
                outbox_path=self.outbox_path,
            )
            
            # Start bridge task
            self._task = asyncio.create_task(self.bridge.start(self.poll_interval))
            self._enabled = True
            
            log.info(f"✅ Telegram integration started (polling every {self.poll_interval}s)")
            return True
        
        except Exception as e:
            log.error(f"Failed to start Telegram integration: {e}")
            return False
    
    async def stop(self):
        """Stop Telegram integration service."""
        if self._task is None:
            return
        
        try:
            if self.bridge:
                self.bridge.stop()
            
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            
            self._task = None
            self._enabled = False
            
            log.info("Telegram integration stopped")
        
        except Exception as e:
            log.error(f"Error stopping Telegram integration: {e}")
    
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._task is not None and not self._task.done()
    
    def get_status(self) -> dict:
        """Get service status."""
        return {
            "configured": self.is_configured(),
            "enabled": self._enabled,
            "running": self.is_running(),
            "poll_interval": self.poll_interval,
            "inbox_path": str(self.inbox_path),
            "outbox_path": str(self.outbox_path),
        }


# ============================================================================
# GLOBAL SERVICE INSTANCE
# ============================================================================

_telegram_service: Optional[TelegramIntegrationService] = None


def initialize_telegram_service(
    bot_token: Optional[str],
    chat_id: Optional[str],
    inbox_path: Path,
    outbox_path: Path,
    poll_interval: int = 30,
) -> TelegramIntegrationService:
    """Initialize global Telegram service."""
    global _telegram_service
    
    _telegram_service = TelegramIntegrationService(
        bot_token=bot_token,
        chat_id=chat_id,
        inbox_path=inbox_path,
        outbox_path=outbox_path,
        poll_interval=poll_interval,
    )
    
    return _telegram_service


def get_telegram_service() -> Optional[TelegramIntegrationService]:
    """Get global Telegram service instance."""
    return _telegram_service


async def start_telegram_service() -> bool:
    """Start global Telegram service if configured."""
    if _telegram_service is None:
        log.error("Telegram service not initialized. Call initialize_telegram_service() first.")
        return False
    
    return await _telegram_service.start()


async def stop_telegram_service():
    """Stop global Telegram service."""
    if _telegram_service is not None:
        await _telegram_service.stop()
