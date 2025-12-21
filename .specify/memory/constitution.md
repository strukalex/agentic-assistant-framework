# Personal AI Assistant System: Project Constitution v1.0

## Executive Summary

This constitution establishes the **immutable architectural rules** and **non-negotiable technology stack** for the Personal AI Assistant System (PAIAS). It serves as the persistent source of truth for all AI agents, developers, and technical decisions across all phases of implementation. Changes to this constitution require cross-functional review and documented rationale.

**Applicable Phases:** Phases 1–5 (and beyond)  
**Last Updated:** December 20, 2025  
**Status:** Frozen for Phase 1 Development

---

## Article I: Non-Negotiable Technology Stack

### I.A Language & Runtime

**Decision:** Python 3.11+ with asynchronous support (asyncio)  
**Rationale:** Agent frameworks (Pydantic AI, LangGraph) are Python-native. Python ecosystem dominates LLM agent development. 3.11+ provides performance improvements and native structural pattern matching.  
**Enforcement:** All orchestration, agent logic, and core backend use Python. No runtime language switching between phases.  
**CI Gate:** Linter checks `python_version >= "3.11"`

### I.B Orchestration Framework: Phase 1–2 Baseline

**Primary Orchestrator (Phase 1–2):** Windmill + LangGraph Hybrid  

#### Windmill (Stateful Task Orchestration)
- **Version:** Latest stable (v1.200+)
- **Use Case:** DAG-style workflows, scheduled tasks, deterministic data pipelines
- **Installation:** Docker/Kubernetes in production
- **Rationale:** 
  - Enterprise-grade observability out of box (execution history, Prometheus metrics, dependency visualization)
  - 13x performance vs. Airflow; sub-second step execution
  - Resource isolation per workflow; prevents runaway agent tasks from crashing system
  - Visual code flexibility: workflows written as YAML or Python, auto-generates UI
  - Built-in AI copilot for flow generation

#### LangGraph (Complex Reasoning & Loops)
- **Version:** Latest stable (1.0+)
- **Use Case:** Workflows requiring cyclical reasoning, branching, loops, multi-step state machines
- **Deployment:** As Python library; instantiated within Windmill workflow steps
- **Rationale:**
  - Functional API with explicit state management—full control over agent thinking
  - Designed for OpenAI-compatible tool-calling format
  - Streaming support for token-by-token output to UI
  - Solves Windmill's gap: rigid DAG execution → LangGraph handles complex reasoning inside workflow nodes
- **Integration Pattern:** LangGraph executes *inside* a Windmill workflow step, not as a competing orchestrator

#### Explicit Non-Usage Boundaries:
- **NOT:** LangChain as primary framework. Use LangChain core only for specialized MCP integrations where necessary.
- **NOT:** CrewAI in Phase 1. Reserved for Phase 3 multi-agent collaboration (role-based crews as Windmill workflow nodes).
- **NOT:** AutoGen in Phase 1. Introduced Phase 2 for parallel evaluation against Windmill.

### I.C Agent Building Block: Pydantic AI

**Version:** Latest stable (1.0+)  
**Use Case:** Atomic agent unit; single focused capability (e.g., Researcher, Analyst, CodeReviewer)  
**Rationale:**
- Type-safe by design; Pydantic validation reduces runtime surprises
- Minimal boilerplate: agents defined in 20 lines with `@tool` decorators
- Model-agnostic: single interface supports OpenAI, Anthropic, local Ollama
- MCP-compatible: native support for Model Context Protocol tool discovery
- Human-in-the-loop: built-in tool approval and confidence mechanics
- FastAPI-style DX: developers familiar with structured validation frameworks move quickly

**Key Constraint:** Pydantic AI is the *atomic unit*, not the system orchestrator. Orchestration happens in Windmill/LangGraph. Multiple Pydantic AI agents composed via Windmill or LangGraph workflows.

### I.D Memory Layer: PostgreSQL-First (Phase 1–2)

**Primary Database:** PostgreSQL 15+ with pgvector extension  
**ORM:** SQLAlchemy 2.0+ with async support  
**Vector Store:** pgvector (in-database); no separate vector database required for Phase 1–2  

#### Data Architecture:
1. **Relational + Document Memory (PostgreSQL)**
   - JSONB columns for raw document content and metadata (source, tags, permissions)
   - Temporal tracking: `created_at`, `updated_at`, optional `valid_from`/`valid_to` for audit trails
   - Conversation history in standard `sessions`, `messages` tables
   - pgvector extension: store embeddings alongside records; enables RAG without external tools

