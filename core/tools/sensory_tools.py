"""Enhanced sensory tools for real-world perception."""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import psutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from core.tools.base_tool import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
)

log = logging.getLogger("digital_being.tools.sensory")


# ============================================================================
# ENHANCED WEB SEARCH
# ============================================================================

class DuckDuckGoSearchTool(BaseTool):
    """Real DuckDuckGo search using duckduckgo-search library."""
    
    @property
    def name(self) -> str:
        return "duckduckgo_search"
    
    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo API (no key needed)"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Search query",
                required=True,
            ),
            ToolParameter(
                name="max_results",
                type="int",
                description="Maximum results (1-20)",
                required=False,
                default=5,
            ),
            ToolParameter(
                name="region",
                type="string",
                description="Region code (wt-wt=global, ru-ru=Russia, us-en=USA)",
                required=False,
                default="wt-wt",
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute DuckDuckGo search."""
        query = kwargs["query"]
        max_results = min(kwargs.get("max_results", 5), 20)
        region = kwargs.get("region", "wt-wt")
        
        try:
            # Dynamic import to allow optional dependency
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Install duckduckgo-search: pip install duckduckgo-search",
                    cost=0,
                )
            
            loop = asyncio.get_event_loop()
            
            # Run search in executor (DDGS is synchronous)
            def _search():
                with DDGS() as ddgs:
                    results = list(ddgs.text(
                        query,
                        region=region,
                        safesearch="moderate",
                        max_results=max_results,
                    ))
                    return results
            
            raw_results = await loop.run_in_executor(None, _search)
            
            # Format results
            results = []
            for r in raw_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "region": region,
                },
                metadata={"source": "duckduckgo", "timestamp": datetime.now().isoformat()},
                cost=2,
            )
        
        except Exception as e:
            log.error(f"DuckDuckGo search failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Search error: {str(e)}",
                cost=1,
            )


# ============================================================================
# RSS FEED READER
# ============================================================================

class RSSReaderTool(BaseTool):
    """Read RSS/Atom feeds from URLs."""
    
    @property
    def name(self) -> str:
        return "rss_read"
    
    @property
    def description(self) -> str:
        return "Fetch and parse RSS/Atom feeds"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="RSS/Atom feed URL",
                required=True,
            ),
            ToolParameter(
                name="max_entries",
                type="int",
                description="Maximum entries to return",
                required=False,
                default=10,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Fetch RSS feed."""
        url = kwargs["url"]
        max_entries = kwargs.get("max_entries", 10)
        
        try:
            try:
                import feedparser
            except ImportError:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Install feedparser: pip install feedparser",
                    cost=0,
                )
            
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            
            if feed.bozo and not feed.entries:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Failed to parse feed: {feed.get('bozo_exception', 'Unknown error')}",
                    cost=1,
                )
            
            entries = []
            for entry in feed.entries[:max_entries]:
                entries.append({
                    "title": entry.get("title", "No title"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:500],  # Truncate
                    "published": entry.get("published", ""),
                    "author": entry.get("author", "Unknown"),
                })
            
            return ToolResult(
                success=True,
                data={
                    "feed_title": feed.feed.get("title", "Unknown"),
                    "feed_link": feed.feed.get("link", ""),
                    "entries": entries,
                    "count": len(entries),
                },
                metadata={"source": "rss", "url": url},
                cost=2,
            )
        
        except Exception as e:
            log.error(f"RSS read failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Feed error: {str(e)}",
                cost=1,
            )


# ============================================================================
# SYSTEM STATS MONITOR
# ============================================================================

class SystemStatsTool(BaseTool):
    """Monitor system resource usage."""
    
    @property
    def name(self) -> str:
        return "system_stats"
    
    @property
    def description(self) -> str:
        return "Get CPU, RAM, disk, network stats"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="detailed",
                type="bool",
                description="Include detailed per-process stats",
                required=False,
                default=False,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Get system stats."""
        detailed = kwargs.get("detailed", False)
        
        try:
            loop = asyncio.get_event_loop()
            
            # Basic stats
            def _get_stats():
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()
                
                mem = psutil.virtual_memory()
                mem_percent = mem.percent
                mem_available_gb = mem.available / (1024**3)
                mem_total_gb = mem.total / (1024**3)
                
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                disk_free_gb = disk.free / (1024**3)
                disk_total_gb = disk.total / (1024**3)
                
                net = psutil.net_io_counters()
                
                return {
                    "cpu": {
                        "percent": cpu_percent,
                        "count": cpu_count,
                    },
                    "memory": {
                        "percent": mem_percent,
                        "available_gb": round(mem_available_gb, 2),
                        "total_gb": round(mem_total_gb, 2),
                    },
                    "disk": {
                        "percent": disk_percent,
                        "free_gb": round(disk_free_gb, 2),
                        "total_gb": round(disk_total_gb, 2),
                    },
                    "network": {
                        "bytes_sent": net.bytes_sent,
                        "bytes_recv": net.bytes_recv,
                    },
                    "platform": {
                        "system": platform.system(),
                        "release": platform.release(),
                        "machine": platform.machine(),
                    },
                }
            
            stats = await loop.run_in_executor(None, _get_stats)
            
            # Add process list if detailed
            if detailed:
                def _get_processes():
                    procs = []
                    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                        try:
                            info = proc.info
                            if info['cpu_percent'] > 1.0 or info['memory_percent'] > 1.0:
                                procs.append({
                                    "pid": info['pid'],
                                    "name": info['name'],
                                    "cpu_percent": round(info['cpu_percent'], 1),
                                    "memory_percent": round(info['memory_percent'], 1),
                                })
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    return sorted(procs, key=lambda x: x['cpu_percent'], reverse=True)[:10]
                
                stats['top_processes'] = await loop.run_in_executor(None, _get_processes)
            
            return ToolResult(
                success=True,
                data=stats,
                metadata={"timestamp": datetime.now().isoformat()},
                cost=1,
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Stats error: {str(e)}",
                cost=0,
            )


# ============================================================================
# WIKIPEDIA API
# ============================================================================

class WikipediaTool(BaseTool):
    """Search and fetch Wikipedia articles."""
    
    @property
    def name(self) -> str:
        return "wikipedia"
    
    @property
    def description(self) -> str:
        return "Search Wikipedia and get article summaries"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Search query or article title",
                required=True,
            ),
            ToolParameter(
                name="language",
                type="string",
                description="Language code (en, ru, etc)",
                required=False,
                default="en",
            ),
            ToolParameter(
                name="sentences",
                type="int",
                description="Number of sentences in summary",
                required=False,
                default=3,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Search Wikipedia."""
        query = kwargs["query"]
        language = kwargs.get("language", "en")
        sentences = kwargs.get("sentences", 3)
        
        try:
            import urllib.parse
            import urllib.request
            
            loop = asyncio.get_event_loop()
            
            # Search API
            def _search():
                search_url = f"https://{language}.wikipedia.org/w/api.php"
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": "1",
                }
                url = f"{search_url}?{urllib.parse.urlencode(params)}"
                
                req = urllib.request.Request(url, headers={"User-Agent": "DigitalBeing/1.0"})
                response = urllib.request.urlopen(req, timeout=10).read()
                data = json.loads(response)
                
                if not data.get("query", {}).get("search"):
                    return None, "No results found"
                
                page_title = data["query"]["search"][0]["title"]
                
                # Get summary
                summary_params = {
                    "action": "query",
                    "prop": "extracts",
                    "exsentences": str(sentences),
                    "exintro": "true",
                    "explaintext": "true",
                    "titles": page_title,
                    "format": "json",
                }
                summary_url = f"{search_url}?{urllib.parse.urlencode(summary_params)}"
                
                req = urllib.request.Request(summary_url, headers={"User-Agent": "DigitalBeing/1.0"})
                response = urllib.request.urlopen(req, timeout=10).read()
                data = json.loads(response)
                
                pages = data.get("query", {}).get("pages", {})
                if not pages:
                    return None, "No page data"
                
                page = list(pages.values())[0]
                page_url = f"https://{language}.wikipedia.org/wiki/{urllib.parse.quote(page_title)}"
                
                return {
                    "title": page_title,
                    "summary": page.get("extract", ""),
                    "url": page_url,
                }, None
            
            result, error = await loop.run_in_executor(None, _search)
            
            if error:
                return ToolResult(
                    success=False,
                    data=None,
                    error=error,
                    cost=1,
                )
            
            return ToolResult(
                success=True,
                data=result,
                metadata={"source": "wikipedia", "language": language},
                cost=2,
            )
        
        except Exception as e:
            log.error(f"Wikipedia search failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Wikipedia error: {str(e)}",
                cost=1,
            )
