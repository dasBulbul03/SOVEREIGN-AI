# Retrieval-Augmented Generation (RAG).md


- This process converts a large document into small, searchable pieces so the AI can find the correct evidence before answering.

# What is RAG?
- RAG means Retrieval-Augmented Generation.

# It combines two operations:
- `Retrieval`: Find relevant information in your documents
- `Generation`: Give that information to the LLM to produce an answer

- Without RAG, the LLM answers using only what it learned during training and may hallucinate.

User question
      ↓
Find relevant sections in company documents
      ↓
Give those sections to the local LLM
      ↓
Generate an answer supported by evidence
      ↓
Show document and page citations


- Instead of asking the model to guess, RAG searches your uploaded # SOPs and may find:

Pump Maintenance SOP — Page 12:
“Close the inlet valve, isolate electrical power,
apply lockout-tagout and verify zero pressure.”

- The LLM uses this retrieved section to prepare its answer.

# 1. Document extraction
- A PDF or image is not immediately usable as clean text.

- Extraction converts it into page-level text:
pump-manual.pdf
├── Page 1 → extracted text
├── Page 2 → extracted text
├── Page 3 → extracted text
└── Page 4 → extracted text

- For scanned PDFs and images, OCR—Optical Character Recognition—is used to recognize printed text.

Scanned PDF image
      ↓ OCR
"Before maintenance, isolate the pump from all energy sources."
- The system preserves page numbers so it can later identify where the information originated.

# 2. What does “chunked” mean?
Large documents are too big to send completely to an LLM for every question. They are divided into smaller sections called chunks.

Example document:
100-page Pump Manual
        ↓
Chunk 1: Introduction
Chunk 2: Installation instructions
Chunk 3: Pump startup procedure
Chunk 4: Emergency shutdown
Chunk 5: Lockout-tagout procedure
...
Chunk 180: Maintenance checklist

A chunk may contain approximately a few paragraphs of text.
Your project currently uses:
- CHUNK_SIZE_CHARS=2800
- CHUNK_OVERLAP_CHARS=400

# This means:
- Each chunk contains up to approximately 2,800 characters.
- Adjacent chunks share approximately 400 characters.

# Why overlap chunks?
- Suppose an important instruction begins at the end of one chunk and finishes in the next:

- Chunk 1 ends:
"Before opening the pump housing, the operator must..."

- Chunk 2 begins:
"...verify zero pressure and apply the mechanical isolation lock."
Without overlap, the complete meaning can be separated. Overlap repeats some surrounding text so important statements remain understandable.

# 3. What is an embedding?
- An embedding is a numerical representation of the meaning of text.

"Shut down the pump safely"
        ↓ Embedding model
[0.18, -0.42, 0.73, 0.09, ...]

Every document chunk is converted into a vector—a list of numbers representing its semantic meaning.
Similar meanings produce vectors that are mathematically close

- "How do I safely stop the pump?"
- "Emergency pump shutdown procedure"

- These sentences use different words, but their meanings are similar, so their embeddings should be close.
The embeddings are generated using a local Ollama model, meaning confidential text does not need to be sent to an external cloud service.

4. What is semantic search?
Traditional keyword search looks for exact words.
For example, searching:
"How do I stop the machine safely?"
might not find a section titled:
"Emergency equipment shutdown procedure"
because the exact words are different.


# Semantic search searches by meaning:

# User question:
- "How do I stop the machine safely?"

# Similar document chunks:
1. "Emergency equipment shutdown procedure"
2. "Isolation before maintenance"
3. "Lockout-tagout requirements"

# # The system:
1. Converts the question into an embedding.
2. Compares the question vector with stored chunk vectors.
3. Finds the closest vectors.
4. Returns the most semantically relevant chunks.

- This is particularly useful for industrial documents where the user and manual may use different terminology.


5. What is an index?
An index is an organized structure that allows information to be found quickly.
Think of the index at the back of a book:
Emergency shutdown ........ Page 42
Pump isolation ............ Page 58
Safety inspection ......... Page 71

- A vector index performs a similar job using semantic meaning instead of alphabetical keywords.

# During indexing, SovereignForgeAI:
Extracts document text
       ↓
Divides it into chunks
       ↓
Generates an embedding for each chunk
       ↓
Stores vectors in Qdrant
       ↓
Makes them quickly searchable

- Without an index, the application would have to read every page of every document for every question. That would be extremely slow and computationally expensive.


