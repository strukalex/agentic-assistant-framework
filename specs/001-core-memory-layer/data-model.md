# Data Model: Core Foundation and Memory Layer

**Feature**: Core Foundation and Memory Layer  
**Date**: 2025-12-21  
**Purpose**: Define database schema, Pydantic models, and entity relationships

## Overview

This document defines the data model for the Core Foundation and Memory Layer, including:
- Database schema (PostgreSQL tables)
- SQLModel entities (ORM + Pydantic validation)
- Pydantic models for API contracts
- Entity relationships and constraints
- Validation rules

---

## Entity Relationship Diagram

```
┌─────────────┐
│   Session   │
│             │
│ id (PK)     │
│ user_id     │
│ created_at  │
│ updated_at  │
│ metadata_   │
└──────┬──────┘
       │
       │ 1:N
       │
       ▼
┌─────────────┐
│   Message   │
│             │
│ id (PK)     │
│ session_id  │◄─── Foreign Key
│ role        │
│ content     │
│ created_at  │
│ metadata_   │
└─────────────┘

┌─────────────┐
│  Document   │  (Independent)
│             │
│ id (PK)     │
│ content     │
│ embedding   │◄─── pgvector (1536 dimensions)
│ metadata_   │
│ created_at  │
│ updated_at  │
└─────────────┘
```

**Key Relationships**:
- One Session has Many Messages (1:N)
- Documents are independent entities (no foreign keys)
- Documents may be referenced in Message.metadata_ via document_id

---

## Database Tables

### 1. `sessions` Table

**Purpose**: Store user interaction sessions (conversation containers)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Unique session identifier (UUID v4) |
| `user_id` | VARCHAR(255) | NOT NULL | User identifier (string; no auth in Phase 1) |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Session creation timestamp (UTC) |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last activity timestamp (UTC) |
| `metadata_` | JSONB | NULLABLE, DEFAULT '{}' | Flexible session metadata (tags, config) |

**Indexes**:
- Primary key index on `id` (automatic)
- B-tree index on `user_id` for user session lookup
- GIN index on `metadata_` for JSONB queries

**SQLModel Definition**:

```python
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
from uuid import UUID as PyUUID, uuid4

class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    
    id: PyUUID = Field(
        sa_column=Column(UUID, primary_key=True, default=uuid4)
    )
    user_id: str = Field(max_length=255, nullable=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    metadata_: dict = Field(
        sa_column=Column(JSONB, nullable=True, default=dict),
        default_factory=dict
    )
```

---

### 2. `messages` Table

**Purpose**: Store conversation messages (chat history)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Unique message identifier (UUID v4) |
| `session_id` | UUID | FOREIGN KEY → sessions(id), NOT NULL | Parent session reference |
| `role` | VARCHAR(50) | NOT NULL, CHECK IN ('user', 'assistant', 'system') | Message role |
| `content` | TEXT | NOT NULL | Message content (plaintext) |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Message creation timestamp (UTC) |
| `metadata_` | JSONB | NULLABLE, DEFAULT '{}' | Flexible message metadata (tokens, model, confidence) |

**Indexes**:
- Primary key index on `id` (automatic)
- B-tree index on `session_id` for conversation queries (high cardinality)
- B-tree index on `created_at` for temporal ordering
- GIN index on `metadata_` for JSONB queries

**Constraints**:
- Foreign key: `session_id` references `sessions(id)` ON DELETE CASCADE
- Check constraint: `role IN ('user', 'assistant', 'system')`

**SQLModel Definition**:

```python
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
from uuid import UUID as PyUUID, uuid4
import enum

class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Message(SQLModel, table=True):
    __tablename__ = "messages"
    
    id: PyUUID = Field(
        sa_column=Column(UUID, primary_key=True, default=uuid4)
    )
    session_id: PyUUID = Field(
        sa_column=Column(UUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    role: MessageRole = Field(sa_column=Column(Enum(MessageRole), nullable=False))
    content: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)
    metadata_: dict = Field(
        sa_column=Column(JSONB, nullable=True, default=dict),
        default_factory=dict
    )
```

