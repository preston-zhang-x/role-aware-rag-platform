# Role Aware RAG Platform — role-aware RAG for enterprise knowledge bases

A role-aware RAG platform for internal enterprise knowledge bases. It filters documents at retrieval time so each user can only retrieve content allowed for their role.

---

<p align="left">
  <a href="./pyproject.toml"><img alt="version" src="https://img.shields.io/badge/version-v0.1.0-0EA5E9?style=flat-square"></a>
  <a href="./LICENSE"><img alt="license" src="https://img.shields.io/badge/license-Apache--2.0-D4A017?style=flat-square"></a>
  <a href="https://github.com/preston-zhang-x/role-aware-rag-platform/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/preston-zhang-x/role-aware-rag-platform/ci.yml?branch=main&label=CI&style=flat-square"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white&style=flat-square">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white&style=flat-square">
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111827&style=flat-square">
  <img alt="Qdrant" src="https://img.shields.io/badge/Qdrant-vector%20store-DC244C?style=flat-square">
  <a href="https://github.com/preston-zhang-x/role-aware-rag-platform/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/preston-zhang-x/role-aware-rag-platform?style=social"></a>
</p>

<p align="left">
  <a href="./README.md">中文</a> |
  <a href="./README.ja.md">日本語</a> |
  <strong>English</strong>
</p>

---

## Overview

Role Aware RAG Platform is a RAG application for internal enterprise knowledge bases. It combines user roles, document permissions, hybrid retrieval, and source tracing in one question-answering flow, making it suitable for internal search, Japanese-style design specifications, and local AI assistants that need access control.

The project focuses on structured parsing for complex Japanese Excel specifications, then combines vector search, BM25, RRF fusion, and reranking to produce grounded answers with traceable sources.

![System Architecture](docs/assets/system-architecture.jpg)

## Highlights

- **Role-aware retrieval**: filters by `allowed_roles` before retrieval, supporting `admin / manager / staff`
- **Multiple retrieval modes**: `vector`, `bm25`, `hybrid`, and `hybrid_rerank`
- **Excel specification parsing**: preserves sheet semantics, merged cells, key-value blocks, and table regions
- **Unified document loading**: supports `.xlsx`, `.xlsm`, `.xls`, `.xlsb`, and `.pdf`
- **Traceable answers**: returns answer text, matched sources, chunk positions, tokens, and latency metadata
- **Separated frontend/backend**: `FastAPI` backend and `React + Vite` frontend
- **Local-first setup**: defaults to `Ollama + BGE-M3 + local rerank-adapter`

## Why a Custom Excel Parser

Many Japanese-style specifications use Excel as a layout tool rather than a simple tabular data format. Plain text extraction can capture the words, but it often loses the relationships between sections, fields, notes, and tables.

The custom parser keeps the structural hints people rely on when reading these documents, which makes chunking, BM25 matching, and source references more reliable.

<table>
  <tr>
    <td width="50%" valign="top" align="center">
      <strong>Direct MarkItDown conversion</strong>
    </td>
    <td width="50%" valign="top" align="center">
      <strong>Custom Excel Parser</strong>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/excel-markitdown-output.png" alt="MarkItDown converting Excel into a noisy table with many Unnamed columns and NaN values" />
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/excel-custom-parser-output.png" alt="Custom Excel parser preserving readable headings, fields, and sections" />
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <sub>Complex Excel specifications often produce <code>Unnamed</code> columns, <code>NaN</code> values, and mixed note/table regions.</sub>
    </td>
    <td width="50%" valign="top">
      <sub>The parser preserves field names, section hierarchy, row relationships, and readable order for better retrieval quality.</sub>
    </td>
  </tr>
</table>

## Demo

![Demo](docs/动画演示.gif)

## Retrieval Modes

Switch modes with `RETRIEVAL_MODE` in `.env`.

| Mode | Description | Best for |
| --- | --- | --- |
| `vector` | Vector search only | Semantic similarity |
| `bm25` | Keyword search only | IDs, field names, exact terms |
| `hybrid` | Vector + BM25 fused with RRF | Balanced recall |
| `hybrid_rerank` | Reranks results after `hybrid` | Higher precision |

## Evaluation

Offline evaluation on the RAGBench `emanual` subset. The default `hybrid_rerank` mode was evaluated on `132` questions.

| Metric | Result |
| --- | --- |
| Accuracy | `90.9%` |
| Source Hit Rate | `100.0%` |
| Avg Source Recall | `0.833` |
| Avg Answer Token F1 | `0.520` |

See [`docs/report_ragbench_emanual_hybrid_rerank.md`](docs/report_ragbench_emanual_hybrid_rerank.md) for the full report.

![RAGBench hybrid rerank evaluation](docs/assets/Snipaste_2026-04-29_18-29-00.png)

## Tech Stack

