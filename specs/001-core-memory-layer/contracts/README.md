# API Contracts: Core Foundation and Memory Layer

**Feature**: Core Foundation and Memory Layer  
**Date**: 2025-12-21  
**Purpose**: Define API contracts for MemoryManager and Pydantic models

## Overview

This directory contains API contract specifications for the Core Foundation and Memory Layer. Since this is an internal library (not a REST API), contracts are defined as:

1. **Python Type Signatures**: Method signatures for MemoryManager
2. **Pydantic Schemas**: JSON Schema for all models
3. **Usage Examples**: Code snippets demonstrating correct usage

---

## MemoryManager API Contract

### Method Signatures

```python
class MemoryManager:
    """
    Async memory abstraction layer for conversation history and semantic search.
    
    All methods are async and emit OpenTelemetry trace spans.
    All database operations are transaction-safe.
    """
    
    # === Session Management ===
    
    async def create_session(
        self,
        user_id: str,
        metadata: dict | None = None
    ) -> UUID:
        """
        Create a new session (optional; sessions auto-create on first message).
        
        Args:
            user_id: User identifier (string; no auth in Phase 1)
            metadata: Optional session metadata (tags, config)
        
        Returns:
            UUID: Newly created session ID
        
        Raises:
            ValueError: If user_id is empty
            DatabaseError: If database operation fails
        
        Traces:
            Span: memory.create_session
            Attributes: user_id, metadata_keys
        """
    
    # === Message Storage & Retrieval ===
    
    async def store_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        metadata: dict | None = None
    ) -> UUID:
        """
        Store a message in a session (auto-creates session if doesn't exist).
        
        Args:
            session_id: Parent session UUID
            role: Message role ('user', 'assistant', 'system')
            content: Message content (non-empty string)
            metadata: Optional message metadata (tokens, model, confidence)
        
        Returns:
            UUID: Newly created message ID
        
        Raises:
            ValueError: If role not in allowed values or content empty
            DatabaseError: If database operation fails
        
        Traces:
            Span: memory.store_message
            Attributes: session_id, role, content_length, metadata_keys
        """
    
    async def get_conversation_history(
        self,
        session_id: UUID,
        limit: int = 100
    ) -> list[Message]:
        """
        Retrieve conversation history for a session (most recent N messages).
        
        Args:
            session_id: Session UUID to retrieve messages from
            limit: Maximum number of messages to return (default: 100)
        
        Returns:
            list[Message]: Messages in chronological order (oldest first)
            Empty list if session doesn't exist or has no messages
        
        Raises:
            ValueError: If limit <= 0
            DatabaseError: If database operation fails
        
        Traces:
            Span: memory.get_conversation_history
            Attributes: session_id, limit, result_count
        """
    
    # === Document Storage & Search ===
    
    async def store_document(
        self,
        content: str,
        metadata: dict | None = None,
        embedding: list[float] | None = None
    ) -> UUID:
        """
        Store a document with optional vector embedding.
        
        Args:
            content: Document content (non-empty string)
            metadata: Optional document metadata (source, category, tags)
            embedding: Optional 1536-dimensional vector embedding
        
        Returns:
            UUID: Newly created document ID
        
        Raises:
            ValueError: If content empty or embedding dimension != 1536
            DatabaseError: If database operation fails
        
        Traces:
            Span: memory.store_document
            Attributes: content_length, has_embedding, metadata_keys
        """
    
    async def semantic_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filters: dict | None = None
    ) -> list[Document]:
        """
        Perform semantic search using vector similarity (cosine distance).
        
        Args:
            query_embedding: 1536-dimensional query vector
            top_k: Number of results to return (default: 10)
            metadata_filters: Optional JSONB filters (e.g., {"category": "research"})
        
        Returns:
            list[Document]: Top K most similar documents (ordered by similarity)
            Empty list if no documents match
        
        Raises:
            ValueError: If query_embedding dimension != 1536 or top_k <= 0
            DatabaseError: If database operation fails
        
        Traces:
            Span: memory.semantic_search
            Attributes: top_k, filter_count, result_count, query_time_ms
        """
    
    # === Temporal & Metadata Queries ===
    
    async def temporal_query(
        self,
        start_date: datetime,
        end_date: datetime,
        metadata_filters: dict | None = None
    ) -> list[Document]:
        """
        Query documents by date range and optional metadata filters.
        
        Args:
            start_date: Start of date range (inclusive, UTC)
            end_date: End of date range (inclusive, UTC)
            metadata_filters: Optional JSONB filters (e.g., {"source": "arxiv"})
        
        Returns:
            list[Document]: Documents created within date range, ordered by created_at DESC
            Empty list if no documents match
        
        Raises:
            ValueError: If end_date < start_date
            DatabaseError: If database operation fails
        
        Traces:
            Span: memory.temporal_query
            Attributes: start_date, end_date, filter_count, result_count
        """
    
    # === Health & Diagnostics ===
    
    async def health_check(self) -> dict[str, Any]:
        """
        Check database connectivity and return health status.
        
        Returns:
            dict: Health status including database version, connectivity
            Example: {"status": "healthy", "postgres_version": "15.3", "pgvector_version": "0.5.1"}
        
        Raises:
            DatabaseError: If database is unreachable
        
        Traces:
            Span: memory.health_check
            Attributes: status, postgres_version
        """
```

