from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncGenerator
import json
import asyncio
from datetime import datetime
import uuid

from app.supabase_client import supabase
from app.auth import get_current_user
from app.llm_providers import openai_manager
from app.config import settings

router = APIRouter(prefix="/api/streaming", tags=["streaming"])

class ReasoningStep:
    def __init__(self, title: str, content: str, icon: str = "brain", details: str = None):
        self.id = str(uuid.uuid4())
        self.title = title
        self.content = content
        self.status = "active"
        self.timestamp = datetime.utcnow().isoformat()
        self.icon = icon
        self.details = details

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "timestamp": self.timestamp,
            "icon": self.icon,
            "details": self.details
        }

    def complete(self):
        self.status = "completed"
        return self

    def error(self, error_message: str):
        self.status = "error"
        self.content = error_message
        return self

async def send_reasoning_step(step: ReasoningStep) -> str:
    """Format a reasoning step as SSE data"""
    return f"data: {json.dumps({'type': 'reasoning_step', 'data': step.to_dict()})}\n\n"

async def send_progress_update(current: int, total: int, message: str) -> str:
    """Format a progress update as SSE data"""
    return f"data: {json.dumps({'type': 'progress', 'data': {'current': current, 'total': total, 'message': message}})}\n\n"

async def send_completion(data: Dict[str, Any]) -> str:
    """Format completion data as SSE data"""
    return f"data: {json.dumps({'type': 'completion', 'data': data})}\n\n"

async def send_regulatory_snapshot_chunk(content: str) -> str:
    """Format a regulatory snapshot text chunk as SSE data"""
    return f"data: {json.dumps({'type': 'regulatory_snapshot_chunk', 'data': {'content': content}})}\n\n"

async def send_error(error_message: str) -> str:
    """Format error as SSE data"""
    return f"data: {json.dumps({'type': 'error', 'data': {'message': error_message}})}\n\n"

async def send_letter_chunk(content: str) -> str:
    """Format a simulated letter text chunk as SSE data"""
    return f"data: {json.dumps({'type': 'letter_chunk', 'data': {'content': content}})}\n\n"

# NEW: Tool call helpers for generic agent streams
async def send_tool_call(tool: str, args: Dict[str, Any]) -> str:
    return f"data: {json.dumps({'type': 'tool_call', 'data': {'tool': tool, 'args': args}})}\n\n"

async def send_tool_result(tool: str, result: Any) -> str:
    return f"data: {json.dumps({'type': 'tool_result', 'data': {'tool': tool, 'result': result}})}\n\n"

