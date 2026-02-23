"""Automatic loader for sensory and action tools."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.tools.registry import ToolRegistry

log = logging.getLogger("digital_being.tools.loader")


class SensoryActionToolLoader:
    """Load and register sensory and action tools based on config."""
    
    def __init__(self, config: Dict[str, Any], registry: ToolRegistry):
        self.config = config
        self.registry = registry
        self.loaded_tools = []
    
    def load_all(self) -> List[str]:
        """Load all enabled tools from config."""
        log.info("Loading sensory and action tools...")
        
        tools_config = self.config.get("tools", {})
        
        # Load sensory tools
        sensory_config = tools_config.get("sensory", {})
        self._load_sensory_tools(sensory_config)
        
        # Load action tools
        action_config = tools_config.get("action", {})
        self._load_action_tools(action_config)
        
        log.info(f"Loaded {len(self.loaded_tools)} tools: {', '.join(self.loaded_tools)}")
        return self.loaded_tools
    
    def _load_sensory_tools(self, config: Dict[str, Any]):
        """Load sensory (input) tools."""
        
        # DuckDuckGo Search
        if config.get("duckduckgo", {}).get("enabled", True):
            try:
                from core.tools.sensory_tools import DuckDuckGoSearchTool
                self.registry.register(DuckDuckGoSearchTool())
                self.loaded_tools.append("duckduckgo_search")
                log.info("✅ DuckDuckGo search enabled")
            except Exception as e:
                log.warning(f"❌ DuckDuckGo search failed to load: {e}")
        
        # RSS Reader
        if config.get("rss", {}).get("enabled", True):
            try:
                from core.tools.sensory_tools import RSSReaderTool
                self.registry.register(RSSReaderTool())
                self.loaded_tools.append("rss_read")
                log.info("✅ RSS reader enabled")
            except Exception as e:
                log.warning(f"❌ RSS reader failed to load: {e}")
        
        # System Stats
        if config.get("system_stats", {}).get("enabled", True):
            try:
                from core.tools.sensory_tools import SystemStatsTool
                self.registry.register(SystemStatsTool())
                self.loaded_tools.append("system_stats")
                log.info("✅ System stats monitor enabled")
            except Exception as e:
                log.warning(f"❌ System stats failed to load: {e}")
        
        # Wikipedia
        if config.get("wikipedia", {}).get("enabled", True):
            try:
                from core.tools.sensory_tools import WikipediaTool
                self.registry.register(WikipediaTool())
                self.loaded_tools.append("wikipedia")
                log.info("✅ Wikipedia search enabled")
            except Exception as e:
                log.warning(f"❌ Wikipedia failed to load: {e}")
    
    def _load_action_tools(self, config: Dict[str, Any]):
        """Load action (output) tools."""
        
        # Telegram
        telegram_config = config.get("telegram", {})
        if telegram_config.get("enabled", False):
            bot_token = telegram_config.get("bot_token")
            chat_id = telegram_config.get("chat_id")
            
            if bot_token and chat_id:
                try:
                    from core.tools.telegram_bot import (
                        TelegramSendTool,
                        TelegramReceiveTool,
                        TelegramBridge,
                    )
                    
                    self.registry.register(TelegramSendTool(bot_token, chat_id))
                    self.registry.register(TelegramReceiveTool(bot_token))
                    self.loaded_tools.extend(["telegram_send", "telegram_receive"])
                    log.info("✅ Telegram bot enabled")
                    
                    # Start bridge
                    import asyncio
                    bridge = TelegramBridge(
                        bot_token=bot_token,
                        chat_id=chat_id,
                        inbox_path=Path("inbox.txt"),
                        outbox_path=Path("outbox.txt"),
                    )
                    asyncio.create_task(bridge.start(
                        poll_interval=telegram_config.get("poll_interval", 30)
                    ))
                    log.info("✅ Telegram bridge started")
                
                except Exception as e:
                    log.warning(f"❌ Telegram failed to load: {e}")
            else:
                log.warning("⚠️ Telegram enabled but missing bot_token or chat_id")
        
        # Windows Notifications
        if config.get("windows_notify", {}).get("enabled", True):
            try:
                import platform
                if platform.system() == "Windows":
                    from core.tools.action_tools import WindowsNotificationTool
                    self.registry.register(WindowsNotificationTool())
                    self.loaded_tools.append("windows_notify")
                    log.info("✅ Windows notifications enabled")
                else:
                    log.info("ℹ️ Windows notifications skipped (not Windows)")
            except Exception as e:
                log.warning(f"❌ Windows notifications failed to load: {e}")
        
        # HTTP Requests
        if config.get("http_request", {}).get("enabled", True):
            try:
                from core.tools.action_tools import HTTPRequestTool
                self.registry.register(HTTPRequestTool())
                self.loaded_tools.append("http_request")
                log.info("✅ HTTP request tool enabled")
            except Exception as e:
                log.warning(f"❌ HTTP request failed to load: {e}")
        
        # Database Logging
        db_config = config.get("database", {})
        if db_config.get("enabled", True):
            try:
                from core.tools.action_tools import DatabaseLogTool
                db_path = Path(db_config.get("path", "data/actions.db"))
                db_path.parent.mkdir(parents=True, exist_ok=True)
                
                self.registry.register(DatabaseLogTool(db_path))
                self.loaded_tools.append("db_log_action")
                log.info(f"✅ Database logging enabled (path: {db_path})")
            except Exception as e:
                log.warning(f"❌ Database logging failed to load: {e}")


def load_sensory_action_tools(config: Dict[str, Any], registry: ToolRegistry) -> List[str]:
    """Convenience function to load all tools."""
    loader = SensoryActionToolLoader(config, registry)
    return loader.load_all()
