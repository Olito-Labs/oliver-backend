import dspy

class GeneralAssistant(dspy.Signature):
    """You are Oliver, an AI assistant specialized in compliance and regulatory matters for financial institutions. 
    You help with questions about compliance, regulations, risk management, and general business topics.
    Use the conversation history to maintain context and provide consistent, helpful responses."""
    
    query = dspy.InputField(desc="User's current question or request")
    history = dspy.InputField(desc="Previous conversation turns for context")
    response = dspy.OutputField(desc="Helpful and professional response that considers conversation history")

class ComplianceAnalysis(dspy.Signature):
    """Analyze compliance-related queries and provide expert guidance for financial institutions.
    Consider previous discussion points and build upon earlier analysis when relevant."""
    
    query = dspy.InputField(desc="Current compliance question or regulatory concern")
    history = dspy.InputField(desc="Previous conversation context")
    context = dspy.InputField(desc="Additional context about the institution or situation", default="")
    analysis = dspy.OutputField(desc="Detailed compliance analysis that builds on previous discussion")

class DocumentAnalysis(dspy.Signature):
    """Analyze documents for compliance and regulatory requirements.
    Reference earlier document discussions and maintain analytical consistency."""
    
    document_content = dspy.InputField(desc="Content of the document to analyze")
    history = dspy.InputField(desc="Previous conversation and analysis context")
    analysis_type = dspy.InputField(desc="Type of analysis needed (compliance, risk, gap analysis)")
    findings = dspy.OutputField(desc="Key findings that consider previous analysis and conversation context") 