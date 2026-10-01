import os
from jarvis.semantic.intent_schema import SemanticDecision, SemanticIntent

def classify_intent(text: str, context_str: str = "") -> SemanticDecision:
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise ValueError("TYPESAFE_API_KEY not configured")

    import typesafe_sdk
    client = typesafe_sdk.TypeSafeClient(api_key=api_key)
    
    # Build a combined text state
    state = f"Command: {text}\nContext:\n{context_str}"
    
    # We must provide questions to system_one
    intent_keys = {k: None for k in SemanticIntent.__members__.keys()}
    questions = {
        "intent_decision": {
            "type": "choice",
            "instructions": "Classify the primary intent of the user's command. Map complex, multi-step requests, or tasks requiring internet search to AGENT_TASK. Ignore conversational filler words.",
            "criteria": intent_keys
        }
    }
    
    try:
        # system_one will map the response to the response_model
        response = client.system_one(
            state=state,
            questions=questions,
            response_model=SemanticDecision
        )
        return response
    except Exception as e:
        raise RuntimeError(f"Jev API classification failed: {e}")
