"""Windmill tool: Fetch a URL and return its content as markdown.

Standalone tool for use in Windmill AI agent steps.
Fetches web pages and converts HTML to clean markdown for easier processing.

Usage in Windmill:
    - Registered at path: f/tools/fetch_url
    - Can be used as a tool in AI agent steps
    - Arguments: url (str), max_length (int, optional)
"""
# requirements:
# httpx>=0.25.0
# markdownify>=0.12.0

from __future__ import annotations

import logging
import re
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default max content length
DEFAULT_MAX_LENGTH = 8000


def main(url: str, max_length: int = DEFAULT_MAX_LENGTH) -> str:
    """Fetch a URL and return its content as markdown.

    Use this tool to get the full content of a web page when search
    snippets aren't detailed enough. Converts HTML to clean markdown
    for easier reading and processing.

    Args:
        url: The URL to fetch (must be http or https)
        max_length: Maximum character length for output (default: 8000)

    Returns:
        Page content converted to markdown, or error message

    Example:
        >>> content = main("https://example.com/article")
        >>> print(content[:500])
    """
    import asyncio

    return asyncio.run(_async_main(url, max_length))


async def _async_main(url: str, max_length: int = DEFAULT_MAX_LENGTH) -> str:
    """Async implementation of URL fetching."""
    import httpx

    logger.info("Fetching URL: %s", url[:100])

    # Validate URL
    if not url.startswith(("http://", "https://")):
        return f"ERROR: Invalid URL scheme. URL must start with http:// or https://. Got: {url[:50]}"

    try:
        timeout = httpx.Timeout(30.0, connect=10.0)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers=headers
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            # Handle non-HTML content
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                if "application/json" in content_type:
                    return f"```json\n{response.text[:max_length]}\n```"
                elif "text/" in content_type:
                    return response.text[:max_length]
                else:
                    return f"ERROR: Cannot process content type: {content_type}"

            html = response.text

            # Convert HTML to markdown
            markdown = _html_to_markdown(html)

            # Clean up excessive whitespace
            markdown = re.sub(r"\n{3,}", "\n\n", markdown)
            markdown = re.sub(r" {2,}", " ", markdown)
            markdown = markdown.strip()

            # Truncate if too long
            if len(markdown) > max_length:
                markdown = markdown[:max_length] + f"\n\n... [truncated, {len(markdown) - max_length} chars omitted]"

            logger.info("Fetched %d chars from %s", len(markdown), url[:50])
            return markdown

    except httpx.TimeoutException:
        return f"ERROR: Timeout fetching URL after 30s: {url[:100]}"
    except httpx.HTTPStatusError as e:
        return f"ERROR: HTTP {e.response.status_code} fetching URL: {url[:100]}"
    except httpx.RequestError as e:
        return f"ERROR: Failed to fetch URL: {type(e).__name__}: {str(e)[:100]}"
    except Exception as e:
        logger.exception("Unexpected error in fetch_url")
        return f"ERROR: Unexpected error: {type(e).__name__}: {str(e)[:100]}"


def _html_to_markdown(html: str) -> str:
    """Convert HTML to markdown."""
    try:
        from markdownify import markdownify

        return markdownify(
            html,
            heading_style="ATX",
            bullets="-",
            strip=["script", "style", "nav", "footer", "header", "aside"],
        )
    except ImportError:
        # Fallback: basic HTML tag stripping
        logger.warning("markdownify not installed, using basic HTML stripping")
        return _basic_html_strip(html)


def _basic_html_strip(html: str) -> str:
    """Basic HTML to text conversion (fallback)."""
    # Remove script and style elements
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Convert common elements
    html = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove remaining tags
    html = re.sub(r"<[^>]+>", "", html)

    # Decode common HTML entities
    html = html.replace("&nbsp;", " ")
    html = html.replace("&amp;", "&")
    html = html.replace("&lt;", "<")
    html = html.replace("&gt;", ">")
    html = html.replace("&quot;", '"')
    html = html.replace("&#39;", "'")

    return html


# Windmill script metadata
__windmill__ = {
    "description": "Fetch a URL and return its content as markdown",
    "summary": "URL Fetcher Tool",
    "schema": {
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch (must be http or https)",
                "format": "uri",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum character length for output",
                "default": 8000,
                "minimum": 1000,
                "maximum": 100000,
            },
        },
        "required": ["url"],
    },
}