@router.post("/fdl/ingest")
async def stream_fdl_ingest(payload: Dict[str, Any], user=Depends(get_current_user)):
    """Stream FDL ingestion (text-only to OpenAI). Uses stored extracted_text from exam_documents."""
    document_id = payload.get('document_id')
    study_id = payload.get('study_id')
    
    if not document_id or not study_id:
        raise HTTPException(status_code=400, detail="document_id and study_id are required")

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection confirmation
            yield "data: {\"type\": \"connected\"}\n\n"
            
            # Step 1: Document Retrieval
            step1 = ReasoningStep(
                "Retrieving First Day Letter metadata", 
                "Loading document metadata and previously extracted text...",
                "file"
            )
            yield await send_reasoning_step(step1)
            await asyncio.sleep(1)  # Simulate processing time
            
            # Load document
            doc_result = supabase.table('exam_documents').select('*').eq('id', document_id).eq('user_id', user['uid']).single().execute()
            if not doc_result.data:
                step1.error("Document not found or access denied")
                yield await send_reasoning_step(step1)
                yield await send_error("Document not found")
                return
            
            document = doc_result.data
            step1.complete()
            step1.content = f"Loaded {document.get('filename','document')} (size: {document.get('file_size','n/a')} bytes)"
            yield await send_reasoning_step(step1)
            
            # Step 2: Get Extracted Text (prefer stored text)
            step2 = ReasoningStep(
                "Preparing Text for AI",
                "Fetching extracted text for analysis...",
                "search"
            )
            yield await send_reasoning_step(step2)
            await asyncio.sleep(1)
            
            try:
                extracted_text = (document.get('extracted_text') or '').strip()
                if not extracted_text:
                    # Fallback: download and extract quickly
                    file_bytes = supabase.storage.from_('exam-documents').download(document['file_path'])
                    import tempfile, os
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmpf:
                        tmpf.write(file_bytes)
                        tmp_path = tmpf.name
                    try:
                        # Minimal text extraction fallback seen in exam.py
                        from .exam import _extract_text  # type: ignore
                    except Exception:
                        # Local import fallback (duplicate basic logic)
                        def _extract_text(fp: str, ft: str) -> str:
                            try:
                                import fitz
                                d = fitz.open(fp)
                                t = ""
                                for i in range(len(d)):
                                    t += d[i].get_text() + "\n\n"
                                d.close(); return t.strip()
                            except Exception:
                                return ""
                    try:
                        extracted_text = _extract_text(tmp_path, document.get('file_type') or 'application/pdf')
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
                if not extracted_text:
                    raise Exception("No extracted text available")
                step2.complete()
                step2.content = f"Text prepared ({len(extracted_text)} characters)."
                yield await send_reasoning_step(step2)
            except Exception as e:
                step2.error(f"Failed to prepare text: {str(e)}")
                yield await send_reasoning_step(step2)
                yield await send_error(f"Text preparation failed: {str(e)}")
                return
            
            # Step 3: AI Model Initialization
            step3 = ReasoningStep(
                "Initializing GPT Analysis Engine",
                "Connecting to OpenAI model and preparing regulatory examination context...",
                "brain"
            )
            yield await send_reasoning_step(step3)
            await asyncio.sleep(1)
            
            client = openai_manager.get_client()
            if not client:
                step3.error("OpenAI client not available")
                yield await send_reasoning_step(step3)
                yield await send_error("AI analysis service unavailable")
                return
                
            step3.complete()
            step3.content = f"Model {settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL} connected successfully for regulatory document analysis."
            yield await send_reasoning_step(step3)
            
            # Step 4: Text Prepared (no file upload to AI)
            step4 = ReasoningStep(
                "Using Extracted Text Only",
                "Complying with policy: sending only text to AI (no PDFs).",
                "file"
            )
            step4.complete()
            yield await send_reasoning_step(step4)
            
            # Step 5: Multi-Step Real-Time AI Analysis
            step5 = ReasoningStep(
                "Starting Multi-Step AI Analysis",
                "Breaking down analysis into streaming steps for real-time feedback...",
                "lightbulb"
            )
            yield await send_reasoning_step(step5)
            await asyncio.sleep(0.5)
            
            # Step 5a: Document Structure Analysis (streaming)
            step5a = ReasoningStep(
                "Analyzing Document Structure",
                "GPT-5 is identifying sections, headers, and overall document layout...",
                "search"
            )
            yield await send_reasoning_step(step5a)
            
            try:
                structure_prompt = (
                    "Analyze this First Day Letter PDF and identify its structure. "
                    "List the main sections, key headers, and document organization. "
                    "Respond with a brief analysis of what sections contain examination requests."
                )
                
                # Use examination-specific model (defaults to GPT-5-mini)
                exam_model = settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL
                structure_params = {
                    "model": exam_model,
                    "input": [{"role": "user", "content": [
                        {"type": "input_text", "text": extracted_text[:150000]},
                        {"type": "input_text", "text": structure_prompt}
                    ]}],
                    "instructions": structure_prompt,
                    "max_output_tokens": 1000,
                    "stream": True,  # Enable streaming for real-time output
                    "store": True,
                }
                
                if exam_model.startswith("gpt-5"):
                    structure_params["reasoning"] = {"effort": "low"}  # Fast analysis
                    structure_params["text"] = {"verbosity": "medium"}
                
                # Stream the structure analysis
                structure_response = client.responses.create(**structure_params)
                structure_content = ""
                
                if hasattr(structure_response, '__iter__'):
                    # Handle streaming response
                    for chunk in structure_response:
                        if hasattr(chunk, 'output') and chunk.output:
                            for item in chunk.output:
                                if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                                    for c in item.content:
                                        if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                            structure_content += c.text
                                            step5a.content = f"Document structure: {structure_content[:100]}..."
                                            yield await send_reasoning_step(step5a)
                                            await asyncio.sleep(0.1)  # Real-time streaming
                else:
                    # Handle non-streaming response
                    if structure_response.output:
                        for item in structure_response.output:
                            if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                                for c in item.content:
                                    if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                        structure_content = c.text
                
                step5a.complete()
                step5a.content = f"Document structure analyzed: {len(structure_content)} characters of insights"
                step5a.details = structure_content
                yield await send_reasoning_step(step5a)
                
            except Exception as e:
                step5a.error(f"Structure analysis failed: {str(e)}")
                yield await send_reasoning_step(step5a)
                # Continue with fallback approach
                structure_content = "Document structure analysis unavailable, proceeding with direct extraction."
            
            # Step 5b: Category Identification (streaming)
            step5b = ReasoningStep(
                "Identifying Risk Categories",
                "GPT-5 is scanning for regulatory risk categories and examination domains...",
                "search"
            )
            yield await send_reasoning_step(step5b)
            
            try:
                category_prompt = (
                    "Based on this First Day Letter, identify the main regulatory risk categories mentioned. "
                    "Look for terms like Credit Risk, Operational Risk, IT/Cybersecurity, BSA/AML, etc. "
                    "Explain which categories you find and where they appear in the document."
                )
                
                exam_model = settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL
                category_params = {
                    "model": exam_model,
                    "input": [{"role": "user", "content": [
                        {"type": "input_text", "text": extracted_text[:150000]},
                        {"type": "input_text", "text": f"Context: {structure_content[:500]}\n\n{category_prompt}"}
                    ]}],
                    "instructions": category_prompt,
                    "max_output_tokens": 1500,
                    "stream": True,
                    "store": True,
                }
                
                if exam_model.startswith("gpt-5"):
                    category_params["reasoning"] = {"effort": "low"}
                    category_params["text"] = {"verbosity": "medium"}
                
                # Stream the category analysis
                category_response = client.responses.create(**category_params)
                category_content = ""
                
                if hasattr(category_response, '__iter__'):
                    for chunk in category_response:
                        if hasattr(chunk, 'output') and chunk.output:
                            for item in chunk.output:
                                if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                                    for c in item.content:
                                        if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                            category_content += c.text
                                            step5b.content = f"Found categories: {category_content[:100]}..."
                                            yield await send_reasoning_step(step5b)
                                            await asyncio.sleep(0.1)
                else:
                    if category_response.output:
                        for item in category_response.output:
                            if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                                for c in item.content:
                                    if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                        category_content = c.text
                
                step5b.complete()
                step5b.content = f"Risk categories identified: {len(category_content)} characters of analysis"
                step5b.details = category_content
                yield await send_reasoning_step(step5b)
                
            except Exception as e:
                step5b.error(f"Category identification failed: {str(e)}")
                yield await send_reasoning_step(step5b)
                category_content = "Category analysis unavailable, using fallback classification."
            
            # Step 5c: Final Request Extraction (streaming)
            step5c = ReasoningStep(
                "Extracting Examination Requests",
                "GPT-5 is now extracting specific examination requests with all details...",
                "lightbulb"
            )
            yield await send_reasoning_step(step5c)
            
            try:
                # Final extraction with context from previous steps
                extraction_prompt = (
                    "Based on the document structure and risk categories identified, extract all specific examination requests. "
                    "For each request, provide: title, description, category, request_code (if any), regulatory_deadline (if any), priority (0-3). "
                    "Use ONLY these categories: 'Credit Risk', 'Interest Rate Risk', 'Liquidity Risk', 'Price Risk', "
                    "'Operational Risk', 'Compliance Risk', 'Strategic Risk', 'Governance/Management Oversight', "
                    "'IT/Cybersecurity', 'BSA/AML', 'Capital Adequacy/Financial Reporting', 'Asset Management/Trust'. "
                    "Return valid JSON only."
                )
                
                exam_model = settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL
                extraction_params = {
                    "model": exam_model,
                    "input": [{"role": "user", "content": [
                        {"type": "input_text", "text": extracted_text[:150000]},
                        {"type": "input_text", "text": f"Context:\nStructure: {structure_content[:300]}\nCategories: {category_content[:300]}\n\n{extraction_prompt}"}
                    ]}],
                    "instructions": extraction_prompt,
                    "max_output_tokens": 6000,
                    "text": {"format": {"type": "json_object"}},
                    "stream": False,
                    "store": True,
                }
                
                if exam_model.startswith("gpt-5"):
                    extraction_params["reasoning"] = {"effort": "medium"}
                    extraction_params["text"]["verbosity"] = "high"
                
                step5c.content = "Performing final extraction with full context and reasoning..."
                yield await send_reasoning_step(step5c)
                
                resp = client.responses.create(**extraction_params)
                step5c.complete()
                step5c.content = "Request extraction completed successfully with contextual analysis"
                yield await send_reasoning_step(step5c)
                
            except Exception as e:
                step5c.error(f"Request extraction failed: {str(e)}")
                yield await send_reasoning_step(step5c)
                yield await send_error(f"AI analysis failed: {str(e)}")
                return
            
            # Step 6: Response Processing
            step6 = ReasoningStep(
                "Processing AI Response",
                "Extracting and validating structured examination requests from GPT-5 output...",
                "search"
            )
            yield await send_reasoning_step(step6)
            await asyncio.sleep(1)
            
            # Extract content from response
            content = ""
            if resp.output:
                for item in resp.output:
                    if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                        for c in item.content:
                            if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                content = c.text
                                break
                    if content:
                        break
            if not content and hasattr(resp, 'output_text'):
                content = resp.output_text
            
            if not content:
                step6.error("No content received from AI analysis")
                yield await send_reasoning_step(step6)
                yield await send_error("AI analysis returned no content")
                return
            
            # Parse JSON response
            import json as _json
            try:
                parsed = _json.loads(content)
                rfis = parsed.get('requests') if isinstance(parsed, dict) else parsed
                if not isinstance(rfis, list):
                    rfis = []
                
                step6.complete()
                step6.content = f"Successfully extracted {len(rfis)} examination requests from AI analysis."
                step6.details = f"Raw AI response:\n{content[:500]}..." if len(content) > 500 else content
                yield await send_reasoning_step(step6)
            except Exception as e:
                step6.error(f"Failed to parse AI response: {str(e)}")
                yield await send_reasoning_step(step6)
                yield await send_error(f"Failed to parse AI response: {str(e)}")
                return
            
            # Step 7: Category Normalization
            step7 = ReasoningStep(
                "Normalizing Request Categories",
                "Validating and normalizing risk categories according to regulatory taxonomy...",
                "check"
            )
            yield await send_reasoning_step(step7)
            await asyncio.sleep(1)
            
            # Category normalization logic
            VALID_CATEGORIES = {
                'Credit Risk', 'Interest Rate Risk', 'Liquidity Risk', 'Price Risk',
                'Operational Risk', 'Compliance Risk', 'Strategic Risk',
                'Governance/Management Oversight', 'IT/Cybersecurity', 'BSA/AML',
                'Capital Adequacy/Financial Reporting', 'Asset Management/Trust'
            }
            
            CATEGORY_MAPPING = {
                'Corporate Governance': 'Governance/Management Oversight',
                'Governance': 'Governance/Management Oversight',
                'Management': 'Governance/Management Oversight',
                'Technology Risk': 'IT/Cybersecurity',
                'Cyber Risk': 'IT/Cybersecurity',
                'Technology': 'IT/Cybersecurity',
                'Market Risk': 'Price Risk',
                'Legal Risk': 'Compliance Risk',
                'Reputation Risk': 'Operational Risk',
                'Reputational Risk': 'Operational Risk',
                'Model Risk': 'Operational Risk'
            }
            
            def normalize_category(category: str) -> str:
                if not category:
                    return 'Operational Risk'
                if category in VALID_CATEGORIES:
                    return category
                if category in CATEGORY_MAPPING:
                    return CATEGORY_MAPPING[category]
                return 'Operational Risk'
            
            # Normalize categories
            normalized_count = 0
            for r in rfis:
                original_category = r.get('category', '')
                normalized_category = normalize_category(original_category)
                if original_category != normalized_category:
                    normalized_count += 1
                r['category'] = normalized_category
            
            step7.complete()
            step7.content = f"Category normalization completed. {normalized_count} categories were normalized to standard taxonomy."
            yield await send_reasoning_step(step7)
            
            # Step 8: Database Storage
            step8 = ReasoningStep(
                "Storing Examination Requests",
                "Saving structured requests to database with proper security and audit trails...",
                "check"
            )
            yield await send_reasoning_step(step8)
            await asyncio.sleep(1)
            
            # Prepare database rows
            rows = []
            for r in rfis:
                row = {
                    'user_id': user['uid'],
                    'study_id': study_id,
                    'title': r.get('title') or (r.get('description') or '')[:120] or 'Request',
                    'description': r.get('description') or '',
                    'category': r.get('category'),
                    'status': 'not_started',
                    'source': 'fdl',
                    'request_code': r.get('request_code'),
                    'priority': r.get('priority') if isinstance(r.get('priority'), int) else 0,
                    'regulatory_deadline': r.get('regulatory_deadline'),
                    'internal_due_date': None,
                    'owner': None,
                    'reviewer': None
                }
                rows.append(row)
            
            # Insert into database
            try:
                inserted = []
                if rows:
                    res = supabase.table('exam_requests').insert(rows).execute()
                    inserted = res.data or []
                
                step8.complete()
                step8.content = f"Successfully stored {len(inserted)} examination requests in database."
                yield await send_reasoning_step(step8)
                
                # Send completion with results
                completion_data = {
                    "created": len(inserted),
                    "requests": inserted,
                    "processing_time": "Real-time with streaming feedback",
                    "ai_model": settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL
                }
                yield await send_completion(completion_data)
                
            except Exception as e:
                step8.error(f"Database storage failed: {str(e)}")
                yield await send_reasoning_step(step8)
                yield await send_error(f"Database storage failed: {str(e)}")
                return
                
        except Exception as e:
            yield await send_error(f"Unexpected error: {str(e)}")
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


