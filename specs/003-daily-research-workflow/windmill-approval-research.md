# Research: Windmill Approval System for Human-in-the-Loop Workflows

**Feature**: 003-daily-research-workflow
**Date**: 2025-12-24
**Purpose**: Document Windmill native approval patterns for implementing human-in-the-loop gates with timeout handling

## Research Questions

### RQ-001: Windmill Approval Gates - Core Mechanism

**Question**: How does Windmill implement approval gates in Python workflows?

**Decision**: Use `wmill.suspend()` to pause workflow execution and create approval requests

**Rationale**:
- Windmill provides native suspend/resume functionality via the `wmill` Python client library
- When a workflow calls `wmill.suspend()`, it:
  1. Pauses execution at that point
  2. Creates a "suspended flow" entry in Windmill's database
  3. Returns a resume URL/token that can be used to continue execution
  4. Preserves all workflow state (variables, context) during suspension
- Pattern for basic approval gate:
  ```python
  import wmill
  from typing import Optional

  def approval_gate(
      action_description: str,
      action_payload: dict,
      timeout_seconds: int = 300  # 5 minutes
  ) -> dict:
      """
      Pause workflow and request human approval.

      Returns approval response after human interaction or timeout.
      """
      # Create approval request payload
      approval_request = {
          "action": action_description,
          "payload": action_payload,
          "requested_at": wmill.get_current_timestamp(),
          "timeout_seconds": timeout_seconds
      }

      # Suspend workflow execution
      # This creates a resume endpoint and pauses the flow
      resume_urls = wmill.suspend(
          approval_request,
          timeout=timeout_seconds,
          required_events=1  # Resume when 1 approval event received
      )

      # Execution pauses here until:
      # 1. Human approves/rejects via resume_urls["approvalPage"]
      # 2. Programmatic resume via API
      # 3. Timeout expires

      # When resumed, check the resume payload
      resume_payload = wmill.get_resume_urls()

      return {
          "approved": resume_payload.get("approved", False),
          "resumed_at": wmill.get_current_timestamp(),
          "comment": resume_payload.get("comment", ""),
          "timed_out": resume_payload.get("timed_out", False)
      }
  ```

**Key Windmill Functions**:
- `wmill.suspend(payload, timeout, required_events)`: Pauses flow, returns resume URLs
- `wmill.get_resume_urls()`: Retrieves resume payload after workflow resumes
- `wmill.get_current_timestamp()`: Gets server timestamp for audit trail

**Alternatives Considered**:
- Custom webhook + sleep loop: Rejected because Windmill's native suspend is more reliable
- External approval service: Rejected because adds complexity and latency

**References**:
- Windmill Python client: https://github.com/windmill-labs/windmill/tree/main/python-client
- Flow suspend/resume docs: https://www.windmill.dev/docs/flows/flow_branches#suspend-and-resume

---

### RQ-002: Timeout Handling Pattern (5-Minute Timeout)

**Question**: How to handle approval timeout and escalation when 5 minutes elapse without response?

**Decision**: Use `wmill.suspend()` timeout parameter + post-resume timeout detection

**Rationale**:
- Windmill's `suspend()` function accepts a `timeout` parameter (in seconds)
- After timeout expires, the workflow automatically resumes with a timeout indicator
- Implementation pattern:
  ```python
  import wmill
  from datetime import datetime, timedelta
  from typing import Literal

  ActionDecision = Literal["approved", "rejected", "escalated"]

  def approval_gate_with_timeout(
      action_type: str,
      action_description: str,
      action_payload: dict,
      timeout_minutes: int = 5
  ) -> tuple[ActionDecision, dict]:
      """
      Request approval with 5-minute timeout and escalation handling.

      Returns:
          (decision, metadata) where decision is "approved" | "rejected" | "escalated"
      """
      timeout_seconds = timeout_minutes * 60
      requested_at = datetime.utcnow()

      # Prepare approval UI payload
      approval_ui = {
          "action_type": action_type,
          "description": action_description,
          "payload": action_payload,
          "requested_at": requested_at.isoformat(),
          "timeout_at": (requested_at + timedelta(seconds=timeout_seconds)).isoformat(),
          "workflow_id": wmill.get_workflow_id(),
          "step_id": wmill.get_step_id()
      }

      # Suspend workflow with timeout
      resume_urls = wmill.suspend(
          approval_ui,
          timeout=timeout_seconds,
          required_events=1
      )

      # Log suspension details for audit trail
      print(f"[APPROVAL] Workflow suspended. Approval page: {resume_urls.get('approvalPage')}")
      print(f"[APPROVAL] Will auto-resume at: {approval_ui['timeout_at']}")

      # ===== EXECUTION PAUSES HERE UNTIL RESUME OR TIMEOUT =====

      # Resumed - check how we were resumed
      resume_payload = wmill.get_resume_urls()
      resumed_at = datetime.utcnow()

      # Detect timeout vs explicit approval/rejection
      timed_out = resume_payload.get("timed_out", False)
      approved = resume_payload.get("approved", False)

      if timed_out:
          # Timeout escalation path
          decision = "escalated"
          metadata = {
              "reason": "approval_timeout",
              "timeout_minutes": timeout_minutes,
              "requested_at": requested_at.isoformat(),
              "timed_out_at": resumed_at.isoformat(),
              "escalation_action": "skip_and_notify",  # Per spec FR-007
              "notification_sent": True  # Would trigger admin notification
          }

          # Log escalation
          print(f"[ESCALATION] Approval timed out after {timeout_minutes} minutes")
          print(f"[ESCALATION] Action '{action_type}' skipped and logged")

      elif approved:
          # Explicit approval
          decision = "approved"
          metadata = {
              "approved_at": resumed_at.isoformat(),
              "approved_by": resume_payload.get("user_id", "unknown"),
              "comment": resume_payload.get("comment", ""),
              "duration_seconds": (resumed_at - requested_at).total_seconds()
          }
          print(f"[APPROVAL] Action approved by {metadata['approved_by']}")

      else:
          # Explicit rejection
          decision = "rejected"
          metadata = {
              "rejected_at": resumed_at.isoformat(),
              "rejected_by": resume_payload.get("user_id", "unknown"),
              "comment": resume_payload.get("comment", ""),
              "duration_seconds": (resumed_at - requested_at).total_seconds()
          }
          print(f"[APPROVAL] Action rejected by {metadata['rejected_by']}")

      return decision, metadata
  ```

**Timeout Behavior**:
- Windmill automatically resumes the flow after `timeout` seconds
- Resume payload includes `timed_out: true` flag
- No explicit approval/rejection from user
- Workflow must implement escalation logic (log, skip, notify)

