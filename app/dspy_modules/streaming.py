import dspy
import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator
from .signatures import GeneralAssistant, ComplianceAnalysis, DocumentAnalysis

class OliverStatusMessageProvider(dspy.streaming.StatusMessageProvider):
    """Custom status message provider for Oliver assistant operations."""
    
    def lm_start_status_message(self, instance, inputs):
        """Status message when starting LLM call."""
        return "🤖 Analyzing your request..."
    
    def lm_end_status_message(self, outputs):
        """Status message when LLM call completes."""
        return "✅ Analysis complete, generating response..."
    
    def module_start_status_message(self, instance, inputs):
        """Status message when starting module execution."""
        module_name = instance.__class__.__name__
        if "Compliance" in module_name:
            return "🔍 Running compliance analysis..."
        elif "Document" in module_name:
            return "📄 Analyzing document content..."
        else:
            return "🧠 Processing your query..."
    
    def module_end_status_message(self, outputs):
        """Status message when module execution completes."""
        return "✨ Response ready!"

class StreamingOliverAssistant(dspy.Module):
    """Streaming version of Oliver Assistant with proper DSPy streaming support."""
    
    def __init__(self):
        super().__init__()
        # Initialize the modules
        self.general_assistant = dspy.ChainOfThought(GeneralAssistant)
        self.compliance_analyzer = dspy.ChainOfThought(ComplianceAnalysis)
        self.document_analyzer = dspy.Predict(DocumentAnalysis)
        
        # Create streamified versions with simplified listeners (only main output fields)
        self._setup_streaming_modules()
    
    def _setup_streaming_modules(self):
        """Setup streaming versions of all modules with appropriate listeners."""
        status_provider = OliverStatusMessageProvider()
        
        # General assistant streaming - only listen to response field
        self.stream_general = dspy.streamify(
            self.general_assistant,
            stream_listeners=[
                dspy.streaming.StreamListener(signature_field_name="response")
            ],
            status_message_provider=status_provider
        )
        
        # Compliance analyzer streaming - only listen to analysis field  
        self.stream_compliance = dspy.streamify(
            self.compliance_analyzer,
            stream_listeners=[
                dspy.streaming.StreamListener(signature_field_name="analysis")
            ],
            status_message_provider=status_provider
        )
        
        # Document analyzer streaming - only listen to findings field
        self.stream_document = dspy.streamify(
            self.document_analyzer,
            stream_listeners=[
                dspy.streaming.StreamListener(signature_field_name="findings")
            ],
            status_message_provider=status_provider
        )
    
    async def stream_response(
        self, 
        query: str, 
        conversation_history: List[Dict[str, str]] = None, 
        context: str = "", 
        analysis_type: str = "general"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream response using DSPy's streaming capabilities.
        
        Args:
            query: User's current question or request
            conversation_history: List of previous conversation turns
            context: Additional context (optional)
            analysis_type: Type of analysis ("general", "compliance", "document")
            
        Yields:
            Dictionary chunks in Oliver's streaming format
        """
        try:
            # Create dspy.History object from conversation history
            history = self._create_history(conversation_history or [])
            
            # Select appropriate streaming module
            stream_module, result_field = self._get_streaming_module(analysis_type)
            
            # Prepare inputs based on analysis type
            inputs = self._prepare_inputs(query, history, context, analysis_type)
            
            # Stream the response
            full_response = ""
            
            async for chunk in stream_module(**inputs):
                if isinstance(chunk, dspy.streaming.StreamResponse):
                    # Handle streaming tokens for main content
                    field_name = chunk.signature_field_name
                    token_chunk = chunk.chunk
                    
                    if field_name == result_field:
                        # Main response content
                        full_response += token_chunk
                        yield {
                            "type": "content",
                            "content": token_chunk,
                            "done": False,
                            "field": field_name
                        }
                
                elif isinstance(chunk, dspy.streaming.StatusMessage):
                    # Handle status updates
                    yield {
                        "type": "status",
                        "content": chunk.message,
                        "done": False
                    }
                
                elif isinstance(chunk, dspy.Prediction):
                    # Final prediction - extract artifacts and complete
                    artifacts = self._detect_artifacts(full_response, analysis_type)
                    
                    # Send artifacts if any
                    if artifacts:
                        yield {
                            "type": "artifacts",
                            "content": artifacts,
                            "done": False
                        }
                    
                    # Try to extract reasoning from the prediction if available
                    reasoning = ""
                    if hasattr(chunk, 'rationale'):
                        reasoning = chunk.rationale
                    
                    # Final completion message
                    yield {
                        "type": "done",
                        "content": "",
                        "done": True,
                        "metadata": {
                            "analysis_type": analysis_type,
                            "reasoning": reasoning,
                            "conversation_turns": len(conversation_history or []),
                            "full_response": full_response
                        }
                    }
        
        except Exception as e:
            # Handle errors
            yield {
                "type": "error",
                "content": f"Error processing request: {str(e)}",
                "done": True,
                "error": str(e)
            }
    
    def _get_streaming_module(self, analysis_type: str):
        """Get the appropriate streaming module and result field for analysis type."""
        if analysis_type == "compliance":
            return self.stream_compliance, "analysis"
        elif analysis_type == "document":
            return self.stream_document, "findings"
        else:
            return self.stream_general, "response"
    
    def _prepare_inputs(self, query: str, history, context: str, analysis_type: str) -> Dict[str, Any]:
        """Prepare inputs for the streaming module based on analysis type."""
        if analysis_type == "compliance":
            return {
                "query": query,
                "history": history,
                "context": context
            }
        elif analysis_type == "document":
            return {
                "document_content": query,
                "history": history,
                "analysis_type": context or "compliance"
            }
        else:
            return {
                "query": query,
                "history": history
            }
    
    def _create_history(self, conversation_history: List[Dict[str, str]]) -> dspy.History:
        """Convert conversation history to dspy.History format."""
        messages = []
        for turn in conversation_history:
            if "query" in turn and "response" in turn:
                messages.append({
                    "query": turn["query"],
                    "response": turn["response"]
                })
        
        return dspy.History(messages=messages)
    
    def _detect_artifacts(self, response: str, analysis_type: str) -> List[Dict[str, Any]]:
        """Detect if the response suggests generating artifacts."""
        artifacts = []
        response_lower = response.lower()
        
        # Common artifact triggers
        if any(keyword in response_lower for keyword in ['report', 'plan', 'matrix', 'checklist']):
            if analysis_type == "compliance":
                artifacts.append({
                    "type": "compliance-report",
                    "title": "Compliance Analysis Report",
                    "description": "Detailed compliance analysis and recommendations",
                    "suggested": True
                })
            
            if "mra" in response_lower or "remediation" in response_lower:
                artifacts.append({
                    "type": "mra-remediation-plan", 
                    "title": "MRA Remediation Plan",
                    "description": "Action plan for addressing regulatory findings",
                    "suggested": True
                })
            
            if "checklist" in response_lower:
                artifacts.append({
                    "type": "compliance-checklist",
                    "title": "Compliance Checklist", 
                    "description": "Step-by-step compliance verification checklist",
                    "suggested": True
                })
        
        return artifacts

class SyncStreamingAssistant:
    """Synchronous wrapper for cases where async is not available."""
    
    def __init__(self):
        self.async_assistant = StreamingOliverAssistant()
    
    def stream_response(self, query: str, conversation_history: List[Dict[str, str]] = None, context: str = "", analysis_type: str = "general"):
        """Synchronous streaming using DSPy's sync streaming capability."""
        # Create synchronous streaming modules
        status_provider = OliverStatusMessageProvider()
        
        if analysis_type == "compliance":
            stream_module = dspy.streamify(
                self.async_assistant.compliance_analyzer,
                stream_listeners=[
                    dspy.streaming.StreamListener(signature_field_name="analysis")
                ],
                status_message_provider=status_provider,
                async_streaming=False  # Enable sync streaming
            )
            result_field = "analysis"
        elif analysis_type == "document":
            stream_module = dspy.streamify(
                self.async_assistant.document_analyzer,
                stream_listeners=[
                    dspy.streaming.StreamListener(signature_field_name="findings")
                ],
                status_message_provider=status_provider,
                async_streaming=False
            )
            result_field = "findings"
        else:
            stream_module = dspy.streamify(
                self.async_assistant.general_assistant,
                stream_listeners=[
                    dspy.streaming.StreamListener(signature_field_name="response")
                ],
                status_message_provider=status_provider,
                async_streaming=False
            )
            result_field = "response"
        
        # Prepare inputs
        history = self.async_assistant._create_history(conversation_history or [])
        inputs = self.async_assistant._prepare_inputs(query, history, context, analysis_type)
        
        # Stream synchronously
        full_response = ""
        
        for chunk in stream_module(**inputs):
            if isinstance(chunk, dspy.streaming.StreamResponse):
                field_name = chunk.signature_field_name
                token_chunk = chunk.chunk
                
                if field_name == result_field:
                    full_response += token_chunk
                    yield {
                        "type": "content",
                        "content": token_chunk,
                        "done": False,
                        "field": field_name
                    }
            
            elif isinstance(chunk, dspy.streaming.StatusMessage):
                yield {
                    "type": "status",
                    "content": chunk.message,
                    "done": False
                }
            
            elif isinstance(chunk, dspy.Prediction):
                artifacts = self.async_assistant._detect_artifacts(full_response, analysis_type)
                
                if artifacts:
                    yield {
                        "type": "artifacts",
                        "content": artifacts,
                        "done": False
                    }
                
                # Try to extract reasoning if available
                reasoning = ""
                if hasattr(chunk, 'rationale'):
                    reasoning = chunk.rationale
                
                yield {
                    "type": "done",
                    "content": "",
                    "done": True,
                    "metadata": {
                        "analysis_type": analysis_type,
                        "reasoning": reasoning,
                        "conversation_turns": len(conversation_history or []),
                        "full_response": full_response
                    }
                }

# Global instances
streaming_assistant = StreamingOliverAssistant()
sync_streaming_assistant = SyncStreamingAssistant() 