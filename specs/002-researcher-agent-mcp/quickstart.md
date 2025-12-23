# Quickstart: ResearcherAgent with MCP Tools

**Feature**: 002-researcher-agent-mcp
**Audience**: Developers setting up local development environment
**Time**: 15-20 minutes

## Prerequisites

- Python 3.11+ installed (`python --version`)
- Node.js 18+ installed (`node --version`) for Open-WebSearch MCP server
- Docker and Docker Compose installed (for PostgreSQL + Jaeger)
- Azure AI Foundry access with DeepSeek 3.2 deployment
- Git repository cloned

## Setup Steps

### 1. Environment Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` and configure:

```bash
# Azure AI Foundry (required)
AZURE_AI_FOUNDRY_ENDPOINT=https://your-resource.azure.ai/models
AZURE_AI_FOUNDRY_API_KEY=your-api-key-here
AZURE_DEPLOYMENT_NAME=deepseek-v3

# MCP Server Configuration
WEBSEARCH_ENGINE=google  # options: google, duckduckgo, bing
WEBSEARCH_MAX_RESULTS=10
WEBSEARCH_TIMEOUT=30

# OpenTelemetry (for observability)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=paias-agent-layer

# Database (inherited from Spec 001)
DATABASE_URL=postgresql+asyncpg://paias:password@localhost:5432/paias_dev
```