@router.post("/fdl/ingest-text")
async def stream_fdl_ingest_text(payload: Dict[str, Any], user=Depends(get_current_user)):
    """Stream FDL ingestion from provided text: persist to exam_documents, then analyze text-only."""
    study_id = payload.get('study_id')
    text = (payload.get('text') or '').strip()
    if not study_id or not text:
        raise HTTPException(status_code=400, detail="text and study_id are required")

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Connected
            yield "data: {\"type\": \"connected\"}\n\n"

            # Step A: Create document row from text
            sA = ReasoningStep("Creating document from text", "Storing simulated First Day Letter text...", "file")
            yield await send_reasoning_step(sA)
            await asyncio.sleep(0.5)
            try:
                row = {
                    'id': str(uuid.uuid4()),
                    'filename': 'simulated_fdl.txt',
                    'file_size': len(text.encode('utf-8')),
                    'file_type': 'text/plain',
                    'file_path': None,
                    'upload_url': '',
                    'study_id': study_id,
                    'user_id': user['uid'],
                    'processing_status': 'uploaded',
                }
                res = supabase.table('exam_documents').insert(row).execute()
                if not res.data:
                    raise Exception("Insert failed")
                doc = res.data[0]
                # Best effort to set extracted_text and source
                try:
                    upd = supabase.table('exam_documents').update({'extracted_text': text, 'source': 'simulated'}).eq('id', doc['id']).eq('user_id', user['uid']).execute()
                    if upd.data and len(upd.data) > 0:
                        doc = upd.data[0]
                except Exception as uex:
                    print(f"[streaming] warn: failed to set extracted_text/source: {uex}")
                sA.complete(); sA.content = f"Document stored (id: {doc['id']}). Proceeding to analysis."
                yield await send_reasoning_step(sA)
            except Exception as ex:
                sA.error(f"Failed to store text: {str(ex)}")
                yield await send_reasoning_step(sA)
                yield await send_error(f"Failed to store simulated text: {str(ex)}")
                return

            # Reuse analysis pipeline by calling stream_fdl_ingest internals using stored text
            # We inline minimal steps: initialize + extraction prompts with text
            # Step B: Initialize model
            sB = ReasoningStep("Initializing GPT Analysis Engine", "Preparing regulatory examination context...", "brain")
            yield await send_reasoning_step(sB)
            await asyncio.sleep(0.5)
            client = openai_manager.get_client()
            if not client:
                sB.error("OpenAI client not available")
                yield await send_reasoning_step(sB)
                yield await send_error("AI analysis service unavailable")
                return
            sB.complete(); sB.content = f"Model {settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL} ready."; yield await send_reasoning_step(sB)

            # Step C: Structure analysis
            sC = ReasoningStep("Analyzing Document Structure", "Identifying sections and headers from text...", "search")
            yield await send_reasoning_step(sC)
            exam_model = settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL
            structure_prompt = (
                "Analyze this First Day Letter text and identify its structure. "
                "List the main sections and where examination requests likely appear."
            )
            structure_params = {
                "model": exam_model,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": text[:150000]},
                    {"type": "input_text", "text": structure_prompt}
                ]}],
                "instructions": structure_prompt,
                "max_output_tokens": 1000,
                "stream": True,
                "store": True,
            }
            if exam_model.startswith("gpt-5"):
                structure_params["reasoning"] = {"effort": "low"}
                structure_params["text"] = {"verbosity": "medium"}
            structure_response = client.responses.create(**structure_params)
            structure_content = ""
            if hasattr(structure_response, '__iter__'):
                for chunk in structure_response:
                    if hasattr(chunk, 'output') and chunk.output:
                        for item in chunk.output:
                            if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                                for c in item.content:
                                    if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                        structure_content += c.text
                                        sC.content = f"Document structure: {structure_content[:100]}..."; yield await send_reasoning_step(sC)
                                        await asyncio.sleep(0.05)
            sC.complete(); sC.content = f"Structure analyzed ({len(structure_content)} chars)"; sC.details = structure_content; yield await send_reasoning_step(sC)

            # Step D: Category analysis
            sD = ReasoningStep("Identifying Risk Categories", "Scanning for regulatory domains...", "search")
            yield await send_reasoning_step(sD)
            category_prompt = (
                "Identify the main regulatory risk categories in the text."
            )
            category_params = {
                "model": exam_model,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": text[:150000]},
                    {"type": "input_text", "text": f"Context: {structure_content[:500]}\n\n{category_prompt}"}
                ]}],
                "instructions": category_prompt,
                "max_output_tokens": 1500,
                "stream": True,
                "store": True,
            }
            if exam_model.startswith("gpt-5"):
                category_params["reasoning"] = {"effort": "low"}
                category_params["text"] = {"verbosity": "medium"}
            category_response = client.responses.create(**category_params)
            category_content = ""
            if hasattr(category_response, '__iter__'):
                for chunk in category_response:
                    if hasattr(chunk, 'output') and chunk.output:
                        for item in chunk.output:
                            if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                                for c in item.content:
                                    if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                        category_content += c.text
                                        sD.content = f"Found categories: {category_content[:100]}..."; yield await send_reasoning_step(sD)
                                        await asyncio.sleep(0.05)
            sD.complete(); sD.content = f"Categories identified ({len(category_content)} chars)"; sD.details = category_content; yield await send_reasoning_step(sD)

            # Step E: Extraction
            sE = ReasoningStep("Extracting Examination Requests", "Generating structured RFI list...", "lightbulb")
            yield await send_reasoning_step(sE)
            extraction_prompt = (
                "Extract all examination requests with fields: title, description, category, "
                "request_code, regulatory_deadline (ISO), priority (0-3). Return valid JSON."
            )
            extraction_params = {
                "model": exam_model,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": text[:150000]},
                    {"type": "input_text", "text": f"Context:\nStructure: {structure_content[:300]}\nCategories: {category_content[:300]}\n\n{extraction_prompt}"}
                ]}],
                "instructions": extraction_prompt,
                "max_output_tokens": 6000,
                "text": {"format": {"type": "json_object"}},
                "stream": False,
                "store": True,
            }
            if exam_model.startswith("gpt-5"):
                extraction_params["reasoning"] = {"effort": "medium"}
                extraction_params["text"] = {"verbosity": "high"}
            resp = client.responses.create(**extraction_params)
            sE.complete(); sE.content = "Request extraction completed"; yield await send_reasoning_step(sE)

            # Process JSON
            content = ""
            if getattr(resp, 'output', None):
                for it in resp.output:
                    if getattr(it, 'type', '') == 'message' and getattr(it, 'content', None):
                        for c in it.content:
                            if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                content = c.text; break
                    if content: break
            if not content and hasattr(resp, 'output_text'):
                content = resp.output_text
            import json as _json
            try:
                parsed = _json.loads(content)
                rfis = parsed.get('requests') if isinstance(parsed, dict) else parsed
                if not isinstance(rfis, list):
                    rfis = []
            except Exception as pe:
                yield await send_error(f"Failed to parse AI response: {pe}")
                return

            # Normalize and store
            VALID_CATEGORIES = {
                'Credit Risk', 'Interest Rate Risk', 'Liquidity Risk', 'Price Risk',
                'Operational Risk', 'Compliance Risk', 'Strategic Risk',
                'Governance/Management Oversight', 'IT/Cybersecurity', 'BSA/AML',
                'Capital Adequacy/Financial Reporting', 'Asset Management/Trust'
            }
            CATEGORY_MAPPING = {
                'Corporate Governance': 'Governance/Management Oversight',
                'Governance': 'Governance/Management Oversight',
                'Management': 'Governance/Management Oversight',
                'Technology Risk': 'IT/Cybersecurity',
                'Cyber Risk': 'IT/Cybersecurity',
                'Technology': 'IT/Cybersecurity',
                'Market Risk': 'Price Risk',
                'Legal Risk': 'Compliance Risk',
                'Reputation Risk': 'Operational Risk',
                'Reputational Risk': 'Operational Risk',
                'Model Risk': 'Operational Risk'
            }
            def normalize_category(category: str) -> str:
                if not category:
                    return 'Operational Risk'
                if category in VALID_CATEGORIES:
                    return category
                if category in CATEGORY_MAPPING:
                    return CATEGORY_MAPPING[category]
                return 'Operational Risk'
            for r in rfis:
                r['category'] = normalize_category(r.get('category'))

            # Insert
            rows = []
            for r in rfis:
                rows.append({
                    'user_id': user['uid'],
                    'study_id': study_id,
                    'title': r.get('title') or (r.get('description') or '')[:120] or 'Request',
                    'description': r.get('description') or '',
                    'category': r.get('category'),
                    'status': 'not_started',
                    'source': 'fdl',
                    'request_code': r.get('request_code'),
                    'priority': r.get('priority') if isinstance(r.get('priority'), int) else 0,
                    'regulatory_deadline': r.get('regulatory_deadline'),
                    'internal_due_date': None,
                    'owner': None,
                    'reviewer': None
                })
            inserted = []
            if rows:
                res = supabase.table('exam_requests').insert(rows).execute()
                inserted = res.data or []

            yield await send_completion({"created": len(inserted), "requests": inserted})

        except Exception as e:
            yield await send_error(f"Unexpected error: {str(e)}")

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


