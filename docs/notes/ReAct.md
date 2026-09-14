We are not using formal ReAct architecture across the project.

  Current implementation is mostly deterministic orchestration:

  Classify → Route model → Retrieve evidence → Generate → Validate → Create artifacts

  The application—not the LLM—selects and sequences tools. This is intentional for auditability and safety, as documented in docs/20-day-3-build-record.md:121.

  The coding workflow is ReAct-like, however:

  Model proposes patch (Reason)
          ↓
  Apply patch (Action)
          ↓
  Compile/test in sandbox (Observation)
          ↓
  Failure returned to model
          ↓
  Model proposes corrected patch

  That repair loop is implemented in backend/app/tasks/runtime.py:410.

  The distinction:

  - Formal ReAct: LLM repeatedly selects actions/tools based on observations.
  - Our system: code controls the workflow and allowed tools; the LLM generates an answer or patch inside that controlled sequence.
  - Chain-of-thought is not stored or displayed.
  - Only bounded action summaries, tool results, evidence and audit events are recorded.

  Therefore, the accurate description is:

  > A deterministic governed agent runtime with a ReAct-like action–observation repair loop for coding tasks.

  We should not claim the entire product implements ReAct unless we later add structured model-selected Thought/Action/Observation iterations through the policy-controlled tool registry.



###


   Concept             Meaning
  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ReAct               A reasoning pattern where the LLM repeatedly decides an action, observes its result, and decides what to do next
  ──────────────────  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   Loop engineering    The broader engineering of the entire agent loop, including limits, validation, retries, state, security and termination

  ReAct describes the model’s decision cycle:

  Reason → Choose action → Execute tool → Observe result → Repeat

  Loop engineering wraps that cycle with production controls:

  Load state
  → Classify and route
  → Build bounded context
  → Ask model for structured action
  → Validate action
  → Check authorization
  → Execute tool
  → Sanitize and persist observation
  → Check timeout, cancellation and step limit
  → Continue, retry, request approval or finish

  A system can have an agent loop without using ReAct. That is largely how our project works:

  - The application determines the sequence.
  - Tools are executed deterministically.
  - The model generates responses or patches.
  - Coding retries use test failures as subsequent observations.

  This is a deterministic engineered loop with some ReAct-like behavior.

  A formal ReAct implementation would let the model select the next permitted action after each observation. Loop engineering would still control what the model is allowed to select.

  For this project, the safest architecture is:

  Engineered loop
  └── Constrained ReAct decision cycle
      ├── Structured actions only
      ├── Policy-authorized tools only
      ├── Maximum steps and retries
      ├── Sanitized observations
      └── Explicit finish or human-review action

  In short: ReAct is one reasoning strategy inside an agent loop; loop engineering is everything required to make that loop safe, reliable and production-ready.
####

