# Contracts: DailyTrendingResearch Workflow

This folder contains **design-time API contracts** for Spec 003.

- `workflow-api.yaml`: OpenAPI 3.0 contract for triggering a workflow run, polling status, and retrieving the final report.

## Notes

- **Approvals**: Human-in-the-loop approvals are executed via Windmill’s native suspend/resume UI. The API exposes approval URLs/status in `RunStatusResponse.approval` for clients to surface to users.
- **Iterations**: The LangGraph loop MUST enforce a hard maximum of **5 iterations** (FR-005).