---

### 3. `documents` Table

**Purpose**: Store documents with vector embeddings for semantic search

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Unique document identifier (UUID v4) |
| `content` | TEXT | NOT NULL | Document content (plaintext) |
| `embedding` | VECTOR(settings.vector_dimension) | NULLABLE | Vector embedding (configurable dimension, default 1536 for OpenAI Ada-002) |
| `metadata_` | JSONB | NULLABLE, DEFAULT '{}' | Flexible document metadata (source, category, tags) |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Document creation timestamp (UTC) |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp (UTC) |

**Indexes**:
- Primary key index on `id` (automatic)
- HNSW index on `embedding` for vector similarity search (cosine distance)
- GIN index on `metadata_` for JSONB queries
- B-tree index on `created_at` for temporal filtering

**Vector Index Configuration**:
```sql
CREATE INDEX idx_documents_embedding_hnsw 
ON documents 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**SQLModel Definition**:

```python
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime
from uuid import UUID as PyUUID, uuid4
from typing import Optional

class Document(SQLModel, table=True):
    __tablename__ = "documents"
    
    id: PyUUID = Field(
        sa_column=Column(UUID, primary_key=True, default=uuid4)
    )
    content: str = Field(nullable=False)
    embedding: Optional[list[float]] = Field(
        sa_column=Column(Vector(1536), nullable=True),
        default=None
    )
    metadata_: dict = Field(
        sa_column=Column(JSONB, nullable=True, default=dict),
        default_factory=dict
    )
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())
```

---

## Pydantic Models (API Contracts)

### 1. AgentResponse

**Purpose**: Standard response format for all agent interactions

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any

class AgentResponse(BaseModel):
    """Standard agent response format."""
    
    answer: str = Field(..., description="The agent's response text")
    reasoning: Optional[str] = Field(None, description="Explanation of agent's reasoning process")
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of tool calls made (name, args, result)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score (0.0-1.0)"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Response generation timestamp (UTC)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": "The capital of France is Paris.",
                "reasoning": "Retrieved from semantic search of geography documents.",
                "tool_calls": [
                    {"name": "semantic_search", "args": {"query": "capital of France"}, "result": "Paris"}
                ],
                "confidence": 0.95,
                "timestamp": "2025-12-21T10:00:00Z"
            }
        }
    }
```

---

### 2. ToolGapReport

**Purpose**: Report missing tools detected during agent execution (Article II.G)

```python
from pydantic import BaseModel, Field
from typing import Optional

class ToolGapReport(BaseModel):
    """Report for detected tool gaps (self-extension capability)."""
    
    missing_tools: list[str] = Field(
        ...,
        description="List of required tool names that are missing"
    )
    attempted_task: str = Field(
        ...,
        description="Description of the task that failed due to missing tools"
    )
    existing_tools_checked: list[str] = Field(
        ...,
        description="List of existing tools that were evaluated but insufficient"
    )
    proposed_mcp_server: Optional[str] = Field(
        None,
        description="Proposed MCP server name to implement (if agent can suggest)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "missing_tools": ["send_email"],
                "attempted_task": "Send research summary via email to user",
                "existing_tools_checked": ["filesystem", "web_search", "semantic_search"],
                "proposed_mcp_server": "mcp-email-server"
            }
        }
    }
```

---

### 3. ApprovalRequest

**Purpose**: Request human approval for actions (Human-in-the-Loop, Article II.C)

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Any, Optional

class RiskLevel(str, Enum):
    """Action risk categorization (Article II.C)."""
    REVERSIBLE = "reversible"               # Read-only, auto-execute
    REVERSIBLE_WITH_DELAY = "reversible_with_delay"  # 5-min timeout
    IRREVERSIBLE = "irreversible"           # Always require approval

