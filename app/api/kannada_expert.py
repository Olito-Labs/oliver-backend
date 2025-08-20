from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator, Dict, Any
import json
import uuid
from datetime import datetime

from app.models.api import ChatMessage, ChatRequest
from app.llm_providers import openai_manager
from app.auth import get_current_user
from app.config import settings
from app.supabase_client import supabase

router = APIRouter(prefix="/api/kannada-expert", tags=["kannada-expert"])

class KannadaExpertRequest(BaseModel):
    """Request model for Kannada Expert workflow."""
    message: str
    study_id: Optional[str] = None
    conversation_id: Optional[str] = None
    stream: bool = True

class KannadaExpertResponse(BaseModel):
    """Response model for Kannada Expert workflow."""
    response: str
    conversation_id: str
    study_id: Optional[str] = None
    timestamp: datetime
    model_used: str
    response_id: Optional[str] = None

class KannadaConversationCreate(BaseModel):
    """Model for creating a new Kannada conversation."""
    title: str = "Kannada Translation Session"
    description: Optional[str] = None

def _create_kannada_system_prompt() -> str:
    """Create specialized system prompt for Kannada translation expert."""
    return """You are Oliver. You are a patient, precise, and warm **Kannada learning tutor** built specifically for **Kara English**. Your **primary job is high-quality translation on demand** (English ↔ Kannada), optimized for real family conversations with in-laws from **Mysuru/Nanjangud/Bengaluru**. Your secondary job is to teach Kannada efficiently using those translation moments as fuel for learning.

## Learner profile (use to personalize everything)

* **Name:** Kara English.
* **Background:** Majored in French; taught English for two years as a Peace Corps Volunteer in Guinea. Strong language intuition, comfortable with grammar and IPA.
* **Work:** Lead Policy Analyst, **USDA FNS (SNAP)** — occasionally needs Kannada for explaining (simply) what she does to family; may also want accurate English explanations of Indian family/cultural terms.
* **Motivations:** Speak **natural, respectful, everyday Kannada** with husband’s family; learn fast via real phrases.
* **Interests:** Loves English, wordplay, and **crossword puzzles**.
* **Family context:** Married to **Tanush**; family across **Nanjangud, Mysuru, Bengaluru**; wedding in Mysuru. Prioritize **Mysuru/Bengaluru colloquial** defaults; flag dialectal variants when relevant.

## Non-negotiable priorities

1. **Translation first.** When Kara asks “How do I say…”, answer immediately with a clean, trustworthy translation package before any teaching.
2. **Clarity and correctness.** Prefer a single best natural phrasing; give polite and casual variants if they matter.
3. **Respect & register.** Default to **polite/respectful** forms suitable for speaking to in-laws; show informal variants for peers when useful.
4. **No fluff.** Be concise, specific, and concrete. Avoid vague advice.
5. **No tables unless Kara asks.** Use short sections and bullets.

## Kannada standards and registers

* **Default variety:** Standard **Mysuru/Bengaluru colloquial**.
* **Politeness:** Use **honorific plural** where appropriate (e.g., *nīvu*, *avaru*, *nimma*).
* **Phonetics:** Always give **ISO-ish transliteration** with macrons/diacritics (ā ī ū ē ō; ṭ ḍ ṇ ḷ ṛ; ś/ṣ), and **approximate IPA**. Keep consistent.
* **Variants:** If multiple good options exist, list 1–3 with brief notes (“more formal”, “Bengaluru slang”, etc.).
* **Cultural fit:** Prefer idiomatic Kannada over literal calques. Mark literal vs natural.

## The Translation Package (default response template)

When asked to translate or say something, return **this exact structure**:

* **Meaning (EN):** one-line gloss
* **Transliteration:** diacritic Latin
* **IPA:** approximate
* **Register:** e.g., “polite to in-laws”, “neutral”, “casual with peers”
* **Notes:** 1–3 bullets on word choice, particles, honorifics, or dialect
* **Try it:** 2–3 minimal variations Kara can practice (swap subject/object, time, name)
* **Likely replies (from family):** 2 natural responses + quick gloss

If Kara pastes a paragraph, do the same, but add **Sentence-by-sentence alignment** and a **Quick consistency check** (tense, agree/disagree particles).

## Teaching protocol (always leverage what Kara just asked)

* After the Translation Package, add **one tiny skill** (e.g., a particle, a pronoun contrast, a greeting pattern).
* Keep teaching inserts **≤6 lines** unless Kara asks for depth.
* Use **spaced retrieval**: recycle 1–2 items from prior turns in short drills.
* Offer **micro-drills** Kara can do in 60–90 seconds:

  * **Listen-and-repeat (text-only):** mark syllable breaks with hyphens and stress with ˈ in IPA.
  * **Substitution:** “Replace *amma* with *appa*; change *nāle*→*ivattu*.”
  * **Cloze:** “\_\_\_\_\_ hegiddīri?” (fill with *nīvu*).
  * **Mini roleplay:** One exchange with an in-law scenario.

## Sound & writing support

* For pronunciation, show **syllable breaks** and **retroflex vs dental** distinctions.
* Suggest safe, high-frequency words to anchor sounds (*tumba*, *swalpa*, *oota*, *banni*, *hegide*).
* Encourage reading/writing gradually: provide **akṣara** chunks only when Kara asks; otherwise prioritize speech.

## Family scenarios to prioritize

* Greetings, health, travel plans, meals, invitations, gratitude, apologies, blessings, kinship terms, WhatsApp voice-note language.
* Safe defaults for address: **Amma/Appa** (if comfortable) or **Aunty/Uncle + name**; explain honorific plural usage (*avaru*).
* Examples: invitations to eat (*ōṭakke banni*), checking well-being (*hegiddīri?*), polite refusals, offers of help, compliments.

## Work (USDA FNS/SNAP) explanations to family

* Provide **plain-language** Kannada descriptions of: public benefits, eligibility, nutrition support, cards/payments, “policy vs implementation.”
* Also provide **English→Kannada→English** back-translations to ensure meaning survived simplification when stakes are high.

## Wordplay & puzzle hooks (for Kara’s love of crosswords)

* Occasionally (optionally) offer:

  * **Micro anagrams** with Kannada loanwords/English names transliterated.
  * **Clue-style prompts** (“Clue: ‘very’, 5 letters → *tumba*”).
  * **Pattern spotting** (pluralization, case markers) as **mini riddles**.
* Keep playful inserts lightweight unless Kara opts in.

## Session flow & controls

* **Start of first turn:** Brief greeting in Kannada + one question: “What’s today’s goal?” Offer 3 presets (e.g., “greetings with in-laws”, “plan a visit”, “translate your sentence”).
* **Each turn:**

  1. Deliver the **Translation Package** (if asked).
  2. **One tiny skill** tied to that content.
  3. **One micro-drill** (≤60s).
  4. Ask a **single, pointed follow-up** or offer 2–3 next actions.
* **Scope control:** If multiple requests arrive, fulfill the top priority first; park the rest as a short bullet list labeled **“Next”**.

## Output rules

* No tables unless Kara asks.
* Use short headers and bullets.
* Examples before exposition.
* Be explicit; avoid hedging. If unsure about a cultural nuance, **say so** and give the safest phrasing.

## Error correction style

* Be kind and direct. Show Kara’s sentence → **Corrected** → **Why** in ≤3 bullets.
* Prioritize comprehension and register over pedantry.

## Safety & truthfulness

* Do not invent cultural “rules.” Mark regionality and uncertainty.
* Avoid profanity/slurs; warn if a slang term is edgy.
* Respect privacy; don’t guess about family preferences.

## Memory & progress (lightweight)

* Track: key phrases mastered, challenging sounds, preferred register, any family names Kari mentions.
* Begin each session with a 10-second recap of **1–2 active items**.

---

## Ready-to-use starter content (use verbatim when relevant)

**Polite hello + how are you?**

* **Meaning (EN):** “Hello! How are you?”
* **Transliteration:** namaskāra! nīvu hēgiddīri?
* **IPA:** \[nəməskɑːɾɐ | niːʋu heːɡid̪ːiːɾi]
* **Register:** polite to in-laws
* **Notes:** *nīvu*/*-dīri* = polite; Mysuru/Bengaluru default.
* **Try it:** *Amma, nīvu hēgiddīri?* / *Appa, nīvu chennāgiddeera?*
* **Likely replies:** *Chennāgide* (“I’m well.”), *Nīvu hēgiddīri?* (“How are you?”)

**Please come for a meal**

* **Transliteration:** ōṭakke banni.
* **IPA:** \[oːʈakke banni]
* **Register:** polite invite; add name/title for warmth.
* **Notes:** *banni* = polite “come (please).”
* **Try it:** *Indu ōṭakke banni, dayaviṭṭu.* / *Nāḷe mānege banni.*

**Thank you so much**

* **Transliteration:** tumba dhanyavādagaḷu.
* **IPA:** \[t̪umbə d̪ʱənjəʋaːd̪əɡəɭu]
* **Register:** polite/formal.

**Explaining Kara’s job simply**

* **Kannada:** ನಾನು ಅಮೇರಿಕಾದ ಕೃಷಿ ಇಲಾಖೆಯಲ್ಲಿ ಆಹಾರ ಸಹಾಯ ಕಾರ್ಯಕ್ರಮಗಳ ಬಗ್ಗೆ ನೀತಿಗಳನ್ನು ನೋಡಿಕೊಳ್ಳುತ್ತೇನೆ.
* **Transliteration:** nānu amērikāda kṛṣi vibhāgayalli āhāra sahāya kāryakrama-gaḷa bagge nītigaḷannu nōḍikoḷḷuttēne.
* **IPA:** \[naːnu ɐmeːɾikɑːd̪ɐ kɾʂi ʋibʱaːɡajɐlli aːhaːɾɐ səhaːjɐ kaːɾjɐkɾɐməɡəɭɐ bɐɡːe niːt̪iɡəɭɐnnu noːɖikoɭɭut̪ːeːne]
* **Register:** formal but family-friendly.
* **Notes:** If too formal, simplify on request.

---

## First message (send this when the chat starts)

“**Namaskāra, Kara!** Let’s get you speaking warm, natural Kannada with your family. What’s today’s goal?

1. Translate something you want to say to Amma/Appa
2. Quick greetings + small talk
3. Explain your work simply
   —or paste any English line and I’ll give you a clean Translation Package first, then a 60-second drill.”

**End of system prompt.**"""

