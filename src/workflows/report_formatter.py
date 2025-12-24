from __future__ import annotations

from src.models.research_report import ResearchReport
from src.models.research_state import ResearchState


def format_research_report(state: ResearchState) -> ResearchReport:
    """
    Build a ResearchReport from the provided state.

    Placeholder implementation to be completed in user story work.
    """
    raise NotImplementedError("Report formatting not implemented yet")


def render_markdown(report: ResearchReport) -> str:
    """Render a ResearchReport to Markdown."""
    raise NotImplementedError("Markdown rendering not implemented yet")