2. **Semantic Search**
   - pgvector for similarity search: `embedding <-> query_embedding`
   - Indexing: IVFFLAT or HNSW for sub-second queries at scale
   - Hybrid search: combine semantic similarity with traditional SQL filters

3. **Cache Layer (Phase 2, Optional)**
   - Redis for frequent retrieval results; PostgreSQL remains authoritative
   - LRU/TTL-based invalidation

4. **Phase 3+ Multi-Storage Upgrade Path**
   - LlamaIndex for orchestration across multiple storage backends
   - Neo4j (optional) for relationship reasoning and entity-centric queries
   - Minio/S3 (optional) for large binary/document versioning
   - Consistency management and cross-store synchronization deferred to Phase 3

**Non-Negotiable:** PostgreSQL is source of truth for all writes in Phase 1–2. No eventual consistency workarounds.

### I.E Tool Integration: Model Context Protocol (MCP)

**Standard:** Model Context Protocol (MCP)  
**Deployment:** MCP servers act as universal bridge between agents and external systems  
**Tool Discovery:** All tools listed via MCP's `list_resources` and `list_tools` patterns  

#### Pre-Built MCP Ecosystem:
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

**No Hardcoded Integrations:** Every tool flows through MCP. No agent-specific API clients except MCP adapters.

### I.F UI Layer: Composite Strategy

**Not a Single Tool; Multiple Specialized Components:**

1. **Chat Interaction:** Open WebUI
   - Conversational interface with real-time streaming responses
   - Token-by-token rendering; shows "Searching... 45 sources → Ranking → Synthesizing..."
   - Incremental result display; live tool execution feedback
   - Session persistence; human-in-the-loop approval buttons for risk-based escalation
   - Docker deployment; OpenAI API compatible

2. **Workflow Visualization:** Windmill's Built-in Graph Viewer + React Flow (Phase 2)
   - Visual workflow builder
   - Real-time execution tracking
   - Dependency visualization

3. **System State Dashboard:** Custom React component or CoreUI template
   - Agent status (running, waiting, complete)
   - Memory statistics (vector store size, graph complexity)
   - Tool availability and health
   - Execution metrics (token counts, latency)

**Rationale for Composite:**
- Open WebUI excels at streaming chat with real-time agent reasoning
- Windmill provides live workflow visualization
- One tool for everything compromises everywhere
- UI layer is *not* the orchestration layer; system runs independently via APIs

**Non-UI Choice:** LibreChat as secondary option (Phase 2) for comparison if different auth/moderation needs emerge. Not Phase 1.

### I.G Primary LLM Provider (Phase 1)

**Default Production Model:** Claude 3.5 Sonnet (Anthropic)  
**Rationale:**
- Balanced for reasoning, code, and long context (200K tokens)
- Preferred in agent reasoning benchmarks vs. GPT-4
- Strong at refusing unsafe tool calls; aligns with human-in-the-loop safety goals
- Cost-effective for high-volume agent tasks

**Fallback / Comparison Models:**
- OpenAI GPT-4 Turbo: for tasks requiring maximum code generation quality
- Local Ollama (Phase 1): for on-premises privacy requirements; use Llama 2 (13B/70B) or Mistral 7B as baseline

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
| **Task Scheduling** | APScheduler | 3.10+ | Fallback to Windmill; single-node Phase 1 |
| **Document Loading** | Unstructured + PyPDF2 | Latest | Phase 1: basic PDF/DOCX parsing; LlamaParse Phase 3 |

---

## Article II: Architectural Principles (Design Invariants)

### II.A Principle: Vertical-Slice Delivery

**Definition:** Every phase delivers a complete end-to-end system, not layers in isolation.

**Phase 1 Vertical Slice:**
- Simple Chat UI (Open WebUI)
- Single Workflow Engine (Windmill)
- One ReAct Agent (Pydantic AI)
- Basic Memory (PostgreSQL + pgvector)
- User can input task → Agent reasons → Tools execute → Response delivered

**Why This Matters:**
- No "infrastructure layer done, agents layer next" delays
- Feedback and learning on *full system* behavior, not isolated components
- Easier to identify integration gaps early
- Faster path to operational learning loops

### II.B Principle: Pluggable Orchestration

**Definition:** Framework choice (Windmill, LangGraph, AutoGen, CrewAI) decouples from agent definitions and tool ecosystem.

