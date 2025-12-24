# Quickstart: DailyTrendingResearch Workflow (Spec 003)

This quickstart is for developers who want to run/trigger the DailyTrendingResearch workflow and understand the expected inputs/outputs.

## What you get

- A Windmill-orchestrated workflow that executes an embedded LangGraph loop: Plan → Research → Critique → Refine → Finish
- A Markdown report with cited sources (FR-008)
- Storage via `MemoryManager` with metadata (FR-009)
- Human-in-the-loop approvals for risky actions using Windmill suspend/resume (FR-006, FR-007)
- End-to-end OpenTelemetry spans (FR-011)

## Prerequisites

- **Python**: 3.11+
- **Docker Compose**: required for local Postgres + Jaeger (per project context)
- **Windmill**: running locally or reachable from your environment (workers execute the Python steps)
- **Env vars**: configured for LLM, DB, and telemetry

## Environment configuration (minimum)

- **Database / Memory**
  - `DATABASE_URL` (PostgreSQL 15+ with pgvector)

- **LLM (Azure AI Foundry / DeepSeek 3.2)**
  - Configure via `src/core/llm.py` requirements:
    - `AZURE_AI_FOUNDRY_ENDPOINT`
    - `AZURE_AI_FOUNDRY_API_KEY`
    - `AZURE_DEPLOYMENT_NAME`

- **OpenTelemetry**
  - `OTEL_SERVICE_NAME=paias`
  - `OTEL_EXPORTER_OTLP_ENDPOINT` (points to your collector; Jaeger/collector per repo setup)

## Trigger the workflow (API contract)

The Phase 1 contract lives at:

- `specs/003-daily-research-workflow/contracts/workflow-api.yaml`

### Start a run

Example request:

```bash
curl -sS -X POST \
  -H 'Content-Type: application/json' \
  http://localhost:8000/v1/research/workflows/daily-trending-research/runs \
  -d '{
    "topic": "AI governance trends 2025",
    "user_id": "8b6a4c64-3e0b-4a65-b0df-4e7e1e95d1e3"
  }'
```

Expected response: `202 Accepted` with a `run_id`.

### Poll run status

```bash
curl -sS \
  http://localhost:8000/v1/research/workflows/daily-trending-research/runs/{run_id}
```

Key fields:

- `status`: `queued|running|suspended_approval|completed|failed|escalated`
- `iterations_used`: must be ≤ 5
- `approval`: when `status=suspended_approval`, contains Windmill approval URLs and timeout info

### Retrieve the final report

```bash
curl -sS \
  http://localhost:8000/v1/research/workflows/daily-trending-research/runs/{run_id}/report
```

Returns Markdown in `markdown` plus normalized `sources`.

## Human approval behavior

If the workflow determines it should execute an action categorized as `REVERSIBLE_WITH_DELAY`, it MUST:

- Suspend execution in Windmill and request approval (FR-006)
- Timeout after **5 minutes** and escalate: log + skip action (FR-007)

In clients, show `approval.approval_page_url` to the user to approve/reject.

## Observability

You should see spans for:

- Windmill step start/end
- LangGraph execution root span + spans per node (`plan`, `research`, `critique`, `refine`, `finish`)
- MCP tool calls
- Memory operations

## Next steps

- Use `data-model.md` for the entity definitions and validation rules.
- Use `contracts/` as the contract-of-record while implementing the actual API + Windmill workflow scripts.


