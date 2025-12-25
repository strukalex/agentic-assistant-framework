from __future__ import annotations

from datetime import datetime, timezone

from ..models.research_report import QualityIndicators, ResearchReport
from ..models.research_state import ResearchState


def format_research_report(state: ResearchState) -> ResearchReport:
    """
    Build a ResearchReport from the provided state.

    Creates a structured report with executive summary, detailed findings,
    source citations, and optional quality indicators.
    """
    quality_indicators = None
    limited_sources = len(state.sources) < 3
    if state.quality_score or limited_sources:
        quality_indicators = QualityIndicators(
            quality_score=state.quality_score,
            warnings=[],
            limited_sources=limited_sources,
        )

    return ResearchReport(
        topic=state.topic,
        user_id=state.user_id,
        executive_summary=state.refined_answer or "No refined answer available yet.",
        detailed_findings=state.critique
        or state.plan
        or "Research findings are not available.",
        sources=state.sources,
        iterations=state.iteration_count,
        generated_at=datetime.now(timezone.utc),
        quality_indicators=quality_indicators,
    )


def render_markdown(report: ResearchReport) -> str:
    """Render a ResearchReport to Markdown."""
    lines: list[str] = []
    lines.append(f"# Daily Trending Research Report: {report.topic}")
    lines.append("## Executive Summary")
    lines.append(report.executive_summary)
    lines.append("## Detailed Findings")
    lines.append(report.detailed_findings)
    lines.append("## Citations")
    if report.sources:
        for idx, source in enumerate(report.sources, start=1):
            lines.append(
                f"{idx}. [{source.title}]({source.url}) — {source.snippet}"
            )
    else:
        lines.append("No sources were provided.")
    lines.append("## Metadata")
    lines.append(f"- Iterations: {report.iterations}")
    lines.append(f"- Generated at: {report.generated_at.isoformat()}")
    if report.quality_indicators:
        qi = report.quality_indicators
        if qi.quality_score is not None:
            lines.append(f"- Quality score: {qi.quality_score:.2f}")
        if qi.limited_sources:
            lines.append("- Sources limited: true")
        if qi.warnings:
            lines.append(f"- Warnings: {', '.join(qi.warnings)}")
    return "\n\n".join(lines)