---

## Pydantic Model Schemas (JSON Schema)

### Session Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Session",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique session identifier"
    },
    "user_id": {
      "type": "string",
      "maxLength": 255,
      "description": "User identifier"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "Session creation timestamp (UTC)"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "Last activity timestamp (UTC)"
    },
    "metadata_": {
      "type": "object",
      "description": "Flexible session metadata",
      "additionalProperties": true
    }
  },
  "required": ["id", "user_id", "created_at", "updated_at"]
}
```

### Message Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Message",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique message identifier"
    },
    "session_id": {
      "type": "string",
      "format": "uuid",
      "description": "Parent session reference"
    },
    "role": {
      "type": "string",
      "enum": ["user", "assistant", "system"],
      "description": "Message role"
    },
    "content": {
      "type": "string",
      "minLength": 1,
      "description": "Message content"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "Message creation timestamp (UTC)"
    },
    "metadata_": {
      "type": "object",
      "description": "Flexible message metadata",
      "additionalProperties": true
    }
  },
  "required": ["id", "session_id", "role", "content", "created_at"]
}
```

### Document Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Document",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique document identifier"
    },
    "content": {
      "type": "string",
      "minLength": 1,
      "description": "Document content"
    },
    "embedding": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "minItems": 1536,
      "maxItems": 1536,
      "description": "1536-dimensional vector embedding (nullable)"
    },
    "metadata_": {
      "type": "object",
      "description": "Flexible document metadata",
      "additionalProperties": true
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "Document creation timestamp (UTC)"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "Last update timestamp (UTC)"
    }
  },
  "required": ["id", "content", "created_at", "updated_at"]
}
```

### AgentResponse Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentResponse",
  "type": "object",
  "properties": {
    "answer": {
      "type": "string",
      "description": "The agent's response text"
    },
    "reasoning": {
      "type": "string",
      "description": "Explanation of agent's reasoning process (nullable)"
    },
    "tool_calls": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "args": {"type": "object"},
          "result": {}
        }
      },
      "description": "List of tool calls made"
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Confidence score (0.0-1.0)"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Response generation timestamp (UTC)"
    }
  },
  "required": ["answer", "confidence", "timestamp"]
}
```

### ToolGapReport Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ToolGapReport",
  "type": "object",
  "properties": {
    "missing_tools": {
      "type": "array",
      "items": {"type": "string"},
      "description": "List of required tool names that are missing"
    },
    "attempted_task": {
      "type": "string",
      "description": "Description of the task that failed"
    },
    "existing_tools_checked": {
      "type": "array",
      "items": {"type": "string"},
      "description": "List of existing tools evaluated"
    },
    "proposed_mcp_server": {
      "type": "string",
      "description": "Proposed MCP server name (nullable)"
    }
  },
  "required": ["missing_tools", "attempted_task", "existing_tools_checked"]
}
```

### ApprovalRequest Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ApprovalRequest",
  "type": "object",
  "properties": {
    "action_type": {
      "type": "string",
      "description": "Type of action (e.g., 'send_email', 'delete_file')"
    },
    "action_description": {
      "type": "string",
      "description": "Human-readable description of the action"
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Agent's confidence (0.0-1.0)"
    },
    "risk_level": {
      "type": "string",
      "enum": ["reversible", "reversible_with_delay", "irreversible"],
      "description": "Risk category"
    },
    "tool_name": {
      "type": "string",
      "description": "Name of the tool that will execute"
    },
    "parameters": {
      "type": "object",
      "description": "Parameters for the tool",
      "additionalProperties": true
    },
    "requires_immediate_approval": {
      "type": "boolean",
      "description": "If true, action blocks until approval"
    },
    "timeout_seconds": {
      "type": "integer",
      "minimum": 1,
      "description": "Auto-reject after N seconds (nullable)"
    }
  },
  "required": [
    "action_type",
    "action_description",
    "confidence",
    "risk_level",
    "tool_name",
    "parameters",
    "requires_immediate_approval"
  ]
}
```

