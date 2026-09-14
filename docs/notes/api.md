
# 1. /workspaces — manages task inputs
A workspace is the secure organizational boundary containing the files available to the agent.
Important endpoints:
GET /workspaces
Finds the user’s available workspaces. Currently, the frontend automatically uses the first one.
GET /workspaces/{workspace_id}/files
Loads files already stored in that workspace.
POST /workspaces/{workspace_id}/files
Uploads PDFs, images, CSVs, text files and other supported inputs.
Conceptually:
Organization
└── Workspace
    ├── Documents
    ├── Images
    ├── CSV files
    └── Other task inputs
The correct API name in the current project is plural: /workspaces, not /workspace.


# 2. /tasks — runs the agentic workflow
This is the most important execution API. It converts a user’s goal and workspace inputs into a governed agent run.
- POST /tasks
Creates and starts an agent task:

{
  "workspace_id": "workspace-id",
  "goal": "Analyze these documents and prepare an approval report",
  "input_file_ids": ["file-1", "file-2"],
  "knowledge_base_ids": ["knowledge-base-id"],
  "requested_outputs": ["docx"]
}


Validate request
      ↓
Classify task
      ↓
Determine required capabilities
      ↓
Select an eligible local model
      ↓
Retrieve workspace/knowledge context
      ↓
Execute governed agent steps
      ↓
Validate result
      ↓
Generate artifact
      ↓
Persist trace and audit events

# Other important task endpoints:
GET /tasks/{task_id}
Returns current status, execution steps, result, citations and artifacts. The Workbench polls this every second while the task is active.
POST /tasks/{task_id}/cancel
Requests safe cancellation.
GET /tasks?limit=50

- Loads task history for the Execution Trace page.


# Relationship between them
/workspaces
Files and confidential input data
        │
        ▼
/knowledge-bases
Indexed and searchable evidence
        │
        ▼
/tasks
Agent orchestration and execution
        │
        ├── Model routing
        ├── Retrieval
        ├── Tool execution
        ├── Local inference
        ├── Validation
        └── Artifact generation


# So the simplest explanation is:
- /workspaces controls what data the agent can access.
- /tasks controls what the agent must do with that data.
- /knowledge-bases controls what indexed evidence the agent can retrieve.
- /models controls which local AI model can perform the work.
- /audit-events records exactly what happened.
For the complete product, /tasks is the core orchestration API. /workspaces is the core data-boundary API. Both are essential, but /tasks connects all the other subsystems together.


# GET /workspaces returns a JSON array containing every workspace belonging to the logged-in user’s organization.
Example:
[
  {
    "id": "4f60ad7b-4295-4ea7-a0fe-58e619b46c21",
    "name": "BOMBE Workspace",
    "status": "active",
    "created_at": "2026-09-13T10:30:00Z"
  }
]
Each workspace contains:
- id: Unique workspace UUID
- name: Display name
- status: Usually active
- created_at: Workspace creation timestamp


- /workspaces returns every workspace matching the logged-in user’s organization_id.
- /workspaces/{id}/files returns every file belonging to that workspace.
- StoredFile contains workspace_id, but no uploaded_by_user_id or file-level permissions.
- The authorization check verifies organization ownership, not individual user ownership.
The current access model is:
Organization
├── User A
├── User B
└── Shared Workspace
    ├── File uploaded by User A
    ├── File uploaded by User B
    └── Shared Knowledge Base        

- Therefore, User A and User B can both fetch all files in that shared workspace.    

- There is another important consequence: tasks and execution traces are also organization-wide. /tasks returns tasks from every workspace belonging to the organization, regardless of which user created them, even though tasks record created_by_user_id.


- For an industrial production system, I recommend this permission model:
Organization
└── Workspace
    ├── Workspace members
    ├── Owner/Admin
    ├── Editor
    └── Viewer

- Organization owner/admin: can access all workspaces.
Workspace member: can access only explicitly assigned workspaces.
Editor: can upload files and execute tasks.
Viewer: can view approved files/results only.
Private workspace: visible only to its creator and assigned members.
Every file: records who uploaded it.
Every task and download: permission-checked and audited.

- So, the current system behaves as a shared organization workspace. It does not yet provide personal-file isolation or per-workspace membership.
