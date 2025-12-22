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
