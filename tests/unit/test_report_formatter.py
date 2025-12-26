from uuid import uuid4

from paias.models.research_state import ResearchState
from paias.models.source_reference import SourceReference
from paias.workflows.report_formatter import format_research_report, render_markdown


def test_format_and_render_report() -> None:
    source = SourceReference(
        title="Example Source",
        url="https://example.com",
        snippet="A helpful snippet about the topic.",
    )
    state = ResearchState(
        topic="AI governance",
        user_id=uuid4(),
        refined_answer="AI governance is about accountability and safety.",
        critique="Ensure citations include regulatory perspectives.",
        iteration_count=2,
        sources=[source],
        quality_score=0.9,
    )

    report = format_research_report(state)
    assert report.topic == state.topic
    assert report.iterations == state.iteration_count
    assert report.sources == [source]

    markdown = render_markdown(report)
    assert "Executive Summary" in markdown
    assert "Detailed Findings" in markdown
    assert "Citations" in markdown
    assert source.title in markdown

