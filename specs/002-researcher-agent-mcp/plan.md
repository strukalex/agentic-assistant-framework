# Implementation Plan: ResearcherAgent with MCP Tools and Tool Gap Detection

**Branch**: `002-researcher-agent-mcp` | **Date**: 2025-12-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-researcher-agent-mcp/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a ResearcherAgent using Pydantic AI that integrates with three MCP tools (Open-WebSearch, filesystem read-only, time context) and implements tool gap detection to honestly report missing capabilities. The agent will connect to the memory layer from Spec 001 (Core Memory Layer), enforce risk-based approval for irreversible actions, and instrument all operations with OpenTelemetry for full observability. This Phase 1 vertical slice validates the Constitution's agent architecture (Pydantic AI + MCP-only tools + DeepSeek 3.2 via Azure AI Foundry).

## Technical Context

**Language/Version**: Python 3.11+ *(non-negotiable; see Constitution Article I.A)*
**Primary Dependencies**: Pydantic AI *(Article I.C)*; pydantic-ai[azure] for Azure AI Foundry; mcp Python client for MCP server integration; FastAPI + Pydantic *(Article I.H)*
**Storage**: PostgreSQL 15+ + pgvector *(Article I.D)* - inherited from Spec 001 (Core Memory Layer)
**Tool Integration**: Model Context Protocol (MCP) *(Article I.E; no hardcoded integrations)*
**UI Layer**: Streamlit for Phase 1-2 *(Article I.F)* - not part of this vertical slice; agent exposes Python API only
**Primary LLM**: DeepSeek 3.2 via Microsoft Azure AI Foundry endpoint *(Article I.G)* using pydantic-ai's AzureModel adapter
**Testing**: pytest + pytest-cov + pytest-asyncio; **minimum 80% coverage** *(Article III.A)*
**Target Platform**: Linux server (development) with Docker containerization for production
**Project Type**: Agent library with async Python API (CLI for manual testing only)
**Performance Goals**:
  - Agent initialization: < 10 seconds (includes MCP server startup)
  - Simple query response: < 5 seconds end-to-end (web search + LLM reasoning)
  - Tool gap detection: < 3 seconds (analyze task + compare vs. available tools)
**Constraints**:
  - All I/O must be async (Article III.B): database queries, MCP calls, LLM API calls
  - No blocking calls in agent execution path
  - MCP servers must gracefully handle initialization failures (fail fast with clear errors)
**Scale/Scope**:
  - Single-agent deployment (not multi-agent orchestration)
  - 3 MCP tool integrations (web search, filesystem read, time context)
  - 1 custom MCP time server to be built
  - Memory integration via dependency injection (MemoryManager from Spec 001)

## Constitution Check

*GATE: Must pass before research begins. Re-check after design phase.*

**Source of truth**: `.specify/memory/constitution.md` (v2.1)
**Project context**: `.specify/memory/project-context.md` (Phase 1: Core Foundation & Agent Layer)

### Constitutional Compliance Checklist (MUST)

- [x] **Article I — Non-Negotiable Technology Stack**: Implementation uses the approved stack:
  - [x] **Python 3.11+**: All agent code and MCP integration
  - [x] **Orchestration**: Not applicable for single-agent vertical slice (Windmill/LangGraph deferred to multi-agent orchestration in later phases)
  - [x] **Agents**: Pydantic AI as atomic agent unit (ResearcherAgent class)
  - [x] **Memory**: PostgreSQL + pgvector via MemoryManager abstraction from Spec 001
  - [x] **Tools**: MCP-only via mcp Python client (Open-WebSearch, mcp-server-filesystem, custom time server)
  - [x] **UI**: Not included in this vertical slice (agent exposes Python API; Streamlit integration deferred)
  - [x] **Primary model**: DeepSeek 3.2 via Azure AI Foundry using pydantic-ai's AzureModel

