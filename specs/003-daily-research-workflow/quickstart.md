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
- **Docker Compose**: required for local Postgres + Jaeger + Windmill
- **Windmill**: included in docker-compose.yml (runs on port 8100)
- **Env vars**: configured for LLM, DB, and telemetry

## Starting the Infrastructure

```bash
# Start all services (Postgres, Jaeger, Windmill)
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Expected output:
# postgres         ... healthy
# jaeger           ... healthy
# windmill_server  ... healthy
# windmill_worker  ... running
```

**Service URLs:**
- **Windmill UI**: http://localhost:8100
- **Jaeger UI**: http://localhost:16686
- **API Server**: http://localhost:8000 (after starting with `python -m src.cli.run_api`)

## Environment configuration

### Minimum (in-process mode, no Windmill)

```bash
# Database / Memory
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/paias

# LLM (Azure AI Foundry / DeepSeek 3.2)
AZURE_AI_FOUNDRY_ENDPOINT=https://your-endpoint.openai.azure.com
AZURE_AI_FOUNDRY_API_KEY=your-api-key
AZURE_DEPLOYMENT_NAME=your-deployment

# OpenTelemetry
OTEL_SERVICE_NAME=paias
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### Full Windmill mode

```bash
# All of the above, plus:

# Enable Windmill orchestration
WINDMILL_ENABLED=true

# Windmill connection
WINDMILL_BASE_URL=http://localhost:8100
WINDMILL_WORKSPACE=default
WINDMILL_TOKEN=your-windmill-token  # Generate in Windmill UI

# Flow path (where your script is registered)
WINDMILL_FLOW_PATH=research/daily_research

# Approval timeout (default: 300 seconds = 5 minutes)
APPROVAL_TIMEOUT_SECONDS=300
```

## Deploying the Workflow to Windmill

### Step 1: Create a Windmill Token

1. Open Windmill UI: http://localhost:8100
2. First time: Create a workspace (e.g., "default") and admin user
3. Go to **Settings > Tokens**
4. Create a new token and add it to your `.env` as `WINDMILL_TOKEN`

### Step 2: Register the Research Script

**Option A: Via Windmill UI**
1. Navigate to **Scripts** in Windmill UI
2. Click **+ New Script**
3. Set path: `f/research/daily_research`
4. Set language: Python
5. Copy the contents of `src/windmill/daily_research.py`
6. Save the script

**Option B: Via Windmill CLI**
```bash
# Install Windmill CLI
pip install wmill

# Login to your Windmill instance
wmill workspace add default http://localhost:8100

# Push the script
wmill script push f/research/daily_research src/windmill/daily_research.py
```

### Step 3: Configure Script Dependencies

In Windmill, edit the script and add dependencies:
```
pydantic>=2.0
httpx>=0.24
langgraph>=0.0.1
```

Or configure the worker to use your project's virtual environment.

## Running the API server

For local development, use the provided CLI helper:

```bash
# From project root
python -m src.cli.run_api
```

This will:
- Load environment variables from `.env` file (if present)
- Start the FastAPI server on `http://127.0.0.1:8000` by default
- Enable auto-reload on code changes (development mode)
- Provide interactive API docs at `http://127.0.0.1:8000/docs`

**Configuration via environment variables:**
- `API_HOST`: Server host (default: `127.0.0.1`)
- `API_PORT`: Server port (default: `8000`)
- `API_RELOAD`: Enable auto-reload (default: `true`)

**Alternative (production):**
```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

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

### Approval flow

1. **Workflow suspends**: When a risky action is detected, the workflow pauses

2. **Check status**: Poll the run endpoint to see suspension
   ```bash
   curl http://localhost:8000/v1/research/workflows/daily-trending-research/runs/{run_id}
   ```
   Response includes:
   ```json
   {
     "status": "suspended_approval",
     "approval": {
       "status": "pending",
       "action_type": "external_api_call",
       "action_description": "Call external service",
       "approval_page_url": "http://localhost:8100/runs/..."
     }
   }
   ```

3. **Approve via API** (programmatic):
   ```bash
   curl -X POST http://localhost:8000/v1/research/workflows/daily-trending-research/runs/{run_id}/approve
   ```

4. **Or reject**:
   ```bash
   curl -X POST http://localhost:8000/v1/research/workflows/daily-trending-research/runs/{run_id}/reject \
     -H 'Content-Type: application/json' \
     -d '{"reason": "Not authorized"}'
   ```

5. **Or approve via Windmill UI**: Open `approval.approval_page_url` in browser

### Timeout behavior

- If no action is taken within 5 minutes (configurable via `APPROVAL_TIMEOUT_SECONDS`)
- The action is **skipped** and marked as `escalated`
- The workflow continues with remaining actions
- Escalation is logged for audit

## In-Process Mode (Testing)

For development without Windmill, set `WINDMILL_ENABLED=false` (default):

```bash
# .env
WINDMILL_ENABLED=false
```

In this mode:
- Workflows run directly in the API process
- Approval gates use in-memory tracking
- No Windmill infrastructure required
- Useful for unit tests and local debugging

## Observability

You should see spans for:

- Windmill step start/end
- LangGraph execution root span + spans per node (`plan`, `research`, `critique`, `refine`, `finish`)
- MCP tool calls
- Memory operations

View traces at: http://localhost:16686 (Jaeger UI)

## Troubleshooting

### Windmill not connecting

```bash
# Check Windmill logs
docker-compose logs windmill_server
docker-compose logs windmill_worker