**How to get Azure AI Foundry credentials**:
1. Log in to [Azure AI Foundry](https://ai.azure.com/)
2. Navigate to your project
3. Go to "Deployments" → "DeepSeek 3.2"
4. Copy the "Endpoint" URL and "API Key"

---

### 2. Install Dependencies

Using Poetry (recommended):

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install --extras "azure mcp otel"

# Activate virtual environment
poetry shell
```

Using pip (alternative):

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Key dependencies installed**:
- `pydantic-ai[azure]`: Pydantic AI with Azure AI Foundry support
- `mcp`: Python MCP client SDK
- `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`: Observability
- `asyncpg`, `sqlmodel`: Database access (from Spec 001)
- `pytest`, `pytest-cov`, `pytest-asyncio`: Testing

---

### 3. Start Infrastructure Services

Start PostgreSQL (from Spec 001) and Jaeger (for observability):

```bash
docker-compose up -d
```

**Services started**:
- PostgreSQL 15 with pgvector extension (port 5432)
- Jaeger all-in-one (UI on http://localhost:16686, OTLP on port 4317)

Verify services are running:

```bash
docker-compose ps
# Should show postgres and jaeger containers as "Up"
```

---

### 4. Run Database Migrations

**Note**: This step assumes Spec 001 (Core Memory Layer) is already implemented.

```bash
# Run Alembic migrations for memory layer
alembic upgrade head
```

If Spec 001 is not yet implemented, skip this step. The ResearcherAgent will fail to initialize without the MemoryManager dependency.

---

### 5. Verify MCP Tool Availability

Test that the Open-WebSearch MCP server can be started:

```bash
# Test npx command
npx -y @open-websearch/mcp-server --version

# Expected output: Version number (e.g., 1.2.3)
```

If this fails:
- Install Node.js 18+ from https://nodejs.org/
- Ensure `npx` is in your PATH

**Note**: The MCP server will be auto-started by the agent initialization code.

---

### 6. Run the Test Suite

Verify the installation with the test suite:

```bash
# Run all tests with coverage
pytest --cov=src --cov-report=html tests/

# Expected output:
# =================== test session starts ===================
# collected X items
# tests/unit/test_researcher_agent.py ........     [ XX%]
# tests/integration/test_mcp_tools.py .....        [ XX%]
# =================== XX passed in X.XXs ===================
# Coverage: XX% (must be >= 80%)
```

**If tests fail**:
- Check `.env` configuration (Azure AI Foundry credentials)
- Verify Docker services are running (`docker-compose ps`)
- Check PostgreSQL connection (`psql -h localhost -U paias paias_dev`)

---

### 7. Manual Testing with CLI

Test the ResearcherAgent with the CLI tool:

```bash
# Activate virtual environment if not already active
poetry shell  # or: source venv/bin/activate

# Run manual test
python -m src.cli.test_agent "What is the capital of France?"
```

**Expected output**:

```
Initializing ResearcherAgent...
├── Loading Azure AI Foundry model (deepseek-v3)
├── Starting MCP tools (web_search, read_file, get_current_time)
│   └── Open-WebSearch server started (npx @open-websearch/mcp-server)
├── Connecting to MemoryManager (PostgreSQL + pgvector)
└── Agent initialized successfully (3.2s)

Running query: "What is the capital of France?"
Tool calls:
  [1] web_search(query="capital of France", max_results=5) → 1.2s

Answer: Paris

Reasoning:
Used web_search to find the capital of France. Top result from Wikipedia
confirmed Paris as the capital and most populous city of France.

Confidence: 0.95

OpenTelemetry traces exported to Jaeger (http://localhost:16686)
```

---

### 8. View Traces in Jaeger UI

1. Open http://localhost:16686 in your browser
2. Select service: `paias-agent-layer`
3. Click "Find Traces"
4. You should see trace spans for:
   - `agent_run` (top-level span)
   - `mcp_tool_call:web_search` (child span)
   - Span attributes: `tool_name`, `parameters`, `confidence_score`

**Example trace structure**:
```
agent_run (5.2s)
├── mcp_tool_call:web_search (1.2s)
│   ├── tool_name: "web_search"
│   ├── parameters: {"query": "capital of France", "max_results": 5}
│   └── result_count: 5
└── confidence_score: 0.95
```

---

### 9. Test Tool Gap Detection

Test the agent with a task that requires missing tools:

```bash
python -m src.cli.test_agent "Retrieve my stock portfolio performance for Q3 2024"
```

**Expected output**:

```
Initializing ResearcherAgent...
└── Agent initialized successfully (2.8s)

Running query: "Retrieve my stock portfolio performance for Q3 2024"

Tool Gap Detected!
Missing tools:
  - financial_data_api
  - account_access

Attempted task: "Retrieve my stock portfolio performance for Q3 2024"

Existing tools checked:
  - web_search
  - read_file
  - get_current_time
  - search_memory
  - store_memory

Recommendation: Install or configure the missing MCP tools to complete this task.
```

---

### 10. Test Risk-Based Approval

Test risk categorization logic:

```bash
python -m src.cli.test_risk_assessment
```

**Expected output**:

```
Testing risk categorization...

web_search(query="test") → RiskLevel.REVERSIBLE
  Requires approval: False (auto-execute)

send_email(to="test@example.com", confidence=0.80) → RiskLevel.REVERSIBLE_WITH_DELAY
  Requires approval: True (confidence < 0.85)

delete_file(path="/data/important.txt", confidence=0.95) → RiskLevel.IRREVERSIBLE
  Requires approval: True (always require approval for irreversible actions)

All tests passed!
```

---

## Troubleshooting

### Issue: Azure AI Foundry connection fails

**Symptoms**:
```
Error: Failed to initialize Azure AI Foundry model
Details: Invalid API key or endpoint
```

**Solution**:
1. Verify `AZURE_AI_FOUNDRY_ENDPOINT` is correct (should end with `/models`)
2. Verify `AZURE_AI_FOUNDRY_API_KEY` is valid (regenerate if needed)
3. Check Azure AI Foundry deployment status (must be "Running")
4. Test endpoint with curl:
   ```bash
   curl -H "api-key: $AZURE_AI_FOUNDRY_API_KEY" \
        $AZURE_AI_FOUNDRY_ENDPOINT/deployments/deepseek-v3
   ```

---

### Issue: Open-WebSearch MCP server fails to start

**Symptoms**:
```
Error: Failed to connect to Open-WebSearch MCP server
Details: npx command not found
```

**Solution**:
1. Install Node.js 18+ from https://nodejs.org/
2. Verify npx is available: `npx --version`
3. Test manual server start:
   ```bash
   npx -y @open-websearch/mcp-server
   # Should start without errors
   ```

---

### Issue: PostgreSQL connection fails

**Symptoms**:
```
Error: Failed to connect to MemoryManager
Details: Connection refused (localhost:5432)
```

**Solution**:
1. Verify Docker services are running: `docker-compose ps`
2. Check PostgreSQL logs: `docker-compose logs postgres`
3. Test connection manually:
   ```bash
   psql -h localhost -U paias paias_dev -c "SELECT version();"
   ```
4. If still failing, restart services:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

---

### Issue: Tests fail with coverage below 80%

**Symptoms**:
```
FAILED: Coverage is XX% (required: 80%)
```

**Solution**:
This indicates missing test coverage for new code. Run coverage report to identify untested lines:

```bash
pytest --cov=src --cov-report=html tests/
open htmlcov/index.html  # View detailed coverage report
```

Add tests for any red (uncovered) lines before proceeding.

---

## Next Steps

After successful setup:

1. **Explore the codebase**:
   - `src/agents/researcher.py`: ResearcherAgent implementation
   - `src/core/tool_gap_detector.py`: Tool gap detection logic
   - `src/core/risk_assessment.py`: Risk categorization
   - `tests/`: All test files

2. **Read the planning docs**:
   - `specs/002-researcher-agent-mcp/plan.md`: Implementation plan
   - `specs/002-researcher-agent-mcp/data-model.md`: Data model definitions
   - `specs/002-researcher-agent-mcp/research.md`: Technical research

3. **Run `/speckit.tasks`** to generate implementation tasks
   - This will create `specs/002-researcher-agent-mcp/tasks.md`
   - Tasks will be ordered by dependency and priority

4. **Implement and test**:
   - Follow test-driven development (TDD)
   - Write tests first, then implementation
   - Ensure coverage stays >= 80%
   - Use OpenTelemetry traces for debugging

---

## Quick Reference

### Common Commands

```bash
# Start services
docker-compose up -d

# Run tests
pytest --cov=src --cov-fail-under=80 tests/

# Run linting
ruff check src/ tests/
black --check src/ tests/

# Format code
black src/ tests/

# Type checking
mypy src/

# View traces
open http://localhost:16686

# Stop services
docker-compose down
```

### Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `AZURE_AI_FOUNDRY_ENDPOINT` | Azure AI Foundry API endpoint | Yes |
| `AZURE_AI_FOUNDRY_API_KEY` | Azure AI Foundry API key | Yes |
| `WEBSEARCH_ENGINE` | Search engine (google/duckduckgo/bing) | No (default: google) |
| `WEBSEARCH_TIMEOUT` | Search timeout in seconds | No (default: 30) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry endpoint | No (default: localhost:4317) |
| `DATABASE_URL` | PostgreSQL connection string | Yes (from Spec 001) |

### Useful Links

- [Feature Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Data Model Documentation](./data-model.md)
- [API Contract (OpenAPI)](./contracts/researcher-agent-api.yaml)
- [Jaeger UI](http://localhost:16686)
- [Pydantic AI Docs](https://ai.pydantic.dev/)
- [MCP Specification](https://modelcontextprotocol.io/)