- [x] **Article II — Architectural Principles (all 7)**: Plan explicitly respects:
  - [x] Vertical-slice delivery: Complete agent (init + tool calls + memory + observability + tests) deliverable
  - [x] Pluggable orchestration: Agent code uses Pydantic AI abstractions only; no framework-specific code
  - [x] Human-in-the-loop by default: Risk categorization (REVERSIBLE/IRREVERSIBLE) + approval gates implemented
  - [x] Observable everything: OpenTelemetry instrumentation for all tool calls, agent runs, confidence scores
  - [x] Multi-storage memory abstraction: Agent uses MemoryManager interface (no direct psycopg2 imports)
  - [x] Isolation & safety boundaries: Async execution model compatible with future process/container isolation
  - [x] Tool gap detection & self-extension: ToolGapDetector implemented (self-extension deferred to maturity trigger)

- [x] **Article III — Operational Standards**:
  - [x] Tests + CI enforce **≥ 80% coverage**: pytest-cov configured with --cov-fail-under=80
  - [x] Async I/O for DB, MCP calls, external APIs: All MCP client calls use asyncio; MemoryManager is async
  - [x] OpenTelemetry instrumentation: @trace_tool_call decorator for MCP calls; agent.run() spans

### If any gate fails

- No violations. All Constitution requirements met.

## Project Structure

### Documentation (this feature)

```text
specs/002-researcher-agent-mcp/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file (in progress)
├── research.md          # Phase 0 output (to be generated)
├── data-model.md        # Phase 1 output (to be generated)
├── quickstart.md        # Phase 1 output (to be generated)
├── contracts/           # Phase 1 output (to be generated)
│   └── researcher-agent-api.yaml  # OpenAPI schema for agent Python API
├── checklists/          # Spec quality validation
│   └── requirements.md  # Completed during /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── agents/
│   ├── __init__.py
│   └── researcher.py           # ResearcherAgent class (Pydantic AI agent definition)
├── core/
│   ├── __init__.py
│   ├── tool_gap_detector.py    # ToolGapDetector class
│   ├── risk_assessment.py      # categorize_action_risk(), requires_approval()
│   └── observability.py        # @trace_tool_call decorator, OpenTelemetry setup
├── mcp_integration/
│   ├── __init__.py
│   ├── setup.py                # setup_mcp_tools() function
│   └── time_server/            # Custom MCP time server
│       ├── server.py           # MCP server implementation
│       └── tools.py            # get_current_time() tool implementation
├── models/
│   ├── __init__.py
│   ├── agent_response.py       # AgentResponse Pydantic model
│   ├── tool_gap_report.py      # ToolGapReport Pydantic model
│   └── risk_level.py           # RiskLevel enum
└── cli/
    ├── __init__.py
    └── test_agent.py           # Manual testing CLI (not production entry point)

tests/
├── unit/
│   ├── test_researcher_agent.py        # FR-003, FR-034 validation
│   ├── test_tool_gap_detector.py       # FR-009 to FR-014 validation
│   ├── test_risk_assessment.py         # FR-015 to FR-023 validation
│   └── test_observability.py           # FR-030, FR-031 validation
├── integration/
│   ├── test_mcp_tools.py               # FR-005 to FR-008 validation
│   └── test_memory_integration.py      # FR-024 to FR-026 validation
└── contract/
    └── test_agent_api_contract.py      # Validates OpenAPI schema

mcp-servers/
└── time-context/                       # Custom MCP time server (Node.js not required)
    ├── README.md
    └── server.py                       # Python-based MCP server (simpler than Node.js)

.env.example                            # FR-027, FR-028, FR-029 environment variable docs
pyproject.toml                          # Poetry dependencies with extras [azure, mcp, otel]
pytest.ini                              # Coverage threshold configuration
docker-compose.yml                      # Local dev environment (PostgreSQL + Jaeger)
```

**Structure Decision**: Single project structure (Option 1) with modular organization:
- `src/agents/`: Pydantic AI agent definitions (atomic units)
- `src/core/`: Cross-cutting concerns (tool gap detection, risk assessment, observability)
- `src/mcp_integration/`: MCP client setup and custom servers
- `src/models/`: Pydantic models for structured outputs
- `tests/`: Unit, integration, and contract tests (mirrors src/ structure)

No separate backend/frontend split needed for this agent library. Future orchestration (Windmill/LangGraph) will import from this package.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. This section intentionally left blank.