# Verify health
curl http://localhost:8100/api/version
```

### Workflow not found

Ensure the script is registered at the correct path:
- Path should match `WINDMILL_FLOW_PATH` setting
- Default: `research/daily_research` (without `f/` prefix)

### Authentication errors

```bash
# Verify your token works
curl -H "Authorization: Bearer $WINDMILL_TOKEN" \
  http://localhost:8100/api/w/default/scripts/list
```

## Developer Notes

### Required Environment Variables Reference

The following environment variables are required or optional for Spec 003 functionality:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| **Database** ||||
| `DATABASE_URL` | Yes | - | PostgreSQL connection string with asyncpg driver |
| **LLM (Azure AI Foundry)** ||||
| `AZURE_AI_FOUNDRY_ENDPOINT` | Yes | - | Azure OpenAI endpoint URL |
| `AZURE_AI_FOUNDRY_API_KEY` | Yes | - | Azure OpenAI API key |
| `AZURE_DEPLOYMENT_NAME` | Yes | - | Model deployment name (e.g., `deepseek-3.2`) |
| **Windmill Orchestration** ||||
| `WINDMILL_ENABLED` | No | `false` | Enable Windmill orchestration (vs in-process) |
| `WINDMILL_BASE_URL` | When enabled | - | Windmill server URL (e.g., `http://localhost:8100`) |
| `WINDMILL_WORKSPACE` | When enabled | `default` | Windmill workspace name |
| `WINDMILL_TOKEN` | When enabled | - | API token from Windmill UI |
| `WINDMILL_FLOW_PATH` | No | `research/daily_research` | Script path in Windmill |
| `APPROVAL_TIMEOUT_SECONDS` | No | `300` | Approval gate timeout (5 minutes) |
| **OpenTelemetry** ||||
| `OTEL_SERVICE_NAME` | No | `paias` | Service name for traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | - | OTLP collector endpoint (e.g., `http://localhost:4317`) |
| **API Server** ||||
| `API_HOST` | No | `127.0.0.1` | Server bind host |
| `API_PORT` | No | `8000` | Server bind port |
| `API_RELOAD` | No | `true` | Enable hot-reload (dev mode) |

### Development vs Production Mode

**Development (in-process mode)**:
- Set `WINDMILL_ENABLED=false` (default)
- Workflows execute directly in the API process
- Approval gates use in-memory tracking
- Faster iteration, no external dependencies beyond Postgres

**Production (Windmill mode)**:
- Set `WINDMILL_ENABLED=true`
- Workflows are durable (survive API restarts)
- Approval gates use Windmill's native suspend/resume
- Resource isolation per worker (1 CPU, 2GB memory)
- Full observability via Windmill UI

### Configuring Windmill Workers

Workers in `docker-compose.yml` are pre-configured with resource limits per FR-010:

```yaml
deploy:
  resources:
    limits:
      cpus: "1.0"
      memory: 2G
```

For higher throughput, start additional workers:

```bash
docker-compose --profile scale up -d
```

### Trace Context Propagation

The API propagates trace context to Windmill via the `traceparent` argument. This enables end-to-end distributed tracing from API request → Windmill job → LangGraph nodes → agent tool calls.

To view traces:
1. Ensure `OTEL_EXPORTER_OTLP_ENDPOINT` is set
2. Run a workflow
3. Open Jaeger UI at http://localhost:16686
4. Search for service `paias`

## Next steps

- Use `data-model.md` for the entity definitions and validation rules.
- Use `contracts/` as the contract-of-record while implementing the actual API + Windmill workflow scripts.
- Review `src/windmill/client.py` for the Windmill API client implementation.
- See `src/windmill/approval_handler.py` for approval gate logic.