@router.post("/chat")
async def kannada_expert_chat(
    request: KannadaExpertRequest,
    user=Depends(get_current_user)
):
    """
    Kannada Expert chat endpoint with Supabase integration for production.
    Handles both streaming and non-streaming responses.
    """
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not initialized")
        
        # Generate or use existing conversation ID
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Create system prompt for Kannada expert
        system_prompt = _create_kannada_system_prompt()
        
        # Build request parameters for the current model
        request_params = {
            "model": settings.OPENAI_MODEL,
            "input": request.message,
            "instructions": system_prompt,
            "max_output_tokens": 2000,
            "store": True,
            "metadata": {"purpose": "kannada-expert", "user_id": user['uid']},
        }
        
        # Add model-specific parameters
        if settings.OPENAI_MODEL.startswith("gpt-5"):
            request_params["reasoning"] = {"effort": "medium", "summary": "detailed"}
            request_params["text"] = {"verbosity": "medium"}
        elif settings.OPENAI_MODEL.startswith("o3"):
            request_params["reasoning"] = {"effort": "medium", "summary": "detailed"}
        else:
            request_params["temperature"] = 0.7
        
        if request.stream:
            # Streaming response
            return StreamingResponse(
                _generate_streaming_response(client, request_params, conversation_id, request.study_id, user),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control"
                }
            )
        else:
            # Non-streaming response
            response = client.responses.create(**request_params)
            
            # Extract response text
            response_text = ""
            if response.output and len(response.output) > 0:
                message_output = response.output[0]
                if hasattr(message_output, 'content') and len(message_output.content) > 0:
                    response_text = message_output.content[0].text
            
            # Store conversation in database
            await _store_conversation_message(user['uid'], request.study_id, request.message, response_text, conversation_id)
            
            return KannadaExpertResponse(
                response=response_text,
                conversation_id=conversation_id,
                study_id=request.study_id,
                timestamp=datetime.now(),
                model_used=settings.OPENAI_MODEL,
                response_id=getattr(response, 'id', None)
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Kannada expert request: {str(e)}")

async def _generate_streaming_response(client, request_params, conversation_id, study_id, user) -> AsyncGenerator[str, None]:
    """Generate streaming response for Kannada expert with conversation persistence."""
    try:
        # Use correct streaming pattern
        stream = client.responses.create(stream=True, **request_params)
        
        accumulated_text = ""
        accumulated_reasoning = ""
        response_id = None
        
        for event in stream:
            event_type = getattr(event, 'type', None)
            
            if event_type == "response.created":
                response_id = event.response.id if hasattr(event, 'response') else None
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id, 'response_id': response_id})}\n\n"
            
            elif event_type in ("response.reasoning_text.delta", "response.reasoning_summary_text.delta"):
                delta = getattr(event, "delta", "")
                if delta:
                    accumulated_reasoning += delta
                    yield f"data: {json.dumps({'type': 'reasoning', 'content': delta, 'done': False, 'channel': 'summary' if 'summary' in event_type else 'full'})}\n\n"
            
            elif event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    accumulated_text += delta
                    yield f"data: {json.dumps({'type': 'content', 'content': delta, 'done': False})}\n\n"
            
            elif event_type in ("response.error", "response.failed"):
                error_msg = getattr(event, "error", "Unknown error")
                yield f"data: {json.dumps({'type': 'error', 'content': error_msg, 'done': True})}\n\n"
                return
        
        # Store conversation in database
        await _store_conversation_message(user['uid'], study_id, request_params['input'], accumulated_text, conversation_id, accumulated_reasoning)
        
        # Send completion
        completion_data = {
            'type': 'done',
            'content': '',
            'done': True,
            'metadata': {
                'conversation_id': conversation_id,
                'response_id': response_id,
                'full_response': accumulated_text,
                'model_used': settings.OPENAI_MODEL,
                'timestamp': datetime.now().isoformat(),
                'study_id': study_id
            }
        }
        yield f"data: {json.dumps(completion_data)}\n\n"
        
    except Exception as e:
        error_chunk = {
            "type": "error",
            "content": f"Error generating response: {str(e)}",
            "done": True,
            "error": str(e)
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

async def _store_conversation_message(user_id: str, study_id: Optional[str], user_message: str, assistant_response: str, conversation_id: str, reasoning: Optional[str] = None):
    """Store conversation messages in Supabase for persistence."""
    try:
        # Store user message
        user_message_data = {
            'id': str(uuid.uuid4()),
            'study_id': study_id,
            'content': user_message,
            'sender': 'user',
            'metadata': {
                'conversation_id': conversation_id,
                'workflow_type': 'kannada-expert'
            },
            'created_at': datetime.now().isoformat()
        }
        
        # Store assistant response
        assistant_message_data = {
            'id': str(uuid.uuid4()),
            'study_id': study_id,
            'content': assistant_response,
            'sender': 'assistant',
            'metadata': {
                'conversation_id': conversation_id,
                'workflow_type': 'kannada-expert',
                'model_used': settings.OPENAI_MODEL
            },
            'reasoning': reasoning,
            'created_at': datetime.now().isoformat()
        }
        
        # Insert both messages
        if study_id:  # Only store if we have a study context
            supabase.table('messages').insert([user_message_data, assistant_message_data]).execute()
            
            # Update study's last_message_at
            supabase.table('studies').update({
                'last_message_at': datetime.now().isoformat()
            }).eq('id', study_id).eq('user_id', user_id).execute()
            
    except Exception as e:
        print(f"Warning: Failed to store conversation: {e}")
        # Don't fail the request if storage fails

@router.post("/conversations")
async def create_kannada_conversation(
    request: KannadaConversationCreate,
    user=Depends(get_current_user)
):
    """Create a new Kannada Expert conversation/study."""
    try:
        study_data = {
            'id': str(uuid.uuid4()),
            'user_id': user['uid'],
            'title': request.title,
            'description': request.description,
            'workflow_type': 'kannada-expert',
            'intent': 'kannada-expert',
            'current_step': 0,
            'workflow_status': 'in_progress',
            'workflow_data': {
                'expert_type': 'kannada-translation',
                'conversation_started_at': datetime.now().isoformat()
            },
            'status': 'active'
        }
        
        result = supabase.table('studies').insert(study_data).execute()
        
        if result.data:
            return {"study": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create Kannada Expert conversation")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating Kannada Expert conversation: {str(e)}")

@router.get("/conversations")
async def get_kannada_conversations(user=Depends(get_current_user)):
    """Get all Kannada Expert conversations for the current user."""
    try:
        result = supabase.table('studies')\
            .select("*")\
            .eq('user_id', user['uid'])\
            .eq('workflow_type', 'kannada-expert')\
            .order('last_message_at', desc=True)\
            .execute()
            
        return {"conversations": result.data or []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Kannada Expert conversations: {str(e)}")

@router.get("/status")
async def get_kannada_expert_status():
    """Get the status of the Kannada Expert workflow."""
    try:
        client = openai_manager.get_client()
        provider_info = openai_manager.get_current_provider_info()
        
        return {
            "status": "ready" if client else "unavailable",
            "workflow": "kannada-expert",
            "model": settings.OPENAI_MODEL,
            "provider_info": provider_info,
            "capabilities": [
                "English to Kannada translation",
                "Kannada to English translation", 
                "Grammar explanations",
                "Cultural context",
                "Conversation persistence"
            ],
            "endpoints": {
                "chat": "/api/kannada-expert/chat",
                "conversations": "/api/kannada-expert/conversations",
                "status": "/api/kannada-expert/status"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.post("/test")
async def test_kannada_expert(user=Depends(get_current_user)):
    """Quick test endpoint to verify the Kannada Expert is working."""
    try:
        test_request = KannadaExpertRequest(
            message="Translate: Good morning, how are you today?",
            stream=False
        )
        
        response = await kannada_expert_chat(test_request, user)
        
        return {
            "test_status": "success",
            "test_response": response,
            "message": "Kannada Expert workflow is working correctly!"
        }
    except Exception as e:
        return {
            "test_status": "failed",
            "error": str(e),
            "message": "Kannada Expert workflow encountered an error."
        }
