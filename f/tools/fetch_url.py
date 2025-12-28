"""Windmill tool: Fetch a URL and return its content as markdown.

This is a standalone Windmill tool that wraps the fetch_url logic from
paias/agents/researcher.py for use in Windmill workflows.

Usage in Windmill:
    - Registered at path: f/tools/fetch_url
    - Arguments: url (str), max_length (int, optional)
"""
# requirements:
# file:///app
# httpx>=0.25.0
# markdownify>=0.12.0

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(url: str, max_length: int = 8000) -> str:
    """Fetch a URL and return its content as markdown.

    Use this tool to get the full content of a web page when search
    snippets aren't detailed enough. Converts HTML to clean markdown
    for easier reading and processing.

    Args:
        url: The URL to fetch (must be http or https)
        max_length: Maximum character length for output (default: 8000)

    Returns:
        Page content converted to markdown, or error message
    """
    return asyncio.run(_async_main(url, max_length))


async def _async_main(url: str, max_length: int = 8000) -> str:
    """Async implementation matching paias/agents/researcher.py fetch_url."""
    import httpx
    from markdownify import markdownify

    logger.info("Fetching URL: %s", url[:100])

    # Validate URL
    if not url.startswith(("http://", "https://")):
        return f"ERROR: Invalid URL scheme. URL must start with http:// or https://. Got: {url[:50]}"

    try:
        timeout = httpx.Timeout(30.0, connect=10.0)
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ResearcherAgent/1.0)",
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

            # Convert HTML to markdown (same as researcher.py)
            markdown = markdownify(
                html,
                heading_style="ATX",
                bullets="-",
                strip=["script", "style", "nav", "footer", "header", "aside"],
            )

            # Clean up excessive whitespace
            markdown = re.sub(r"\n{3,}", "\n\n", markdown)
            markdown = re.sub(r" {2,}", " ", markdown)
            markdown = markdown.strip()

            # Truncate if too long
            if len(markdown) > max_length:
                markdown = markdown[:max_length] + f"\n\n... [truncated, {len(markdown) - max_length} chars omitted]"

            logger.info("Retrieved %d chars from %s", len(markdown), url[:50])
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
