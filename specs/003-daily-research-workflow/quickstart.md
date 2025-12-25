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

## Environment configuration

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

## Triggering Workflows

### Via Windmill UI

1. Navigate to the flow in Windmill UI (http://localhost:8100)
2. Click "Run" and provide `topic` and `user_id` parameters

### Via Windmill API

```bash
# Using Windmill's native API
curl -X POST "http://localhost:8100/api/w/default/jobs/run_script_by_path" \
  -H "Authorization: Bearer $WINDMILL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "f/research/daily_research", "args": {"topic": "AI governance trends 2025", "user_id": "8b6a4c64-3e0b-4a65-b0df-4e7e1e95d1e3"}}'
```

### Checking Run Status

Use the Windmill UI or API to poll job status:

```bash
# Get job status
curl -H "Authorization: Bearer $WINDMILL_TOKEN" \
  "http://localhost:8100/api/w/default/jobs/get/{job_id}"
```

Key fields in the response:
- `status`: `queued|running|suspended|completed|failed`
- When `status=suspended`, the workflow is waiting for approval

## Human approval behavior

If the workflow determines it should execute an action categorized as `REVERSIBLE_WITH_DELAY`, it MUST:

- Suspend execution in Windmill and request approval (FR-006)
- Timeout after **5 minutes** and escalate: log + skip action (FR-007)

### Approval flow

1. **Workflow suspends**: When a risky action is detected, the workflow pauses and appears in Windmill UI

2. **Check status**: View the job in Windmill UI or poll via API:
   ```bash
   curl -H "Authorization: Bearer $WINDMILL_TOKEN" \
     "http://localhost:8100/api/w/default/jobs/get/{job_id}"
   ```

3. **Approve via Windmill UI**:
   - Open the job in Windmill UI
   - Click "Resume" to approve the suspended action

4. **Or approve via Windmill API**:
   ```bash
   curl -X POST "http://localhost:8100/api/w/default/jobs/resume/{job_id}" \
     -H "Authorization: Bearer $WINDMILL_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"resume_id": "approval_id", "approver": "user@example.com"}'
   ```

### Timeout behavior

- If no action is taken within 5 minutes (configurable via `APPROVAL_TIMEOUT_SECONDS`)
- The action is **skipped** and marked as `escalated`
- The workflow continues with remaining actions
- Escalation is logged for audit

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
| `WINDMILL_BASE_URL` | Yes | - | Windmill server URL (e.g., `http://localhost:8100`) |
| `WINDMILL_WORKSPACE` | No | `default` | Windmill workspace name |
| `WINDMILL_TOKEN` | Yes | - | API token from Windmill UI |
| `WINDMILL_FLOW_PATH` | No | `research/daily_research` | Script path in Windmill |
| `APPROVAL_TIMEOUT_SECONDS` | No | `300` | Approval gate timeout (5 minutes) |
| **OpenTelemetry** ||||
| `OTEL_SERVICE_NAME` | No | `paias` | Service name for traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | - | OTLP collector endpoint (e.g., `http://localhost:4317`) |

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

Trace context is propagated to Windmill via the `traceparent` argument. This enables end-to-end distributed tracing from Windmill job → LangGraph nodes → agent tool calls.

To view traces:
1. Ensure `OTEL_EXPORTER_OTLP_ENDPOINT` is set
2. Run a workflow
3. Open Jaeger UI at http://localhost:16686
4. Search for service `paias`

## Next steps

- Use `data-model.md` for the entity definitions and validation rules.
- Review `src/windmill/daily_research.py` for the workflow script implementation.
- See `src/windmill/approval_handler.py` for approval gate logic.