---

## Usage Examples

### Example 1: Store and Retrieve Conversation

```python
from uuid import uuid4
from core.memory import MemoryManager

# Initialize MemoryManager
memory = MemoryManager()

# Create a new session ID
session_id = uuid4()

# Store user message
await memory.store_message(
    session_id=session_id,
    role="user",
    content="What is async programming?",
    metadata={"source": "web_ui"}
)

# Store assistant response
await memory.store_message(
    session_id=session_id,
    role="assistant",
    content="Async programming allows non-blocking I/O operations...",
    metadata={
        "model": "claude-3-5-sonnet",
        "confidence": 0.95,
        "token_count": 150
    }
)

# Retrieve conversation history
history = await memory.get_conversation_history(session_id, limit=10)
for msg in history:
    print(f"{msg.role}: {msg.content}")
```

### Example 2: Semantic Search

```python
from core.memory import MemoryManager

memory = MemoryManager()

# Assume we have a query embedding from an embedding service
query_embedding = [0.1, 0.2, ..., 0.9]  # 1536 dimensions

# Perform semantic search
results = await memory.semantic_search(
    query_embedding=query_embedding,
    top_k=5,
    metadata_filters={"category": "research"}
)

# Display results
for doc in results:
    print(f"Document ID: {doc.id}")
    print(f"Content: {doc.content[:100]}...")
    print(f"Source: {doc.metadata_.get('source', 'unknown')}")
    print("---")
```

### Example 3: Temporal Query

```python
from datetime import datetime, timedelta
from core.memory import MemoryManager

memory = MemoryManager()

# Query documents from the last 30 days
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=30)

documents = await memory.temporal_query(
    start_date=start_date,
    end_date=end_date,
    metadata_filters={"source": "arxiv"}
)

print(f"Found {len(documents)} documents from the last 30 days")
```

### Example 4: Health Check

```python
from core.memory import MemoryManager

memory = MemoryManager()

# Check database health
health = await memory.health_check()
print(f"Status: {health['status']}")
print(f"PostgreSQL Version: {health['postgres_version']}")
print(f"pgvector Version: {health.get('pgvector_version', 'unknown')}")
```

---

## Error Handling

### Standard Exceptions

All MemoryManager methods may raise:

1. **ValueError**: Invalid input parameters (empty content, wrong dimensions, etc.)
2. **DatabaseError**: Database connection or query failures
3. **ValidationError**: Pydantic validation failures (raised by SQLModel)

### Example Error Handling

```python
from sqlalchemy.exc import DatabaseError
from pydantic import ValidationError

try:
    await memory.store_message(
        session_id=session_id,
        role="invalid_role",  # Invalid role
        content="Test message"
    )
except ValueError as e:
    print(f"Invalid input: {e}")
except DatabaseError as e:
    print(f"Database error: {e}")
except ValidationError as e:
    print(f"Validation error: {e}")
```

---

## OpenTelemetry Trace Attributes

### Standard Attributes for All Operations

- `service.name`: "paias-memory-layer"
- `operation.type`: Method name (e.g., "store_message", "semantic_search")
- `operation.success`: Boolean indicating success/failure
- `db.system`: "postgresql"

### Operation-Specific Attributes

#### store_message
- `session_id`: UUID
- `role`: string
- `content_length`: integer
- `has_metadata`: boolean

#### semantic_search
- `top_k`: integer
- `filter_count`: integer (number of metadata filters)
- `result_count`: integer
- `query_time_ms`: float

#### temporal_query
- `start_date`: ISO 8601 string
- `end_date`: ISO 8601 string
- `filter_count`: integer
- `result_count`: integer

---

## Contract Versioning

**Version**: 1.0.0  
**Status**: Initial release (Phase 1)  
**Breaking Changes**: None (initial version)

Future contract changes will follow semantic versioning:
- **Major**: Breaking API changes (method signature changes, removed methods)
- **Minor**: New methods added (backward compatible)
- **Patch**: Bug fixes, documentation updates

---

## Summary

This contract specification defines:

- ✅ **8 public MemoryManager methods** with complete type signatures
- ✅ **6 Pydantic models** with JSON Schema definitions
- ✅ **Usage examples** for all primary operations
- ✅ **Error handling patterns** for robustness
- ✅ **OpenTelemetry attributes** for observability
- ✅ **Versioning strategy** for future evolution

**Ready for**: Quickstart documentation (Phase 1, next step)

