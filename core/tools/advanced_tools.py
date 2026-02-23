"""Advanced tools for Phase 2: Browser automation, Vision, Audio, Knowledge Graph."""

from __future__ import annotations

import asyncio
import json
import logging
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.tools.base_tool import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
)

log = logging.getLogger("digital_being.tools.advanced")


# ============================================================================
# BROWSER AUTOMATION
# ============================================================================

class BrowserTool(BaseTool):
    """Browser automation using Playwright."""
    
    def __init__(self):
        super().__init__()
        self._browser = None
        self._context = None
        self._page = None
    
    @property
    def name(self) -> str:
        return "browser"
    
    @property
    def description(self) -> str:
        return "Automate browser interactions: navigate, click, fill forms, screenshot"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action: navigate, click, fill, screenshot, close",
                required=True,
            ),
            ToolParameter(
                name="url",
                type="string",
                description="URL to navigate (for 'navigate' action)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="selector",
                type="string",
                description="CSS selector for element (for 'click'/'fill' actions)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="text",
                type="string",
                description="Text to fill (for 'fill' action)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="save_path",
                type="string",
                description="Path to save screenshot (for 'screenshot' action)",
                required=False,
                default="",
            ),
        ]
    
    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                raise ImportError("Install playwright: pip install playwright && playwright install chromium")
            
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                user_agent="DigitalBeing/1.0",
                viewport={"width": 1920, "height": 1080},
            )
            self._page = await self._context.new_page()
            log.info("Browser initialized (Chromium headless)")
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute browser action."""
        action = kwargs["action"].lower()
        
        try:
            await self._ensure_browser()
            
            if action == "navigate":
                url = kwargs.get("url")
                if not url:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="URL required for navigate action",
                        cost=0,
                    )
                
                await self._page.goto(url, timeout=30000)
                title = await self._page.title()
                content = await self._page.content()
                
                return ToolResult(
                    success=True,
                    data={
                        "url": url,
                        "title": title,
                        "content_length": len(content),
                    },
                    metadata={"action": "navigate"},
                    cost=3,
                )
            
            elif action == "click":
                selector = kwargs.get("selector")
                if not selector:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Selector required for click action",
                        cost=0,
                    )
                
                await self._page.click(selector, timeout=10000)
                
                return ToolResult(
                    success=True,
                    data={"clicked": selector},
                    metadata={"action": "click"},
                    cost=1,
                )
            
            elif action == "fill":
                selector = kwargs.get("selector")
                text = kwargs.get("text", "")
                
                if not selector:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Selector required for fill action",
                        cost=0,
                    )
                
                await self._page.fill(selector, text, timeout=10000)
                
                return ToolResult(
                    success=True,
                    data={"filled": selector, "text_length": len(text)},
                    metadata={"action": "fill"},
                    cost=1,
                )
            
            elif action == "screenshot":
                save_path = kwargs.get("save_path", "screenshot.png")
                await self._page.screenshot(path=save_path, full_page=False)
                
                return ToolResult(
                    success=True,
                    data={"saved_to": save_path},
                    metadata={"action": "screenshot"},
                    cost=2,
                )
            
            elif action == "close":
                if self._browser:
                    await self._browser.close()
                    await self._playwright.stop()
                    self._browser = None
                    self._context = None
                    self._page = None
                    log.info("Browser closed")
                
                return ToolResult(
                    success=True,
                    data={"closed": True},
                    metadata={"action": "close"},
                    cost=0,
                )
            
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Unknown action: {action}",
                    cost=0,
                )
        
        except Exception as e:
            log.error(f"Browser action '{action}' failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )


# ============================================================================
# VISION MODEL
# ============================================================================

class VisionTool(BaseTool):
    """Analyze images using LLaVA vision model via Ollama."""
    
    def __init__(self, ollama_client: Optional[Any] = None):
        super().__init__()
        self._ollama = ollama_client
    
    @property
    def name(self) -> str:
        return "vision_analyze"
    
    @property
    def description(self) -> str:
        return "Analyze images with LLaVA vision model: describe, detect objects, read text"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.VISION
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="image_path",
                type="string",
                description="Path to image file",
                required=True,
            ),
            ToolParameter(
                name="prompt",
                type="string",
                description="What to analyze (e.g., 'Describe this image', 'What objects do you see?')",
                required=False,
                default="Describe what you see in this image in detail.",
            ),
            ToolParameter(
                name="model",
                type="string",
                description="Vision model name",
                required=False,
                default="llava",
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Analyze image with vision model."""
        image_path = Path(kwargs["image_path"])
        prompt = kwargs.get("prompt", "Describe what you see in this image in detail.")
        model = kwargs.get("model", "llava")
        
        try:
            if not image_path.exists():
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Image not found: {image_path}",
                    cost=0,
                )
            
            # Read image as base64
            image_data = base64.b64encode(image_path.read_bytes()).decode()
            
            # Call Ollama with vision model
            if not self._ollama:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Ollama client not configured",
                    cost=0,
                )
            
            loop = asyncio.get_event_loop()
            
            def _vision_call():
                # Use Ollama API with images parameter
                import requests
                
                response = requests.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "images": [image_data],
                        "stream": False,
                    },
                    timeout=60,
                )
                
                if response.status_code != 200:
                    raise Exception(f"Ollama API error: {response.status_code}")
                
                return response.json()["response"]
            
            description = await loop.run_in_executor(None, _vision_call)
            
            return ToolResult(
                success=True,
                data={
                    "image": str(image_path),
                    "prompt": prompt,
                    "description": description,
                    "model": model,
                },
                metadata={"source": "vision", "model": model},
                cost=10,  # Vision models are expensive
            )
        
        except Exception as e:
            log.error(f"Vision analysis failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )


# ============================================================================
# AUDIO TRANSCRIPTION
# ============================================================================

class AudioTranscribeTool(BaseTool):
    """Transcribe audio using Whisper model via Ollama."""
    
    @property
    def name(self) -> str:
        return "audio_transcribe"
    
    @property
    def description(self) -> str:
        return "Transcribe audio files to text using Whisper"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.AUDIO
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="audio_path",
                type="string",
                description="Path to audio file (mp3, wav, m4a, etc)",
                required=True,
            ),
            ToolParameter(
                name="language",
                type="string",
                description="Language code (en, ru, etc) or 'auto' for detection",
                required=False,
                default="auto",
            ),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Transcribe audio file."""
        audio_path = Path(kwargs["audio_path"])
        language = kwargs.get("language", "auto")
        
        try:
            if not audio_path.exists():
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Audio file not found: {audio_path}",
                    cost=0,
                )
            
            try:
                import whisper
            except ImportError:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Install whisper: pip install openai-whisper",
                    cost=0,
                )
            
            loop = asyncio.get_event_loop()
            
            def _transcribe():
                # Load model (cached after first use)
                model = whisper.load_model("base")
                
                # Transcribe
                result = model.transcribe(
                    str(audio_path),
                    language=None if language == "auto" else language,
                )
                
                return result
            
            result = await loop.run_in_executor(None, _transcribe)
            
            return ToolResult(
                success=True,
                data={
                    "audio": str(audio_path),
                    "text": result["text"],
                    "language": result.get("language", "unknown"),
                    "segments": len(result.get("segments", [])),
                },
                metadata={"source": "whisper"},
                cost=8,
            )
        
        except Exception as e:
            log.error(f"Audio transcription failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )


# ============================================================================
# KNOWLEDGE GRAPH
# ============================================================================

class KnowledgeGraphTool(BaseTool):
    """Build and query knowledge graph using NetworkX."""
    
    def __init__(self, graph_path: Path):
        super().__init__()
        self._graph_path = graph_path
        self._graph = None
    
    @property
    def name(self) -> str:
        return "knowledge_graph"
    
    @property
    def description(self) -> str:
        return "Manage knowledge graph: add concepts, create relations, query connections"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.MEMORY
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action: add_concept, add_relation, query, get_neighbors, save",
                required=True,
            ),
            ToolParameter(
                name="concept",
                type="string",
                description="Concept name (for add_concept, query, get_neighbors)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="from_concept",
                type="string",
                description="Source concept (for add_relation)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="to_concept",
                type="string",
                description="Target concept (for add_relation)",
                required=False,
                default="",
            ),
            ToolParameter(
                name="relation_type",
                type="string",
                description="Relation type (for add_relation)",
                required=False,
                default="related_to",
            ),
        ]
    
    async def _ensure_graph(self):
        """Ensure graph is loaded."""
        if self._graph is None:
            try:
                import networkx as nx
            except ImportError:
                raise ImportError("Install networkx: pip install networkx")
            
            if self._graph_path.exists():
                # Load existing graph
                graph_data = json.loads(self._graph_path.read_text(encoding="utf-8"))
                self._graph = nx.node_link_graph(graph_data)
                log.info(f"Loaded knowledge graph: {len(self._graph.nodes)} nodes, {len(self._graph.edges)} edges")
            else:
                # Create new graph
                self._graph = nx.DiGraph()
                log.info("Created new knowledge graph")
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute knowledge graph operation."""
        action = kwargs["action"].lower()
        
        try:
            await self._ensure_graph()
            
            if action == "add_concept":
                concept = kwargs.get("concept")
                if not concept:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Concept name required",
                        cost=0,
                    )
                
                self._graph.add_node(concept, created_at=datetime.now().isoformat())
                
                return ToolResult(
                    success=True,
                    data={"concept": concept, "nodes_count": len(self._graph.nodes)},
                    metadata={"action": "add_concept"},
                    cost=1,
                )
            
            elif action == "add_relation":
                from_concept = kwargs.get("from_concept")
                to_concept = kwargs.get("to_concept")
                relation_type = kwargs.get("relation_type", "related_to")
                
                if not from_concept or not to_concept:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Both from_concept and to_concept required",
                        cost=0,
                    )
                
                # Add nodes if they don't exist
                if from_concept not in self._graph:
                    self._graph.add_node(from_concept)
                if to_concept not in self._graph:
                    self._graph.add_node(to_concept)
                
                # Add edge
                self._graph.add_edge(from_concept, to_concept, type=relation_type)
                
                return ToolResult(
                    success=True,
                    data={
                        "from": from_concept,
                        "to": to_concept,
                        "type": relation_type,
                        "edges_count": len(self._graph.edges),
                    },
                    metadata={"action": "add_relation"},
                    cost=1,
                )
            
            elif action == "get_neighbors":
                concept = kwargs.get("concept")
                if not concept or concept not in self._graph:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Concept '{concept}' not found in graph",
                        cost=0,
                    )
                
                # Get neighbors
                neighbors = list(self._graph.neighbors(concept))
                
                return ToolResult(
                    success=True,
                    data={"concept": concept, "neighbors": neighbors, "count": len(neighbors)},
                    metadata={"action": "get_neighbors"},
                    cost=1,
                )
            
            elif action == "save":
                import networkx as nx
                
                # Save graph to JSON
                self._graph_path.parent.mkdir(parents=True, exist_ok=True)
                graph_data = nx.node_link_data(self._graph)
                self._graph_path.write_text(
                    json.dumps(graph_data, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                
                return ToolResult(
                    success=True,
                    data={
                        "saved_to": str(self._graph_path),
                        "nodes": len(self._graph.nodes),
                        "edges": len(self._graph.edges),
                    },
                    metadata={"action": "save"},
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
            log.error(f"Knowledge graph action '{action}' failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )
