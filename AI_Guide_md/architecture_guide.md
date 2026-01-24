# CEPF System Architecture & RAG Pipeline

## 1. Data Pipeline (RAG Flow)
1. **Input & Preprocessing**
   - **Parsing:** Convert PDF/Docx to text (PyPDF2, Tesseract).
   - **Cleaning:** Remove PII (Personal Identifiable Information) and duplicates.
   - **Chunking:** Split text by semantic meaning or token limit (e.g., 500 tokens).

2. **Embedding & Storage**
   - **Embedding Model:** Google Vertex AI or OpenAI Embeddings.
   - **Vector DB:** FAISS or Milvus.
   - **Schema (Relational Mapping):**
     - `experiences` Table: id, content, type(work/project), start_date, end_date, tech_stack(tags).

3. **Retrieval Strategy**
   - **Hybrid Search:** Keyword Match (BM25) + Semantic Search (Vector).
   - **Filtering:** Filter by `tech_stack` matching the target company's stack.

## 2. LLM Workflow
- **Models:** Gemini 1.5 Pro (Main Reasoning), Claude 3.5 Sonnet (Writing Style).
- **Agent:** Vertex AI Agent Builder for orchestration.

## 3. Security & Constraints
- **Data Privacy:** Encrypt sensitive user career data at rest.
- **Access Control:** Firebase Auth (JWT) required for all API access.