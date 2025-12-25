"""Streamlit UI for DailyTrendingResearch workflow.

This app provides a simple web interface for:
1. Entering research topics
2. Triggering research workflows
3. Viewing research reports and sources

Per plan.md "Streamlit Dashboard (Local)" section and tasks.md T058.

Run with: streamlit run streamlit_app.py
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import streamlit as st

# Configure page
st.set_page_config(
    page_title="Research Dashboard",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "research_results" not in st.session_state:
    st.session_state.research_results: list[dict[str, Any]] = []
if "running" not in st.session_state:
    st.session_state.running = False
if "current_job_id" not in st.session_state:
    st.session_state.current_job_id: str | None = None


def get_execution_mode() -> str:
    """Determine execution mode based on available environment."""
    if os.getenv("WINDMILL_BASE_URL") and os.getenv("WINDMILL_TOKEN"):
        return "windmill"
    return "local"


async def run_local_research(topic: str, user_id: str) -> dict[str, Any]:
    """Run research workflow locally without Windmill."""
    from src.workflows.research_graph import InMemoryMemoryManager, compile_research_graph
    from src.models.research_state import ResearchState
    from src.workflows.report_formatter import format_research_report, render_markdown

    memory_manager = InMemoryMemoryManager()
    app = compile_research_graph(memory_manager=memory_manager)

    initial_state = ResearchState(topic=topic, user_id=uuid.UUID(user_id))
    final_state = await app.ainvoke(initial_state)

    report = format_research_report(final_state)
    markdown = render_markdown(report)

    return {
        "status": final_state.status.value,
        "iterations": final_state.iteration_count,
        "report": markdown,
        "sources": [src.model_dump() for src in report.sources],
        "quality_score": final_state.quality_score,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def run_windmill_research(topic: str, user_id: str) -> dict[str, Any]:
    """Run research workflow via Windmill API."""
    from src.windmill.client import WindmillClient

    flow_path = os.getenv("WINDMILL_FLOW_PATH", "f/research/run_research")

    async with WindmillClient() as client:
        # Use sync trigger to wait for result
        result = await client.trigger_flow_sync(
            flow_path,
            {
                "topic": topic,
                "user_id": user_id,
            },
            timeout=600.0,  # 10 minute timeout
        )

    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result


def run_research_sync(topic: str, user_id: str) -> dict[str, Any]:
    """Synchronous wrapper for research execution."""
    mode = get_execution_mode()

    if mode == "windmill":
        return asyncio.run(run_windmill_research(topic, user_id))
    else:
        return asyncio.run(run_local_research(topic, user_id))


# Sidebar
with st.sidebar:
    st.title("🔬 Research Dashboard")
    st.markdown("---")

    # Execution mode indicator
    mode = get_execution_mode()
    if mode == "windmill":
        st.success("🌐 Windmill Mode")
        st.caption("Connected to Windmill orchestration")
    else:
        st.info("💻 Local Mode")
        st.caption("Running research graph locally")

    st.markdown("---")

    # Research history
    st.subheader("📚 History")
    if st.session_state.research_results:
        for i, result in enumerate(reversed(st.session_state.research_results[-10:])):
            with st.expander(f"Research #{len(st.session_state.research_results) - i}", expanded=False):
                st.caption(f"Topic: {result.get('topic', 'N/A')[:50]}...")
                st.caption(f"Status: {result.get('status', 'N/A')}")
                st.caption(f"Iterations: {result.get('iterations', 'N/A')}")
    else:
        st.caption("No research history yet")

# Main content
st.title("🔬 Daily Trending Research")
st.markdown("Enter a topic to research and get a comprehensive report with sources.")

# Research input form
with st.form("research_form", clear_on_submit=False):
    topic = st.text_area(
        "Research Topic",
        placeholder="e.g., Latest developments in AI agents and autonomous systems",
        height=100,
        max_chars=500,
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        user_id = st.text_input(
            "User ID (UUID)",
            value=str(uuid.uuid4()),
            help="A unique identifier for tracking research sessions",
        )
    with col2:
        st.markdown("&nbsp;")
        submitted = st.form_submit_button(
            "🚀 Start Research",
            use_container_width=True,
            disabled=st.session_state.running,
        )

# Handle form submission
if submitted and topic:
    if len(topic.strip()) < 3:
        st.error("Please enter a more specific research topic (at least 3 characters).")
    else:
        st.session_state.running = True

        with st.spinner("🔄 Researching... This may take a few minutes."):
            try:
                result = run_research_sync(topic.strip(), user_id)
                result["topic"] = topic.strip()
                st.session_state.research_results.append(result)
                st.session_state.running = False
                st.rerun()
            except Exception as e:
                st.session_state.running = False
                st.error(f"Research failed: {str(e)}")

# Display results
if st.session_state.research_results:
    latest = st.session_state.research_results[-1]

    st.markdown("---")
    st.subheader("📊 Latest Research Results")

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", latest.get("status", "N/A").title())
    with col2:
        st.metric("Iterations", latest.get("iterations", "N/A"))
    with col3:
        quality = latest.get("quality_score")
        if quality is not None:
            st.metric("Quality Score", f"{quality:.2f}")
        else:
            st.metric("Quality Score", "N/A")
    with col4:
        sources_count = len(latest.get("sources", []))
        st.metric("Sources", sources_count)

    # Report section
    st.markdown("### 📝 Research Report")
    report_markdown = latest.get("report", "No report available")
    st.markdown(report_markdown)

    # Sources section
    if latest.get("sources"):
        st.markdown("### 🔗 Sources")
        for i, source in enumerate(latest["sources"], 1):
            with st.expander(f"{i}. {source.get('title', 'Untitled')}", expanded=False):
                st.markdown(f"**URL:** [{source.get('url', 'N/A')}]({source.get('url', '#')})")
                if source.get("snippet"):
                    st.markdown(f"**Snippet:** {source.get('snippet')}")

    # Download button
    st.download_button(
        label="📥 Download Report",
        data=report_markdown,
        file_name=f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown",
    )

else:
    # Welcome message when no research has been done yet
    st.markdown("---")
    st.info("👋 Enter a research topic above to get started!")

    st.markdown("""
    ### How it works:

    1. **Enter a topic** - Describe what you want to research (1-500 characters)
    2. **Click Start Research** - The system will:
       - Plan the research approach
       - Search for relevant sources
       - Synthesize findings
       - Iterate to improve quality
    3. **Review the report** - Get a comprehensive research report with:
       - Executive summary
       - Detailed findings
       - Source citations
       - Quality metrics

    ### Example topics:
    - "Latest developments in large language models"
    - "Best practices for Python async programming"
    - "Trends in sustainable energy technology"
    """)

# Footer
st.markdown("---")
st.caption(
    f"Mode: {get_execution_mode().title()} | "
    f"Research Count: {len(st.session_state.research_results)} | "
    "Powered by Pydantic AI + LangGraph"
)
