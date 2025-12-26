"""Windmill flow entry point for DailyTrendingResearch workflow.

This script is the Windmill-executable entry point that imports from the
paias package (installed from local path in custom Dockerfile.windmill).

Usage in Windmill:
    - Registered at path: f/research/run_research
    - Arguments: topic (str), user_id (str), client_traceparent (str, optional)

Architecture:
    - paias package is installed from file:///app in Windmill's venv
    - Source code is copied to /app in the custom Docker image
    - Clean imports directly from the installed package
"""
# requirements:
# file:///app

from __future__ import annotations

import sys
import os
import subprocess

# =============================================================================
# Environment variable diagnostics - WHITELIST_ENVS in docker-compose.yml
# controls which env vars are passed to Python scripts by Windmill
# =============================================================================

print("=== WINDMILL ENVIRONMENT DIAGNOSTICS ===")
print(f"Python executable: {sys.executable}")
print(f"sys.path: {sys.path}")

# Check key environment variables (WHITELIST_ENVS must include these)
_key_env_vars = ["AZURE_AI_FOUNDRY_ENDPOINT", "AZURE_AI_FOUNDRY_API_KEY", "AZURE_DEPLOYMENT_NAME", "OTEL_EXPORTER_OTLP_ENDPOINT"]
print("Key env vars (via WHITELIST_ENVS):")
for v in _key_env_vars:
    val = os.environ.get(v, "<NOT SET>")
    # Mask sensitive values
    if "KEY" in v and val != "<NOT SET>":
        val = val[:8] + "..." if len(val) > 8 else "***"
    print(f"  {v}: {val}")

# Check where paias is installed FIRST (most important)
try:
    result = subprocess.run([sys.executable, '-m', 'pip', 'show', 'paias'], capture_output=True, text=True)
    print(f"paias package info:\n{result.stdout}")
    if result.stderr:
        print(f"paias show stderr: {result.stderr}")
except Exception as e:
    print(f"Failed to show paias: {e}")

# Try importing step by step
print("Attempting imports...")
try:
    import paias
    print(f"SUCCESS: import paias -> {paias.__file__}")
except ImportError as e:
    print(f"FAILED: import paias -> {e}")
    # Check what's at the expected location
    for p in sys.path:
        candidate = os.path.join(p, 'paias')
        if os.path.exists(candidate):
            print(f"  Found paias dir at {candidate}: {os.listdir(candidate)}")
        candidate_init = os.path.join(p, 'paias', '__init__.py')
        if os.path.exists(candidate_init):
            print(f"  Found paias/__init__.py at {candidate_init}")

# Check site-packages location
import site
print(f"Site packages: {site.getsitepackages()}")

# Check site-packages contents for paias
for sp in site.getsitepackages():
    paias_in_sp = os.path.join(sp, 'paias')
    egg_link = os.path.join(sp, 'paias.egg-link')
    if os.path.exists(paias_in_sp):
        print(f"Found paias in site-packages: {paias_in_sp}")
    if os.path.exists(egg_link):
        print(f"Found paias.egg-link: {egg_link}")
        with open(egg_link) as f:
            print(f"  Contents: {f.read()}")

print("=== END DIAGNOSTICS ===")
# === END DIAGNOSTIC LOGGING ===

import asyncio
import logging
from typing import Any
from uuid import uuid4

# Import from pre-installed paias package
from paias.workflows.research_graph import (
    InMemoryMemoryManager,
    compile_research_graph,
)
from paias.models.research_state import ResearchState
from paias.workflows.report_formatter import (
    format_research_report,
    render_markdown,
)
from paias.windmill.approval_handler import (
    ApprovalRequest,
    process_planned_actions,
)
from paias.models.planned_action import PlannedAction
from paias.core.config import settings
from paias.agents.researcher import run_researcher_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Try to import wmill for Windmill-specific functionality
try:
    import wmill

    WMILL_AVAILABLE = True
except ImportError:
    wmill = None  # type: ignore[assignment]
    WMILL_AVAILABLE = False


async def _default_action_executor(action: PlannedAction) -> dict[str, Any]:
    """Default action executor that logs execution."""
    logger.info(f"Executing action: {action.action_type} - {action.description}")
    return {
        "success": True,
        "action_type": action.action_type,
        "message": f"Action '{action.action_type}' executed successfully",
    }


async def _windmill_suspend_for_approval(
    approval_request: ApprovalRequest,
) -> dict[str, Any]:
    """Suspend workflow and wait for Windmill approval."""
    logger.info(f"Requesting approval for action: {approval_request.action_type}")

    if not WMILL_AVAILABLE or wmill is None:
        # Auto-approve for testing without wmill
        logger.info("Auto-approving action (wmill not available)")
        return {
            "decision": "approve",
            "approver": "test-auto-approval",
        }

    from datetime import timedelta

    timeout_seconds = settings.approval_timeout_seconds
    logger.info(f"Suspending workflow for approval (timeout: {timeout_seconds}s)")

    try:
        resume_payload = wmill.suspend(
            timeout=timedelta(seconds=timeout_seconds),
            default_args={"decision": "pending"},
            enums={"decision": ["approve", "reject"]},
            description=f"""
## Action Approval Required

**Action Type:** {approval_request.action_type}

**Description:** {approval_request.action_description}

Please review and select 'approve' to proceed or 'reject' to skip this action.

_Timeout: {timeout_seconds} seconds_
""",
        )
        logger.info(f"Approval received: {resume_payload.get('decision', 'unknown')}")
        return resume_payload

    except Exception as e:
        logger.error(f"Approval request failed: {e}")
        return {
            "decision": "reject",
            "error": str(e),
            "reason": "timeout_or_error",
        }


