"""
Digital Being - Advanced Web Search
Расширенный веб-поиск с поддержкой нескольких поисковых систем
"""

import logging
import json
from typing import Any

try:
    import requests
except ImportError:
    requests = None

log = logging.getLogger("digital_being.tools.web_search_advanced")

class WebSearchAdvanced:
    """
    Расширенный веб-поиск
    
    Поддерживаемые поисковики:
    - DuckDuckGo (бесплатный, без API key)
    - Google Custom Search API (требует API key)
    - SerpAPI (требует API key)
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.google_api_key = self.config.get("google_api_key")
        self.google_cse_id = self.config.get("google_cse_id")
        self.serpapi_key = self.config.get("serpapi_key")
        
    def search_duckduckgo(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Поиск через DuckDuckGo (HTML scraping)
        Бесплатный, но может быть заблокирован
        """
        if not requests:
            log.error("requests library not installed")
            return []
        
        try:
            # DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            results = []
            
            # Abstract
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", "DuckDuckGo Result"),
                    "snippet": data.get("Abstract"),
                    "url": data.get("AbstractURL"),
                    "source": "duckduckgo"
                })
            
            # Related Topics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                        "source": "duckduckgo"
                    })
            
            log.info(f"DuckDuckGo search: {len(results)} results for '{query}'")
            return results[:max_results]
            
        except Exception as e:
            log.error(f"DuckDuckGo search failed: {e}")
            return []
    
    def search_google(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Поиск через Google Custom Search API
        Требует API key и CSE ID
        """
        if not self.google_api_key or not self.google_cse_id:
            log.warning("Google API key or CSE ID not configured")
            return []
        
        if not requests:
            log.error("requests library not installed")
            return []
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_cse_id,
                "q": query,
                "num": max_results
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title"),
                    "snippet": item.get("snippet"),
                    "url": item.get("link"),
                    "source": "google"
                })
            
            log.info(f"Google search: {len(results)} results for '{query}'")
            return results
            
        except Exception as e:
            log.error(f"Google search failed: {e}")
            return []
    
    def search(self, query: str, max_results: int = 5, prefer: str = "duckduckgo") -> dict:
        """
        Универсальный поиск
        
        Args:
            query: Поисковый запрос
            max_results: Максимум результатов
            prefer: Предпочитаемый поисковик (duckduckgo/google)
        
        Returns:
            dict с результатами
        """
        results = []
        
        # Пробуем предпочитаемый поисковик
        if prefer == "google" and self.google_api_key:
            results = self.search_google(query, max_results)
        
        # Если не получилось, пробуем DuckDuckGo
        if not results:
            results = self.search_duckduckgo(query, max_results)
        
        return {
            "success": len(results) > 0,
            "query": query,
            "count": len(results),
            "results": results
        }

def execute(args: dict[str, Any]) -> dict[str, Any]:
    """
    Выполнить веб-поиск
    
    Args:
        args: {
            "query": "поисковый запрос",
            "max_results": 5,
            "prefer": "duckduckgo"
        }
    
    Returns:
        dict с результатами
    """
    query = args.get("query", "")
    max_results = args.get("max_results", 5)
    prefer = args.get("prefer", "duckduckgo")
    
    if not query:
        return {"success": False, "error": "Empty query"}
    
    searcher = WebSearchAdvanced()
    return searcher.search(query, max_results, prefer)