Using both would make the product more adaptive while retaining its current safety guarantees.

  ReAct would improve the agent’s decisions. Loop engineering would ensure those decisions remain bounded, observable and recoverable.

  ### Improvements by workflow

   Workflow               ReAct improvement                                           Loop-engineering control
  ━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Coding                 Inspect files, patch, test, interpret failure and repair    Sandbox, immutable tests, rollback, retry and step limits
  ─────────────────────  ──────────────────────────────────────────────────────────  ──────────────────────────────────────────────────────────────────────
   Document analysis      Search again when evidence is insufficient                  Citation requirements, evidence budgets and deterministic validation
  ─────────────────────  ──────────────────────────────────────────────────────────  ──────────────────────────────────────────────────────────────────────
   Knowledge retrieval    Reformulate weak queries and inspect the best sources       Workspace isolation, retrieval limits and source authorization
  ─────────────────────  ──────────────────────────────────────────────────────────  ──────────────────────────────────────────────────────────────────────
   Multimodal             Use vision only when OCR or parsing is uncertain            Page limits, confidence thresholds and human-review escalation
  ─────────────────────  ──────────────────────────────────────────────────────────  ──────────────────────────────────────────────────────────────────────
   Procurement            Investigate missing quotation information                   Keep totals, compliance rules and vendor ranking deterministic
  ─────────────────────  ──────────────────────────────────────────────────────────  ──────────────────────────────────────────────────────────────────────
   Artifact generation    Correct validation failures                                 Atomic publication, checksums and bounded retries

  ### 1. Better coding repairs

  The existing coding workflow already has the foundation:

  Read repository
  → Run tests
  → Generate patch
  → Apply patch
  → Test
  → Retry

  A constrained ReAct cycle could let the model choose among:

  { "action": "read_file", "path": "src/service.py" }
  { "action": "search_repository", "query": "calculate_total" }
  { "action": "apply_patch", "patch": "..." }
  { "action": "run_tests", "command": "pytest" }
  { "action": "finish", "summary": "..." }

  This would avoid always sending a large repository snapshot and let the coder inspect only relevant files.

  Expected benefits:

  - Smaller prompts
  - Better navigation of larger repositories
  - More targeted patches
  - Improved recovery from failed tests
  - Fewer unnecessary file modifications

  ### 2. Adaptive document retrieval

  The current flow retrieves evidence once and generates an answer. With ReAct:

  Search “pump isolation”
  → Observe weak results
  → Search “lockout valve V-14”
  → Read the best document section
  → Determine evidence is sufficient
  → Generate cited response

  This can improve:

  - Recall across differently worded documents
  - Answers to multi-part questions
  - Handling of missing evidence
  - Citation quality
  - Recognition that human review is required

  The engineered loop would limit search iterations, total evidence characters and model tokens.

  ### 3. Selective multimodal processing

  Instead of invoking vision broadly:

  Parse document
  → Detect unreadable table
  → Run OCR
  → Observe low confidence
  → Inspect only that page with vision
  → Compare extracted values

  Benefits:

  - Lower latency
  - Less memory usage
  - Fewer vision-model loads
  - Better extraction from scanned quotations
  - Clear uncertainty reporting

  ### 4. More reliable task recovery

  Loop engineering would persist every transition:

  PLANNING
  → ACTION_SELECTED
  → ACTION_AUTHORIZED
  → TOOL_RUNNING
  → OBSERVATION_RECORDED
  → NEXT_ACTION

  After a restart, the worker could resume from the last safe transition instead of restarting the entire workflow.

  This requires:

  - Idempotent actions
  - Worker leases and heartbeats
  - Version checks
  - Retry classification
  - Checkpoints
  - Duplicate-artifact prevention

  ### 5. Human approval inside the loop

  The model could produce a structured action:

  {
    "action": "request_human_review",
    "reason_summary": "The quotation total conflicts with the source document.",
    "required_decision": "Confirm whether tax is included."
  }

  The workflow enters waiting_approval, releases worker capacity and continues after approval.

  This is particularly useful for:

  - Safety recommendations
  - Ambiguous procurement evidence
  - Destructive code changes
  - Missing policy documents
  - Low-confidence visual extraction

  ### 6. Better observability

  The trace could show:

  Action 1: Search knowledge
  Reason: Initial evidence did not cover isolation verification
  Observation: 4 relevant passages found

  Action 2: Read page 12
  Reason: Highest-ranked passage references the required control
  Observation: Lockout and sign-off requirements confirmed

  Action 3: Finish
  Reason: Evidence threshold satisfied

  This provides explainability without exposing private chain-of-thought.

  ### What should remain deterministic

  Do not give ReAct control over:

  - Authentication or authorization
  - Model-registry permissions
  - Model routing eligibility
  - Queue scheduling
  - Workspace boundaries
  - Procurement arithmetic
  - Compliance calculations
  - Sandbox security
  - Artifact validation
  - Checksums or audit records

  The model may request actions, but application code must authorize and execute them.

  ### Recommended implementation order

  1. Formalize the existing coding repair cycle with structured actions.
  2. Add adaptive search/read actions to document workflows.
  3. Add waiting_approval and resumable checkpoints.
  4. Introduce selective OCR/vision actions.
  5. Add worker leases and action-level recovery.
  6. Measure success before expanding the action set.

  Track:

  - Task completion rate
  - Coding test-pass rate
  - Average actions per workflow
  - Retry rate
  - Prompt and completion tokens
  - Retrieval citation quality
  - Human-escalation rate
  - End-to-end latency

  The main gain would be quality and adaptability, not raw speed. ReAct can increase latency because it makes multiple model calls. Loop engineering keeps that additional work controlled and
  ensures it produces a measurable improvement.

