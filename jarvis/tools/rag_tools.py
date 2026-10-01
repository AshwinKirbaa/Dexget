import os
from jarvis.tools.base import RiskLevel, Tool, ToolResult

def rag_ingest(file_path: str) -> ToolResult:
    from jarvis.memory.rag import rag_system
    
    # Resolve relative paths or ~ if needed
    if file_path.startswith("~"):
        file_path = os.path.expanduser(file_path)
        
    # Search common locations if absolute path not given
    if not os.path.isabs(file_path):
        candidates = [
            file_path,
            os.path.join(os.path.expanduser("~/Desktop"), file_path),
            os.path.join(os.path.expanduser("~/Documents"), file_path),
            os.path.join(os.path.expanduser("~/Downloads"), file_path),
        ]
        found = False
        for c in candidates:
            if os.path.exists(c):
                file_path = c
                found = True
                break
        if not found:
            return ToolResult(False, error="not_found", observation=f"Could not find {file_path}")
            
    try:
        rag_system.ingest_document(file_path)
        return ToolResult(True, observation=f"Ingested {os.path.basename(file_path)} into memory.")
    except Exception as e:
        return ToolResult(False, error=str(e), observation=f"Failed to ingest {file_path}: {e}")

def register(registry) -> None:
    registry.register(Tool(
        name="rag_ingest",
        description="Ingest a document into JARVIS memory (RAG). Supports PDF, DOCX, TXT, MD, CSV, etc.",
        parameters={
            "file_path": {"type": "str", "required": True}
        },
        risk_level=RiskLevel.LOW,
        func=rag_ingest,
        category="memory"
    ))