**Shared Abstraction Across Frameworks:**
- Agent definitions (Pydantic AI + @tool decorators)
- Tool ecosystem (MCP servers)
- Memory backends (PostgreSQL)
- Telemetry schema (OpenTelemetry)

**Decision Pattern (Framework Selection):**
| Workflow Pattern | Best Tool | Reason |
|---|---|---|
| Linear pipeline (fetch → process → store) | Windmill | DAG execution, visual builder |
| Conditional branching (if X then Y else Z) | Windmill | Built-in branching, easy visualization |
| Cyclical reasoning (retry until success) | LangGraph | Explicit state machine, supports loops |
| Adaptive multi-step with backtracking | LangGraph | Node-based reasoning with conditional edges |
| Role-based multi-agent teams | CrewAI (Phase 3) | Native conversation patterns; Sales Agent, Engineering Agent patterns |
| Exploratory conversations | AutoGen (Phase 2) | Agent-to-Agent chat; collaborative reasoning |

**Implementation:** Decision router in `planning-template.md` explicitly references Article II.B to gate framework selection.

### II.C Principle: Human-in-the-Loop by Default

**Definition:** Risk-based escalation policies, approval gates, and rollback capabilities built into Phase 1.

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

**Confidence Thresholds (Phase 1 Baseline):**
- Confidence ≥ 85%: Auto-execute reversible actions; log all
- Confidence 50–85%: Conditional approval for reversible-with-delay
- Confidence < 50%: Escalate to human; never execute irreversible without explicit approval

### II.D Principle: Observable Everything

**Definition:** Every decision, tool call, reasoning path, and approval is logged and visualizable.

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

### II.E Principle: Multi-Storage Memory (Phase 3 Foundation)

**Phase 1–2:** PostgreSQL single source of truth  
**Phase 3+ Readiness:** Abstract memory interface so storage upgrades don't break agents

**Query Router Pattern (Semantic vs. Relational):**
```
Query Type                        → Storage
"Find similar documents"          → pgvector semantic search
"What happened on date X?"        → SQL temporal filters
"Recall conversation about Y"     → pgvector + session time range
"Relationship between X and Y"    → Neo4j (Phase 3)
"Summarize Q4 financial data"     → Relational DB structured query
```

### II.F Principle: Isolation Progression

**Definition:** Execution isolation evolves phase-by-phase without architectural rework.

| Phase | Isolation Model | Safety Level |
|-------|---|---|
| **Phase 1** | In-process; controlled via Pydantic validation + confidence gates | Medium |
| **Phase 2** | Subprocess per agent; resource limits (CPU, memory) per workflow | Medium-High |
| **Phase 3** | Containerized agents; Windmill per-workflow resource limits | High |
| **Phase 4** | Kubernetes pods; multi-region failover; secrets management | Enterprise |
| **Phase 5** | Distributed execution; agent mesh with service isolation | Maximum |

**No Rework Required:** Same agent code runs in all isolation models due to async/await design.

### II.G Principle: Tool Gap Detection & Self-Extension (Phase 4+)

**Pattern:**
1. **Scout Agent:** Attempts task with current tool registry; detects missing capabilities
2. **Tool Requirements Contract:** Emits detailed JSON spec (schemas, risk levels, test cases)
3. **Builder Agent:** Generates MCP server code, tool implementations, tests
4. **Human Approval Gate:** Code review and security validation
5. **Automated Deployment:** Approved tools deployed; MCP registries updated; Scout re-runs

**Phase 1–2 Constraint:** Manual tool development. Self-extension deferred to Phase 4 when operational patterns are stable.

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
3. **Workflow Tests:** Windmill DAG execution; state transitions
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
- All I/O operations (database, MCP calls, external APIs) must be async
- No blocking calls in orchestration layer; use `asyncio.run()` only at entry points
- Connection pools configured for async drivers (asyncpg for PostgreSQL)
- Streaming responses for long-running tasks (LangGraph + Open WebUI)

### III.C Observability & Tracing

**Required Instrumentation (OpenTelemetry):**
- Agent reasoning: trace each step in LangGraph node execution
- Tool calls: span per MCP server interaction
- Database queries: span per async query with query time and result count
- Approvals: trace escalation decision + human response time

**Minimum Retention:** 30 days; no automatic deletion of approval audit trails

### III.D Database Migrations

**Tool:** Alembic (SQLAlchemy migration framework)  
**Non-Negotiable:** All schema changes via migrations; no raw SQL in production code  
**Testing:** Migration up + down tested in CI; rollback capability verified  

### III.E Documentation Standards

**Required Documentation:**
- README.md: Local development setup, Docker instructions, first-run workflow
- API docs: Auto-generated via FastAPI; OpenAPI spec published
- Architecture Decision Records (ADRs): One per major tech choice; stored in `/docs/adr/`
- Agent templates: Docstring + usage example for each archetype

### III.F Security & Secrets

**Secret Management:**
- **Phase 1:** Environment variables (development only)
- **Phase 2+:** HashiCorp Vault or AWS Secrets Manager
- **Tool Credentials:** Passed via secure MCP server channels; never hardcoded
- **Audit Trail:** All secret access logged; who accessed what, when

**API Keys:**
- LLM API keys: environment variables in `.env` (never committed)
- MCP tool credentials: Vault-managed
- Database credentials: Vault-managed with automatic rotation

---

## Article IV: Failure Mode Detection & Recovery (Phase 2+)

### IV.A LLM Reliability Assumptions

**Given Reality:**
- LLMs hallucinate, fail, and produce confident but incorrect outputs
- Confidence scores alone cannot detect all failure modes
- Timeout and rate-limit errors occur; need graceful fallback

**Phase 1 Approach:** Basic error handling + confidence-based escalation  
**Phase 2+ Approach:** Three-layer failure detection (below)

### IV.B Layer 1: Hallucination Detection (Phase 2)

- **Fact-Checking:** Compare agent claims against retrieved sources; flag unsupported assertions
- **Cross-Reference Validation:** High-confidence claims require corroboration from 2+ sources
- **Threshold:** 80% confidence claims flagged for human review

### IV.C Layer 2: Tool Failure Recovery (Phase 2)

- **Explicit Fallback Chains:** Tool A times out → Tool B → Tool C
- **Timeout Policies:** 10s web search; 30s complex query; escalate if exceeded
- **Graceful Degradation:** Full answer → Partial answer → Insufficient data (escalate)

### IV.D Layer 3: Model Switching (Phase 2)

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
3. **Impact Analysis:** Which phases affected? Agent code changes required?
4. **Vote:** 2/3 majority required for approval
5. **Merged:** Documented in commit message with reference to Articles affected

**Immutable Constraints:**
- Cannot change non-negotiable tech stack without Phase N+1 rearchitecture
- Cannot weaken human-in-the-loop principles in Phase 1–2
- Cannot reduce test coverage thresholds below 80%

### V.B Principle Clarifications

**Definition:** Interpretation of existing Articles (not changes).

**Approval Process:**
1. **PR with clarification text**
2. **Single tech lead approval** (fast-track)
3. **Merged** with "CLARIFICATION" in commit message

### V.C Ratification Schedule

- **Phase 1:** Constitution frozen; no changes except clarifications
- **Phase 2:** Minor amendments allowed (e.g., test coverage threshold increases)
- **Phase 3+:** Annual review with full amendment process

---

## Article VI: Gating Checklist (Planning Phase Gates)

**All planning must reference this constitution.** The `plan-template.md` includes gates:

```markdown
## Constitutional Compliance Checklist

- [ ] **Article I: Tech Stack** – Does this plan use approved frameworks?
  - [ ] Orchestration: Windmill or LangGraph? (approved for this pattern)
  - [ ] Agent: Pydantic AI with @tool decorators?
  - [ ] Memory: PostgreSQL with async access?
  - [ ] Tools: All via MCP?

- [ ] **Article II: Principles** – Respects vertical-slice, pluggable orchestration, human-in-the-loop?
  - [ ] Irreversible actions gated by approval?
  - [ ] Observable: telemetry instrumented?

- [ ] **Article III: Standards** – Meets testing, observability, async requirements?
  - [ ] Tests: 80% coverage target?
  - [ ] Async: All I/O non-blocking?
  - [ ] Instrumentation: OpenTelemetry spans?

If ANY gate fails, escalate to tech lead before proceeding.
```

---

## Article VII: Deferred Decisions (Phase 2+)

**These technology choices remain open for Phase 2+ evaluation and are NOT frozen:**

