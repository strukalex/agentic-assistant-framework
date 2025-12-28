"""Windmill-native research workflow using standalone Windmill tools.

This script provides an alternative to run_research.py that uses the standalone
Windmill tools (web_search, fetch_url, search_memory, store_memory) directly
instead of the MCP-based Pydantic AI agent.

Usage in Windmill:
    - Registered at path: f/research/run_research_windmill
    - Arguments: topic (str), max_iterations (int, optional)

Architecture:
    - Uses Windmill's AI agent capabilities with standalone tools
    - Tools are registered at f/tools/* and called via wmill.call()
    - No MCP server required - all tools are native Windmill scripts
"""
# requirements:
# file:///app
# wmill>=1.0.0

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Silence httpx/httpcore verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Try to import wmill for Windmill-specific functionality
try:
    import wmill

    WMILL_AVAILABLE = True
except ImportError:
    wmill = None  # type: ignore[assignment]
    WMILL_AVAILABLE = False


# Tool paths in Windmill
TOOL_WEB_SEARCH = "f/tools/web_search"
TOOL_FETCH_URL = "f/tools/fetch_url"
TOOL_SEARCH_MEMORY = "f/tools/search_memory"
TOOL_STORE_MEMORY = "f/tools/store_memory"


def _call_tool(path: str, **kwargs: Any) -> Any:
    """Call a Windmill tool synchronously."""
    if not WMILL_AVAILABLE or wmill is None:
        raise RuntimeError(f"Cannot call tool {path}: wmill not available")
    return wmill.run_script(path, kwargs)


async def _call_tool_async(path: str, **kwargs: Any) -> Any:
    """Call a Windmill tool asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _call_tool(path, **kwargs))


def main(
    topic: str,
    max_iterations: int = 3,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Windmill-native research workflow using standalone tools.

    This is an alternative entry point that uses Windmill tools directly
    instead of the MCP-based Pydantic AI agent.

    Args:
        topic: Research topic (1-500 chars)
        max_iterations: Maximum research iterations (default: 3)
        user_id: Optional user identifier

    Returns:
        Dict with status, report, sources, and metadata
    """
    if user_id is None:
        user_id = str(uuid4())

    return asyncio.run(_async_main(topic, max_iterations, user_id))


async def _async_main(
    topic: str,
    max_iterations: int,
    user_id: str,
) -> dict[str, Any]:
    """Async implementation of the Windmill-native workflow."""
    logger.info("=" * 80)
    logger.info("STARTING WINDMILL-NATIVE RESEARCH WORKFLOW")
    logger.info(f"Topic: {topic}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Max iterations: {max_iterations}")
    logger.info("=" * 80)

    start_time = time.time()
    sources: list[dict[str, Any]] = []
    findings: list[str] = []
    iteration = 0

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(0)
            logger.info("Progress: 0%% - Starting research")
        except Exception as e:
            logger.debug(f"Failed to set progress: {e}")

    try:
        # Phase 1: Check memory for existing knowledge
        logger.info("")
        logger.info("PHASE 1: Checking memory for existing knowledge")
        memory_results = await _call_tool_async(TOOL_SEARCH_MEMORY, query=topic, top_k=5)

        if memory_results and isinstance(memory_results, list) and len(memory_results) > 0:
            logger.info(f"Found {len(memory_results)} relevant documents in memory")
            for doc in memory_results:
                content = doc.get("content", "")
                if content and "NO RESULTS FOUND" not in content.upper():
                    findings.append(f"[From Memory] {content}")
                    sources.append({
                        "type": "memory",
                        "content": content[:200],
                        "metadata": doc.get("metadata", {}),
                    })
        else:
            logger.info("No relevant documents found in memory")

        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(20)
                logger.info("Progress: 20%% - Memory search complete")
            except Exception as e:
                logger.debug(f"Failed to set progress: {e}")

        # Phase 2: Web search and content fetching
        logger.info("")
        logger.info("PHASE 2: Web search and content gathering")

        for iteration in range(1, max_iterations + 1):
            logger.info(f"--- Iteration {iteration}/{max_iterations} ---")

            # Construct search query (refine based on iteration)
            if iteration == 1:
                search_query = topic
            else:
                # For subsequent iterations, try more specific queries
                search_query = f"{topic} latest developments {datetime.now().year}"

            logger.info(f"Searching for: {search_query}")
            search_results = await _call_tool_async(
                TOOL_WEB_SEARCH, query=search_query, max_results=5
            )

            if not search_results or "NO RESULTS FOUND" in str(search_results).upper():
                logger.info("No search results found")
                continue

            # Parse search results to extract URLs
            urls_to_fetch: list[str] = []
            if isinstance(search_results, str):
                # Extract URLs from formatted string output
                import re
                urls_to_fetch = re.findall(r"URL:\s*(https?://[^\s\n]+)", search_results)
                findings.append(f"[Web Search] {search_results[:500]}")

            # Fetch detailed content from top URLs
            for url in urls_to_fetch[:2]:  # Limit to 2 URLs per iteration
                logger.info(f"Fetching content from: {url}")
                try:
                    content = await _call_tool_async(
                        TOOL_FETCH_URL, url=url, max_length=4000
                    )
                    if content and "ERROR:" not in content:
                        findings.append(f"[From {url}] {content[:1000]}")
                        sources.append({
                            "type": "web",
                            "url": url,
                            "content_preview": content[:200],
                        })
                except Exception as e:
                    logger.warning(f"Failed to fetch {url}: {e}")

            # Update progress
            progress = 20 + int((iteration / max_iterations) * 50)
            if WMILL_AVAILABLE and wmill is not None:
                try:
                    wmill.set_progress(progress)
                    logger.info(f"Progress: {progress}%% - Iteration {iteration} complete")
                except Exception:
                    pass

            # Check if we have enough findings
            if len(findings) >= 5:
                logger.info("Sufficient findings gathered, stopping early")
                break

        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(75)
                logger.info("Progress: 75%% - Synthesizing report")
            except Exception:
                pass

        # Phase 3: Synthesize report
        logger.info("")
        logger.info("PHASE 3: Synthesizing research report")

        report = _synthesize_report(topic, findings, sources)
        logger.info(f"Report generated ({len(report)} chars)")

        # Phase 4: Store findings in memory
        logger.info("")
        logger.info("PHASE 4: Storing findings in memory")

        if findings:
            # Combine findings into a summary for storage
            summary = f"Research on '{topic}':\n\n"
            summary += "\n\n".join(findings[:5])  # Store top 5 findings

            try:
                store_result = await _call_tool_async(
                    TOOL_STORE_MEMORY,
                    content=summary[:10000],  # Limit content size
                    topic=topic,
                    sources=["web_search", "fetch_url"],
                )
                logger.info(f"Stored in memory: {store_result}")
            except Exception as e:
                logger.warning(f"Failed to store in memory: {e}")

        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(100)
                logger.info("Progress: 100%% - Workflow complete")
            except Exception:
                pass

        elapsed = time.time() - start_time
        logger.info("")
        logger.info("=" * 80)
        logger.info("WORKFLOW COMPLETED SUCCESSFULLY")
        logger.info(f"Total time: {elapsed:.1f}s")
        logger.info(f"Iterations: {iteration}")
        logger.info(f"Sources: {len(sources)}")
        logger.info("=" * 80)

        return {
            "status": "completed",
            "iterations": iteration,
            "report": report,
            "sources": sources,
            "elapsed_seconds": elapsed,
            "user_id": user_id,
        }

    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("WORKFLOW FAILED")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("=" * 80)
        raise


def _synthesize_report(
    topic: str, findings: list[str], sources: list[dict[str, Any]]
) -> str:
    """Synthesize findings into a research report."""
    lines = [
        f"# Research Report: {topic}",
        "",
        f"*Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "## Summary",
        "",
    ]

    if not findings:
        lines.append("No significant findings were gathered for this topic.")
    else:
        lines.append(f"This report synthesizes {len(findings)} findings from {len(sources)} sources.")
        lines.append("")
        lines.append("## Key Findings")
        lines.append("")

        for i, finding in enumerate(findings[:10], 1):
            # Truncate long findings
            finding_text = finding[:500] + "..." if len(finding) > 500 else finding
            lines.append(f"### Finding {i}")
            lines.append("")
            lines.append(finding_text)
            lines.append("")

    if sources:
        lines.append("## Sources")
        lines.append("")
        for i, source in enumerate(sources, 1):
            source_type = source.get("type", "unknown")
            if source_type == "web":
                url = source.get("url", "unknown")
                lines.append(f"{i}. [{url}]({url})")
            elif source_type == "memory":
                lines.append(f"{i}. [Retrieved from memory]")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by Windmill-native research workflow*")

    return "\n".join(lines)


# Windmill script metadata
__windmill__ = {
    "description": "Execute research workflow using native Windmill tools",
    "summary": "Windmill-Native Research Workflow",
    "schema": {
        "properties": {
            "topic": {
                "type": "string",
                "description": "Research topic (1-500 characters)",
                "minLength": 1,
                "maxLength": 500,
            },
            "max_iterations": {
                "type": "integer",
                "description": "Maximum research iterations (default: 3)",
                "default": 3,
                "minimum": 1,
                "maximum": 10,
            },
            "user_id": {
                "type": "string",
                "description": "Optional user identifier (UUID string). Auto-generated if not provided.",
            },
        },
        "required": ["topic"],
    },
}
