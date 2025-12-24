# Manual Testing Scripts

## manual_test_agent.py

Tests **User Story 1** (basic research queries), **User Story 2** (tool gap detection), and **User Story 3** (risk-based action approval).

### Usage

```bash
# Run from project root
cd /home/lex/GitHub/agentic-assistant-framework

# Test basic Q&A (should succeed with AgentResponse)
python -m src.cli.test_agent "What is the capital of France?"

# Test tool gap detection (should return ToolGapReport)
python -m src.cli.test_agent "Retrieve my stock portfolio performance for Q3 2024"

# More examples that should trigger gap detection
python -m src.cli.test_agent "Send an email to john@example.com"
python -m src.cli.test_agent "Query the database for all admin users"
python -m src.cli.test_agent "Make a purchase of 100 shares of AAPL"
```

### Example Output: AgentResponse (Normal Query)

```
============================================================
Question:   What is the capital of France?
Answer:     Paris
Confidence: 0.95
Reasoning:  Used web_search to find 'capital of France'. Top result from Wikipedia confirmed Paris.

Tool calls:
- web_search (SUCCESS) 1234ms params={'query': 'capital of France', 'max_results': 5}
============================================================
```

### Example Output: ToolGapReport (Missing Tools)

```
============================================================
Question:        Retrieve my stock portfolio performance for Q3 2024

⚠️  TOOL GAP DETECTED!

The agent cannot complete this task because required tools are missing.

Missing tools:
  • financial_data_api
  • account_access

Attempted task:  Retrieve my stock portfolio performance for Q3 2024

Available tools checked (5):
  ✓ web_search
  ✓ read_file
  ✓ get_current_time
  ✓ search_memory
  ✓ store_memory

💡 Recommendation: Install or configure the missing MCP tools to complete this task.
============================================================
```

## Prerequisites

Before running the script, ensure:

1. **Environment configured**: `.env` file with Azure AI Foundry credentials
2. **Infrastructure running**: Docker services (PostgreSQL + Jaeger)
   ```bash
   docker-compose up -d
   ```
3. **Dependencies installed**: Editable install complete
   ```bash
   pip install -e .[dev]
   ```

## Troubleshooting

### Error: "AZURE_AI_FOUNDRY_ENDPOINT environment variable is required"

**Solution**: Ensure `.env` file is configured with Azure credentials:
```bash
AZURE_AI_FOUNDRY_ENDPOINT=https://your-resource.azure.ai/models
AZURE_AI_FOUNDRY_API_KEY=your-api-key-here
AZURE_DEPLOYMENT_NAME=deepseek-v3
```

### Error: "Failed to connect to MCP server"

**Solution**: Ensure Node.js 24+ is installed and npx is available:
```bash
npx --version  # Should output version number
```

### Error: "Failed to connect to MemoryManager"

**Solution**: Ensure PostgreSQL is running:
```bash
docker-compose ps  # Check postgres container is "Up"
```

## Testing User Story 3: Risk-Based Action Approval

**Note**: The risk assessment system is now integrated! All MCP tool invocations are automatically assessed for risk level.

### How Risk Assessment Works

The agent categorizes every tool action into three risk levels:

1. **REVERSIBLE** (auto-executes with logging):
   - `web_search`, `read_file` (safe paths), `get_current_time`, `search_memory`
   - Example: Searching the web is read-only and safe

2. **REVERSIBLE_WITH_DELAY** (requires approval if confidence < 0.85):
   - `send_email`, `create_calendar_event`, `schedule_task`
   - Example: Sending an email can be recalled within a time window

3. **IRREVERSIBLE** (always requires approval):
   - `delete_file`, `make_purchase`, `send_money`, `modify_production`
   - Unknown/unrecognized tools default to IRREVERSIBLE (conservative safety)

### Special Cases: Context-Dependent Risk

Reading sensitive files escalates from REVERSIBLE → REVERSIBLE_WITH_DELAY:
- Paths containing: `/etc/shadow`, `api_key`, `secret`, `credentials`, `password`

### Observing Risk Assessment in Logs

When you run the test script, watch for these log messages:

**Auto-executed REVERSIBLE actions:**
```
[INFO] ✅ Auto-executing REVERSIBLE action - tool: web_search, parameters: {'query': 'capital of France'}
```

**Approval required (IRREVERSIBLE or low-confidence REVERSIBLE_WITH_DELAY):**
```
[WARNING] ⚠️ Action requires approval - tool: delete_file, risk: irreversible, confidence: 1.00
```

**Tool response when approval is required:**
```
Answer: APPROVAL REQUIRED: Tool 'delete_file' with risk level 'irreversible'
        requires human approval before execution. Parameters: {'path': '/data/file.txt'}
```

### Testing Different Risk Scenarios

```bash
# 1. REVERSIBLE: Should auto-execute (check logs for "Auto-executing REVERSIBLE action")
python -m src.cli.test_agent "What is the capital of France?"

# 2. Sensitive file read: Currently treats as REVERSIBLE in this MVP
#    (file reading via MCP uses read_file tool from mcp-server-filesystem)
python -m src.cli.test_agent "Read the file at /etc/shadow"

# 3. Tool gap for IRREVERSIBLE actions: Should detect missing tool
#    (These tools don't exist, so gap detection triggers first)
python -m src.cli.test_agent "Delete the file /data/important.txt"
python -m src.cli.test_agent "Send an email to john@example.com saying hello"
python -m src.cli.test_agent "Make a purchase of 100 shares of AAPL"

# 4. REVERSIBLE_WITH_DELAY: Currently would require approval if tool existed
#    (These will trigger tool gap detection since send_email isn't in MCP tools)
python -m src.cli.test_agent "Schedule a meeting for tomorrow at 2pm"
```

### Expected Behavior

**Current Implementation (Phase 5 MVP):**

Since the agent only has REVERSIBLE tools available (web_search, read_file, get_current_time):
- ✅ All web searches will auto-execute with logging
- ✅ File reads will auto-execute (unless you add a tool that supports delete/send operations)
- ⚠️ Requests for IRREVERSIBLE/REVERSIBLE_WITH_DELAY tools will trigger **tool gap detection** (User Story 2) before risk assessment even runs

**To See Approval Blocking in Action:**

You would need to add MCP tools for IRREVERSIBLE actions (like `delete_file` or `send_email`). When you do:
1. The tool gap detection will pass (tool is available)
2. Risk assessment will categorize the action
3. If requires_approval() returns True, the agent will return an approval request message instead of executing

### Monitoring via Logs and Jaeger

**Check logs for risk assessment:**
```bash
# Look for these log patterns:
grep "Auto-executing REVERSIBLE" logs.txt
grep "Action requires approval" logs.txt
```

**View in Jaeger UI:**
- Navigate to http://localhost:16686
- Find traces with span attributes showing risk assessment decisions

## Next Steps

After successful manual testing:
1. Run automated test suite: `pytest tests/unit/test_risk_assessment.py -v`
2. Run contract tests: `pytest tests/contract/test_agent_api_contract.py::TestRiskAssessmentContract -v`
3. View traces in Jaeger UI: http://localhost:16686
4. Proceed to Phase 6 (Memory Integration for Knowledge Persistence) implementation