**Escalation Strategy** (per spec FR-007):
1. Log the timeout event with full context
2. Skip the blocked action (don't execute)
3. Send notification to admin/operator
4. Continue workflow with remaining steps
5. Mark run as "partially completed" if critical action was skipped

**Alternatives Considered**:
- Blocking wait indefinitely: Rejected per constitutional requirement for 5-minute timeout
- Retry approval request: Rejected because could create infinite loops
- Auto-approve on timeout: Rejected because violates safety principle

**References**:
- Spec FR-007: Timeout approval requests after 5 minutes and escalate
- Spec SC-005: Approval timeout escalation at 5-minute mark (tolerance: +/- 10 seconds)
- Constitution Article II.C: Human-in-the-Loop by Default

---

### RQ-003: Programmatic Resume via Windmill API

**Question**: How to programmatically approve/reject suspended workflows via API (for testing and automation)?

**Decision**: Use Windmill REST API `/api/w/{workspace}/jobs/resume/{job_id}` endpoint

**Rationale**:
- Windmill exposes REST API for resuming suspended flows
- Enables programmatic approval for:
  - Automated testing (approve/reject in tests)
  - Admin override (force approval/rejection)
  - Integration with external approval systems (Slack, email)
- Implementation pattern:
  ```python
  import httpx
  import os
  from typing import Literal

  class WindmillApprovalClient:
      """Client for programmatic approval handling via Windmill API."""

      def __init__(self, base_url: str = None, token: str = None):
          self.base_url = base_url or os.getenv("WINDMILL_BASE_URL", "http://localhost:8000")
          self.token = token or os.getenv("WINDMILL_TOKEN")
          self.workspace = os.getenv("WINDMILL_WORKSPACE", "default")

      async def resume_flow(
          self,
          job_id: str,
          approved: bool,
          comment: str = "",
          user_id: str = "api_client"
      ) -> dict:
          """
          Programmatically resume a suspended flow with approval decision.

          Args:
              job_id: The suspended job/flow ID
              approved: True to approve, False to reject
              comment: Optional comment for audit trail
              user_id: Identity of approver (for logging)

          Returns:
              API response with resume status
          """
          url = f"{self.base_url}/api/w/{self.workspace}/jobs/resume/{job_id}"

          payload = {
              "approved": approved,
              "comment": comment,
              "user_id": user_id,
              "timed_out": False  # Explicitly not a timeout
          }

          headers = {
              "Authorization": f"Bearer {self.token}",
              "Content-Type": "application/json"
          }

          async with httpx.AsyncClient() as client:
              response = await client.post(url, json=payload, headers=headers)
              response.raise_for_status()
              return response.json()

      async def get_pending_approvals(self) -> list[dict]:
          """
          List all suspended flows awaiting approval in the workspace.

          Returns:
              List of suspended job metadata
          """
          url = f"{self.base_url}/api/w/{self.workspace}/jobs/queue/suspended"

          headers = {"Authorization": f"Bearer {self.token}"}

          async with httpx.AsyncClient() as client:
              response = await client.get(url, headers=headers)
              response.raise_for_status()
              return response.json()
  ```

**Usage Example - Testing**:
  ```python
  import pytest
  from tests.fixtures.windmill_client import WindmillApprovalClient

  @pytest.mark.asyncio
  async def test_approval_gate_timeout():
      """Test that approval gate handles timeout correctly."""
      client = WindmillApprovalClient()

      # Trigger workflow that has approval gate
      job_id = await trigger_research_workflow(topic="test")

      # Wait for suspension
      await asyncio.sleep(2)

      # Verify workflow is suspended
      pending = await client.get_pending_approvals()
      assert any(job["id"] == job_id for job in pending)

      # Don't approve - let it timeout (wait 5+ minutes in real test)
      # For faster test, use mock time or shorter timeout
      await asyncio.sleep(310)  # 5 min 10 sec

      # Check workflow resumed with escalation
      job_status = await client.get_job_status(job_id)
      assert job_status["completed"] is True
      assert "escalated" in job_status["logs"]

  @pytest.mark.asyncio
  async def test_approval_gate_approved():
      """Test that approval gate resumes on approval."""
      client = WindmillApprovalClient()

      # Trigger workflow
      job_id = await trigger_research_workflow(topic="test")

      # Wait for suspension
      await asyncio.sleep(2)

      # Programmatically approve
      await client.resume_flow(
          job_id=job_id,
          approved=True,
          comment="Auto-approved by test suite"
      )

      # Wait for completion
      await asyncio.sleep(5)

      # Verify workflow completed successfully
      job_status = await client.get_job_status(job_id)
      assert job_status["completed"] is True
      assert "approved" in job_status["logs"]
  ```

**API Endpoints**:
- `POST /api/w/{workspace}/jobs/resume/{job_id}`: Resume suspended flow
- `GET /api/w/{workspace}/jobs/queue/suspended`: List suspended flows
- `GET /api/w/{workspace}/jobs/get/{job_id}`: Get job status/logs

**Authentication**:
- Requires Windmill API token (user or service account)
- Token passed via `Authorization: Bearer {token}` header
- Token must have `jobs:write` permission for resume endpoint

**Alternatives Considered**:
- Windmill CLI: Rejected because API is more programmatic and testable
- Direct database manipulation: Rejected because bypasses Windmill's state management

**References**:
- Windmill API docs: https://www.windmill.dev/docs/core_concepts/jobs
- Job resume endpoint: https://www.windmill.dev/docs/core_concepts/jobs#resuming-jobs

---

### RQ-004: Integration with LLM Agent Workflows (LangGraph + Windmill)

**Question**: How to integrate Windmill approval gates with LangGraph cyclical reasoning workflows?

**Decision**: Embed approval gate check as a Windmill workflow step BEFORE executing risky LangGraph nodes

**Rationale**:
- Windmill orchestrates the overall DAG (linear flow)
- LangGraph runs within Windmill steps (cyclical reasoning)
- Approval gates are Windmill-level concerns (not LangGraph-level)
- Architecture pattern:
  ```
  Windmill Workflow:
  ┌─────────────────────────────────────────────────────────────┐
  │ Step 1: Validate Input                                      │
  │ Step 2: Run LangGraph Research Loop (Plan→Research→Critique)│
  │ Step 3: Format Report                                       │
  │ Step 4: Approval Gate (if report triggers risky action)    │ ← SUSPEND HERE
  │ Step 5: Execute Approved Action (e.g., send email)         │
  │ Step 6: Store to Memory                                     │
  └─────────────────────────────────────────────────────────────┘
  ```

- Implementation pattern:
  ```python
  # File: src/windmill/daily_research.py
  # Main Windmill workflow script

  import wmill
  from src.workflows.research_graph import run_research_graph
  from src.workflows.report_formatter import format_markdown_report
  from src.core.risk_assessment import categorize_action_risk, RiskLevel
  from src.windmill.approval_handler import approval_gate_with_timeout

  def main(topic: str, user_id: str):
      """
      Main Windmill workflow for DailyTrendingResearch.

      This is executed as a Windmill Python script.
      Each phase can suspend/resume independently.
      """

      # ========== STEP 1: Validate Input ==========
      if not topic or len(topic) > 500:
          raise ValueError("Invalid topic: must be 1-500 characters")

      print(f"[WORKFLOW] Starting research for topic: {topic}")

      # ========== STEP 2: Run LangGraph Research Loop ==========
      # This is embedded execution - LangGraph runs in-process
      research_result = run_research_graph(
          topic=topic,
          max_iterations=5,
          user_id=user_id
      )

      print(f"[WORKFLOW] Research completed after {research_result['iterations']} iterations")

      # ========== STEP 3: Format Report ==========
      report = format_markdown_report(
          findings=research_result["findings"],
          sources=research_result["sources"],
          metadata={"topic": topic, "user_id": user_id}
      )

      # ========== STEP 4: Risk Assessment & Approval Gate ==========
      # Check if the research triggered any risky actions
      # (e.g., "send summary email", "post to social media")

      planned_actions = research_result.get("planned_actions", [])

      for action in planned_actions:
          risk_level = categorize_action_risk(
              action["type"],
              action["parameters"]
          )

          if risk_level in [RiskLevel.REVERSIBLE_WITH_DELAY, RiskLevel.IRREVERSIBLE]:
              # Requires approval - suspend workflow
              print(f"[APPROVAL] Action '{action['type']}' requires approval (risk: {risk_level})")

              decision, metadata = approval_gate_with_timeout(
                  action_type=action["type"],
                  action_description=action["description"],
                  action_payload=action["parameters"],
                  timeout_minutes=5
              )

              if decision == "approved":
                  # Execute the action
                  print(f"[ACTION] Executing approved action: {action['type']}")
                  execute_action(action)

              elif decision == "escalated":
                  # Timeout - skip and log
                  print(f"[ESCALATION] Skipping action due to timeout: {action['type']}")
                  log_escalation(action, metadata)
                  send_admin_notification(action, metadata)

              else:  # rejected
                  print(f"[APPROVAL] Action rejected: {action['type']}")
                  log_rejection(action, metadata)

      # ========== STEP 5: Store to Memory ==========
      from src.core.memory import MemoryManager

      memory = MemoryManager()
      doc_id = memory.store_document(
          content=report,
          metadata={
              "type": "research_report",
              "topic": topic,
              "user_id": user_id,
              "sources": research_result["sources"],
              "iterations": research_result["iterations"]
          }
      )

      print(f"[WORKFLOW] Report stored with ID: {doc_id}")

      # ========== Return Final Result ==========
      return {
          "report": report,
          "doc_id": doc_id,
          "iterations": research_result["iterations"],
          "sources_count": len(research_result["sources"]),
          "actions_approved": sum(1 for a in planned_actions if a.get("decision") == "approved"),
          "actions_escalated": sum(1 for a in planned_actions if a.get("decision") == "escalated")
      }
  ```

**Key Design Decisions**:
1. **LangGraph is embedded** - Runs in-process within Windmill step, NOT as separate microservice
2. **Approval gates are Windmill steps** - Uses native `wmill.suspend()`, not LangGraph state nodes
3. **Risk assessment happens after research** - LangGraph completes Plan→Research→Critique cycles, then Windmill checks if output triggers risky actions
4. **One approval per risky action** - If research suggests 3 risky actions, get 3 separate approvals (or batch into one UI)

**LangGraph State Bridge**:
  ```python
  # File: src/workflows/research_graph.py

  from langgraph.graph import StateGraph, END
  from src.models.research_state import ResearchState

  def run_research_graph(topic: str, max_iterations: int, user_id: str) -> dict:
      """
      Execute LangGraph research loop - embedded in Windmill workflow.

      This function is called FROM Windmill, runs LangGraph, returns result.
      NO suspension happens inside LangGraph - that's Windmill's job.
      """

      # Define LangGraph nodes
      workflow = StateGraph(ResearchState)

      workflow.add_node("plan", plan_node)
      workflow.add_node("research", research_node)
      workflow.add_node("critique", critique_node)
      workflow.add_node("refine", refine_node)
      workflow.add_node("finish", finish_node)

      # Define edges with conditional routing
      workflow.set_entry_point("plan")
      workflow.add_edge("plan", "research")
      workflow.add_edge("research", "critique")
      workflow.add_conditional_edges(
          "critique",
          should_continue,
          {
              "refine": "refine",
              "finish": "finish"
          }
      )
      workflow.add_edge("refine", "research")  # Loop back
      workflow.add_edge("finish", END)

      # Compile and run
      app = workflow.compile()

      initial_state = ResearchState(
          topic=topic,
          user_id=user_id,
          iteration_count=0,
          max_iterations=max_iterations
      )

      # Execute graph (synchronous in this context)
      final_state = app.invoke(initial_state)

      # Return serializable result for Windmill
      return {
          "findings": final_state.refined_answer,
          "sources": final_state.sources,
          "iterations": final_state.iteration_count,
          "planned_actions": final_state.planned_actions  # Actions that might need approval
      }
  ```

**Separation of Concerns**:
- **LangGraph**: Handles cyclical reasoning (Plan → Research → Critique → Refine)
- **Windmill**: Handles orchestration, approval gates, timeout management, storage
- **Pydantic AI (ResearcherAgent)**: Atomic agent execution within LangGraph nodes

**Alternatives Considered**:
- Approval gates as LangGraph nodes: Rejected because LangGraph can't natively suspend/resume flows
- External approval service: Rejected because Windmill native approval is simpler
- Blocking wait in LangGraph: Rejected because breaks Windmill's job isolation

**References**:
- LangGraph in Windmill: https://www.windmill.dev/docs/integrations/langgraph
- Spec FR-002: LangGraph as embedded library within Windmill workflow steps
- Spec FR-006: Pause workflow execution for REVERSIBLE_WITH_DELAY actions

---

### RQ-005: Approval UI and User Experience

**Question**: What UI does Windmill provide for approval interactions, and how can we customize it?

**Decision**: Use Windmill's auto-generated approval page with custom payload rendering

**Rationale**:
- When `wmill.suspend()` is called, Windmill automatically generates:
  1. **Approval Page URL**: `{windmill_url}/approve/{job_id}/{token}`
  2. **Resume API Endpoint**: `/api/w/{workspace}/jobs/resume/{job_id}`
- The approval page displays:
  - The `payload` passed to `wmill.suspend()` (rendered as JSON or custom HTML)
  - Approve/Reject buttons
  - Optional comment field
  - Timeout countdown timer
- Customization via payload structure:
  ```python
  def create_approval_ui_payload(action: dict) -> dict:
      """
      Create rich approval UI payload for Windmill.

      Windmill renders this payload on the approval page.
      Use structured data for better UX.
      """
      return {
          # Core approval metadata
          "approval_type": "action_review",
          "action_type": action["type"],
          "risk_level": action["risk_level"],

          # Human-readable description
          "title": f"Approve {action['type']}?",
          "description": action["description"],

          # Action details (rendered as table/JSON)
          "action_details": {
              "parameters": action["parameters"],
              "estimated_impact": action.get("impact", "unknown"),
              "reversibility": action["risk_level"]
          },

          # Context for decision-making
          "context": {
              "workflow_id": wmill.get_workflow_id(),
              "requested_by": action.get("user_id", "system"),
              "requested_at": datetime.utcnow().isoformat(),
              "timeout_minutes": 5
          },

          # Links for more info
          "references": [
              {"label": "Research Report", "url": action.get("report_url", "#")},
              {"label": "Workflow Logs", "url": f"/runs/{wmill.get_workflow_id()}"}
          ]
      }
  ```

**Approval Page Features**:
- Auto-generated URL is shareable (can send via email/Slack)
- Token-based authentication (no login required for approval)
- Timeout countdown shown to user
- Mobile-responsive design
- Approval decision logged in Windmill audit trail

**Custom HTML Rendering** (Optional):
  ```python
  # For richer UI, pass HTML in payload
  approval_payload = {
      "html_content": f"""
      <div class="approval-request">
          <h2>Research Action Approval Required</h2>
          <p><strong>Action:</strong> {action['type']}</p>
          <p><strong>Description:</strong> {action['description']}</p>
          <p><strong>Risk Level:</strong> {action['risk_level']}</p>

          <h3>Parameters:</h3>
          <pre>{json.dumps(action['parameters'], indent=2)}</pre>

          <h3>Context:</h3>
          <ul>
              <li>Topic: {topic}</li>
              <li>Sources: {len(sources)}</li>
              <li>Iterations: {iterations}</li>
          </ul>

          <p><em>This approval will timeout in 5 minutes.</em></p>
      </div>
      """,
      "raw_data": action  # Fallback for API clients
  }
  ```

**Notification Integration** (External):
  ```python
  async def send_approval_notification(
      approval_url: str,
      action: dict,
      notification_channels: list[str]
  ):
      """
      Send approval request to external channels.

      Call this immediately after wmill.suspend() to notify approvers.
      """
      message = f"""
      🔔 Approval Required

      Action: {action['type']}
      Description: {action['description']}
      Risk Level: {action['risk_level']}

      Approve/Reject: {approval_url}

      ⏰ Timeout: 5 minutes
      """

      if "slack" in notification_channels:
          await send_slack_message(channel="#approvals", text=message)

      if "email" in notification_channels:
          await send_email(
              to=action.get("approver_email", "admin@example.com"),
              subject="Approval Required: " + action['type'],
              body=message
          )
  ```

**Alternatives Considered**:
- Custom approval UI service: Rejected because Windmill's built-in UI is sufficient for Phase 1
- Slack-native approval: Deferred to Phase 2 (can integrate via notification pattern above)

**References**:
- Windmill approval page: https://www.windmill.dev/docs/flows/flow_approval
- Custom UI rendering: Windmill supports HTML in suspend payload

---

### RQ-006: Testing Strategy for Approval Gates

**Question**: How to test approval gates in unit and integration tests without waiting 5 minutes?

**Decision**: Use mock time, shorter timeouts in tests, and Windmill API for programmatic approval

**Rationale**:
- Three testing approaches:
  1. **Unit tests** - Mock `wmill.suspend()` to simulate immediate resume
  2. **Integration tests (fast)** - Use 5-second timeout instead of 5 minutes
  3. **Integration tests (realistic)** - Use programmatic API approval (no wait)

**Unit Test Pattern** (Fast):
  ```python
  # File: tests/unit/test_approval_handler.py

  import pytest
  from unittest.mock import patch, MagicMock
  from src.windmill.approval_handler import approval_gate_with_timeout

  @pytest.mark.asyncio
  async def test_approval_gate_approved():
      """Test approval gate with mocked approval."""

      with patch("wmill.suspend") as mock_suspend, \
           patch("wmill.get_resume_urls") as mock_resume:

          # Mock Windmill functions
          mock_suspend.return_value = {
              "approvalPage": "http://localhost:8000/approve/123/token",
              "resume": "http://localhost:8000/api/resume/123"
          }

          mock_resume.return_value = {
              "approved": True,
              "timed_out": False,
              "user_id": "test_user",
              "comment": "Looks good"
          }

          # Execute approval gate
          decision, metadata = approval_gate_with_timeout(
              action_type="send_email",
              action_description="Send summary to user@example.com",
              action_payload={"to": "user@example.com", "subject": "Research Summary"},
              timeout_minutes=5
          )

          # Verify approval
          assert decision == "approved"
          assert metadata["approved_by"] == "test_user"
          assert metadata["comment"] == "Looks good"

          # Verify Windmill calls
          mock_suspend.assert_called_once()
          assert mock_suspend.call_args[1]["timeout"] == 300  # 5 minutes

  @pytest.mark.asyncio
  async def test_approval_gate_timeout():
      """Test approval gate with mocked timeout."""

      with patch("wmill.suspend") as mock_suspend, \
           patch("wmill.get_resume_urls") as mock_resume:

          # Mock timeout scenario
          mock_resume.return_value = {
              "approved": False,
              "timed_out": True,
              "user_id": None,
              "comment": ""
          }

          # Execute approval gate
          decision, metadata = approval_gate_with_timeout(
              action_type="send_email",
              action_description="Send summary",
              action_payload={},
              timeout_minutes=5
          )

          # Verify escalation
          assert decision == "escalated"
          assert metadata["reason"] == "approval_timeout"
          assert metadata["escalation_action"] == "skip_and_notify"
  ```

**Integration Test Pattern** (Programmatic Approval):
  ```python
  # File: tests/integration/test_approval_gates.py

  import pytest
  import asyncio
  from tests.fixtures.windmill_client import WindmillApprovalClient, trigger_workflow

  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_approval_gate_e2e_approved():
      """
      End-to-end test: Workflow suspends, API approves, workflow resumes.

      No waiting - programmatic approval via API.
      """
      client = WindmillApprovalClient()

      # Trigger research workflow with risky action
      job_id = await trigger_workflow(
          script="daily_research",
          args={
              "topic": "test approval gate",
              "user_id": "test_user",
              "planned_actions": [
                  {
                      "type": "send_email",
                      "description": "Send summary email",
                      "parameters": {"to": "test@example.com"},
                      "risk_level": "REVERSIBLE_WITH_DELAY"
                  }
              ]
          }
      )

      # Wait for workflow to suspend (should be ~2 seconds)
      await asyncio.sleep(3)

      # Verify workflow is suspended
      pending = await client.get_pending_approvals()
      assert any(job["id"] == job_id for job in pending), "Workflow should be suspended"

      # Programmatically approve
      await client.resume_flow(
          job_id=job_id,
          approved=True,
          comment="Auto-approved by integration test",
          user_id="test_bot"
      )

      # Wait for workflow to complete
      await asyncio.sleep(5)

      # Verify workflow completed successfully
      job = await client.get_job_status(job_id)
      assert job["completed"] is True
      assert "approved" in job["result"]["logs"].lower()
      assert job["result"]["actions_approved"] == 1

  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_approval_gate_e2e_timeout():
      """
      End-to-end test: Workflow suspends, timeout occurs, workflow escalates.

      Uses SHORT timeout (5 seconds) for fast test.
      """
      client = WindmillApprovalClient()

      # Trigger workflow with SHORT timeout (override for testing)
      job_id = await trigger_workflow(
          script="daily_research",
          args={
              "topic": "test timeout",
              "user_id": "test_user",
              "planned_actions": [
                  {
                      "type": "send_email",
                      "description": "Send summary email",
                      "parameters": {"to": "test@example.com"},
                      "risk_level": "REVERSIBLE_WITH_DELAY"
                  }
              ],
              "approval_timeout_seconds": 5  # SHORT timeout for test
          }
      )

      # Wait for suspension
      await asyncio.sleep(2)

      # Verify suspended
      pending = await client.get_pending_approvals()
      assert any(job["id"] == job_id for job in pending)

      # DO NOT APPROVE - let it timeout
      await asyncio.sleep(7)  # Wait past timeout

      # Verify workflow resumed with escalation
      job = await client.get_job_status(job_id)
      assert job["completed"] is True
      assert "escalated" in job["result"]["logs"].lower()
      assert job["result"]["actions_escalated"] == 1
      assert job["result"]["actions_approved"] == 0
  ```

**Test Configuration**:
  ```python
  # File: tests/conftest.py

  import os
  import pytest

  @pytest.fixture(autouse=True)
  def windmill_test_config():
      """Configure Windmill client for testing."""
      os.environ["WINDMILL_BASE_URL"] = "http://localhost:8000"
      os.environ["WINDMILL_WORKSPACE"] = "test"
      os.environ["WINDMILL_TOKEN"] = "test_token_123"

      # Use shorter timeouts in tests (override in workflow code)
      os.environ["APPROVAL_TIMEOUT_SECONDS"] = "5"  # Fast tests

      yield

      # Cleanup
      del os.environ["APPROVAL_TIMEOUT_SECONDS"]
  ```

**Key Testing Strategies**:
1. **Unit tests**: Mock all Windmill functions, instant execution
2. **Fast integration tests**: Use 5-second timeout instead of 5 minutes
3. **Realistic integration tests**: Use programmatic API approval (no timeout wait)
4. **E2E tests (optional)**: Use full 5-minute timeout in staging environment

**Alternatives Considered**:
- Using sleep(300) in tests: Rejected because too slow
- Fake time library: Rejected because Windmill timeout is server-side
- Skipping integration tests: Rejected because approval is critical functionality

**References**:
- Spec SC-003: Approval gates pause workflow within 2 seconds
- Spec SC-005: Approval timeout at 5-minute mark (tolerance: +/- 10 seconds)

---

## Summary of Decisions

| Research Question | Decision | Impact |
|---|---|---|
| RQ-001: Approval Gate Mechanism | Use `wmill.suspend()` with timeout parameter | Core workflow suspension pattern |
| RQ-002: Timeout Handling | Detect `timed_out` flag in resume payload, log and skip action | Escalation logic implementation |
| RQ-003: Programmatic Resume | Use Windmill REST API `/api/jobs/resume/{job_id}` | Testing and automation support |
| RQ-004: LangGraph Integration | Approval gates at Windmill level, not LangGraph nodes | Architecture separation of concerns |
| RQ-005: Approval UI | Use auto-generated approval page with custom payload | User experience implementation |
| RQ-006: Testing Strategy | Mock + short timeout + programmatic API | Fast and reliable test suite |

## Implementation Checklist

Based on research findings, implement the following for Spec 003:

- [ ] **Core Approval Module** (`src/windmill/approval_handler.py`):
  - [ ] `approval_gate_with_timeout()` function using `wmill.suspend()`
  - [ ] Timeout detection and escalation logic
  - [ ] Approval UI payload formatting
  - [ ] Logging and audit trail for all decisions

- [ ] **Windmill Workflow** (`src/windmill/daily_research.py`):
  - [ ] Risk assessment before action execution
  - [ ] Approval gate integration for REVERSIBLE_WITH_DELAY actions
  - [ ] Escalation handling (log, skip, notify)
  - [ ] Post-approval action execution

- [ ] **API Client** (`tests/fixtures/windmill_client.py`):
  - [ ] `WindmillApprovalClient` class
  - [ ] `resume_flow()` method for programmatic approval
  - [ ] `get_pending_approvals()` method for test verification
  - [ ] `get_job_status()` method for result checking

- [ ] **Tests**:
  - [ ] Unit tests with mocked `wmill.suspend()` (fast)
  - [ ] Integration tests with 5-second timeout (fast)
  - [ ] Integration tests with programmatic API approval (realistic)
  - [ ] E2E test with full 5-minute timeout (optional, staging only)

- [ ] **Configuration**:
  - [ ] Environment variable `APPROVAL_TIMEOUT_SECONDS` (default 300)
  - [ ] Environment variable `WINDMILL_BASE_URL`
  - [ ] Environment variable `WINDMILL_TOKEN` for API access

- [ ] **Documentation**:
  - [ ] Update `quickstart.md` with approval gate setup
  - [ ] Document approval UI customization patterns
  - [ ] Add testing guide for approval workflows

## Open Questions

None. All technical unknowns resolved.

## Next Steps

Proceed to implementation:
1. Create `src/windmill/approval_handler.py` with core approval logic
2. Integrate approval gates into `src/windmill/daily_research.py` workflow
3. Implement `WindmillApprovalClient` for testing
4. Write comprehensive test suite (unit + integration)
5. Update documentation with approval patterns

## References

### Official Documentation
- Windmill Flows: https://www.windmill.dev/docs/flows/flow_branches
- Windmill Jobs API: https://www.windmill.dev/docs/core_concepts/jobs
- Windmill Python Client: https://github.com/windmill-labs/windmill/tree/main/python-client
- LangGraph in Windmill: https://www.windmill.dev/docs/integrations/langgraph

### Project Specifications
- Spec 003 (this feature): `/specs/003-daily-research-workflow/spec.md`
  - FR-006: Pause workflow for REVERSIBLE_WITH_DELAY actions
  - FR-007: 5-minute timeout with escalation
  - SC-003: Approval gate activation within 2 seconds
  - SC-005: Timeout at 5-minute mark (tolerance: +/- 10 seconds)
- Constitution v2.3: `.specify/memory/constitution.md`
  - Article II.C: Human-in-the-Loop by Default
  - Article II.D: Observable Everything (audit trail required)

### Related Research
- Spec 002 Research: `/specs/002-researcher-agent-mcp/research.md`
  - RQ-006: Risk assessment implementation patterns
  - Risk categorization (REVERSIBLE, REVERSIBLE_WITH_DELAY, IRREVERSIBLE)
