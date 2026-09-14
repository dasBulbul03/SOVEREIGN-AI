| Route | Main component | Purpose |
|---|---|---|
| `/workbench` | `Workbench` | Upload files and execute agent tasks |
| `/overview` | `Overview` | Show system, dependency and model status |
| `/models` | `Models` | Inspect and health-check local models |
| `/knowledge` | `Knowledge` | Upload, index and search organizational knowledge |
| `/trace` | `Trace` | Inspect task execution and audit history |
| `/security` | `Security` | Display sovereignty and local-service evidence |



# 3.1 Workspace Files panel
When the component first opens, its useEffect:
1. Requests GET /workspaces.
2. Selects the first available workspace.
3. Concurrently requests:
GET /workspaces/{workspace_id}/files
GET /knowledge-bases?workspace_id={workspace_id}
4. Stores the files and knowledge bases in React state.
5. Selects the first knowledge base that is ready and has an active index.
This is the concurrent file and knowledge-base loading you asked about earlier.

# File upload
Clicking Plus, the upload area or “Browse local files” opens the native file picker.
Supported frontend extensions:
- PDF
- Markdown
- TXT
- CSV
- PNG
- JPG/JPEG
For every selected file, the frontend sends:
POST /workspaces/{workspace_id}/files
Content-Type: multipart/form-data
Multiple selected files are uploaded one after another. Successfully uploaded files are added to the top of the frontend list.

# When “Run sovereign agent” is clicked, it sends:
- POST /tasks
Content-Type: application/json
Idempotency-Key: <new random UUID>
Payload:
{
  "workspace_id": "...",
  "goal": "User prompt",
  "input_file_ids": ["all current workspace file IDs"],
  "knowledge_base_ids": ["first ready knowledge base ID"],
  "requested_outputs": ["docx"]
}
The idempotency key protects against accidental duplicate task creation.

- After acceptance, the backend returns a task ID. The component stores it as activeTaskId.


# Deterministic routing display
After task processing starts, this section displays backend-provided:
- Classified task type
- Agent profile
- Selected model key
The frontend does not select the model itself. It only displays the backend routing decision.


# 3.3 Live Agent Trace panel
Once a task ID exists, React Query calls:
GET /tasks/{task_id}
While the task is active, it repeats the request every second.
It displays:
- Task status
- Run attempt number
- Elapsed execution time
- Step count
- Step title and detail
- Step status
- Individual step duration
Polling stops when the task becomes:
- Completed
- Failed
- Cancelled
- Timed out
Cancel safely
While a task is active, the button sends:
POST /tasks/{task_id}/cancel
It then immediately refreshes the task state.
Open audit view

# This navigates to:
/trace?task={task_id}

- However, the current Trace component does not read the task URL parameter. It normally selects the first task returned by the API. That is a current functional gap.

# Open audit view
This navigates to:
/trace?task={task_id}
However, the current Trace component does not read the task URL parameter. It normally selects the first task returned by the API. That is a current functional gap.


# 3.4 Agent Result panel
This displays the backend’s latest_run.result_text.
It also displays:
- Selected model
- Final task status
- “VERIFIED LOCAL” badge for completed tasks
- Backend error category/message when execution fails
This panel does not make a separate API call; it uses the task polling result.

# 3.5 Validated Artifact panel
The component takes the first artifact from:
latest_run.artifacts[0]
It displays:
- Artifact filename
- File size
- Validation status
- First 12 characters of its SHA-256 hash
The Download link points to the backend artifact URL.

# 4. Overview
Component: [overview-models.tsx (line 10)](/Users/soumanpaul/Desktop/Desk/interview/products/sih/ai-agentic-flow/frontend/components/control-plane/overview-models.tsx:10)
The Overview page requests:
- GET /readiness
- GET /models
4.1 Summary metric cards
The four cards display:
1. API readiness
2. Number of registered models
3. Number of ready local models
4. Cloud providers, currently statically displayed as zero
4.2 Service Readiness panel
It reads readiness.details.dependencies and displays each backend-reported dependency with:
- Dependency name
- ready or unavailable
- Reported latency
- Green or amber indicator
4.3 Local Infrastructure panel
It displays up to four registered models, including:
- Model name
- Provider
- Model key
- Latest health status
4.4 Configured Local Models table
It displays all models with:
- Model name
- Provider
- Health status
- Context-window size
- Routing priority
“Start new task” navigates to /workbench.


# 5. Model Registry
Component: [overview-models.tsx (line 24)](/Users/soumanpaul/Desktop/Desk/interview/products/sih/ai-agentic-flow/frontend/components/control-plane/overview-models.tsx:24)
When opened, it requests:
GET /models
5.1 Registry summary
Displays:
- Total registered models
- Ready models
- Enabled models
- Cloud providers, statically shown as zero
5.2 Model cards
Each card displays:
- Capabilities
- Model name and model key
- Provider
- Context window
- Priority
- Quantization
- Latest health-check time
- Current readiness
Check Readiness action
Clicking it sends:
POST /models/{model_id}/health-check
After success, React Query invalidates the models cache and reloads the registry.
Currently, a single shared mutation state is used, so while one model is being checked, all model health buttons become disabled and display “Checking…”.
5.3 Capability Router panel
This is currently an explanatory visualization:
Prompt and context
      ↓
Required capabilities
      ↓
Enabled models ordered by priority
      ↓
Selected model
It does not execute routing from this panel. The actual routing happens in the backend during task execution.
The selected model shown here is simply models[0], not necessarily the model selected for a particular task.
“Register model” is disabled because a registration API has not yet been connected.


# 6. Knowledge Base
Component: [knowledge.tsx (line 9)](/Users/soumanpaul/Desktop/Desk/interview/products/sih/ai-agentic-flow/frontend/components/control-plane/knowledge.tsx:9)
When the page opens:
1. Loads all workspaces.
2. Selects the first workspace.
3. Concurrently loads:
GET /knowledge-bases?workspace_id={workspace_id}
GET /workspaces/{workspace_id}/files
4. Selects the first knowledge base returned.
6.1 Upload Documents action
The file picker accepts one file at a time.
Selecting a file only places it in temporary frontend state. The upload does not begin until “Upload and index” is clicked.
6.2 Upload and Index process
The process is:
Check for knowledge base
        ↓
Create “Operations Library” if missing
        ↓
Upload selected file
        ↓
Create ingestion job using all workspace files
        ↓
Poll ingestion status every second
        ↓
Reload files and knowledge-base state
Endpoints used:
POST /knowledge-bases
POST /workspaces/{workspace_id}/files
POST /knowledge-bases/{knowledge_base_id}/ingestions
GET  /ingestions/{ingestion_id}
The ingestion request includes the newly uploaded file plus all existing workspace files.

# 6.3 Collection sidebar and document table
The table displays:
- Document name
- Short ID
- Size
- Status
- Local scope
The All Knowledge, Indexed and Processing buttons currently show counts only. They do not actually filter the table.
The “Operations Library” dropdown is also visual only; it does not open a library selector.
6.4 Retrieval Test panel
Submitting “Search locally” sends:
POST /knowledge-bases/{knowledge_base_id}/search
With:
{
  "query": "User's question",
  "limit": 5
}
The results display:
- Similarity percentage
- Source document
- Page or page range
- Retrieved chunk text
The search button remains disabled until the knowledge base has an active index version.
The top toolbar search input and retrieval-test input share the same query state, but only the lower retrieval form actually triggers the search.

# 7.1 Persisted Runs panel
It requests:
GET /tasks?limit=50
Refresh behavior:
- Every second if any task is active
- Every five seconds when all tasks are finished
The first task is selected automatically unless the user clicks another task.
Each row displays:
- Task goal
- Agent profile
- Elapsed runtime
- Completed, failed or active state

# 7.2 Trace Detail panel
For the selected task, it shows:
- Status
- Goal
- Run ID
- Attempt
- Runtime
- Step count
- Agent profile
- Retry count
Its timeline displays every persisted execution step:
- Sequence number
- Step kind
- Tool name
- Title
- Detail
- Duration
- Routing reason and selected model for routing steps
7.3 Audit event loading
Once a run is selected, it requests:
GET /audit-events?run_id={run_id}
Audit events are refreshed every second while the selected task is active.
7.4 Export Audit JSON
Clicking Export:
1. Combines the selected task and audit events into JSON.
2. Creates a temporary browser Blob.
3. Downloads a file named:
sovereign-audit-{run_id}.json
This export happens entirely in the browser. It does not call a backend export endpoint.


# 8. Sovereignty Monitor
Component: [trace-security.tsx (line 33)](/Users/soumanpaul/Desktop/Desk/interview/products/sih/ai-agentic-flow/frontend/components/control-plane/trace-security.tsx:33)
The page obtains data from:
GET /readiness
8.1 Sovereignty summary
Displays:
- Overall API status
- Backend service name
- Number of ready dependencies
- Number of reported dependencies
8.2 Security-control cards
Displays the configured state of:
- External AI
- Local model inference
- Local knowledge index
- Local document storage
- API health
- Configured API boundary

- These cards are informational and have no click actions.

# 
8.3 Dependency Verification panel
Displays each backend dependency in a terminal-style layout with:
- Service name
- Status
- Latency
The UI correctly warns that backend readiness alone does not prove operating-system-level network isolation.
8.4 Integrated Safeguards panel
Displays static coverage labels for:
- Configured API boundary
- Local model registry
- Workspace file service
- MIME and file-size validation
- Knowledge ingestion jobs
- Model health observations
“Run egress test” is disabled because no dedicated egress-test backend endpoint is connected.
