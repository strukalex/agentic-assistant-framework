# agentic-assistant-framework Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-23

## Active Technologies

- Python 3.11+ *(non-negotiable; see Constitution Article I.A)* + Pydantic AI *(Article I.C)*; pydantic-ai[azure] for Azure AI Foundry; mcp Python client for MCP server integration; FastAPI + Pydantic *(Article I.H)* (002-researcher-agent-mcp)

## Project Structure

```text
src/
├── core/
│   ├── llm.py              # Shared LLM utilities (Article II.I)
│   ├── telemetry.py        # Unified telemetry (Article II.H)
│   ├── memory.py           # Memory management
│   └── tool_gap_detector.py
├── agents/
│   └── researcher.py       # ResearcherAgent
├── models/
├── mcp_integration/
└── ...
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+ *(non-negotiable; see Constitution Article I.A)*: Follow standard conventions

## Shared Utilities

**IMPORTANT**: All agents MUST use shared utility modules per Constitution Article II.H and II.I:

### LLM Configuration (Article II.I)
- **Location**: `src/core/llm.py`
- **Functions**:
  - `get_azure_model() -> OpenAIModel`: Factory for Azure AI Foundry models
  - `parse_agent_result(result) -> T`: Extract data from Pydantic AI RunResult
- **Usage**:
  ```python
  from src.core.llm import get_azure_model, parse_agent_result

  model = get_azure_model()
  agent = Agent(model=model, ...)

  result = await agent.run(query)
  payload = parse_agent_result(result)
  ```
- **DO NOT**: Read AZURE_* environment variables directly, duplicate LLM configuration, implement custom result parsing

### Telemetry (Article II.H)
- **Location**: `src/core/telemetry.py`
- **Functions**:
  - `@trace_memory_operation(operation_name)`: For database operations
  - `@trace_agent_operation(operation_name)`: For agent execution
  - `@trace_tool_call`: For MCP tool invocations
- **DO NOT**: Create duplicate telemetry modules or TracerProvider initializations

## Recent Changes

- 2025-12-23: Added shared LLM utilities module (src/core/llm.py) per Constitution v2.3
- 002-researcher-agent-mcp: Added Python 3.11+ *(non-negotiable; see Constitution Article I.A)* + Pydantic AI *(Article I.C)*; pydantic-ai[azure] for Azure AI Foundry; mcp Python client for MCP server integration; FastAPI + Pydantic *(Article I.H)*

<!-- MANUAL ADDITIONS START -->

## Windmill Workflow Integration

### Script Generation & Deployment
- **Automation Protocol**: When asked to generate scripts for Windmill, you MUST:
  1. Write the code to a local file (e.g., `scripts/filename.py`).
  2. IMMEDIATELY run `wmill push` to deploy it.
  3. **Do not ask for permission** to execute the push command.
  
### Tooling
- **CLI**: Use the `wmill` CLI for all Windmill interactions.
- **Error Handling**: If `wmill push` fails, analyze the error, fix the script or path, and retry automatically.

### Path Conventions
- Unless specified, deploy scripts to `f/[project]/[script_name]`.
- Always output the final deployed path (e.g., `https://app.windmill.dev/scripts/...`) after success.


<!-- MANUAL ADDITIONS END -->
