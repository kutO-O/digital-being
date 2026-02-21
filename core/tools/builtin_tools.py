"""Built-in tools for common operations."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from core.tools.base_tool import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
)

log = logging.getLogger("digital_being.tools.builtin")


# ============================================================================
# WEB TOOLS
# ============================================================================

class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo."""
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Search the web and return relevant results"
    
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
                validation={"min_length": 1, "max_length": 500},
            ),
            ToolParameter(
                name="max_results",
                type="int",
                description="Maximum number of results",
                required=False,
                default=5,
                validation={"min": 1, "max": 20},
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute web search."""
        query = kwargs["query"]
        max_results = kwargs.get("max_results", 5)
        
        try:
            # Use DuckDuckGo HTML parsing (simple, no API key needed)
            import urllib.parse
            import urllib.request
            from html.parser import HTMLParser
            
            class DDGParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self.in_result = False
                    self.current_title = ""
                    self.current_url = ""
                
                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == "a" and "class" in attrs_dict:
                        if "result__a" in attrs_dict.get("class", ""):
                            self.in_result = True
                            self.current_url = attrs_dict.get("href", "")
                
                def handle_data(self, data):
                    if self.in_result:
                        self.current_title += data.strip()
                
                def handle_endtag(self, tag):
                    if tag == "a" and self.in_result:
                        if self.current_title and self.current_url:
                            self.results.append({
                                "title": self.current_title,
                                "url": self.current_url,
                            })
                        self.in_result = False
                        self.current_title = ""
                        self.current_url = ""
            
            # Build URL
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            # Fetch
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            
            loop = asyncio.get_event_loop()
            html = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
            )
            
            # Parse
            parser = DDGParser()
            parser.feed(html)
            
            results = parser.results[:max_results]
            
            return ToolResult(
                success=True,
                data={"query": query, "results": results, "count": len(results)},
                metadata={"source": "duckduckgo"},
                cost=2,  # Web requests are more expensive
            )
        
        except Exception as e:
            log.error(f"Web search failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Search failed: {str(e)}",
                cost=1,
            )


class ReadUrlTool(BaseTool):
    """Fetch and read content from URL."""
    
    @property
    def name(self) -> str:
        return "read_url"
    
    @property
    def description(self) -> str:
        return "Fetch content from a URL and return text"
    
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
                description="Maximum content length",
                required=False,
                default=10000,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Fetch URL content."""
        url = kwargs["url"]
        max_length = kwargs.get("max_length", 10000)
        
        try:
            import urllib.request
            from html.parser import HTMLParser
            
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                
                def handle_data(self, data):
                    self.text.append(data.strip())
            
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
            )
            
            # Extract text
            extractor = TextExtractor()
            extractor.feed(content)
            text = " ".join(extractor.text)
            text = text[:max_length]
            
            return ToolResult(
                success=True,
                data={"url": url, "content": text, "length": len(text)},
                cost=2,
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to fetch URL: {str(e)}",
                cost=1,
            )


# ============================================================================
# FILE TOOLS
# ============================================================================

class FileReadTool(BaseTool):
    """Read file content."""
    
    def __init__(self, allowed_dirs: List[Path]):
        super().__init__()
        self._allowed_dirs = allowed_dirs
    
    @property
    def name(self) -> str:
        return "file_read"
    
    @property
    def description(self) -> str:
        return "Read content from a file"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="File path to read",
                required=True,
            ),
            ToolParameter(
                name="encoding",
                type="string",
                description="File encoding",
                required=False,
                default="utf-8",
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Read file."""
        path_str = kwargs["path"]
        encoding = kwargs.get("encoding", "utf-8")
        
        try:
            path = Path(path_str).resolve()
            
            # Security check
            allowed = any(
                str(path).startswith(str(d.resolve()))
                for d in self._allowed_dirs
            )
            if not allowed:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Access denied: path outside allowed directories",
                    cost=0,
                )
            
            content = path.read_text(encoding=encoding)
            
            return ToolResult(
                success=True,
                data={"path": str(path), "content": content, "size": len(content)},
                cost=1,
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to read file: {str(e)}",
                cost=0,
            )


class FileWriteTool(BaseTool):
    """Write content to file."""
    
    def __init__(self, allowed_dirs: List[Path]):
        super().__init__()
        self._allowed_dirs = allowed_dirs
    
    @property
    def name(self) -> str:
        return "file_write"
    
    @property
    def description(self) -> str:
        return "Write content to a file"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="File path to write",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write",
                required=True,
            ),
            ToolParameter(
                name="encoding",
                type="string",
                description="File encoding",
                required=False,
                default="utf-8",
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Write file."""
        path_str = kwargs["path"]
        content = kwargs["content"]
        encoding = kwargs.get("encoding", "utf-8")
        
        try:
            path = Path(path_str).resolve()
            
            # Security check
            allowed = any(
                str(path).startswith(str(d.resolve()))
                for d in self._allowed_dirs
            )
            if not allowed:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Access denied: path outside allowed directories",
                    cost=0,
                )
            
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=encoding)
            
            return ToolResult(
                success=True,
                data={"path": str(path), "size": len(content)},
                cost=1,
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to write file: {str(e)}",
                cost=0,
            )


# ============================================================================
# CODE TOOLS
# ============================================================================

class PythonExecuteTool(BaseTool):
    """Execute Python code in sandbox."""
    
    @property
    def name(self) -> str:
        return "python_execute"
    
    @property
    def description(self) -> str:
        return "Execute Python code and return output"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CODE
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="Python code to execute",
                required=True,
                validation={"max_length": 10000},
            ),
            ToolParameter(
                name="timeout",
                type="int",
                description="Execution timeout in seconds",
                required=False,
                default=30,
                validation={"min": 1, "max": 300},
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute Python code."""
        code = kwargs["code"]
        timeout = kwargs.get("timeout", 30)
        
        try:
            # Write code to temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Execute with timeout
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: subprocess.run(
                            ["python3", temp_path],
                            capture_output=True,
                            text=True,
                            timeout=timeout,
                        )
                    ),
                    timeout=timeout + 5,
                )
                
                return ToolResult(
                    success=result.returncode == 0,
                    data={
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.returncode,
                    },
                    error=result.stderr if result.returncode != 0 else None,
                    cost=3,  # Code execution is expensive
                )
            
            finally:
                # Clean up
                Path(temp_path).unlink(missing_ok=True)
        
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                data=None,
                error=f"Execution timeout ({timeout}s exceeded)",
                cost=3,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Execution failed: {str(e)}",
                cost=1,
            )


# ============================================================================
# DATA TOOLS
# ============================================================================

class JSONParseTool(BaseTool):
    """Parse and validate JSON."""
    
    @property
    def name(self) -> str:
        return "json_parse"
    
    @property
    def description(self) -> str:
        return "Parse JSON string and return structured data"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.DATA
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="json_string",
                type="string",
                description="JSON string to parse",
                required=True,
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Parse JSON."""
        json_string = kwargs["json_string"]
        
        try:
            data = json.loads(json_string)
            return ToolResult(
                success=True,
                data={"parsed": data, "type": type(data).__name__},
                cost=1,
            )
        except json.JSONDecodeError as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid JSON: {str(e)}",
                cost=0,
            )