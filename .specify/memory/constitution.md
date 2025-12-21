<!--
═══════════════════════════════════════════════════════════════════════════════
SYNC IMPACT REPORT
═══════════════════════════════════════════════════════════════════════════════

VERSION CHANGE: v1.0 → v2.0 (MAJOR)

RATIONALE FOR MAJOR BUMP:
- Fundamental governance model change: phase-specific rules → conditional principles
- All Articles rewritten to be lifecycle-immutable
- Removed Article VII (Deferred Decisions) - removed entirely (no deferred decisions in constitution)
- Removed Article VIII (Roadmap Alignment) - phases are implementation concerns, not constitutional
- Removed Appendix B (Phase Mapping) - no longer applicable

MODIFIED PRINCIPLES:
- Article I.B: "Orchestration Framework: Phase 1–2 Baseline" → "Orchestration Framework: Pattern-Driven Selection"
- Article I.D: "Memory Layer: PostgreSQL-First (Phase 1–2)" → "Memory Layer: PostgreSQL-First Architecture"
- Article I.F: "UI Layer" - removed phase-specific references (e.g., "React Flow Phase 2")
- Article I.G: "Primary LLM Provider (Phase 1)" → "Primary LLM Provider"
- Article I.H: Removed phase references (e.g., "Fallback to Windmill; single-node Phase 1")
- Article II.A: Removed "Phase 1 Vertical Slice" concrete example; replaced with pattern
- Article II.B: Removed phase markers from Decision Pattern table
- Article II.C: "Phase 1 Baseline" confidence thresholds → "Baseline Configuration"
- Article II.E: "Multi-Storage Memory (Phase 3 Foundation)" → "Multi-Storage Memory Abstraction"
- Article II.F: Removed (Isolation Progression was phase-specific implementation detail)
- Article II.G: "Tool Gap Detection & Self-Extension (Phase 4+)" → "Tool Gap Detection & Self-Extension"
- Article III.F: Security section - removed phase progression; replaced with maturity triggers
- Article IV: "Failure Mode Detection & Recovery (Phase 2+)" → "Failure Mode Detection & Recovery"
- Article V.C: Removed "Ratification Schedule" (phase-bound)

REMOVED SECTIONS:
- Article VII: Deferred Decisions (Phase 2+) - removed entirely (constitutions define what IS decided, not what might be)
- Article VIII: Alignment with Roadmap - phases are not constitutional concerns
- Appendix B: Quick Reference – Article to Phase Mapping
- Appendix C: Maturity-Triggered Expansions - removed (still deferred decisions in disguise)

ADDED SECTIONS:
- Article II.F: Isolation & Safety Boundaries (replaces old II.F with maturity-triggered rules)