# Index versions
- The project also records an index_version.
# For example:
Version 1 → Manual A + Manual B
Version 2 → Manual A + Manual B + Updated SOP
The active index version tells the system which set of indexed content should be used for retrieval.

# 6. What does Qdrant store?
Qdrant is the vector database used for semantic search.

For every chunk, it stores:
Vector:
[0.18, -0.42, 0.73, ...]

Payload:
- Original chunk text
- Knowledge-base ID
- Document ID
- Document name
- Page start
- Page end
- Index version

{
  "vector": [0.18, -0.42, 0.73],
  "payload": {
    "display_name": "Pump Safety SOP.pdf",
    "page_start": 12,
    "page_end": 13,
    "text": "Apply lockout-tagout and verify zero pressure."
  }
}

- Qdrant finds the vectors most similar to the user’s question and returns their payloads.

- PostgreSQL remains responsible for relational records such as users, workspaces, files, documents and ingestion jobs.

# 7. What is a citation?
A citation identifies the source supporting an answer.
# Example answer:
Before maintenance, disconnect electrical power, apply lockout-tagout, isolate the inlet and outlet valves, and verify zero pressure.

# Citation:
Source: Pump Safety SOP.pdf
Pages: 12–13
Match score: 91%
The citation is possible because every chunk retains its:
- Document name
- Document ID
- Page start
- Page end
- Original text
Why citations matter
Citations allow users to:
- Verify the AI’s answer
- Open the original source
- Confirm the correct procedure
- Detect unsupported claims
- Maintain an audit trail
- Demonstrate regulatory compliance
In confidential industrial work, the model’s answer alone should not be considered sufficient. The user needs evidence showing where the answer came from.


# Complete example
Suppose you upload a 100-page file called Pump Safety SOP.pdf.
During indexing
Pump Safety SOP.pdf
        ↓
Extract text and page numbers
        ↓
Split into overlapping chunks
        ↓
Generate an embedding for each chunk
        ↓
Store vectors and source information in Qdrant
During a user question
Question:
"What should I do before opening the pump?"

        ↓

Convert question into an embedding

        ↓

Qdrant semantic search

        ↓

Retrieved evidence:
1. Pump Safety SOP.pdf, page 12 — 94%
2. Maintenance Manual.pdf, page 28 — 87%

        ↓

Local LLM receives:
- User question
- Retrieved evidence
- Source information

        ↓

Generated answer:
"Isolate electrical and mechanical energy, apply
lockout-tagout, and verify zero pressure."

        ↓

Citation:
Pump Safety SOP.pdf, page 12
Why the system needs RAG
RAG provides five major benefits:
- Accuracy: The model answers using organization-approved documents.
- Privacy: Documents, embeddings and inference remain on-premise.
- Fresh information: Updating the knowledge base updates what the model can retrieve without retraining it.
- Efficiency: Only relevant chunks are sent to the LLM instead of entire manuals.
- Traceability: Answers can include document-level and page-level citations.


# Citations
- Citations in Retrieval-Augmented Generation (RAG) systems map generated text back to specific source chunks to prevent hallucinations and build trust

# Chunking

# Embeddings,

# Indexing 

# Retrieval



- For this pipeline, the project uses a combination of Python libraries, Ollama and Qdrant. It does not currently use `LangChain` or `LlamaIndex`; the RAG pipeline is implemented directly in the backend.

# Tool used at each stage
| Processing stage | Tool/library used | Purpose |
|---|---|---|
| Upload file | FastAPI `UploadFile` + `python-multipart` | Receives multipart file uploads |
| Validate and save | Python `pathlib`, `hashlib`, filesystem APIs | Validates, stores and calculates SHA-256 |
| Extract PDF text | PyMuPDF | Extracts native text and page numbers |
| OCR scanned pages | Tesseract OCR through `pytesseract` | Recognizes text in scanned PDFs/images |
| Image processing | Pillow | Opens images and converts PDF pages for OCR |
| Split into chunks | Custom Python chunker | Creates overlapping text sections |
| Generate embeddings | Ollama `/api/embed` | Runs the local embedding model |
| Embedding model | `nomic-embed-text` | Converts text into numerical vectors |
| Store vectors | Qdrant | Stores and searches vector embeddings |
| Store metadata | PostgreSQL + SQLAlchemy | Stores documents, chunks, jobs and index versions |
| Network communication | `httpx` | Calls Ollama and Qdrant APIs |
| Background indexing | FastAPI `BackgroundTasks` | Runs ingestion after returning the job response |