@router.post("/fdl/simulate")
async def simulate_fdl(payload: Dict[str, Any], user=Depends(get_current_user)):
    """Stream generation of a simulated First Day Letter using the exam model."""
    regulator = (payload.get("regulator") or "OCC").strip() or "OCC"
    focus_areas = payload.get("focus_areas") or []
    additional_focus = payload.get("additional_focus") or ""
    organization = payload.get("organization") or "Your Bank"

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            yield "data: {\"type\": \"connected\"}\n\n"

            step = ReasoningStep(
                "Generating First Day Letter",
                f"Preparing a realistic {regulator} first-day letter with selected focus areas...",
                "file"
            )
            yield await send_reasoning_step(step)

            client = openai_manager.get_client()
            if not client:
                yield await send_error("AI generation service unavailable")
                return

            exam_model = settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL

            system_prompt = (
                "You are Oliver, producing a professional First Day Letter (FDL) that a regulator would send "
                "to a bank prior to an on-site or remote examination. Write a realistic, concise, and formal "
                "letter in well-structured markdown. Include: date, recipient, greeting, a brief overview of the "
                "examination scope, bulletized or enumerated requests by domain, logistics (due dates, contact, "
                "format expectations), and a professional sign-off. Keep it readable and organized."
            )

            areas_str = ", ".join([str(a) for a in focus_areas]) if focus_areas else "general examination domains"
            user_prompt = (
                f"Regulator: {regulator}. Organization: {organization}.\n"
                f"Primary focus areas: {areas_str}.\n"
                f"Additional considerations: {additional_focus}\n\n"
                "Please draft the First Day Letter accordingly. Use markdown for headings and numbered lists."
            )

            # Stream using official Responses streaming interface for reliable deltas
            full_text = ""
            try:
                stream_params = {
                    "model": exam_model,
                    "input": [{
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    }],
                    "instructions": system_prompt,
                    "max_output_tokens": 4000,
                    "store": False,
                }
                if exam_model.startswith("gpt-5"):
                    stream_params["reasoning"] = {"effort": "low"}
                    stream_params["text"] = {"verbosity": "medium"}

                # Use streaming context manager
                with client.responses.stream(**stream_params) as resp_stream:
                    for event in resp_stream:
                        ev_type = getattr(event, 'type', '')
                        if ev_type == 'response.output_text.delta':
                            delta = getattr(event, 'delta', None)
                            if delta:
                                full_text += delta
                                yield await send_letter_chunk(delta)
                        elif ev_type == 'response.error':
                            err = getattr(event, 'error', None)
                            msg = str(err) if err else 'Unknown error'
                            yield await send_error(f"OpenAI streaming error: {msg}")
                            return
                        elif ev_type == 'response.completed':
                            # Completed normally
                            break
            except Exception as stream_ex:
                # Fallback to non-streaming create if stream not supported
                try:
                    request_params = {
                        "model": exam_model,
                        "input": [{
                            "role": "user",
                            "content": [{"type": "input_text", "text": user_prompt}],
                        }],
                        "instructions": system_prompt,
                        "max_output_tokens": 4000,
                        "store": False,
                        "stream": False,
                    }
                    if exam_model.startswith("gpt-5"):
                        request_params["reasoning"] = {"effort": "low"}
                        request_params["text"] = {"verbosity": "medium"}
                    fallback_resp = client.responses.create(**request_params)
                    content = ""
                    if fallback_resp.output:
                        for item in fallback_resp.output:
                            if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                                for c in item.content:
                                    if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                        content = c.text
                                        break
                            if content:
                                break
                    full_text = content
                    if full_text:
                        yield await send_letter_chunk(full_text)
                except Exception as final_ex:
                    yield await send_error(f"Simulation failed: {str(final_ex)}")
                    return

            # Finish
            step.complete()
            step.content = "Letter generation completed."
            yield await send_reasoning_step(step)
            yield await send_completion({"letter": full_text, "ai_model": exam_model})

        except Exception as e:
            yield await send_error(f"Simulation failed: {str(e)}")

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# ====================================================================
# Generic Agent Runner (tool-calling skeleton with streaming UX)
# ====================================================================

