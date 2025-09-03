## Product Requirements Document (PRD): Oliver Backend

### 1. Objective
Deliver a reliable, secure, and scalable backend that powers Oliver’s AI-driven compliance workflows for banks. The backend ingests documents, analyzes them with LLMs, persists structured results, and exposes authenticated APIs for the frontend.

### 2. Primary Users
- Compliance Officers, Risk Managers, Audit Leads
- Internal Admin/Developers (observability, ops)

### 3. Scope (V1-V2)
- V1: Studies CRUD, document ingest, analysis (MRA, Exam FDL/Requests), chat streaming proxy, Supabase auth integration, RLS-compatible storage, structured JSON outputs.
- V2: First-principles MRA analysis (implemented), request validation (implemented), presentation slide synthesis, richer analytics & audit trails.

### 4. Key Workflows
- MRA Intake: Upload → Extract Text → Structured MRA findings → First-principles + remediation guidance.
- Exam Prep: FDL ingest (PDF/text) → Request extraction → Requests CRUD → Evidence validation.
- Chat: Streaming analysis with conversation state and reasoning metadata.

### 5. Functional Requirements

5.1 Authentication & Authorization
- Supabase JWT auth required for all endpoints (RLS-friendly).
- Enforce user-level ownership on all reads/writes (filter by `user_id`).

5.2 Studies
- Create/list/get/update studies in `studies` (and `exam_studies` for isolated exam lane).
- Fields: `workflow_type`, `workflow_status`, `current_step`, `workflow_data` JSON.

5.3 Documents (MRA)
- Upload to Supabase Storage `mra-documents` and persist row in `mra_documents`.
- Analyze with OpenAI Responses API to return strict JSON (schema below).
- Track `processing_status`, `error_message`, `analysis_results`.

5.4 Documents (Exam)
- Upload to Storage `exam-documents`, persist rows in `exam_documents`.
- Analyze for checklist/requests; FDL ingest (PDF/text) to `exam_requests`.
- Link documents to requests; validate evidence with LLM and store results.

5.5 Chat Streaming
- Proxy `/api/chat/stream` for SSE; support `previous_response_id` and structured event types: `content`, `canvas_content`, `status`, `reasoning`, `artifacts`, `done`.

### 6. Data Models (summary)
- studies, exam_studies
- mra_documents, exam_documents
- exam_requests, exam_request_documents
- messages (for reasoning analytics; optional in V1 workflows)

### 7. Core APIs (high-level)
- Studies: `POST/GET/PATCH /api/studies`, Exam lane at `/api/exam/studies`.
- MRA Documents: `POST /api/documents/upload`, `GET /api/documents/{id}`, `POST /api/documents/{id}/analyze`, `GET /api/documents/study/{study_id}`, `DELETE /api/documents/{id}`.
- Exam: `POST /api/exam/documents/upload`, `POST /api/exam/documents/{id}/analyze`, `GET /api/exam/documents/{id}`, `POST /api/exam/fdl/ingest`, `POST /api/exam/fdl/ingest-text`, `GET/POST/PATCH/DELETE /api/exam/requests*`, `POST /api/exam/requests/{id}/validate`.
- Chat: `POST /api/chat/stream` (server-sent events).

### 8. LLM Integration
- OpenAI Responses API via `openai_manager` with model selection (`gpt-5-*` or `o3-*`).
- JSON output enforcement: `text.format.type = json_object`.
- Reasoning controls: `reasoning.effort`, `text.verbosity`.

### 9. MRA Analysis: JSON Schema (V2)
```
MRAAnalysisResult {
  summary: string
  findings: MRAFinding[]
  total_findings: number
  critical_deadlines: string[]
  processing_time_ms: number
  confidence: number
  first_principles?: {
    problem_statement?: string
    decomposition?: string[]
    causal_factors?: string[]
    regulatory_expectations?: string[]
    risks?: string[]
  }
  remediation_guidance?: {
    quick_wins?: string[]
    critical_actions?: string[]
    phases?: { phase: string; goals?: string[]; notes?: string }[]
    owners?: string[]
    timeline_30_60_90?: { 30_days?: string[]; 60_days?: string[]; 90_days?: string[] }
    acceptance_criteria?: string[]
    monitoring_metrics?: string[]
    required_artifacts?: string[]
  }
  overall_risk_level?: string
  urgency?: string
  key_regulatory_citations?: string[]
}

MRAFinding {
  id: string
  type: 'BSA/AML'|'Lending'|'Operations'|'Capital'|'Management'|'IT'|'Other'
  severity: 'Matter Requiring Attention'|'Deficiency'|'Violation'|'Recommendation'
  description: string
  regulatory_citation?: string
  deadline?: string
  response_required: boolean
  extracted_text: string
  confidence: number
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
}
```

### 10. Non-Functional Requirements (NFRs)
- Security: All endpoints require Supabase JWT; enforce user scoping; no PII in logs.
- Availability: 99.9% uptime target; graceful degradation on LLM/API failures.
- Performance: Document analysis < 30s typical; endpoints < 500ms p50 (non-analysis).
- Observability: Structured logs, request IDs, error traces around LLM calls/storage/DB.
- Data Integrity: Transactions or compensating actions (e.g., storage cleanup on DB failure).

### 11. Error Handling
- Standard JSON error envelope with `detail` and HTTP status.
- Analysis failures set `processing_status=failed` and populate `error_message`.

### 12. Storage & Tables (Supabase)
- Buckets: `mra-documents`, `exam-documents`.
- Tables: `mra_documents`, `exam_documents`, `exam_requests`, `exam_request_documents`, `studies`, `exam_studies`, optionally `messages` for analytics.
- RLS policies: user must match `user_id`.

### 13. Configuration
- Environment: `OPENAI_MODEL`, `OPENAI_EXAM_MODEL`, Supabase URL/keys.
- Model tuning: switchable `gpt-5-*` vs `o3-*` with reasoning verbosity.

### 14. Migration/Compatibility
- Frontend types extended to consume new fields safely; UIs fallback if absent.
- Existing endpoints unchanged; response shape extended (non-breaking additions).

### 15. Open Questions
- Do we store reasoning traces for compliance audit? Scope and retention policy.
- Background job queue for long-running analyses? (Celery/Redis or serverless tasks.)
- Rate limiting per user to control LLM costs.

### 16. Milestones
- M1: MRA V2 first-principles (DONE)
- M2: Validation analytics summaries & exports
- M3: Presentation generator integration


