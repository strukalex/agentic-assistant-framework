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
- `wmill sync push --skip-variables --skip-secrets --skip-resources`: Push scripts to Windmill (use `echo "Y" | wmill sync push ...` to auto-confirm)
- `wmill script generate-metadata`: Regenerate script metadata before pushing if stale
- `docker compose -f docker-compose.yml -f .private/docker-compose.override.yml build --no-cache windmill_worker`: Rebuild worker with new dependencies
- `docker compose -f docker-compose.yml -f .private/docker-compose.override.yml up -d windmill_worker`: Restart worker after rebuild

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
  1. Write the code to a local file (e.g., `f/tools/filename.py`).
  2. IMMEDIATELY run `echo "Y" | wmill sync push --skip-variables --skip-secrets --skip-resources` to deploy.
  3. **Do not ask for permission** to execute the push command.

### Tooling
- **CLI**: Use `wmill sync push` (NOT `wmill push` which doesn't exist).
- **Error Handling**: If push fails, analyze the error, fix the script, and retry automatically.

### Path Conventions
- Deploy scripts to `f/[project]/[script_name].py` (e.g., `f/tools/mem0_add.py`).
- Always output the final deployed path after success.

### Dependency Management (IMPORTANT)
- **DO NOT mount local venv into container** - compiled packages are architecture-specific
- **All `paias` dependencies are pre-installed** at worker startup via editable install to Windmill's cache
- **Use `# requirements:` directive** to skip Windmill's dependency resolution for scripts using `paias`:
  ```python
  # requirements:
  # ^ Empty requirements directive disables Windmill's import inference.
  # The paias package and all dependencies are pre-installed at container startup
  # via `pip install -e /opt/paias_project` in docker-compose.override.yml.
  ```
- **For scripts NOT using paias**, use PEP-723 inline script metadata:
  ```python
  # /// script
  # requires-python = ">=3.11"
  # dependencies = [
  #     "some-package>=1.0.0",
  # ]
  # ///
  ```
- **Adding new dependencies**: Add to `pyproject.toml`, then restart worker:
  ```bash
  docker compose -f docker-compose.yml -f .private/docker-compose.override.yml restart windmill_worker
  ```

### Script Conventions
- The `main()` function MUST NOT have any decorators
- Windmill parses the function signature directly for argument extraction
- Type hints are required on all parameters (e.g., `content: str`, not just `content`)
- Optional parameters must have default values (e.g., `metadata: dict[str, Any] | None = None`)
- Include `__windmill__` metadata dict with schema for better UI generation
- If you need tracing/decorators, wrap the logic in an internal function and call it from `main()`

### Docker Architecture
- `docker-compose.yml`: Base config with windmill_worker using standard image
- `.private/docker-compose.override.yml`: Overrides worker with:
  - Custom `Dockerfile.windmill-playwright` (Playwright + system deps)
  - Volume mount: `./:/opt/paias_project` (full project for editable install)
  - Startup command: `uv pip install --target /tmp/windmill/cache/python_3_12/global-site-packages -e /opt/paias_project`
  - This installs paias + all pyproject.toml dependencies to Windmill's cache
- **Editable install benefits**: Local changes to `paias/` are immediately reflected in worker (no rebuild needed)
- **When to restart worker**: Only when adding new dependencies to `pyproject.toml`

<!-- MANUAL ADDITIONS END -->