@router.post("/agent/run")
async def agent_run(payload: Dict[str, Any], user=Depends(get_current_user)):
    """Stream a simple autonomous agent that plans, calls demo tools, and reports results.

    Request payload shape (flexible):
      { "goal": str, "url": Optional[str], "study_id": Optional[str] }
    """
    goal = (payload.get("goal") or "").strip() or "Explore and demonstrate tool-calling"
    url = (payload.get("url") or "").strip() or None

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Connected event
            yield "data: {\"type\": \"connected\"}\n\n"

            # Step: Understand goal
            s1 = ReasoningStep(
                "Understanding the goal",
                f"Interpreting user goal: '{goal}' and preparing a lightweight plan...",
                "brain"
            )
            yield await send_reasoning_step(s1)
            await asyncio.sleep(0.3)
            s1.complete()
            s1.content = "Goal parsed. I'll create a short plan and pick the first tool."
            yield await send_reasoning_step(s1)

            # Step: Plan
            plan = [
                "Draft plan with milestones",
                "Call demo tools to gather a small piece of data",
                "Summarize what happened and return a result"
            ]
            s2 = ReasoningStep(
                "Creating a plan",
                "Plan: 1) Draft plan 2) Run one demo tool 3) Summarize",
                "lightbulb",
                details="\n".join(f"- {p}" for p in plan)
            )
            yield await send_reasoning_step(s2)
            await asyncio.sleep(0.3)
            s2.complete()
            s2.content = "Plan ready. Proceeding to tool execution."
            yield await send_reasoning_step(s2)

            # Tool execution branch
            if url:
                # Tool: fetch_url_title
                yield await send_tool_call("fetch_url_title", {"url": url})
                try:
                    import httpx, re
                    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                        r = await client.get(url)
                        text = r.text[:20000] if r.text else ""
                        m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
                        title = m.group(1).strip() if m else None
                        meta = {
                            "status": r.status_code,
                            "title": title,
                            "bytes": len(r.content) if r.content else 0
                        }
                        yield await send_tool_result("fetch_url_title", meta)
                        await asyncio.sleep(0.2)
                        s3 = ReasoningStep(
                            "Analyzing fetched page",
                            f"HTTP {meta['status']}. Title: {meta['title'] or 'N/A'}",
                            "search",
                            details=str(meta)
                        )
                        yield await send_reasoning_step(s3)
                        s3.complete()
                        yield await send_reasoning_step(s3)
                except Exception as e:
                    yield await send_tool_result("fetch_url_title", {"error": str(e)})
            else:
                # Tool: sleep
                duration = 1
                yield await send_tool_call("sleep", {"seconds": duration})
                await asyncio.sleep(duration)
                yield await send_tool_result("sleep", {"ok": True, "slept": duration})

            # Optional: EXA web search + summarization
            if settings.EXA_API_KEY:
                try:
                    s_exa = ReasoningStep(
                        "Searching the web (EXA)",
                        "Querying EXA for top results and metadata...",
                        "search"
                    )
                    yield await send_reasoning_step(s_exa)
                    import httpx
                    query = goal if goal else (f"site:{url}" if url else "Oliver compliance agent")
                    async with httpx.AsyncClient(timeout=20) as client:
                        exa_headers = {"x-api-key": settings.EXA_API_KEY, "Content-Type": "application/json"}
                        exa_body = {"query": query, "numResults": 5}
                        r = await client.post("https://api.exa.ai/search", headers=exa_headers, json=exa_body)
                        results = r.json() if r.status_code < 400 else {"error": r.text}
                        yield await send_tool_call("exa_search", {"query": query})
                        yield await send_tool_result("exa_search", results)
                        s_exa.complete(); s_exa.content = "Got search results"; s_exa.details = str(results)[:800]
                        yield await send_reasoning_step(s_exa)

                    # Summarize via OpenAI
                    client = openai_manager.get_client()
                    if client and results and isinstance(results, dict) and results.get("results"):
                        docs = results.get("results", [])
                        top_snippets = []
                        for d in docs:
                            snippet = (d.get("title") or "") + "\n" + (d.get("text") or d.get("snippet") or "")
                            top_snippets.append(snippet[:1000])
                        summary_input = "\n\n".join(top_snippets[:5])
                        instr = (
                            "Summarize the key points, with 3 bullets and 1-2 risks/opportunities."
                        )
                        req = {
                            "model": settings.OPENAI_MODEL,
                            "input": [{"role": "user", "content": [{"type": "input_text", "text": summary_input}]}],
                            "instructions": instr,
                            "max_output_tokens": 800,
                            "store": False,
                        }
                        if settings.OPENAI_MODEL.startswith("gpt-5"):
                            req["reasoning"] = {"effort": "low"}
                            req["text"] = {"verbosity": "medium"}
                        resp = client.responses.create(**req)
                        text = ""
                        if getattr(resp, 'output', None):
                            for it in resp.output:
                                if getattr(it, 'type', '') == 'message' and getattr(it, 'content', None):
                                    for c in it.content:
                                        if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                            text = c.text; break
                                if text: break
                        if not text and hasattr(resp, 'output_text'):
                            text = resp.output_text
                        yield await send_tool_result("summarize", {"summary": text})
                        s_sum = ReasoningStep("Drafting summary", "Created a concise brief from search results", "lightbulb", text)
                        s_sum.complete();
                        yield await send_reasoning_step(s_sum)
                except Exception as ex_err:
                    yield await send_tool_result("exa_search", {"error": str(ex_err)})

            # Completion summary
            summary = {
                "goal": goal,
                "used_tool": "fetch_url_title" if url else "sleep",
                "note": "This is a working skeleton. Swap in real tools as needed."
            }

            s4 = ReasoningStep("Summarizing outcome", "Packaging results and finishing up...", "check")
            yield await send_reasoning_step(s4)
            await asyncio.sleep(0.2)
            s4.complete()
            s4.content = "Done. Emitting completion event."
            yield await send_reasoning_step(s4)
            yield await send_completion(summary)

        except Exception as e:
            yield await send_error(f"Agent failed: {str(e)}")

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )
