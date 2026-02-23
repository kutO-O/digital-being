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
# URL READER
# ============================================================================

class URLReaderTool(BaseTool):
    """Fetch and parse web pages using httpx + BeautifulSoup."""
    
    @property
    def name(self) -> str:
        return "url_reader"
    
    @property
    def description(self) -> str:
        return "Download and extract text content from web pages"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="URL to fetch",
                required=True,
            ),
            ToolParameter(
                name="max_length",
                type="int",
                description="Maximum text length to return",
                required=False,
                default=5000,
            ),
            ToolParameter(
                name="extract_links",
                type="bool",
                description="Also extract links from page",
                required=False,
                default=False,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Fetch URL content."""
        url = kwargs["url"]
        max_length = kwargs.get("max_length", 5000)
        extract_links = kwargs.get("extract_links", False)
        
        try:
            try:
                import httpx
                from bs4 import BeautifulSoup
            except ImportError:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Install dependencies: pip install httpx beautifulsoup4",
                    cost=0,
                )
            
            # Fetch page
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "DigitalBeing/1.0"})
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Extract text
                text = soup.get_text(separator='\n', strip=True)
                
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                text = '\n'.join(line for line in lines if line)
                
                # Truncate if needed
                if len(text) > max_length:
                    text = text[:max_length] + "... [truncated]"
                
                result = {
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "title": soup.title.string if soup.title else "No title",
                    "text": text,
                    "length": len(text),
                }
                
                # Extract links if requested
                if extract_links:
                    links = []
                    for a in soup.find_all('a', href=True)[:50]:  # Limit to 50 links
                        links.append({
                            "text": a.get_text(strip=True)[:100],
                            "href": a['href'],
                        })
                    result["links"] = links
                
                return ToolResult(
                    success=True,
                    data=result,
                    metadata={"source": "url_reader", "timestamp": datetime.now().isoformat()},
                    cost=3,
                )
        
        except httpx.HTTPStatusError as e:
            log.error(f"HTTP error fetching {url}: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
                cost=1,
            )
        except Exception as e:
            log.error(f"URL reader failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
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


# ============================================================================
# SCREENSHOT + OCR
# ============================================================================

class ScreenshotOCRTool(BaseTool):
    """Take screenshot and extract text using OCR."""
    
    @property
    def name(self) -> str:
        return "screenshot_ocr"
    
    @property
    def description(self) -> str:
        return "Capture screen and extract text with Tesseract OCR"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.VISION
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="save_path",
                type="string",
                description="Optional path to save screenshot",
                required=False,
                default="",
            ),
            ToolParameter(
                name="monitor",
                type="int",
                description="Monitor number (0=primary, 1=second, etc)",
                required=False,
                default=0,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Take screenshot and OCR."""
        save_path = kwargs.get("save_path", "")
        monitor = kwargs.get("monitor", 0)
        
        try:
            try:
                from PIL import Image, ImageGrab
                import pytesseract
            except ImportError:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Install dependencies: pip install pillow pytesseract\nAlso install Tesseract-OCR system package",
                    cost=0,
                )
            
            loop = asyncio.get_event_loop()
            
            def _capture():
                # Take screenshot
                screenshot = ImageGrab.grab()
                
                # Save if path provided
                if save_path:
                    screenshot.save(save_path)
                
                # Extract text with OCR
                text = pytesseract.image_to_string(screenshot)
                
                return {
                    "text": text.strip(),
                    "size": screenshot.size,
                    "saved_to": save_path if save_path else None,
                    "length": len(text.strip()),
                }
            
            result = await loop.run_in_executor(None, _capture)
            
            return ToolResult(
                success=True,
                data=result,
                metadata={"source": "screenshot_ocr", "timestamp": datetime.now().isoformat()},
                cost=5,
            )
        
        except Exception as e:
            log.error(f"Screenshot OCR failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )


# ============================================================================
# PDF READER
# ============================================================================

class PDFReaderTool(BaseTool):
    """Extract text and structure from PDF files."""
    
    @property
    def name(self) -> str:
        return "pdf_read"
    
    @property
    def description(self) -> str:
        return "Extract text, metadata, and structure from PDF files"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Path to PDF file",
                required=True,
            ),
            ToolParameter(
                name="max_pages",
                type="int",
                description="Maximum pages to process (0=all)",
                required=False,
                default=10,
            ),
            ToolParameter(
                name="extract_structure",
                type="bool",
                description="Extract document structure (headings, tables)",
                required=False,
                default=False,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Read PDF file."""
        file_path = Path(kwargs["file_path"])
        max_pages = kwargs.get("max_pages", 10)
        extract_structure = kwargs.get("extract_structure", False)
        
        try:
            try:
                import pdfplumber
            except ImportError:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Install pdfplumber: pip install pdfplumber",
                    cost=0,
                )
            
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"File not found: {file_path}",
                    cost=0,
                )
            
            loop = asyncio.get_event_loop()
            
            def _read_pdf():
                pages_content = []
                tables = []
                
                with pdfplumber.open(file_path) as pdf:
                    metadata = pdf.metadata or {}
                    total_pages = len(pdf.pages)
                    pages_to_process = min(total_pages, max_pages) if max_pages > 0 else total_pages
                    
                    for i, page in enumerate(pdf.pages[:pages_to_process]):
                        # Extract text
                        text = page.extract_text() or ""
                        pages_content.append({
                            "page": i + 1,
                            "text": text[:2000],  # Truncate per page
                        })
                        
                        # Extract tables if structure requested
                        if extract_structure:
                            page_tables = page.extract_tables()
                            if page_tables:
                                for table in page_tables:
                                    tables.append({
                                        "page": i + 1,
                                        "rows": len(table),
                                        "preview": table[:3] if len(table) > 3 else table,
                                    })
                
                # Combine all text
                full_text = "\n\n".join(p["text"] for p in pages_content)
                
                return {
                    "metadata": {
                        "title": metadata.get("Title", "Unknown"),
                        "author": metadata.get("Author", "Unknown"),
                        "subject": metadata.get("Subject", ""),
                        "total_pages": total_pages,
                        "processed_pages": pages_to_process,
                    },
                    "text": full_text[:10000],  # Limit total text
                    "pages": pages_content,
                    "tables": tables if extract_structure else None,
                    "length": len(full_text),
                }
            
            result = await loop.run_in_executor(None, _read_pdf)
            
            return ToolResult(
                success=True,
                data=result,
                metadata={"source": "pdf_reader", "file": str(file_path)},
                cost=4,
            )
        
        except Exception as e:
            log.error(f"PDF read failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )
