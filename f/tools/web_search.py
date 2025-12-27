"""Windmill tool: Search the web for information.

Standalone tool for use in Windmill AI agent steps.
Uses DuckDuckGo search (no API key required) with fallback options.

Usage in Windmill:
    - Registered at path: f/tools/web_search
    - Can be used as a tool in AI agent steps
    - Arguments: query (str), max_results (int, optional)
"""
# requirements:
# duckduckgo-search>=6.0.0
# httpx>=0.25.0

from __future__ import annotations

import logging
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(query: str, max_results: int = 10) -> str:
    """Search the web for information on a topic.

    Performs a web search and returns formatted results with titles,
    snippets, and URLs. Use this tool to find current information
    that may not be in memory.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 10)

    Returns:
        Formatted search results as text, or error message

    Example:
        >>> results = main("latest AI breakthroughs 2024")
        >>> print(results)
    """
    import asyncio

    return asyncio.run(_async_main(query, max_results))


async def _async_main(query: str, max_results: int = 10) -> str:
    """Async implementation of web search."""
    logger.info("Web search: %s (max_results=%d)", query[:100], max_results)

    try:
        # Try DuckDuckGo search (no API key required)
        results = await _duckduckgo_search(query, max_results)

        if not results:
            return "NO RESULTS FOUND: No search results for the given query."

        # Format results
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(
                f"[{i}] {result['title']}\n"
                f"    URL: {result['url']}\n"
                f"    {result['snippet']}\n"
            )

        output = f"Found {len(results)} results for '{query}':\n\n" + "\n".join(formatted)
        logger.info("Web search returned %d results", len(results))
        return output

    except Exception as e:
        logger.error("Web search failed: %s", str(e))
        return f"SEARCH ERROR: {str(e)}"


async def _duckduckgo_search(query: str, max_results: int) -> list[dict[str, str]]:
    """Search using DuckDuckGo (no API key required)."""
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("link", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                })
        return results

    except ImportError:
        logger.warning("duckduckgo-search not installed, trying httpx fallback")
        return await _httpx_duckduckgo_fallback(query, max_results)
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s, trying fallback", str(e))
        return await _httpx_duckduckgo_fallback(query, max_results)


async def _httpx_duckduckgo_fallback(query: str, max_results: int) -> list[dict[str, str]]:
    """Fallback search using DuckDuckGo HTML API via httpx."""
    import httpx
    import re

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # DuckDuckGo HTML search
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            response.raise_for_status()

            html = response.text
            results = []

            # Parse results from HTML (basic regex parsing)
            # Look for result links and snippets
            result_pattern = r'class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
            snippet_pattern = r'class="result__snippet"[^>]*>([^<]*)<'

            links = re.findall(result_pattern, html)
            snippets = re.findall(snippet_pattern, html)

            for i, (url, title) in enumerate(links[:max_results]):
                snippet = snippets[i] if i < len(snippets) else ""
                # DuckDuckGo uses redirect URLs, extract actual URL
                if "uddg=" in url:
                    actual_url = re.search(r'uddg=([^&]*)', url)
                    if actual_url:
                        from urllib.parse import unquote
                        url = unquote(actual_url.group(1))

                results.append({
                    "title": title.strip(),
                    "url": url,
                    "snippet": snippet.strip(),
                })

            return results

    except Exception as e:
        logger.error("Fallback search failed: %s", str(e))
        return []


# Windmill script metadata
__windmill__ = {
    "description": "Search the web for information on any topic",
    "summary": "Web Search Tool",
    "schema": {
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string",
                "minLength": 1,
                "maxLength": 500,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["query"],
    },
}
