# Manual Testing Scripts

## manual_test_agent.py

Tests both **User Story 1** (basic research queries) and **User Story 2** (tool gap detection).

### Usage

```bash
# Run from project root
cd /home/lex/GitHub/agentic-assistant-framework

# Test basic Q&A (should succeed with AgentResponse)
python specs/002-researcher-agent-mcp/scripts/manual_test_agent.py "What is the capital of France?"

# Test tool gap detection (should return ToolGapReport)
python specs/002-researcher-agent-mcp/scripts/manual_test_agent.py "Retrieve my stock portfolio performance for Q3 2024"

# More examples that should trigger gap detection
python specs/002-researcher-agent-mcp/scripts/manual_test_agent.py "Send an email to john@example.com"
python specs/002-researcher-agent-mcp/scripts/manual_test_agent.py "Query the database for all admin users"
python specs/002-researcher-agent-mcp/scripts/manual_test_agent.py "Make a purchase of 100 shares of AAPL"
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
3. **Dependencies installed**: Poetry or pip install complete
   ```bash
   poetry install --extras "azure mcp otel"
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

## Next Steps

After successful manual testing:
1. Run automated test suite: `pytest --cov=src --cov-fail-under=80 tests/`
2. View traces in Jaeger UI: http://localhost:16686
3. Proceed to Phase 5 (Risk-Based Action Approval) implementation
