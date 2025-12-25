# 🧠 Personal AI Assistant System (PAIAS)

A local-first ecosystem for autonomous agents, designed for long-term memory and complex reasoning.

## Project Overview

PAIAS is a modular framework for building and running AI agents that can perform real work. Unlike standard chatbots that rely on ephemeral context, this system is architected for persistence and reliability. It combines deterministic workflow orchestration with the adaptive reasoning capabilities of Large Language Models (LLMs).

## Core Architecture

The system implements a **Composite UI** and **Hybrid Orchestration** strategy, leveraging best-in-class open-source tools to handle specific layers of the agent lifecycle:

*   🧠 **Agent Logic:** **Pydantic AI** provides type-safe, atomic reasoning capabilities.
*   ⚙️ **Orchestration:** **Windmill** handles durable, long-running workflows, while **LangGraph** manages complex cyclical reasoning loops.
*   💾 **Memory:** **PostgreSQL** with **pgvector** serves as the single source of truth for both relational data and semantic vector search.
*   🔌 **Integrations:** The **Model Context Protocol (MCP)** standardizes how agents connect to external tools (Filesystem, Google Drive, GitHub), preventing vendor lock-in.
*   👀 **User Interface:** A composite layer using **Streamlit** (Phase 1-2) for streaming chat interactions and Windmill for real-time workflow visualization. Production UI (LibreChat or React/Next.js) planned for Phase 3+.

## Core Foundation & Memory Layer (Phase 1)

This repository now includes the Phase 1 memory layer feature, built around Python 3.11, SQLModel, asyncpg, pgvector, and OpenTelemetry. The implementation is container-first and ships with Docker Compose for PostgreSQL + Jaeger.

### Dev tools [todo: if you see this move this section as part of your tasks]
Provides wmill command
`npm install -g windmill-cli`

#### Windmill setup
`wmill workspace add default http://localhost:8100`

Follow the prompts to log in (default user: admin@windmill.dev / changeme)

`wmill sync pull`  # Pulls the default workspace structure to your local disk

### Quickstart

For the ResearcherAgent (Spec 002) quickstart, follow the detailed guide in
`specs/002-researcher-agent-mcp/quickstart.md` and the CLI walkthrough in
`src/cli/README.md`. The abbreviated setup is below.

```bash
# Clone & enter repo
git clone <repository-url>
cd agentic-assistant-framework

# Set up virtual environment
pyenv install 3.11.14
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# Install the project in editable mode with all development dependencies
pip install -e .[dev]

# Install Node.js dependencies for MCP servers (requires Node.js 24+)
npm install

# Copy environment defaults
cp .env.example .env

# Launch infra (PostgreSQL + Jaeger + Windmill)
docker-compose up -d

# TESTING

# Run tests with coverage gate
pytest
```

## Windmill Orchestration (Spec 003)

The DailyTrendingResearch workflow uses **Windmill** for durable workflow orchestration with human-in-the-loop approval gates.

### Starting Windmill

```bash
# Start all services including Windmill
docker-compose up -d

# Or start with additional workers for parallel execution
docker-compose --profile scale up -d
```

**Services started:**
- **Windmill UI**: http://localhost:8100 (workflow management, approvals)
- **PostgreSQL**: localhost:5432 (shared with app)
- **Jaeger**: http://localhost:16686 (tracing)

### Windmill Configuration

Add these to your `.env` file:

```bash
# Windmill connection (matches docker-compose settings)
WINDMILL_BASE_URL=http://localhost:8100
WINDMILL_WORKSPACE=default
WINDMILL_TOKEN=  # Generate in Windmill UI: Settings > Tokens

# Flow path (where the research workflow is registered)
WINDMILL_FLOW_PATH=research/daily_research
```

### Deploying the Research Flow

1. Open Windmill UI at http://localhost:8100
2. Create a new workspace or use `default`
3. Create a new Script at path `f/research/daily_research`
4. Copy the contents of `src/windmill/daily_research.py`
5. Set the script language to Python
6. Configure environment variables in Windmill:
   - `DATABASE_URL`
   - `AZURE_AI_FOUNDRY_ENDPOINT`, `AZURE_AI_FOUNDRY_API_KEY`, `AZURE_DEPLOYMENT_NAME`

### Triggering Workflows

**Via Windmill UI:**
1. Navigate to the flow in Windmill UI
2. Click "Run" and provide `topic` and `user_id` parameters

**Via Windmill API:**
```bash
# Using Windmill's native API
curl -X POST "http://localhost:8100/api/w/default/jobs/run_script_by_path" \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"path": "f/research/daily_research", "args": {"topic": "AI trends 2025", "user_id": "550e8400-e29b-41d4-a716-446655440000"}}'
```

### Approval Gates

When a workflow requires human approval (for `REVERSIBLE_WITH_DELAY` actions):
1. The workflow suspends and appears in the Windmill UI pending approval
2. Open the Windmill UI to approve/reject
3. Workflow resumes after approval or times out after 5 minutes

See `specs/003-daily-research-workflow/quickstart.md` for detailed usage.

### Reset & DB re-init

To fully reset local infra, re-create the DB schema, and set `PYTHONPATH` automatically:

```bash
npm run reset
```

What the script does:
- Stops containers, removes volumes, restarts infra (`docker compose` fallback to `docker-compose`)
- Waits for Postgres health
- Runs `alembic upgrade head` to initialize the schema

Manual re-init (if you prefer the long form):
```bash
docker compose down
docker compose down -v
docker compose up -d
alembic upgrade head
```

### Running tests

Use the npm wrappers to auto-activate `venv` when present:

```bash
# npm wrappers
npm test              # alias to npm run test:py
npm run test:py -q tests/integration

# Test the ResearcherAgent with MCP tools
npm run test:agent "What is the capital of France?"
```

Or run pytest directly:
```bash
pytest
```

### LLM + Web Search (Phase 1 Agent Layer)

The Phase 1 agent spec assumes:

- **Default LLM**: DeepSeek 3.2 via **Microsoft Azure AI Foundry** (see `AZURE_AI_FOUNDRY_*` in `env.example`)
- **Web Search**: **Open-WebSearch MCP** (embedded via `npm install`, see `package.json`) (see `WEBSEARCH_*` in `env.example`)

### Updating packages

Use information from:
`pip list --outdated`

### Project Structure (Phase 1)

```
src/
  core/          # config, telemetry, memory manager (async)
  models/        # SQLModel + Pydantic models
tests/
  unit/          # unit tests (models, telemetry)
  integration/   # database + trace integration tests
  fixtures/      # shared fixtures and sample data
alembic/
  versions/      # migration scripts
docker-compose.yml  # PostgreSQL + Jaeger for local dev
```

### Operational Notes

- Minimum Python version: 3.11
- Coverage gate: 80% enforced via `pytest --cov=src --cov-fail-under=80`
- All DB operations must be async and traced (OpenTelemetry → Jaeger)
- ADR: See `docs/adr/0001-memory-layer.md` for memory-layer stack & constraints
