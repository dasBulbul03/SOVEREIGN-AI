# A. Uploading from the Workbench


1. Browser sends the file
The frontend creates FormData and sends:
POST /workspaces/{workspace_id}/files
Content-Type: multipart/form-data
Cookie: local-session-cookie


2. Backend checks workspace access
The backend verifies:
workspace.organization_id == logged_in_user.organization_id

3. Backend validates the file
The following extensions are allowed:
.pdf  .txt  .md  .csv  .png  .jpg  .jpeg
It validates:
- Safe filename
- No .. path traversal
- No control characters
- Maximum filename length of 255 characters
- Maximum file size of 20 MB
- PDF signature starts with %PDF-
- PNG signature is valid
- JPEG signature is valid

Browser upload
     ↓
Temporary .upload file
     ↓
Validate size and signature
     ↓
Atomic move to permanent storage

5. SHA-256 is calculated
While streaming, the backend calculates the file’s SHA-256 hash.

This supports:
- Integrity verification
- Audit evidence
- Detecting whether content changed
- Artifact traceability

6. File is stored in the Docker volume
The physical storage path follows this structure:
/app/data/
└── workspaces/
    └── {workspace_id}/
        └── uploads/
            └── {generated_file_uuid}.pdf
The original filename is not used as the physical filename. A generated UUID prevents collisions and unsafe paths.
/app/data is backed by the persistent Docker volume workspace_data, so files survive container restarts.


7. Metadata is saved in PostgreSQL
A stored_files record is created containing:
{
  "id": "generated-file-id",
  "workspace_id": "workspace-id",
  "display_name": "pump-manual.pdf",
  "storage_key": "workspaces/.../uploads/....pdf",
  "media_type": "application/pdf",
  "size_bytes": 1048576,
  "sha256": "...",
  "status": "available",
  "created_at": "..."
}

- Only metadata is stored in PostgreSQL. The actual binary file is stored in the Docker volume.


8. Frontend updates the file panel
The API returns the file record, and the frontend immediately adds it to the visible list.
At this point:
- The file is stored.
- The file is available to tasks.
- No embeddings have been generated.
- Nothing has been inserted into Qdrant.
- The file has not necessarily been OCR-processed or indexed.


2. B. Using the uploaded file in a task
When “Run sovereign agent” is clicked, the frontend includes uploaded file IDs in:
{
  "input_file_ids": [
    "file-id-1",
    "file-id-2"
  ]
}
The agent runtime can use the read_file tool.
For text files:
TXT/Markdown/CSV → read directly as UTF-8 text
For PDFs and images:
PDF/Image
   ↓
Document extraction/OCR
   ↓
Normalized page-level text
   ↓
Agent receives bounded content

- Normalized extraction results are stored under:
workspaces/{workspace_id}/extracted/{document_id}/pages.json

The agent tool verifies that the file belongs to the task’s workspace before reading it


# C. Uploading from Knowledge Base
- The Knowledge Base page performs additional processing after storing the file.
Frontend code: [knowledge.tsx (line 37)](/Users/soumanpaul/Desktop/Desk/interview/products/sih/ai-agentic-flow/frontend/components/control-plane/knowledge.tsx:37)

Upload file
    ↓
Create Operations Library if missing
    ↓
Create ingestion job
    ↓
Extract text/OCR
    ↓
Split text into overlapping chunks
    ↓
Generate embeddings using local Ollama
    ↓
Store chunk metadata in PostgreSQL
    ↓
Store vectors and text payload in Qdrant
    ↓
Activate new knowledge-base index version

# PostgreSQL stores
- File metadata
- Extracted document metadata
- Page and chunk metadata
- Knowledge-base/document relationship
- Ingestion job progress
- Active index version


# Qdrant stores
- Each Qdrant point contains:
{
  "id": "vector-point-id",
  "vector": ["embedding numbers"],
  "payload": {
    "knowledge_base_id": "...",
    "document_id": "...",
    "index_version": 1,
    "page_start": 2,
    "page_end": 2,
    "text": "Extracted document chunk...",
    "display_name": "pump-manual.pdf"
  }
}
This enables semantic search with document and page citations.

# Important difference
Workbench upload
→ Stored as direct task input
→ Not automatically added to Qdrant

Knowledge Base upload and index
→ Stored as a file
→ Extracted and chunked
→ Embedded locally
→ Added to Qdrant
→ Available for semantic RAG search

# One current behavior to note: 
- Knowledge Base ingestion sends the newly uploaded file plus all existing workspace files for indexing, rather than indexing only the newly selected file.
