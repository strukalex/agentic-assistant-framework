# Data Models: ResearcherAgent with MCP Tools and Tool Gap Detection

**Feature**: 002-researcher-agent-mcp
**Date**: 2025-12-22
**Purpose**: Define all Pydantic models for type-safe agent inputs/outputs

## Model Hierarchy

```
AgentResponse (output from researcher.run())
│
├── answer: str
├── reasoning: str
├── tool_calls: List[ToolCallRecord]
└── confidence: float

ToolGapReport (output from ToolGapDetector.detect_missing_tools())
│
├── missing_tools: List[str]
├── attempted_task: str
└── existing_tools_checked: List[str]

RiskLevel (enum for risk assessment)
│
├── REVERSIBLE
├── REVERSIBLE_WITH_DELAY
└── IRREVERSIBLE

ToolCallRecord (embedded in AgentResponse)
│
├── tool_name: str
├── parameters: dict
├── result: Optional[Any]
├── duration_ms: int
└── status: ToolCallStatus

ToolCallStatus (enum for tool execution status)
│
├── SUCCESS
├── FAILED
└── TIMEOUT
```

## Model Definitions

### AgentResponse

**Purpose**: Structured output from ResearcherAgent.run() (FR-003)

**Source File**: `src/models/agent_response.py`

```python
from pydantic import BaseModel, Field, confloat
from typing import List

class AgentResponse(BaseModel):
    """
    Structured response from ResearcherAgent.

    Attributes:
        answer: The final answer to the user's query
        reasoning: Explanation of tool choices and reasoning process
        tool_calls: List of all tool invocations made during execution
        confidence: Model's self-assessed confidence (0.0-1.0)
    """
    answer: str = Field(
        ...,
        description="The final answer to the user's query",
        min_length=1
    )
    reasoning: str = Field(
        ...,
        description="Explanation of how the answer was derived, including tool choices",
        min_length=1
    )
    tool_calls: List["ToolCallRecord"] = Field(
        default_factory=list,
        description="All tool invocations made during agent execution"
    )
    confidence: confloat(ge=0.0, le=1.0) = Field(
        ...,
        description="Confidence score between 0.0 and 1.0"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Paris",
                "reasoning": "Used web_search to find 'capital of France'. Top result from Wikipedia confirmed Paris.",
                "tool_calls": [
                    {
                        "tool_name": "web_search",
                        "parameters": {"query": "capital of France", "max_results": 5},
                        "result": [{"title": "Paris - Wikipedia", "url": "...", "snippet": "..."}],
                        "duration_ms": 1234,
                        "status": "SUCCESS"
                    }
                ],
                "confidence": 0.95
            }
        }
```

**Validation Rules**:
- `answer`: Must be non-empty string (user must receive some response)
- `reasoning`: Must be non-empty string (observability requirement)
- `confidence`: Must be between 0.0 and 1.0 (used for approval logic)
- `tool_calls`: Can be empty list (for tasks answerable without tools)

**State Transitions**: Immutable (created once after agent.run() completes)

**Related Requirements**: FR-003, SC-002, SC-010

---

### ToolCallRecord

**Purpose**: Record of a single tool invocation during agent execution

**Source File**: `src/models/agent_response.py`

```python
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Optional

class ToolCallStatus(str, Enum):
    """Status of a tool call execution."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"

class ToolCallRecord(BaseModel):
    """
    Record of a single tool invocation.

    Attributes:
        tool_name: Name of the MCP tool invoked
        parameters: Input parameters passed to the tool
        result: Tool output (None if failed/timeout)
        duration_ms: Execution time in milliseconds
        status: Execution status (success/failed/timeout)
    """
    tool_name: str = Field(
        ...,
        description="Name of the MCP tool that was invoked"
    )
    parameters: dict = Field(
        ...,
        description="Input parameters passed to the tool"
    )
    result: Optional[Any] = Field(
        None,
        description="Tool output; None if execution failed or timed out"
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Execution time in milliseconds"
    )
    status: ToolCallStatus = Field(
        ...,
        description="Execution status: SUCCESS, FAILED, or TIMEOUT"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "web_search",
                "parameters": {"query": "capital of France", "max_results": 5},
                "result": [
                    {"title": "Paris - Wikipedia", "url": "https://...", "snippet": "Paris is the capital..."}
                ],
                "duration_ms": 1234,
                "status": "SUCCESS"
            }
        }
```

**Validation Rules**:
- `tool_name`: Must be non-empty string
- `duration_ms`: Must be >= 0 (prevents negative time values)
- `result`: Nullable (None when status is FAILED or TIMEOUT)
- `status`: Must be one of SUCCESS, FAILED, TIMEOUT

**State Transitions**: Immutable (created once after tool execution completes)

**Related Requirements**: FR-030, FR-031, SC-008

---

### ToolGapReport

**Purpose**: Diagnostic report when agent detects missing tool capabilities (FR-013)

**Source File**: `src/models/tool_gap_report.py`