TEMPLATES REQUIRING UPDATES:
✅ .specify/templates/plan-template.md - Constitution Check section updated
✅ .specify/templates/spec-template.md - Constitution Constraints section updated
✅ .specify/templates/tasks-template.md - Constitution-driven requirements section updated
⚠ .specify/templates/commands/*.md - Review for outdated phase-specific references

FOLLOW-UP TODOS:
- Review all existing specs/plans/tasks for phase-specific language that now conflicts
- Update command files to reference conditional patterns instead of phase gates
- Consider adding ADR documenting the v1.0→v2.0 migration rationale

═══════════════════════════════════════════════════════════════════════════════
-->

# Personal AI Assistant System: Project Constitution v2.0

## Executive Summary

This constitution establishes the **immutable architectural rules** and **non-negotiable technology stack** for the Personal AI Assistant System (PAIAS). It serves as the persistent source of truth for all AI agents, developers, and technical decisions across the entire system lifecycle. Changes to this constitution require cross-functional review and documented rationale per Article V.

**Ratification Date:** 2025-12-20  
**Last Amended:** 2025-12-21  
**Status:** Active

---

## Article I: Non-Negotiable Technology Stack

### I.A Language & Runtime

**Decision:** Python 3.11+ with asynchronous support (asyncio)

**Rationale:** Python-native agent frameworks (Pydantic AI, LangGraph) and mature asyncio ecosystem.

**Enforcement:** All orchestration, agent logic, and core backend MUST use Python. No runtime language switching.

**CI Gate:** Linter checks `python_version >= "3.11"`

### I.B Orchestration Framework: Pattern-Driven Selection

**Hybrid Orchestration:** Windmill + LangGraph

**Selection Criteria (Pattern-to-Framework Mapping):**

| Workflow Pattern | Orchestrator | Use Case |
|---|---|---|
| Linear pipeline (fetch → process → store) | Windmill | DAG execution, visual builder, enterprise observability |
| Conditional branching (if X then Y else Z) | Windmill | Built-in branching with easy visualization |
| Cyclical reasoning (retry until success) | LangGraph | Explicit state machine, supports loops and backtracking |
| Adaptive multi-step with backtracking | LangGraph | Node-based reasoning with conditional edges |
| Role-based multi-agent teams | CrewAI | Native conversation patterns; role specialization (Sales, Engineering) |
| Exploratory agent-to-agent conversations | AutoGen | Collaborative reasoning via agent chat protocols |

**Usage Rules:**
- **Windmill** (v1.200+): Stateful task orchestration, scheduled tasks, deterministic data pipelines. Deploy as primary orchestrator.
- **LangGraph** (v1.0+): Complex reasoning requiring loops, branching, or multi-step state machines. Deploy as Python library inside Windmill workflow steps.
- **CrewAI**: Use ONLY for role-based multi-agent collaboration patterns. Deploy as Windmill workflow nodes.
- **AutoGen**: Use ONLY for exploratory conversational multi-agent patterns requiring agent-to-agent negotiation.

**Explicit Non-Usage:**
- **NOT:** LangChain as primary framework. Use LangChain core only for specialized MCP integrations where necessary due to existing ecosystem tooling.

**Integration Pattern:** LangGraph executes *inside* Windmill workflow steps; CrewAI and AutoGen integrate as Windmill workflow nodes. Windmill remains the primary orchestration layer.

### I.C Agent Building Block: Pydantic AI

**Version:** Latest stable (1.0+)

**Use Case:** Atomic agent unit; single focused capability (e.g., Researcher, Analyst, CodeReviewer)

**Rationale:** Type-safe, minimal boilerplate, model-agnostic, MCP-compatible agent framework.

**Key Constraint:** Pydantic AI is the *atomic unit*, not the system orchestrator. Orchestration happens in Windmill/LangGraph. Multiple Pydantic AI agents are composed via Windmill or LangGraph workflows.

### I.D Memory Layer: PostgreSQL-First Architecture

**Primary Database:** PostgreSQL 15+ with pgvector extension  
**ORM:** SQLAlchemy 2.0+ with async support  
**Vector Store:** pgvector (in-database)

**Data Architecture:**

1. **Relational + Document Memory (PostgreSQL)**
   - JSONB columns for raw document content and metadata (source, tags, permissions)
   - Temporal tracking: `created_at`, `updated_at`, optional `valid_from`/`valid_to` for audit trails
   - Conversation history in standard `sessions`, `messages` tables
   - pgvector extension: store embeddings alongside records; enables RAG without external tools

2. **Semantic Search**
   - pgvector for similarity search: `embedding <-> query_embedding`
   - Indexing: IVFFLAT or HNSW for sub-second queries at scale
   - Hybrid search: combine semantic similarity with traditional SQL filters

3. **Cache Layer (Maturity-Triggered)**
   - **Trigger:** When query patterns show >70% repeat retrieval within 1-hour windows OR when p95 query latency exceeds 200ms
   - **Implementation:** Redis for frequent retrieval results; PostgreSQL remains authoritative
   - **Invalidation:** LRU/TTL-based; cache misses fall through to PostgreSQL

4. **Multi-Storage Expansion (Maturity-Triggered)**
   - **Trigger:** When relationship queries (graph traversal) exceed 30% of query volume OR when vector storage exceeds 10M embeddings
   - **Options:**
     - LlamaIndex for orchestration across multiple storage backends
     - Neo4j for relationship reasoning and entity-centric queries
     - Pinecone/Weaviate for specialized vector operations at scale
     - Minio/S3 for large binary/document versioning
   - **Migration Path:** Abstract memory interface ensures storage upgrades don't break agents

**Non-Negotiable:** PostgreSQL is source of truth for all writes. No eventual consistency workarounds at the persistence layer.

**Query Router Pattern (Semantic vs. Relational):**
```
Query Type                        → Storage
"Find similar documents"          → pgvector semantic search
"What happened on date X?"        → SQL temporal filters
"Recall conversation about Y"     → pgvector + session time range
"Relationship between X and Y"    → Neo4j (if graph expansion triggered)
"Summarize Q4 financial data"     → Relational DB structured query
```

### I.E Tool Integration: Model Context Protocol (MCP)

**Standard:** Model Context Protocol (MCP)  
**Deployment:** MCP servers act as universal bridge between agents and external systems  
**Tool Discovery:** All tools listed via MCP's `list_resources` and `list_tools` patterns

**Pre-Built MCP Ecosystem:**
- Data Access: Filesystem, GitHub, Google Drive, Notion, databases
- External APIs: OpenWeather, financial data, news, social media
- Execution: Bash, HTTP, scheduled tasks
- Messaging: Slack, email, Discord

**Agent Tool Discovery Pattern:**
```
Agent: "I need to search for documents"
  ↓
MCP Client: "Which MCP servers have search?"
  ↓
Available: filesystem, googledrive, notion
  ↓
Agent: "Use filesystem for local docs, googledrive for shared"
  ↓
MCP Servers: Execute actual API calls
```

**No Hardcoded Integrations:** Every tool MUST flow through MCP. No agent-specific API clients except MCP adapters.

### I.F UI Layer: Composite Strategy

**Not a Single Tool; Multiple Specialized Components:**

1. **Chat Interaction:** Open WebUI
   - Conversational interface with real-time streaming responses
   - Token-by-token rendering; shows "Searching... 45 sources → Ranking → Synthesizing..."
   - Incremental result display; live tool execution feedback
   - Session persistence; human-in-the-loop approval buttons for risk-based escalation
   - Docker deployment; OpenAI API compatible

2. **Workflow Visualization:** Windmill's Built-in Graph Viewer + React Flow (when custom visualization needs arise)
   - Visual workflow builder
   - Real-time execution tracking
   - Dependency visualization

3. **System State Dashboard:** Custom React component or CoreUI template
   - Agent status (running, waiting, complete)
   - Memory statistics (vector store size, graph complexity)
   - Tool availability and health
   - Execution metrics (token counts, latency)

**Rationale:** Specialized components (Open WebUI for chat, Windmill for workflow visualization) provide better UX than single monolithic UI.

**Alternative Evaluation Trigger:** If authentication/moderation requirements change (e.g., enterprise SSO, multi-tenant isolation), evaluate LibreChat as secondary option for comparison.

### I.G Primary LLM Provider

**Default Production Model:** Claude 3.5 Sonnet (Anthropic)

**Rationale:** Balanced reasoning/code performance, long context (200K tokens), strong safety alignment, cost-effective at scale.

**Fallback / Comparison Models:**
- **OpenAI GPT-4 Turbo:** For tasks requiring maximum code generation quality
- **Local Ollama:** For on-premises privacy requirements; use Llama 2 (13B/70B) or Mistral 7B as baseline

**Non-Negotiable:** Model agnostic at *agent level* via Pydantic AI. Can swap providers without rewriting agent logic.

### I.H Supporting Tools & Libraries

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **Async Framework** | FastAPI | 0.110+ | REST API for agent results; ASGI async native |
| **Validation** | Pydantic | 2.0+ | Type safety; used by OpenAI SDK, Anthropic SDK |
| **Testing** | pytest + pytest-cov | Latest | Industry standard; coverage enforcement |
| **Linting** | Ruff + Black | Latest | Python 3.11+ compatible; 10x faster than flake8 |
| **Async Database** | asyncpg (PostgreSQL driver) | 0.30+ | Non-blocking DB I/O; required for async agents |
| **Observability** | OpenTelemetry + Logfire | Latest | Traces all agent decisions; integrates with Langfuse/Datadog |
| **Task Scheduling** | APScheduler | 3.10+ | Cron-style scheduling when Windmill not required |
| **Document Loading** | Unstructured + PyPDF2 | Latest | Basic PDF/DOCX parsing; LlamaParse for complex layouts when accuracy demands it |

---

## Article II: Architectural Principles (Design Invariants)

### II.A Principle: Vertical-Slice Delivery

**Definition:** Every delivery increment MUST provide a complete end-to-end system, not layers in isolation.

**Minimum Viable Vertical Slice:**
- User interaction layer (chat UI or API endpoint)
- Orchestration logic (workflow or agent reasoning)
- At least one functional agent with tool access
- Persistent memory (read + write capability)
- Observable execution (logs + traces for debugging)

**Validation:** A vertical slice is complete when a user can input a task, the system reasons and executes tools, and a response is delivered with full audit trail.

### II.B Principle: Pluggable Orchestration

**Definition:** Framework choice (Windmill, LangGraph, AutoGen, CrewAI) MUST decouple from agent definitions and tool ecosystem.

**Shared Abstraction Across Frameworks:**
- Agent definitions (Pydantic AI + @tool decorators)
- Tool ecosystem (MCP servers)
- Memory backends (PostgreSQL)
- Telemetry schema (OpenTelemetry)

**Decision Router:** Planning documents MUST reference Article I.B pattern-to-framework mapping to justify orchestrator selection. No framework lock-in without documented pattern mismatch.

**Implementation Requirement:** Agents written once; deployable across multiple orchestration frameworks with minimal adapter code.

### II.C Principle: Human-in-the-Loop by Default

**Definition:** Risk-based escalation policies, approval gates, and rollback capabilities MUST be present before production deployment.

**Action Categories by Reversibility:**

1. **Reversible (Read-Only)**
   - Pattern: Auto-execute with logging
   - Examples: Search queries, data retrieval, analysis
   - Gate: Post-execution log only

2. **Reversible with Delay**
   - Pattern: Request approval with time window
   - Examples: Send email, create calendar events, schedule tasks
   - Gate: Pre-execution approval + 5-minute timeout fallback

3. **Irreversible**
   - Pattern: Never auto-execute; always require approval
   - Examples: Delete files, make purchases, send money, modify production systems
   - Gate: Pre-execution approval mandatory (no timeout)

**Baseline Confidence Thresholds:**
- Confidence ≥ 85%: Auto-execute reversible actions; log all
- Confidence 50–85%: Conditional approval for reversible-with-delay
- Confidence < 50%: Escalate to human; never execute irreversible without explicit approval

**Tuning:** Confidence thresholds MAY be adjusted based on operational data (false positive/negative rates), but irreversible actions MUST always require human approval regardless of confidence.

### II.D Principle: Observable Everything

**Definition:** Every decision, tool call, reasoning path, and approval MUST be logged and visualizable.

**Mandatory Telemetry:**
- **Execution Capture:** Agent decision context (task, model, tools considered)
- **Outcome Tracking:** Success/failure labels, user corrections
- **Tool Calls:** Input, output, latency, failures
- **Approvals:** User decision, timestamp, override rationale
- **Token Usage:** Per request, per model, aggregated costs
- **Confidence Scores:** Per decision; used to tune escalation policies

**Backends:**
- Primary: OpenTelemetry spans → Logfire / Datadog
- Secondary: PostgreSQL audit tables for human-in-the-loop decisions
- Visualization: Custom React dashboard + Windmill execution UI

**Retention:** Minimum 30 days; no automatic deletion of approval audit trails.

### II.E Principle: Multi-Storage Memory Abstraction

**Definition:** Memory interfaces MUST abstract storage implementation so backend upgrades don't break agents.

**Current Baseline:** PostgreSQL single source of truth (see Article I.D)

**Future-Ready Pattern:** When multi-storage expansion is triggered (see Appendix D), agents interact through abstract memory interface:
```python
memory.semantic_search(query="user intent", top_k=10)  # Routes to pgvector or Pinecone
memory.graph_query(entity="Person", relation="works_with")  # Routes to PostgreSQL or Neo4j
memory.temporal_query(date_range="2024-Q4")  # Routes to PostgreSQL
```

**No Direct Coupling:** Agent code MUST NOT import database-specific drivers (e.g., `psycopg2`, `neo4j.GraphDatabase`) directly. All persistence flows through memory abstraction layer.

### II.F Principle: Isolation & Safety Boundaries

**Definition:** Execution isolation MUST evolve based on maturity triggers without requiring agent code rewrites.

**Maturity-Triggered Isolation Levels:**

| Trigger Condition | Isolation Model | Implementation |
|---|---|---|
| **Development / Single User** | In-process execution | Pydantic validation + confidence gates |
| **Multi-User / Concurrent Workflows** | Subprocess per agent | Resource limits (CPU, memory) per workflow |
| **Production / Untrusted Code Execution** | Containerized agents | Windmill per-workflow resource limits; Docker isolation |
| **Enterprise / Multi-Tenant** | Kubernetes pods | Multi-region failover; secrets management; network policies |
| **High-Security / Distributed** | Agent mesh | Service isolation; zero-trust networking; runtime attestation |

**No Rework Required:** Same agent code runs in all isolation models due to async/await design and abstract interfaces.

### II.G Principle: Tool Gap Detection & Self-Extension

**Definition:** When operational, the system MUST detect missing tool capabilities and facilitate extension.

**Pattern:**
1. **Scout Agent:** Attempts task with current tool registry; detects missing capabilities
2. **Tool Requirements Contract:** Emits detailed JSON spec (schemas, risk levels, test cases)
3. **Builder Agent:** Generates MCP server code, tool implementations, tests
4. **Human Approval Gate:** Code review and security validation
5. **Automated Deployment:** Approved tools deployed; MCP registries updated; Scout re-runs

**Maturity Trigger:** Self-extension enabled when:
- Tool failure rate due to missing capabilities exceeds 10% of tasks
- Manual tool development turnaround exceeds 48 hours on average
- Operational patterns have stabilized (90-day baseline established)

**Until Trigger Met:** Manual tool development only.

---

## Article III: Operational Standards

### III.A Testing & Code Quality

**Coverage Thresholds (Mandatory Enforcement):**
- **Minimum Overall Coverage:** 80% (`pytest --cov-fail-under=80`)
- **API Endpoints:** 85% coverage; all success/failure paths tested
- **Agent Logic:** 80% coverage; tool selection, error handling, escalation paths
- **Database Queries:** 75% coverage; ORM migrations tested end-to-end

**Test Types Required:**
1. **Unit Tests:** Individual functions in isolation; no external services
2. **Integration Tests:** Agent + tool calls; MCP server interactions
3. **Workflow Tests:** Orchestrator execution; state transitions
4. **Regression Tests:** Critical paths (human-in-the-loop escalation, approval flows)
5. **Safety Tests:** Irreversible actions always escalate; confidence thresholds respected

**CI Gate:**
```bash
pytest --cov=src --cov-fail-under=80 --cov-report=html tests/
# Fails build if coverage < 80%
```

**Linting Standards:**
- Formatter: Black (line length 100)
- Linter: Ruff (strict mode)
- Type Checking: mypy (strict mode)
- All required to pass before merge

### III.B Async Best Practices

**Non-Negotiable:**
- All I/O operations (database, MCP calls, external APIs) MUST be async
- No blocking calls in orchestration layer; use `asyncio.run()` only at entry points
- Connection pools configured for async drivers (asyncpg for PostgreSQL)
- Streaming responses for long-running tasks (LangGraph + Open WebUI)

### III.C Observability & Tracing

**Required Instrumentation (OpenTelemetry):**
- Agent reasoning: trace each step in orchestrator execution
- Tool calls: span per MCP server interaction
- Database queries: span per async query with query time and result count
- Approvals: trace escalation decision + human response time

**Minimum Retention:** 30 days; no automatic deletion of approval audit trails

### III.D Database Migrations

**Tool:** Alembic (SQLAlchemy migration framework)  
**Non-Negotiable:** All schema changes MUST use migrations; no raw SQL in production code  
**Testing:** Migration up + down tested in CI; rollback capability verified

### III.E Documentation Standards

**Required Documentation:**
- README.md: Local development setup, Docker instructions, first-run workflow
- API docs: Auto-generated via FastAPI; OpenAPI spec published
- Architecture Decision Records (ADRs): One per major tech choice; stored in `/docs/adr/`
- Agent templates: Docstring + usage example for each archetype

### III.F Security & Secrets

**Secret Management Maturity Levels:**

| Maturity Stage | Secret Storage | Trigger Condition |
|---|---|---|
| **Development** | Environment variables (`.env` files) | Local development only; never committed |
| **Production Single-Tenant** | HashiCorp Vault or AWS Secrets Manager | Multi-user deployment; API keys shared across users |
| **Production Multi-Tenant** | Per-tenant secret isolation + rotation | Customer data separation required by compliance |

**Tool Credentials:**
- Passed via secure MCP server channels; never hardcoded in agent code
- All secret access logged: who accessed what, when

**API Keys:**
- LLM API keys: environment variables in `.env` (never committed)
- MCP tool credentials: Vault-managed when production maturity reached
- Database credentials: Vault-managed with automatic rotation when production maturity reached

---

## Article IV: Failure Mode Detection & Recovery

### IV.A LLM Reliability Assumptions

**Given Reality:**
- LLMs hallucinate, fail, and produce confident but incorrect outputs
- Confidence scores alone cannot detect all failure modes
- Timeout and rate-limit errors occur; need graceful fallback

**Mandatory Baseline:** Basic error handling + confidence-based escalation (Article II.C)

**Enhanced Detection Layers (Maturity-Triggered):**

### IV.B Layer 1: Hallucination Detection

**Trigger:** When user correction rate exceeds 15% of agent responses

**Implementation:**
- **Fact-Checking:** Compare agent claims against retrieved sources; flag unsupported assertions
- **Cross-Reference Validation:** High-confidence claims require corroboration from 2+ sources
- **Threshold:** 80%+ confidence claims flagged for human review if unsupported

### IV.C Layer 2: Tool Failure Recovery

**Trigger:** When tool timeout/failure rate exceeds 5% of tool calls

**Implementation:**
- **Explicit Fallback Chains:** Tool A times out → Tool B → Tool C
- **Timeout Policies:** 10s web search; 30s complex query; escalate if exceeded
- **Graceful Degradation:** Full answer → Partial answer → Insufficient data (escalate)

### IV.D Layer 3: Model Switching

**Trigger:** When single-model failure rate exceeds 10% or cost per task exceeds budget thresholds

**Implementation:**
- **Health Monitoring:** Rate limits, errors, latency per model
- **Automatic Failover:** GPT-4 fails → Claude-3 → local Ollama
- **Cost-Aware Selection:** Expensive models only when cheaper ones fail

---

## Article V: Amendment Process

### V.A Constitutional Changes

**Definition:** Changes affecting tech stack, architectural principles, or core standards.

**Approval Process:**
1. **Proposal:** Pull request with documented rationale
2. **Review:** Cross-functional approval (tech lead, PM, principal engineer)
3. **Impact Analysis:** What breaks? What code changes required? Migration path?
4. **Vote:** 2/3 majority required for approval
5. **Merged:** Documented in commit message with reference to Articles affected

**Version Bumping:**
- **MAJOR:** Backward incompatible governance/principle removals or redefinitions
- **MINOR:** New principle/section added or materially expanded guidance
- **PATCH:** Clarifications, wording, typo fixes, non-semantic refinements

**Immutable Constraints:**
- Cannot change non-negotiable tech stack without rearchitecture proposal + migration plan
- Cannot weaken human-in-the-loop principles (Article II.C)
- Cannot reduce test coverage thresholds below 80%

### V.B Principle Clarifications

**Definition:** Interpretation of existing Articles (not changes).

**Approval Process:**
1. **PR with clarification text**
2. **Single tech lead approval** (fast-track)
3. **Merged** with "CLARIFICATION" in commit message

**Version Bump:** PATCH increment only.

---

## Article VI: Gating Checklist (Planning & Implementation Gates)

**All planning MUST reference this constitution.** Templates include automated gates:

```markdown
## Constitutional Compliance Checklist

- [ ] **Article I: Tech Stack** – Does this plan use approved frameworks?
  - [ ] Python 3.11+?
  - [ ] Orchestration: Pattern-to-framework mapping followed (Article I.B)?
  - [ ] Agents: Pydantic AI with @tool decorators?
  - [ ] Memory: PostgreSQL with async access?
  - [ ] Tools: All via MCP (no hardcoded integrations)?

- [ ] **Article II: Principles** – Respects all 7 principles?
  - [ ] Vertical slice deliverable?
  - [ ] Pluggable orchestration (framework-agnostic agent code)?
  - [ ] Human-in-the-loop for irreversible actions?
  - [ ] Observable: telemetry instrumented (Article II.D)?
  - [ ] Memory abstraction (no direct DB driver imports in agents)?

- [ ] **Article III: Standards** – Meets testing, observability, async requirements?
  - [ ] Tests: 80% coverage target enforced?
  - [ ] Async: All I/O non-blocking?
  - [ ] Instrumentation: OpenTelemetry spans?

If ANY gate fails, escalate to tech lead before proceeding.
```

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **MCP** | Model Context Protocol; universal standard for tool discovery and execution |
| **Reversible Action** | Action that can be undone or logged post-execution (search, analysis) |
| **Irreversible Action** | Action with permanent consequences (delete, purchase, send money) |
| **Confidence Threshold** | Model's self-assessed likelihood of correctness; used for escalation decisions |
| **Vertical Slice** | Complete end-to-end system (UI → orchestration → agent → memory) in miniature |
| **Pluggable Orchestration** | Framework choice decouples from agent definitions and tool ecosystem |
| **Audit Trail** | Complete log of human decisions, approvals, and system actions |
| **OpenTelemetry** | Standard for traces, metrics, logs; enables observability across all layers |
| **Maturity Trigger** | Operational metric threshold that activates advanced features (e.g., cache layer, multi-storage) |

---


---

**Ratified:** 2025-12-20  
**Last Amended:** 2025-12-21  
**Next Review:** When Article V.A amendment proposal submitted