class ApprovalRequest(BaseModel):
    """Request for human approval of an action."""
    
    action_type: str = Field(
        ...,
        description="Type of action (e.g., 'send_email', 'delete_file', 'make_purchase')"
    )
    action_description: str = Field(
        ...,
        description="Human-readable description of what the action will do"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Agent's confidence in action correctness (0.0-1.0)"
    )
    risk_level: RiskLevel = Field(
        ...,
        description="Risk category (reversible, reversible_with_delay, irreversible)"
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool that will execute the action"
    )
    parameters: dict[str, Any] = Field(
        ...,
        description="Parameters that will be passed to the tool"
    )
    requires_immediate_approval: bool = Field(
        ...,
        description="If True, action blocks until approval; if False, queued for async approval"
    )
    timeout_seconds: Optional[int] = Field(
        None,
        description="Auto-reject after N seconds if no response (None = no timeout)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "action_type": "send_email",
                "action_description": "Send research summary to user@example.com",
                "confidence": 0.85,
                "risk_level": "reversible_with_delay",
                "tool_name": "email_mcp_server",
                "parameters": {
                    "to": "user@example.com",
                    "subject": "Daily Research Summary",
                    "body": "Here are today's findings..."
                },
                "requires_immediate_approval": True,
                "timeout_seconds": 300
            }
        }
    }
```

---

## Validation Rules

### Session Validation

1. **user_id**: Non-empty string, max 255 characters
2. **created_at**: UTC timestamp, cannot be in the future
3. **updated_at**: UTC timestamp, must be >= created_at
4. **metadata_**: Valid JSON object (validated by PostgreSQL JSONB)

### Message Validation

1. **role**: Must be one of: 'user', 'assistant', 'system'
2. **content**: Non-empty string (min length: 1)
3. **session_id**: Must reference an existing session (foreign key constraint)
4. **created_at**: UTC timestamp, cannot be in the future
5. **metadata_**: Valid JSON object

**Pydantic Validator Example**:

```python
from pydantic import field_validator

class MessageCreate(BaseModel):
    session_id: PyUUID
    role: MessageRole
    content: str
    metadata_: dict = Field(default_factory=dict)
    
    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        return v.strip()
```

### Document Validation

1. **content**: Non-empty string (min length: 1)
2. **embedding**: If provided, must be exactly 1536 floats
3. **created_at**: UTC timestamp, cannot be in the future
4. **updated_at**: UTC timestamp, must be >= created_at
5. **metadata_**: Valid JSON object

**Pydantic Validator Example**:

```python
from pydantic import field_validator

