"""Contract tests for the DailyTrendingResearch workflow API.

Validates that the OpenAPI contract matches implementation expectations,
including approval status fields for User Story 2 (FR-006, FR-007).
"""

from pathlib import Path

import yaml


CONTRACT_PATH = (
    Path(__file__)
    .resolve()
    .parents[2]
    / "specs"
    / "003-daily-research-workflow"
    / "contracts"
    / "workflow-api.yaml"
)


def _load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def test_contract_contains_expected_paths_and_schemas() -> None:
    """Verify contract contains all required endpoints and schemas."""
    spec = _load_contract()

    paths = spec.get("paths", {})
    assert "/v1/research/workflows/daily-trending-research/runs" in paths
    assert "/v1/research/workflows/daily-trending-research/runs/{run_id}" in paths
    assert (
        "/v1/research/workflows/daily-trending-research/runs/{run_id}/report"
        in paths
    )

    schemas = spec["components"]["schemas"]
    for schema in [
        "CreateRunRequest",
        "CreateRunResponse",
        "RunStatusResponse",
        "ReportResponse",
        "ApprovalStatus",
        "RunStatus",
        "SourceReference",
    ]:
        assert schema in schemas

    # Key constraints from the contract
    request = schemas["CreateRunRequest"]["properties"]
    assert request["topic"]["maxLength"] == 500
    assert request["user_id"]["format"] == "uuid"

    run_status = schemas["RunStatus"]["enum"]
    assert set(run_status) == {
        "queued",
        "running",
        "suspended_approval",
        "completed",
        "failed",
        "escalated",
    }

    source_ref = schemas["SourceReference"]["properties"]
    assert source_ref["snippet"]["maxLength"] == 1000


def test_approval_status_schema_has_required_fields() -> None:
    """Verify ApprovalStatus schema contains all approval-related fields.

    Per FR-006: Workflow must suspend for REVERSIBLE_WITH_DELAY actions.
    Per FR-007: Approval timeout must be 5 minutes ± 10 seconds.
    """
    spec = _load_contract()
    schemas = spec["components"]["schemas"]

    approval_status = schemas["ApprovalStatus"]
    properties = approval_status.get("properties", {})

    # Required fields for approval flow (US2)
    assert "status" in properties, "ApprovalStatus must have status field"
    assert "action_type" in properties, "ApprovalStatus must have action_type field"
    assert "action_description" in properties, "ApprovalStatus must have action_description field"
    assert "timeout_at" in properties, "ApprovalStatus must have timeout_at field"

    # Status enum values for approval flow
    status_field = properties["status"]
    expected_statuses = {"not_required", "pending", "approved", "rejected", "escalated"}
    if "enum" in status_field:
        assert set(status_field["enum"]) == expected_statuses

    # Windmill approval URLs
    assert "approval_page_url" in properties, "ApprovalStatus should have approval_page_url"
    assert "resume_url" in properties, "ApprovalStatus should have resume_url"
    assert "cancel_url" in properties, "ApprovalStatus should have cancel_url"

    # Timeout field should be datetime format
    timeout_field = properties["timeout_at"]
    assert timeout_field.get("format") == "date-time", "timeout_at should be date-time format"


def test_run_status_includes_suspended_approval() -> None:
    """Verify RunStatus enum includes suspended_approval for US2.

    When a workflow has a pending approval, status should be 'suspended_approval'.
    """
    spec = _load_contract()
    schemas = spec["components"]["schemas"]

    run_status = schemas["RunStatus"]
    status_values = run_status.get("enum", [])

    assert "suspended_approval" in status_values, (
        "RunStatus must include 'suspended_approval' for pending approval states"
    )
    assert "escalated" in status_values, (
        "RunStatus must include 'escalated' for timeout escalation"
    )


def test_run_status_response_includes_approval_field() -> None:
    """Verify RunStatusResponse includes approval field for status details."""
    spec = _load_contract()
    schemas = spec["components"]["schemas"]

    run_status_response = schemas["RunStatusResponse"]
    properties = run_status_response.get("properties", {})

    assert "approval" in properties, "RunStatusResponse must include approval field"

    # Approval field should reference ApprovalStatus schema
    approval_field = properties["approval"]
    assert "$ref" in approval_field or "type" in approval_field


def test_contract_error_response_structure() -> None:
    """Verify ErrorResponse and RunError schemas are properly defined."""
    spec = _load_contract()
    schemas = spec["components"]["schemas"]

    # ErrorResponse should exist
    assert "ErrorResponse" in schemas
    error_response = schemas["ErrorResponse"]
    assert "error" in error_response.get("properties", {})

    # RunError should have message, code, and details
    assert "RunError" in schemas
    run_error = schemas["RunError"]
    properties = run_error.get("properties", {})

    assert "message" in properties, "RunError must have message field"
    assert "code" in properties, "RunError should have optional code field"
    assert "details" in properties, "RunError should have optional details field"


def test_create_run_response_includes_links() -> None:
    """Verify CreateRunResponse includes navigation links."""
    spec = _load_contract()
    schemas = spec["components"]["schemas"]

    create_response = schemas["CreateRunResponse"]
    properties = create_response.get("properties", {})

    assert "run_id" in properties, "CreateRunResponse must include run_id"
    assert "status" in properties, "CreateRunResponse must include status"
    assert "links" in properties, "CreateRunResponse should include links for HATEOAS"


def test_source_reference_has_retrieved_at() -> None:
    """Verify SourceReference includes retrieved_at timestamp for FR-008."""
    spec = _load_contract()
    schemas = spec["components"]["schemas"]

    source_ref = schemas["SourceReference"]
    properties = source_ref.get("properties", {})

    assert "retrieved_at" in properties, "SourceReference must have retrieved_at"
    assert properties["retrieved_at"].get("format") == "date-time"