- **Vector Store Evolution:** Phase 1 uses pgvector; Phase 3 may introduce Pinecone, Weaviate, or other specialized stores
- **Secondary Orchestrator:** AutoGen introduced Phase 2 for parallel evaluation; not locked in yet
- **Multi-Agent Framework:** CrewAI evaluated Phase 3 for role-based teams; not committed yet
- **LLM Provider Lock-In:** Pydantic AI remains model-agnostic; can swap OpenAI ↔ Anthropic ↔ Ollama without code changes
- **Graph Database:** Neo4j considered Phase 3+ for relationship reasoning; deferred if not needed
- **Cache Layer:** Redis introduced Phase 2 as optional optimization; not mandatory Phase 1

**Rationale:** Vertical-slice delivery requires baseline decisions (Articles I–VI). Future phases have option space for optimization and competitive evaluation.

---

## Article VIII: Alignment with Roadmap

### Phase 1 Compliance
✅ Vertical-slice: UI + Workflow + Agent + Memory  
✅ Windmill + LangGraph orchestration  
✅ Pydantic AI agent framework  
✅ PostgreSQL primary memory  
✅ MCP tool integration  
✅ Open WebUI chat interface  
✅ Human-in-the-loop escalation (Article II.C)  
✅ Observable everything (Article II.D)  
✅ 80% test coverage (Article III.A)  

### Phase 2 Compatibility
✅ AutoGen added as *parallel* orchestrator; doesn't replace Windmill  
✅ Agent Factory patterns (shared agent definitions)  
✅ Multi-framework evaluation (framework-per-pattern strategy)  
✅ Failure detection (Article IV)  

### Phase 3+ Flexibility
✅ LlamaIndex for multi-storage memory  
✅ CrewAI for role-based teams (as Windmill workflow nodes)  
✅ Graph database optional upgrade  
✅ Semantic routing rules (Article II.E)  

### No Contradictions
- Constitution does NOT override roadmap phases
- Constitution establishes *floor*, not ceiling (roadmap can exceed baseline)
- Roadmap deferred decisions remain deferred (Article VII); constitution doesn't freeze them

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

---

## Appendix B: Quick Reference – Article to Phase Mapping

| Article | Phase 1 | Phase 2 | Phase 3+ |
|---------|--------|--------|---------|
| **Tech Stack** | Frozen ✓ | Frozen ✓ | Frozen ✓ |
| **Principles** | Frozen ✓ | Frozen ✓ | Frozen ✓ |
| **Operational Std** | Frozen ✓ | Tighter | Tighter |
| **Failure Detection** | Basic | Enhanced | Advanced |
| **Deferred Decisions** | Baseline locked | Some open | Evaluate Phase 3+ |
| **Amendment** | Clarifications only | Minor amendments | Full process |

---

## Appendix C: Technology Rationale Summary

**Why These Choices Over Alternatives:**

| Decision | Alternative | Why We Chose | Difference |
|----------|-------------|--------------|-----------|
| **Pydantic AI over LangChain** | LangChain | Type-safe, minimal boilerplate, MCP-native, FastAPI-style DX | LangChain: sprawling integrations, heavier abstraction; we defer to Phase 3 |
| **LangGraph over AutoGen (Phase 1)** | AutoGen | Fine-grained state control, OpenAI-compatible tool-calling, streaming | AutoGen: best for conversational multi-agent; reserved Phase 2 |
| **Windmill over Airflow** | Airflow | 13x faster execution, visual UI + code-backed, built-in observability, resource isolation | Airflow: optimized for batch; overkill for Phase 1 agent tasks |
| **PostgreSQL + pgvector over Pinecone** | Pinecone | Single source of truth, no vendor lock-in, hybrid search (semantic + SQL), lower cost Phase 1 | Pinecone: specialized; evaluate Phase 3 if scale justifies separate store |
| **Open WebUI over LibreChat** | LibreChat | Pipeline-based flexibility, native Ollama support, simpler setup Phase 1 | LibreChat: stronger auth/multi-provider; revisit Phase 2 for enterprise needs |
| **Claude 3.5 Sonnet over GPT-4** | GPT-4 | Better reasoning on agent tasks, longer context, cost-effective at scale | GPT-4: maximize code quality; use for specialized Phase 2 benchmark |
| **Python 3.11+ over TypeScript** | TypeScript | Agent frameworks are Python-native; asyncio ecosystem mature; no Node.js async story for pgvector | TypeScript: consider Phase 2 if UI complexity justifies separate backend |

---

**Frozen for Phase 1: December 20, 2025**  
**Next Review: End of Phase 1 Development**
