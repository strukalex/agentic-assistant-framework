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

### Quickstart

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

# Launch infra (PostgreSQL + Jaeger)
docker-compose up -d

# TESTING

# Add the project root to PYTHONPATH
export PYTHONPATH="$PWD/src:$PYTHONPATH"

# Run tests with coverage gate
pytest
```

### Reset & DB re-init

To fully reset local infra, re-create the DB schema, and set `PYTHONPATH` automatically:

```bash
npm run reset
```

What the script does:
- Stops containers, removes volumes, restarts infra (`docker compose` fallback to `docker-compose`)
- Waits for Postgres health
- Runs `alembic upgrade head` to initialize the schema
- Exports `PYTHONPATH="$PWD/src:$PYTHONPATH"` for the session

Manual re-init (if you prefer the long form):
```bash
docker compose down
docker compose down -v
docker compose up -d
alembic upgrade head
```

### Running tests (PYTHONPATH automated)

Use the helper to avoid manually exporting `PYTHONPATH` and to auto-activate `venv` when present:

```bash
# npm wrappers (PYTHONPATH handled by the script)
npm test              # alias to npm run test:py
npm run test:py -q tests/integration

# Test the ResearcherAgent with MCP tools
npm run test:agent "What is the capital of France?"
```

If you want to run pytest directly, set `PYTHONPATH` first:
```bash
export PYTHONPATH="$PWD/src:$PYTHONPATH"
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
