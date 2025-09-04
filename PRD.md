## Product Requirements Document (PRD): Oliver Backend

This document is a concise handover for new engineers/agents working on the Oliver backend. It reflects the current, running system and how to extend it safely.

### 1) Objective
Provide secure, RLS‑compatible APIs that power Oliver’s compliance workflows (MRA Finding Analysis, Examination Prep, streaming agent), using Supabase for auth/storage/DB and OpenAI Responses for analysis. All user data is tenant‑isolated via `user_id` filters.

### 2) Architecture (Runtime)

- FastAPI app at `app/main.py`
  - Routers: `api/studies.py`, `api/documents.py` (MRA), `api/exam.py` (Exam lane), `api/chat.py`, `api/streaming.py` (SSE), plus feature endpoints.
- Supabase
  - Buckets: `mra-documents`, `exam-documents`
  - Tables: `studies`, `exam_studies`, `mra_documents`, `exam_documents`, `exam_requests`, `exam_request_documents`
- OpenAI Responses API via `app/llm_providers.py` (`gpt-5-*` default, optional `o3-*`)
- Optional external search: EXA (`EXA_API_KEY`) used by agent streaming route

Request flow examples
1) MRA: upload → store in `mra-documents` → analyze via OpenAI → structured JSON persisted on `mra_documents.analysis_results` → frontend renders findings and guidance
2) Exam: upload FDL → `/api/streaming/fdl/ingest` streams reasoning while creating rows in `exam_requests` → evidence linking and per‑request validation persisted to `exam_requests.validation_results`
3) Agent: `/api/streaming/agent/run` emits `reasoning_step`, `tool_call`, `tool_result`, and `completion` events; optionally calls EXA and summarizes with OpenAI

### 3) Workflows (Backend responsibilities)

- MRA Finding Analysis
  - Ingest PDF/DOC/DOCX, extract text (PyMuPDF/python‑docx)
  - Call OpenAI with strict JSON schema (see section 8)
  - Persist `analysis_results` on `mra_documents`

- Examination Prep
  - First‑Day Letter ingest (PDF or text) → request extraction to `exam_requests`
  - Evidence upload to `exam_documents`, link via `exam_request_documents`
  - Validation: load linked files, send to OpenAI, persist `validation_results` and `last_validated_at` on `exam_requests`
  - Streaming variants in `api/streaming.py` provide UI reasoning steps

- Streaming Agent (Oliver)
  - Route: `POST /api/streaming/agent/run` (SSE)
  - Emits `reasoning_step` (UI timeline), optional `exa_search` `tool_call/tool_result`, final `completion`
  - Summarization via OpenAI from search snippets when EXA is configured

### 4) Authentication & Security

- Supabase JWT required; `get_current_user` injects `user['uid']`
- All DB reads/writes are filtered by `user_id` (checked in every route)
- No plaintext keys in responses; environment loaded via `app/config.py`

### 5) Core Data Models

- `studies` / `exam_studies`: per‑user workflow state
  - `workflow_type`, `current_step`, `workflow_status`, `workflow_data` JSON
- `mra_documents`: file metadata, `processing_status`, `analysis_results`
- `exam_documents`: file metadata + `processing_status`
- `exam_requests`: extracted RFI records with `validation_results`
- `exam_request_documents`: join table

### 6) Public API Surface

- Studies: `POST/GET/PATCH /api/studies` (and `/api/exam/studies` for exam lane)
- MRA Documents: 
  - `POST /api/documents/upload`
  - `GET /api/documents/{id}`
  - `POST /api/documents/{id}/analyze`
  - `GET /api/documents/study/{study_id}`
  - `DELETE /api/documents/{id}`
- Examination:
  - `POST /api/exam/documents/upload`
  - `GET /api/exam/documents/{id}`
  - `POST /api/exam/documents/{id}/analyze`
  - `POST /api/exam/fdl/ingest` and `POST /api/exam/fdl/ingest-text`
  - `GET/POST/PATCH/DELETE /api/exam/requests*`
  - `POST /api/exam/requests/{id}/validate`
  - Streaming: `POST /api/streaming/fdl/ingest`, `POST /api/streaming/fdl/simulate`
- Chat (SSE proxy): `POST /api/chat/stream`
- Agent (SSE): `POST /api/streaming/agent/run`

SSE event types used by UI
- Reasoning stream: `{ type: 'reasoning_step', data: { id, title, content, status, ... } }`
- Tooling: `{ type: 'tool_call' | 'tool_result', data: { tool, args/result } }`
- Completion/Error: `{ type: 'completion' | 'error', data: {...} }`

### 7) Environment Configuration

`app/config.py` reads:
- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default `gpt-5`), `OPENAI_EXAM_MODEL` (default `gpt-5-mini`)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`
- `EXA_API_KEY` (optional: enables EXA search in the agent)
- `FRONTEND_URL`, `PORT`

### 8) JSON Contracts (extract)

MRAAnalysisResult (persisted on `mra_documents.analysis_results`)
```
  summary: string
  findings: MRAFinding[]
  total_findings: number
  critical_deadlines: string[]
  processing_time_ms: number
  confidence: number
first_principles?: { ... }
remediation_guidance?: { ... }
  overall_risk_level?: string
  urgency?: string
  key_regulatory_citations?: string[]
```

MRAFinding (per finding)
```
  id: string
  type: 'BSA/AML'|'Lending'|'Operations'|'Capital'|'Management'|'IT'|'Other'
  severity: 'Matter Requiring Attention'|'Deficiency'|'Violation'|'Recommendation'
  description: string
  regulatory_citation?: string
  deadline?: string
  response_required: boolean
  extracted_text: string
  confidence: number
// optional first‑principles fields
  what_it_means?: string
  why_it_matters?: string
  root_causes?: string[]
  regulatory_expectations?: string[]
  control_gaps?: string[]
  recommended_actions?: { action: string; owner?: string; timeframe?: string; effort?: string; impact?: string }[]
  acceptance_criteria?: string[]
  artifacts_to_prepare?: string[]
  risk_impact?: string
  urgency?: string
  dependencies?: string[]
  closure_narrative_outline?: string
```

### 9) Non‑Functional Requirements
- Security: JWT required; RLS enforced; no PII in logs.
- Availability: 99.9% target; degrade gracefully on LLM or EXA failure.
- Performance: document analysis typically < 30s; standard endpoints < 500ms p50.
- Observability: meaningful log lines around each external I/O (OpenAI, storage, DB).
- Data integrity: clean up storage on DB insert failure (already implemented best‑effort).

### 10) Developer Runbook

Local dev
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Set env: `OPENAI_API_KEY`, Supabase keys; optional `EXA_API_KEY`
4. `uvicorn app.main:app --reload`

Adding a new streaming step
- Put SSE in `api/streaming.py`; use helpers `send_reasoning_step`, `send_tool_call`, `send_tool_result`, `send_completion`
- Always filter DB reads/writes by `user['uid']`

### 11) Compatibility & Migration
- Frontend handles missing optional fields defensively (e.g., no guidance → generic next steps)
- New routes should follow existing patterns and return stable JSON envelopes

### 12) Roadmap
- Validation analytics exports
- Better audit metadata for LLM calls
- Background batch jobs for large PDFs