class DocumentCreate(BaseModel):
    content: str
    embedding: Optional[list[float]] = None
    metadata_: dict = Field(default_factory=dict)
    
    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Document content cannot be empty")
        return v.strip()
    
    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimension(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        if v is not None and len(v) != 1536:
            raise ValueError(f"Embedding must be 1536-dimensional, got {len(v)}")
        return v
    
    @field_validator("embedding")
    @classmethod
    def validate_embedding_values(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        if v is not None:
            if not all(isinstance(x, (int, float)) for x in v):
                raise ValueError("Embedding must contain only numeric values")
        return v
```

### AgentResponse Validation

1. **answer**: Non-empty string
2. **confidence**: Float between 0.0 and 1.0 (inclusive)
3. **timestamp**: UTC timestamp
4. **tool_calls**: List of dictionaries (validated as JSON-serializable)

### ApprovalRequest Validation

1. **action_type**: Non-empty string
2. **confidence**: Float between 0.0 and 1.0 (inclusive)
3. **risk_level**: Must be one of RiskLevel enum values
4. **timeout_seconds**: If provided, must be positive integer

---

## Entity State Transitions

### Session States

Sessions are stateless in Phase 1 (no explicit state machine). State tracking may be added in Phase 2 via metadata_:

```json
{
  "state": "active | archived | expired",
  "last_activity": "2025-12-21T10:00:00Z"
}
```

### Message States

Messages are immutable once created (no state transitions). Deletion is handled by session cascade.

### Document States

Documents are immutable once created (no state transitions). Updates create new document versions in Phase 2.

---

## Metadata Schema Examples

### Session Metadata

```json
{
  "session_type": "research | analysis | conversation",
  "tags": ["daily-research", "phase-1"],
  "config": {
    "max_messages": 1000,
    "auto_archive_after_days": 30
  }
}
```

### Message Metadata

```json
{
  "token_count": 150,
  "model_used": "claude-3-5-sonnet",
  "confidence_score": 0.92,
  "processing_time_ms": 250,
  "referenced_documents": ["uuid-1", "uuid-2"]
}
```

### Document Metadata

```json
{
  "source": "arxiv | wikipedia | user_upload",
  "category": "research | documentation | notes",
  "tags": ["python", "async", "database"],
  "author": "John Doe",
  "version": "1.0",
  "url": "https://example.com/document"
}
```

---

## Query Patterns

### 1. Retrieve Conversation History

```python
# Get last N messages for a session, ordered by time
messages = await db.execute(
    select(Message)
    .where(Message.session_id == session_id)
    .order_by(Message.created_at.desc())
    .limit(limit)
)
return messages.scalars().all()[::-1]  # Reverse to get chronological order
```

### 2. Semantic Search

```python
# Find top K most similar documents using cosine similarity
from sqlalchemy import func

results = await db.execute(
    select(Document)
    .order_by(Document.embedding.cosine_distance(query_embedding))
    .limit(top_k)
)
return results.scalars().all()
```

### 3. Temporal Query with Metadata Filters

```python
# Find documents within date range and matching metadata
results = await db.execute(
    select(Document)
    .where(
        Document.created_at >= start_date,
        Document.created_at <= end_date,
        Document.metadata_["category"].astext == "research"
    )
    .order_by(Document.created_at.desc())
)
return results.scalars().all()
```

---

## Database Constraints Summary

| Constraint Type | Table | Description |
|----------------|-------|-------------|
| **Primary Key** | sessions | `id` (UUID) |
| **Primary Key** | messages | `id` (UUID) |
| **Primary Key** | documents | `id` (UUID) |
| **Foreign Key** | messages | `session_id` → sessions(id) ON DELETE CASCADE |
| **Unique** | None | No unique constraints (UUIDs are naturally unique) |
| **Check** | messages | `role IN ('user', 'assistant', 'system')` |
| **Not Null** | sessions | `id`, `user_id`, `created_at`, `updated_at` |
| **Not Null** | messages | `id`, `session_id`, `role`, `content`, `created_at` |
| **Not Null** | documents | `id`, `content`, `created_at`, `updated_at` |
| **Index (B-tree)** | sessions | `user_id` |
| **Index (B-tree)** | messages | `session_id`, `created_at` |
| **Index (B-tree)** | documents | `created_at` |
| **Index (HNSW)** | documents | `embedding` (vector cosine ops) |
| **Index (GIN)** | sessions | `metadata_` (JSONB) |
| **Index (GIN)** | messages | `metadata_` (JSONB) |
| **Index (GIN)** | documents | `metadata_` (JSONB) |

---

## Migration Summary

**Initial Migration (001_initial_schema.py)** will:

1. Enable `pgvector` extension
2. Create `sessions` table with indexes
3. Create `messages` table with foreign key and indexes
4. Create `documents` table with vector column and indexes
5. Create HNSW index on `documents.embedding`
6. Create GIN indexes on all `metadata_` columns

**Rollback** will:

1. Drop all three tables (CASCADE)
2. Drop pgvector extension (if safe)

---

## Summary

This data model provides:

- ✅ **Three core entities**: Session, Message, Document
- ✅ **Pydantic validation**: Type-safe models with field validators
- ✅ **SQLModel ORM**: Single source of truth for schemas
- ✅ **Vector support**: 1536-dimensional embeddings with HNSW indexing
- ✅ **Flexible metadata**: JSONB columns for extensibility
- ✅ **Foreign key relationships**: Session → Messages (1:N)
- ✅ **Temporal tracking**: created_at/updated_at on all entities
- ✅ **Comprehensive indexes**: B-tree, GIN, HNSW for optimal query performance

**Ready for**: Contract generation (Phase 1, next step)

