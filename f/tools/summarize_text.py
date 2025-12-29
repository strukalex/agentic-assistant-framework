#py: >=3.11,<3.12

"""Windmill tool: Summarize text using LLM.

Standalone tool for use in Windmill AI agent steps.
Uses the shared LLM infrastructure (Azure AI Foundry or local Ollama).

Usage in Windmill:
    - Registered at path: f/tools/summarize_text
    - Can be used as a tool in AI agent steps
    - Arguments: text (str), max_length (int, optional), style (str, optional)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SummaryStyle = Literal["concise", "detailed", "bullet_points"]


def main(
    text: str,
    max_length: int = 200,
    style: SummaryStyle = "concise",
) -> str:
    """Summarize text using LLM.

    Takes input text and produces a summary using the configured LLM
    (Azure AI Foundry or local Ollama).

    Args:
        text: The text to summarize
        max_length: Target maximum length for the summary in words (default: 200)
        style: Summary style - 'concise', 'detailed', or 'bullet_points'

    Returns:
        Summary of the input text, or error message
    """
    return asyncio.run(_async_main(text, max_length, style))


async def _async_main(
    text: str,
    max_length: int = 200,
    style: SummaryStyle = "concise",
) -> str:
    """Async implementation of text summarization."""
    from pydantic_ai import Agent

    from paias.core.llm import get_azure_model, parse_agent_result

    logger.info(
        "Summarizing text (%d chars) with style=%s, max_length=%d",
        len(text),
        style,
        max_length,
    )

    if not text or not text.strip():
        return "ERROR: No text provided for summarization."

    if len(text.strip()) < 50:
        return text.strip()  # Text too short to summarize

    # Build style-specific instructions
    style_instructions = {
        "concise": "Provide a brief, concise summary capturing the main points.",
        "detailed": "Provide a comprehensive summary that covers all key details and nuances.",
        "bullet_points": "Provide a summary as a bulleted list of key points.",
    }

    system_prompt = f"""You are a precise text summarizer.
{style_instructions.get(style, style_instructions["concise"])}
Keep the summary under {max_length} words.
Preserve the original meaning and important details.
Do not add information not present in the original text."""

    try:
        model = get_azure_model()
        agent = Agent(
            model=model,
            system_prompt=system_prompt,
        )

        result = await agent.run(f"Summarize the following text:\n\n{text}")
        summary = parse_agent_result(result)

        if summary is None:
            return "ERROR: Failed to generate summary."

        logger.info("Generated summary (%d chars)", len(str(summary)))
        return str(summary)

    except Exception as e:
        logger.exception("Summarization failed")
        return f"ERROR: Summarization failed: {type(e).__name__}: {str(e)[:200]}"


# Windmill script metadata
__windmill__ = {
    "description": "Summarize text using LLM (Azure AI Foundry or local Ollama)",
    "summary": "Text Summarization Tool",
    "schema": {
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to summarize",
                "minLength": 1,
            },
            "max_length": {
                "type": "integer",
                "description": "Target maximum length for the summary in words",
                "default": 200,
                "minimum": 10,
                "maximum": 1000,
            },
            "style": {
                "type": "string",
                "description": "Summary style",
                "enum": ["concise", "detailed", "bullet_points"],
                "default": "concise",
            },
        },
        "required": ["text"],
    },
}
