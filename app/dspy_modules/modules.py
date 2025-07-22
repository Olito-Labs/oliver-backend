import dspy
from typing import Dict, Any, Optional
from .signatures import GeneralAssistant, ComplianceAnalysis, DocumentAnalysis

class OliverAssistant(dspy.Module):
    """Main assistant module for Oliver - handles general queries and routing."""
    
    def __init__(self):
        super().__init__()
        # Use ChainOfThought for better reasoning
        self.general_assistant = dspy.ChainOfThought(GeneralAssistant)
        self.compliance_analyzer = dspy.ChainOfThought(ComplianceAnalysis)
        self.document_analyzer = dspy.Predict(DocumentAnalysis)
    
    def forward(self, query: str, context: str = "", analysis_type: str = "general") -> Dict[str, Any]:
        """
        Forward method that routes queries to appropriate modules.
        
        Args:
            query: User's question or request
            context: Additional context (optional)
            analysis_type: Type of analysis ("general", "compliance", "document")
        
        Returns:
            Dictionary with response and metadata
        """
        try:
            if analysis_type == "compliance":
                result = self.compliance_analyzer(query=query, context=context)
                return {
                    "response": result.analysis,
                    "type": "compliance_analysis",
                    "reasoning": getattr(result, 'rationale', ''),
                    "artifacts": self._detect_artifacts(result.analysis, "compliance")
                }
            elif analysis_type == "document":
                result = self.document_analyzer(
                    document_content=query,
                    analysis_type=context or "compliance"
                )
                return {
                    "response": result.findings,
                    "type": "document_analysis",
                    "artifacts": self._detect_artifacts(result.findings, "document")
                }
            else:
                # General assistant
                result = self.general_assistant(query=query)
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
    """Wrapper for streaming responses - simulates streaming for now."""
    
    def __init__(self):
        super().__init__()
        self.assistant = OliverAssistant()
    
    async def stream_response(self, query: str, context: str = "", analysis_type: str = "general"):
        """
        Simulate streaming response by yielding chunks.
        In a real implementation, this would integrate with the LLM's streaming API.
        """
        # Get the full response first
        result = self.assistant(query=query, context=context, analysis_type=analysis_type)
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
streaming_assistant = StreamingAssistant() 