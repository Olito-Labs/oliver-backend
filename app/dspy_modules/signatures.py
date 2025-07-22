import dspy

class GeneralAssistant(dspy.Signature):
    """You are Oliver, an AI assistant specialized in compliance and regulatory matters for financial institutions. 
    You help with questions about compliance, regulations, risk management, and general business topics.
    Provide helpful, accurate, and professional responses."""
    
    query = dspy.InputField(desc="User's question or request")
    response = dspy.OutputField(desc="Helpful and professional response to the user's query")

class ComplianceAnalysis(dspy.Signature):
    """Analyze compliance-related queries and provide expert guidance for financial institutions."""
    
    query = dspy.InputField(desc="Compliance question or regulatory concern")
    context = dspy.InputField(desc="Additional context about the institution or situation", default="")
    analysis = dspy.OutputField(desc="Detailed compliance analysis and recommendations")

class DocumentAnalysis(dspy.Signature):
    """Analyze documents for compliance and regulatory requirements."""
    
    document_content = dspy.InputField(desc="Content of the document to analyze")
    analysis_type = dspy.InputField(desc="Type of analysis needed (compliance, risk, gap analysis)")
    findings = dspy.OutputField(desc="Key findings and recommendations from the analysis") 