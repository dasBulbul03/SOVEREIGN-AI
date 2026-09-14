
Yes, Workbench can perform similar RAG. The Knowledge Base exists because the two areas serve different lifecycles.

   Workbench                             Knowledge Base
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   One-time task context                 Reusable organizational knowledge
  ────────────────────────────────────  ──────────────────────────────────────
   Temporary uploads                     Persistently indexed documents
  ────────────────────────────────────  ──────────────────────────────────────
   Best for a few task-specific files    Best for manuals, policies and SOPs
  ────────────────────────────────────  ──────────────────────────────────────
   Direct read or temporary RAG          Precomputed embeddings in Qdrant
  ────────────────────────────────────  ──────────────────────────────────────
   Faster setup for users                Faster repeated searches
  ────────────────────────────────────  ──────────────────────────────────────
   Context belongs to one task           Versioned, curated shared collection

  If we use only Workbench, it must extract, chunk, embed, and index documents repeatedly for every task. On an M1 with 8 GB RAM, that increases latency, memory use, and duplicate storage. We
  would also lose proper collection management, document versions, reusable indexes, and controlled knowledge updates.

  If we use only Knowledge Base, users must index every temporary document before asking a simple question, which creates unnecessary friction.

  The best design is to keep both but unify the experience:

  - Upload into Workbench.
  - Choose Use for this task or Add to Knowledge Base.
  - Small files can be read directly.
  - Large or multiple files use temporary task-scoped RAG automatically.
  - Knowledge Base documents use their existing persistent index.
  - The agent merges results and records file/page citations.
  - After completion, temporary vectors are removed while task evidence and audit metadata remain.

  So the user should not be forced to leave Workbench. The Knowledge Base remains the persistent, reusable knowledge-management layer behind it.
 


# Knowledge Base
- The Knowledge Base page is where a user prepares trusted organizational documents for AI retrieval.

- it starts and manages the complete ingestion pipeline.


Upload file
    ↓
Create ingestion job
    ↓
Extract text / run OCR
    ↓
Create page-level normalized text
    ↓
Split text into chunks
    ↓
Generate embeddings
    ↓
Store vectors in Qdrant
    ↓
Store document/chunk metadata in PostgreSQL
    ↓
Mark knowledge-base index as ready



1. Normal Workbench upload
POST /workspaces/{workspace_id}/files
This only:
- Validates the file
- Saves it in local storage
- Calculates SHA-256
- Creates a PostgreSQL file record
It does not immediately create embeddings.


2. Knowledge Base ingestion
POST /knowledge-bases/{knowledge_base_id}/ingestions
This starts the complete background indexing operation:
- Text extraction
- OCR when necessary
- Chunking
- Embedding generation through Ollama
- Vector storage in Qdrant
- Citation metadata storage
- Index-version activation


3. Knowledge Base search
When the user searches:
POST /knowledge-bases/{knowledge_base_id}/search
the system creates another embedding—but this one represents the 

user’s question:
User question
    ↓
Ollama creates query embedding
    ↓
Qdrant compares query vector with document vectors
    ↓
Most relevant chunks returned
    ↓
Text + document name + page citation displayed

So embeddings are generated in two places:
- During ingestion: one embedding for every document chunk.
- During search: one embedding for the user’s question.
The Knowledge Base is therefore the manager of the complete searchable document index, not merely an embedding trigger.



# what user will do in Knowledge Base  page
- The Knowledge Base page is where a user prepares trusted organizational documents for AI retrieval.



The Knowledge Base page is where a user prepares trusted organizational documents for AI retrieval.

## Typical user workflow

### 1. Open the Knowledge Base page

The page automatically loads:

- The organization’s first workspace
- Its existing files
- Its first knowledge base, usually `Operations Library`
- Current indexing status

The user can see documents, file sizes and processing status.

### 2. Upload a reference document

The user clicks **Upload documents** and selects a file such as:

- Safety SOP
- Maintenance manual
- Company policy
- Technical specification
- Inspection report
- Equipment diagram or scanned document

After selecting it, an upload strip appears showing the filename and size.

### 3. Click “Upload and index”

This is the important action.

The system:

```text
Validates and stores the file
        ↓
Extracts text or performs OCR
        ↓
Divides the document into chunks
        ↓
Generates local embeddings
        ↓
Stores vectors in Qdrant
        ↓
Records document metadata in PostgreSQL
        ↓
Marks the knowledge base as ready
```

The button displays **Indexing…** while processing.

If the `Operations Library` knowledge base does not exist, the application creates it automatically.

### 4. Review document status

The document table shows:

- Document name
- Short document/file ID
- File size
- Processing status
- `LOCAL` data scope

The collection summary / intended status filters are:

- All Knowledge
- Indexed
- Processing

Currently, (important) these9 only show counts; filtering/actual table filtering is not implemented yet.

### 5. Test document retrieval

The user enters a question in **Retrieval Test**, for example:

```text
What is the safe pump isolation procedure?
```

Then clicks **Search locally**.

The system:

1. Generates an embedding for the question.
2. Searches Qdrant for semantically similar document chunks.
3. Returns up to five relevant results.
4. Displays the similarity percentage.
5. Shows the source document and page number.
6. Shows the exact retrieved text.

Example result:

```text
93% MATCH

Pump Safety SOP.pdf · Page 12

Before maintenance, isolate electrical power,
apply lockout-tagout and verify zero pressure.
```

This lets the user verify that the correct information was indexed before using it in an agent task.

### 6. Use the knowledge in the Workbench

After the knowledge base is ready, the user returns to **Agentic Workbench** and asks something such as:

```text
Review the pump maintenance procedure and prepare
a safety-compliance recommendation.
```

The current Workbench automatically attaches the first ready knowledge base to the task.

The agent can then:

```text
Understand the request
        ↓
Search the Knowledge Base
        ↓
Retrieve relevant evidence
        ↓
Generate a grounded answer
        ↓
Include source citations
        ↓
Create the requested DOCX
```

## Simple distinction

- **Knowledge Base page:** Prepare, index and test trusted reusable documents.
- **Workbench page:** Ask the agent to perform a task using uploaded files and indexed knowledge.
- **Execution Trace page:** Verify how the agent processed the task.

## Current UI limitations

The current Knowledge Base page has a few incomplete controls:

- It uploads one selected file at a time.
- `Operations Library` is not yet a working knowledge-base selector.
- All Knowledge, Indexed and Processing do not filter the table.
- Uploading and indexing currently submits all existing workspace files along with the new file.
- There is no document delete or remove-from-index action.
- The Workbench automatically selects the first ready knowledge base; the user cannot choose one manually yet.