| Layer | Components |
| --- | --- |
| Backend | `FastAPI`, `SQLAlchemy`, `Alembic` |
| Retrieval | `Qdrant`, `BM25`, `RRF`, local `reranker` |
| AI | `OpenAI-compatible API`, default `Ollama`, `BGE-M3`, `qwen3.5:4b` |
| Parsing | `openpyxl`, `pdfplumber`, `markitdown` |
| Frontend | `React 19`, `Vite`, `TanStack Query`, `React Router`, `Tailwind CSS` |
| Infra | `PostgreSQL`, `Docker Compose` |

## Quick Start

### 1. Prerequisites

- Python `3.11`
- `uv`
- Docker / Docker Compose
- Ollama
- Node.js and `npm`

### 2. Configure Environment Variables

```powershell
Copy-Item .env.example .env
```

The default local path uses `Ollama + BGE-M3 + hybrid_rerank`. If you do not want reranking, change `RETRIEVAL_MODE` in `.env` to `hybrid`, `bm25`, or `vector`.

### 3. Install Dependencies

```powershell
uv sync --extra rerank
npm --prefix frontend install
```

### 4. Start Core Services

```powershell
docker compose up -d db qdrant
uv run alembic upgrade head
```

### 5. Prepare Local Models

If Ollama is not already running, start it in a separate terminal.

```powershell
$env:OLLAMA_MAX_LOADED_MODELS="1"
$env:OLLAMA_NUM_PARALLEL="1"
ollama serve
```

Pull the default models.

```powershell
ollama pull qwen3.5:4b
ollama pull bge-m3
```

### 6. Start rerank-adapter

Required only when `RETRIEVAL_MODE=hybrid_rerank`. Run it in a separate terminal.

```powershell
uv run python script/run_rerank_adapter.py
```

### 7. Recreate the Vector Collection and Ingest Documents

```powershell
uv run python script/reset_qdrant_collection.py --collection documents
uv run python script/ingest_repo_spec.py --dir docs --pattern *.xlsx --recursive
```

To ingest a single file:

```powershell
uv run python script/ingest_repo_spec.py --file "docs\設計_処理設計書_excel_parser.xlsx"
```

### 8. Create Initial Login Users

Generate a bcrypt password hash.

```powershell
uv run python -c "from app.core.security import hash_password; print(hash_password('123456'))"
```

Insert users into the database.

```sql
INSERT INTO users (username, hashed_password, role)
VALUES
  ('admin_demo', '<PUT_HASH_HERE>', 'admin'),
  ('manager_demo', '<PUT_HASH_HERE>', 'manager'),
  ('staff_demo', '<PUT_HASH_HERE>', 'staff');
```

### 9. Start the Application

Backend:

```powershell
uv run uvicorn app.main:app --reload
```

Frontend:

```powershell
npm --prefix frontend run dev
```

Useful URLs:

| Service | URL |
| --- | --- |
| FastAPI | `http://127.0.0.1:8000` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| Frontend | `http://127.0.0.1:5173` |
| Login | `http://127.0.0.1:5173/login` |
| Chat | `http://127.0.0.1:5173/chat` |
| Qdrant HTTP | `http://127.0.0.1:6333` |
| rerank-adapter | `http://localhost:8090` |

## API Overview

### Auth

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | Form login, returns a JWT |
| `GET` | `/api/v1/auth/me` | Returns the current user |

Login example:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin_demo&password=123456"
```

### RAG

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/rag/ask` | Runs retrieval QA for the current user's role |

Ask example:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/rag/ask" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is the function name of FN-007?\"}"
```

## Document Parsing and Ingestion

- `.xlsx` / `.xlsm`: handled by `JapaneseExcelParser` first
- `.xls` / `.xlsb`: handled by `MarkItDownFallback`
- `.pdf`: handled by `PDFMarkdownParser` first
- Ingested metadata includes `source_file`, `source_key`, `allowed_roles`, `chunk_index`, `sheet_name`, `cell_range`, and `content_type`

## Repository Layout

```text
.
├─ app/                 Backend application
│  ├─ api/v1/           auth / docs / rag / health APIs
│  ├─ core/             Configuration, auth, logging, error handling
│  ├─ db/               SQLAlchemy models and database session
│  ├─ clients/          Qdrant client wrapper
│  └─ services/         Parsing, ingestion, retrieval, RAG, reranking logic
├─ frontend/            React frontend
├─ script/              Ingestion, evaluation, Qdrant reset, rerank scripts
├─ docs/                Design documents, specifications, evaluation reports
├─ tests/               Unit and integration tests
├─ alembic/             Database migrations
├─ docker-compose.yml   PostgreSQL / Qdrant / pgAdmin
└─ .env.example         Environment variable example
```

## Tests

Backend:

```powershell
uv run pytest
```

Frontend:

```powershell
npm --prefix frontend run lint
```

## License

This project is licensed under [`Apache-2.0`](./LICENSE).
