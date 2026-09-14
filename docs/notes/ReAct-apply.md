

#####

The best place is inside the Agent Runtime, after task classification/model routing and before final artifact generation.

  Task submitted
        ↓
  Classify and route model
        ↓
  Constrained ReAct loop
    ┌─────────────────────┐
    │ Decide next action  │
    │ Execute safe tool   │
    │ Record observation  │
    │ Continue or finish  │
    └─────────────────────┘
        ↓
  Validate result
        ↓
  Generate artifacts

  ### 1. Coding workflow — highest value

  The coding workflow already behaves like a constrained ReAct loop in backend/app/tasks/runtime.py:410:

  Inspect repository
  → Run baseline tests
  → Propose patch
  → Apply patch
  → Observe test output
  → Repair patch if necessary

  We could formalize this as structured actions:

  {
    "action": "apply_patch",
    "arguments": {
      "patch": "..."
    },
    "reason_summary": "The failure originates in the division guard."
  }

  Possible actions:

  - read_repository
  - apply_patch
  - run_python_tests
  - finish
  - request_human_review

  This is the safest and most useful initial ReAct implementation because the actions already have deterministic validation and sandbox boundaries.

  ### 2. Document and knowledge workflows

  ReAct would improve tasks where the first retrieval does not provide enough evidence.

  Search knowledge base
  → Observe weak or incomplete results
  → Reformulate query
  → Search again
  → Read the relevant document
  → Produce cited answer

  Useful actions:

  - search_knowledge
  - read_file
  - analyze_visual_pages
  - finish
  - request_human_review

  The existing document flow currently gathers evidence once and then calls the model in backend/app/tasks/runtime.py:790. A constrained loop could replace that single retrieval-to-generation
  transition.

  ### 3. Automatic workflow mode

  ReAct could help auto mode decide which permitted evidence operation is needed:

  Observe task
  → Inspect available file metadata
  → Read selected files
  → Search relevant knowledge bases
  → Determine task type
  → Continue through the appropriate workflow

  The deterministic classifier and model router should remain outside the ReAct loop. ReAct should choose only from capabilities already approved by policy.

  ### 4. Multimodal document analysis

  For quotations, scanned documents and images:

  Extract text
  → Observe missing table values
  → Inspect selected visual pages
  → Compare OCR and visual results
  → Flag uncertainty or finish

  This would be useful for selectively invoking vision rather than processing every page.

  ### Where not to use it

  Avoid ReAct for operations that must remain deterministic:

  - Authentication and authorization
  - Workspace isolation
  - Model eligibility and priority
  - Queue scheduling
  - Procurement totals and compliance calculations
  - File-path validation
  - Artifact checksums
  - Sandbox restrictions
  - Final approval decisions

  The LLM may recommend an action, but policy code must authorize and execute it.

  ### Recommended code structure

  Add a focused runtime module:

  backend/app/tasks/
  ├── runtime.py
  ├── react_loop.py
  ├── react_actions.py
  └── react_prompts.py

  react_loop.py would:

  1. Build the bounded context.
  2. Request a structured action from the selected model.
  3. Validate it against a strict schema.
  4. Authorize it through backend/app/tools/registry.py.
  5. Execute the tool.
  6. Store a bounded observation in the task trace.
  7. Stop after finish, human review, timeout or maximum steps.

  Do not persist raw chain-of-thought. Persist only:

  - Selected action
  - Short reason summary
  - Sanitized arguments
  - Tool observation
  - Evidence references
  - Duration and status

  Recommended rollout order: formalize the existing coding repair loop first, then add iterative document retrieval, and finally extend it to selective multimodal analysis.