```python
from pydantic import BaseModel, Field
from typing import List

class ToolGapReport(BaseModel):
    """
    Report of missing tool capabilities detected during task analysis.

    Attributes:
        missing_tools: List of tool names/capabilities that are required but unavailable
        attempted_task: Original task description that triggered the gap detection
        existing_tools_checked: List of available tool names that were checked
    """
    missing_tools: List[str] = Field(
        ...,
        description="List of required capabilities not available in MCP tool registry",
        min_items=1
    )
    attempted_task: str = Field(
        ...,
        description="The task description that required the missing tools",
        min_length=1
    )
    existing_tools_checked: List[str] = Field(
        ...,
        description="List of available MCP tools that were evaluated",
        min_items=0
    )

    class Config:
        json_schema_extra = {
            "example": {
                "missing_tools": ["financial_data_api", "account_access"],
                "attempted_task": "Retrieve my stock portfolio performance for Q3 2024",
                "existing_tools_checked": ["web_search", "read_file", "get_current_time", "memory_search"]
            }
        }
```

**Validation Rules**:
- `missing_tools`: Must contain at least 1 tool name (if empty, no gap exists → return None instead)
- `attempted_task`: Must be non-empty string (for audit trail)
- `existing_tools_checked`: Can be empty list (edge case: MCP registry is empty)

**State Transitions**: Immutable (created once after gap detection completes)

**Related Requirements**: FR-009 to FR-014, SC-003

---

### RiskLevel

**Purpose**: Enum for categorizing tool action risk levels (FR-015)

**Source File**: `src/models/risk_level.py`

```python
from enum import Enum

class RiskLevel(str, Enum):
    """
    Risk categorization for tool actions.

    Values:
        REVERSIBLE: Read-only actions with no side effects (e.g., search, read_file)
        REVERSIBLE_WITH_DELAY: Actions that can be undone within a time window (e.g., send_email)
        IRREVERSIBLE: Actions with permanent consequences (e.g., delete_file, make_purchase)
    """
    REVERSIBLE = "reversible"
    REVERSIBLE_WITH_DELAY = "reversible_with_delay"
    IRREVERSIBLE = "irreversible"
```

**Validation Rules**:
- Must be one of three defined values (enforced by Enum)
- Immutable (Enums are frozen)

**State Transitions**: N/A (stateless enum)

**Usage Example**:
```python
from src.models.risk_level import RiskLevel
from src.core.risk_assessment import categorize_action_risk, requires_approval

risk = categorize_action_risk("delete_file", {"path": "/data/important.txt"})
assert risk == RiskLevel.IRREVERSIBLE
assert requires_approval(risk, confidence=0.95) is True  # Always require approval
```

**Related Requirements**: FR-015 to FR-023, SC-004, SC-005

---

## Entity Relationships

```
ResearcherAgent
  ↓ uses
MemoryManager (from Spec 001)
  ↓ provides
semantic_search() → List[SearchResult]
store_document() → str (document ID)

ResearcherAgent
  ↓ uses
MCP ClientSession
  ↓ provides
list_tools() → List[MCPTool]
call_tool() → Any

ResearcherAgent
  ↓ returns
AgentResponse
  ↓ contains
List[ToolCallRecord]

ToolGapDetector
  ↓ analyzes
task_description: str
  ↓ compares against
available_tools: List[MCPTool]
  ↓ returns
Optional[ToolGapReport]

risk_assessment.categorize_action_risk()
  ↓ takes
tool_name: str, parameters: dict
  ↓ returns
RiskLevel

risk_assessment.requires_approval()
  ↓ takes
action: RiskLevel, confidence: float
  ↓ returns
bool (approval required)
```

## Validation Summary

| Model | Key Validation | Enforcement |
|---|---|---|
| AgentResponse | confidence ∈ [0.0, 1.0] | Pydantic confloat |
| AgentResponse | answer, reasoning non-empty | Pydantic min_length=1 |
| ToolCallRecord | duration_ms >= 0 | Pydantic ge=0 |
| ToolCallRecord | status ∈ {SUCCESS, FAILED, TIMEOUT} | Pydantic Enum |
| ToolGapReport | missing_tools has >= 1 item | Pydantic min_items=1 |
| RiskLevel | value ∈ {REVERSIBLE, REVERSIBLE_WITH_DELAY, IRREVERSIBLE} | Python Enum |

## Persistence

**Note**: These models are **transient** (not persisted to database in this vertical slice).

Future persistence (Phase 2+):
- AgentResponse: Store in `agent_executions` table for audit trail
- ToolGapReport: Store in `tool_gap_log` table for self-extension analysis
- ToolCallRecord: Store in `tool_call_log` table for observability and debugging

For now, persistence is handled via:
1. OpenTelemetry spans (observability)
2. Application logs (debugging)
3. MemoryManager (semantic search + storage via Spec 001)

## Type Safety Guarantees

All models use Pydantic v2 for:
- Runtime validation (catches invalid data at API boundaries)
- IDE autocomplete (mypy type checking)
- JSON schema generation (automatic OpenAPI docs)
- Serialization/deserialization (JSON ↔ Python objects)

Example type safety check:
```python
# This will raise ValidationError at runtime
invalid = AgentResponse(
    answer="Paris",
    reasoning="",  # ERROR: min_length=1 violated
    tool_calls=[],
    confidence=1.5  # ERROR: must be <= 1.0
)

# This passes validation
valid = AgentResponse(
    answer="Paris",
    reasoning="Found via web search",
    tool_calls=[],
    confidence=0.95
)
```
