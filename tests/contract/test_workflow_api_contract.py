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

