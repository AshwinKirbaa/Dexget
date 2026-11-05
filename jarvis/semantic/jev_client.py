import os
import threading
from jarvis.semantic.intent_schema import SemanticDecision, SemanticIntent

_client = None
_client_key = None
_client_lock = threading.Lock()


def is_configured() -> bool:
    return bool(os.environ.get("TYPESAFE_API_KEY", "").strip())


def _get_client():
    """Reuse the HTTP client so semantic routing avoids connection setup."""
    global _client, _client_key
    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("TYPESAFE_API_KEY not configured")
    with _client_lock:
        if _client is None or _client_key != api_key:
            import typesafe_sdk
            timeout = float(os.environ.get("JARVIS_SEMANTIC_TIMEOUT_SECONDS", "2.0"))
            try:
                _client = typesafe_sdk.TypeSafeClient(api_key=api_key, timeout=timeout)
            except TypeError:
                # Compatibility with older SDKs and lightweight test doubles.
                _client = typesafe_sdk.TypeSafeClient(api_key=api_key)
            _client_key = api_key
    return _client

def classify_intent(text: str, context_str: str = "") -> SemanticDecision:
    client = _get_client()
    
    # Build a combined text state
    # A small context window improves follow-up understanding without adding
    # avoidable classification latency.
    max_context = int(os.environ.get("JARVIS_JEV_CONTEXT_CHARS", "1200"))
    state = f"Command: {text}\nContext:\n{context_str[-max_context:]}"
    
    # We must provide questions to system_one
    intent_keys = {k: None for k in SemanticIntent.__members__.keys()}
    questions = {
        "intent_decision": {
            "type": "choice",
            "instructions": (
                "Classify the user's meaning, not exact wording. Understand polite, indirect, "
                "conversational, multilingual, and follow-up phrasing using the supplied context. "
                "Use the most specific intent. Map general questions to KNOWLEDGE_QUERY, casual "
                "dialogue to CONVERSATION, and complex or multi-step work to AGENT_TASK. Extract "
                "all useful entities into the response fields. Never invent missing destructive "
                "action parameters."
            ),
            "criteria": intent_keys
        }
    }
    
    try:
        # system_one will map the response to the response_model
        response = client.system_one(
            state=state,
            questions=questions,
            response_model=SemanticDecision,
            timeout=float(os.environ.get("JARVIS_SEMANTIC_TIMEOUT_SECONDS", "2.0")),
        )
        return response
    except Exception as e:
        raise RuntimeError(f"Jev API classification failed: {e}")