# Complete tool flow
Pump Safety SOP.pdf
        │
        ▼
FastAPI UploadFile
Receives the uploaded file
        │
        ▼
Python file-storage service
Validates type/size and calculates SHA-256
        │
        ▼
PyMuPDF
Extracts native PDF text and page numbers
        │
        ├── Enough text found
        │         └── Use native PDF text
        │
        └── Very little text found
                  └── Pillow + Tesseract OCR
                      recognize text from page image
        │
        ▼
Custom Python chunker
Creates overlapping text chunks
        │
        ▼
Ollama + nomic-embed-text
Converts each chunk into an embedding vector
        │
        ├── PostgreSQL
        │   Stores document and chunk metadata
        │
        └── Qdrant
            Stores vectors, text and citation metadata


# 1. Text extraction: PyMuPDF
It processes the PDF page by page:
Page 1 → text + page number 1
Page 2 → text + page number 2
Page 3 → text + page number 3

# 2. OCR: Tesseract and Pillow
- If a PDF page contains less text than the configured threshold, the system assumes that the page might be scanned.

# It then:
1. Uses PyMuPDF to render the page as an image.
2. Uses Pillow to construct the image.
3. Passes the image to Tesseract OCR.
4. Compares native text with OCR text.
5. Uses OCR text only if it found more content.

- For PNG and JPEG files, Tesseract OCR is used directly.
- The Docker image installs the native tesseract-ocr program, while pytesseract is the Python wrapper that calls it.


# 3. Chunking: custom Python implementation
Code: [chunker.py (line 6)](/Users/soumanpaul/Desktop/Desk/interview/products/sih/ai-agentic-flow/backend/app/documents/chunker.py:6)
Chunking is handled by project-owned Python code, not an external RAG framework.
Current configuration:
CHUNK_SIZE_CHARS=2800
CHUNK_OVERLAP_CHARS=400
The chunker:
- Processes each page separately.
- Normalizes repeated whitespace.
- Creates sections up to approximately 2,800 characters.
- Tries to end at a word boundary.
- Repeats approximately 400 characters in the next chunk.
- Records the page number with every chunk.
Because each page is processed separately, a chunk currently does not span multiple pages.


# 4. Embeddings: Ollama
Code: [ollama.py (line 86)](/Users/soumanpaul/Desktop/Desk/interview/products/sih/ai-agentic-flow/backend/app/model_providers/ollama.py:86)
The backend sends chunks to the locally running Ollama service:
POST /api/embed
Payload:
{
  "model": "nomic-embed-text",
  "input": [
    "First document chunk...",
    "Second document chunk..."
  ],
  "truncate": true,
  "keep_alive": "2m"
}
The configured embedding model is:
nomic-embed-text
The ingestion service processes chunks in batches of eight.
Ollama returns a vector for each chunk:
{
  "embeddings": [
    [0.18, -0.42, 0.73, 0.09],
    [0.51, 0.11, -0.28, 0.64]
  ]
}
This process runs locally.


# 5. Vector indexing: Qdrant
Code: [qdrant_store.py (line 8)](/Users/soumanpaul/Desktop/Desk/interview/products/sih/ai-agentic-flow/backend/app/services/qdrant_store.py:8)
The backend uses a custom QdrantStore class and communicates with Qdrant through its HTTP API using httpx.
It first checks whether the collection exists:
GET /collections/sovereignforge_chunks
If it does not exist, the backend creates it:
PUT /collections/sovereignforge_chunks
The collection uses:
{
  "vectors": {
    "size": "<embedding dimensions>",
    "distance": "Cosine"
  }
}
Cosine distance measures similarity between the meanings represented by two vectors.
The vectors are then uploaded in batches of 64:
PUT /collections/sovereignforge_chunks/points?wait=true


# 6. Citation information
Citation generation does not use a separate external tool. The project attaches source metadata to each Qdrant point:
{
  "knowledge_base_id": "...",
  "document_id": "...",
  "index_version": 1,
  "page_start": 12,
  "page_end": 12,
  "display_name": "Pump Safety SOP.pdf",
  "text": "Apply lockout-tagout before opening the pump..."
}
When Qdrant returns a relevant point, the backend uses these fields to display:
Pump Safety SOP.pdf · Page 12 · 93% match


- FastAPI → PyMuPDF/Tesseract → Custom Chunker →
Ollama nomic-embed-text → Qdrant + PostgreSQL