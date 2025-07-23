import dspy
from typing import Dict, Any, Optional, List
from .signatures import GeneralAssistant, ComplianceAnalysis, DocumentAnalysis

class OliverAssistant(dspy.Module):
    """Main assistant module for Oliver - handles general queries and routing with conversation memory."""
    
    def __init__(self):
        super().__init__()
        # Use ChainOfThought for better reasoning
        self.general_assistant = dspy.ChainOfThought(GeneralAssistant)
        self.compliance_analyzer = dspy.ChainOfThought(ComplianceAnalysis)
        self.document_analyzer = dspy.Predict(DocumentAnalysis)
    
    def forward(self, query: str, conversation_history: List[Dict[str, str]] = None, context: str = "", analysis_type: str = "general") -> Dict[str, Any]:
        """
        Forward method that routes queries to appropriate modules with conversation memory.
        
        Args:
            query: User's current question or request
            conversation_history: List of previous conversation turns [{"query": "...", "response": "..."}]
            context: Additional context (optional)
            analysis_type: Type of analysis ("general", "compliance", "document")
        
        Returns:
            Dictionary with response and metadata
        """
        try:
            # Create dspy.History object from conversation history
            history = self._create_history(conversation_history or [])
            
            if analysis_type == "compliance":
                result = self.compliance_analyzer(
                    query=query, 
                    history=history,
                    context=context
                )
                return {
                    "response": result.analysis,
                    "type": "compliance_analysis",
                    "reasoning": getattr(result, 'rationale', ''),
                    "artifacts": self._detect_artifacts(result.analysis, "compliance")
                }
            elif analysis_type == "document":
                result = self.document_analyzer(
                    document_content=query,
                    history=history,
                    analysis_type=context or "compliance"
                )
                return {
                    "response": result.findings,
                    "type": "document_analysis",
                    "artifacts": self._detect_artifacts(result.findings, "document")
                }
            else:
                # General assistant
                result = self.general_assistant(
                    query=query, 
                    history=history
                )
                return {
                    "response": result.response,
                    "type": "general_response",
                    "reasoning": getattr(result, 'rationale', ''),
                    "artifacts": self._detect_artifacts(result.response, "general")
                }
        
        except Exception as e:
            return {
                "response": f"I apologize, but I encountered an error processing your request: {str(e)}",
                "type": "error",
                "error": str(e)
            }
    
    def _create_history(self, conversation_history: List[Dict[str, str]]) -> dspy.History:
        """
        Convert conversation history to dspy.History format.
        
        Args:
            conversation_history: List of conversation turns
            
        Returns:
            dspy.History object
        """
        messages = []
        for turn in conversation_history:
            # Each turn should have query and response
            if "query" in turn and "response" in turn:
                messages.append({
                    "query": turn["query"],
                    "response": turn["response"]
                })
        
        return dspy.History(messages=messages)
    
    def _detect_artifacts(self, response: str, analysis_type: str) -> list:
        """
        Detect if the response suggests generating artifacts.
        This is a simple keyword-based detection that can be enhanced later.
        """
        artifacts = []
        response_lower = response.lower()
        
        # Common artifact triggers
        if any(keyword in response_lower for keyword in ['report', 'plan', 'matrix', 'checklist']):
            if analysis_type == "compliance":
                artifacts.append({
                    "type": "compliance-report",
                    "title": "Compliance Analysis Report",
                    "description": "Detailed compliance analysis and recommendations"
                })
            elif "mra" in response_lower or "remediation" in response_lower:
                artifacts.append({
                    "type": "mra-remediation-plan",
                    "title": "MRA Remediation Plan",
                    "description": "Action plan for addressing regulatory findings"
                })
            elif "checklist" in response_lower:
                artifacts.append({
                    "type": "compliance-checklist",
                    "title": "Compliance Checklist",
                    "description": "Step-by-step compliance verification checklist"
                })
        
        return artifacts

class StreamingAssistant(dspy.Module):
    """Wrapper for streaming responses with conversation memory."""
    
    def __init__(self):
        super().__init__()
        self.assistant = OliverAssistant()
    
    async def stream_response(self, query: str, conversation_history: List[Dict[str, str]] = None, context: str = "", analysis_type: str = "general"):
        """
        Simulate streaming response by yielding chunks with conversation memory.
        In a real implementation, this would integrate with the LLM's streaming API.
        """
        # Get the full response first with conversation history
        result = self.assistant(
            query=query, 
            conversation_history=conversation_history,
            context=context, 
            analysis_type=analysis_type
        )
        response = result["response"]
        
        # Yield chunks of the response
        chunk_size = 50  # characters per chunk
        for i in range(0, len(response), chunk_size):
            chunk = response[i:i + chunk_size]
            yield {
                "type": "content",
                "content": chunk,
                "done": False
            }
        
        # Yield artifacts if any
        if result.get("artifacts"):
            yield {
                "type": "artifacts",
                "content": result["artifacts"],
                "done": False
            }
        
        # Signal completion
        yield {
            "type": "done",
            "content": "",
            "done": True,
            "metadata": {
                "analysis_type": result.get("type"),
                "reasoning": result.get("reasoning", "")
            }
        }

# Global assistant instance
assistant = OliverAssistant()
# Import from the new streaming module
from .streaming import streaming_assistant 