def main(
    topic: str,
    user_id: str | None = None,
    client_traceparent: str | None = None,
) -> dict[str, Any]:
    """
    Windmill entrypoint: execute the research graph with approval gating.

    This is the main entry point when this script is executed by Windmill.
    Windmill expects a synchronous function, so we run the async implementation
    using asyncio.run().

    Args:
        topic: Research topic (1-500 chars).
        user_id: Optional user identifier (UUID string). Auto-generated if not provided.
        client_traceparent: Optional W3C traceparent for distributed tracing.

    Returns:
        Dict with status, iterations, report, sources, and action_results.
    """
    # Auto-generate user_id if not provided
    if user_id is None:
        user_id = str(uuid4())
    
    return asyncio.run(
        _async_main(topic, user_id, client_traceparent)
    )


async def _async_main(
    topic: str,
    user_id: str,
    client_traceparent: str | None = None,
) -> dict[str, Any]:
    """Async implementation of the Windmill workflow."""
    logger.info("=" * 80)
    logger.info("STARTING RESEARCH WORKFLOW")
    logger.info(f"Topic: {topic}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Traceparent: {client_traceparent or 'None'}")
    logger.info("=" * 80)

    # Set progress for Windmill UI (percentage only - no message parameter)
    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(0)
            logger.info("Progress: 0%% - Starting research workflow")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    try:
        # Execute the research graph
        logger.info("PHASE 1: Initializing research graph")
        logger.info("- Creating in-memory memory manager")
        memory_mgr = InMemoryMemoryManager()
        logger.info("- Configuring ResearcherAgent with MCP tools")
        app = compile_research_graph(
            memory_manager=memory_mgr,
            agent_runner=run_researcher_agent,
        )

        logger.info("- Creating initial state")
        initial_state = ResearchState(topic=topic, user_id=user_id)
        logger.info(f"  Max iterations: {initial_state.max_iterations}")
        logger.info(f"  Quality threshold: {initial_state.quality_threshold}")

        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(10)
                logger.info("Progress: 10%% - Running research graph")
            except Exception as e:
                logger.debug("Failed to set progress: %s", e)

        logger.info("")
        logger.info("PHASE 2: Executing research graph")
        logger.info("- Starting LangGraph workflow (Plan → Research → Critique → Refine/Finish)")
        logger.info("  This may take several minutes depending on topic complexity...")

        final_state: ResearchState = await app.ainvoke(
            initial_state, traceparent=client_traceparent
        )
    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("PHASE 2 FAILED: Error during research graph execution")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("=" * 80)
        raise

    logger.info("")
    logger.info("PHASE 2 COMPLETE: Research graph execution finished")
    logger.info(f"- Status: {final_state.status.value}")
    logger.info(f"- Total iterations: {final_state.iteration_count}")
    logger.info(f"- Sources found: {len(final_state.sources)}")
    logger.info(f"- Quality score: {final_state.quality_score}")
    logger.info(f"- Planned actions: {len(final_state.planned_actions) if final_state.planned_actions else 0}")

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(70)
            logger.info("Progress: 70%% - Formatting report")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    # Format the report
    logger.info("")
    logger.info("PHASE 3: Formatting research report")
    report = format_research_report(final_state)
    markdown = render_markdown(report)
    logger.info(f"- Report formatted (length: {len(markdown)} chars)")

    # Process planned actions with approval gating
    action_results: list[dict[str, Any]] = []
    approval_status: str | None = None

    if final_state.planned_actions:
        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(80)
                logger.info("Progress: 80%% - Processing planned actions")
            except Exception as e:
                logger.debug("Failed to set progress: %s", e)

        logger.info("")
        logger.info("PHASE 4: Processing planned actions")
        logger.info(f"- Found {len(final_state.planned_actions)} planned actions")

        action_results = await process_planned_actions(
            final_state.planned_actions,
            action_executor=_default_action_executor,
            suspend_for_approval=_windmill_suspend_for_approval,
        )

        statuses = [r.get("approval_status") for r in action_results]
        if "escalated" in statuses:
            approval_status = "escalated"
        elif "rejected" in statuses:
            approval_status = "rejected"
        elif all(s in ("approved", "not_required") for s in statuses):
            approval_status = "completed"
        else:
            approval_status = "partial"

        logger.info(f"- Actions processed: {len(action_results)}")
        logger.info(f"- Overall approval status: {approval_status}")
    else:
        logger.info("")
        logger.info("PHASE 4: No planned actions to process")

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(100)
            logger.info("Progress: 100%% - Workflow completed")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    logger.info("")
    logger.info("=" * 80)
    logger.info("WORKFLOW COMPLETED SUCCESSFULLY")
    logger.info("=" * 80)

    return {
        "status": final_state.status.value,
        "iterations": final_state.iteration_count,
        "report": markdown,
        "sources": [src.model_dump() for src in report.sources],
        "memory_document_id": final_state.memory_document_id,
        "action_results": action_results,
        "approval_status": approval_status,
    }


# Windmill script metadata
__windmill__ = {
    "description": "Execute deep research on a topic with approval gating",
    "summary": "DailyTrendingResearch Workflow",
    "schema": {
        "properties": {
            "topic": {
                "type": "string",
                "description": "Research topic (1-500 characters)",
                "minLength": 1,
                "maxLength": 500,
            },
            "client_traceparent": {
                "type": "string",
                "description": "Optional W3C traceparent for distributed tracing",
            },
        },
        "required": ["topic"],
    },
}
