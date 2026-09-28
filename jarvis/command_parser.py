import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class WorkflowStep:
    action: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""

@dataclass
class ParsedCommand:
    raw_command: str
    primary_intent: str
    target_application: Optional[str] = None
    target_website: Optional[str] = None
    environment: str = "desktop"
    workflow_steps: List[WorkflowStep] = field(default_factory=list)

def parse_compound_command(cmd: str) -> ParsedCommand:
    cmd = cmd.strip()
    parsed = ParsedCommand(raw_command=cmd, primary_intent="unknown")
    
    # Check for Discord workflow: "open discord, join Hangout voice call and turn camera on"
    m = re.match(r"^(?:open|launch)\s+discord\s*,\s*join\s+(.+?)\s+voice\s+call\s+and\s+turn\s+camera\s+on$", cmd, re.IGNORECASE)
    if m:
        parsed.primary_intent = "application_workflow"
        parsed.target_application = "Discord"
        parsed.environment = "desktop"
        parsed.workflow_steps.append(WorkflowStep(action="join_voice_call", target=m.group(1).strip()))
        parsed.workflow_steps.append(WorkflowStep(action="enable_camera"))
        return parsed

    # 4. Browser search with profile: "open brave in default and search hotstar"
    m = re.match(r"^(?:open|launch)\s+([a-zA-Z0-9_\s]+?)\s+(?:in|with)\s+([a-zA-Z0-9_\s]+?)\s+(?:profile\s+)?(?:and\s+)?search\s+(.+)$", cmd, re.IGNORECASE)
    if m:
        parsed.primary_intent = "browser_search"
        parsed.environment = "browser"
        parsed.target_application = m.group(1).strip()
        parsed.workflow_steps.append(WorkflowStep(action="search", parameters={"profile": m.group(2).strip(), "query": m.group(3).strip()}))
        return parsed

    # Calculator compound: "open calculator and do 2+2"
    m = re.match(r"^(?:open|launch)\s+calculator\s+and\s+do\s+(.+)$", cmd, re.IGNORECASE)
    if m:
        parsed.primary_intent = "application_workflow"
        parsed.target_application = "Calculator"
        parsed.environment = "desktop"
        parsed.workflow_steps.append(WorkflowStep(action="open", target="Calculator"))
        parsed.workflow_steps.append(WorkflowStep(action="calculate", parameters={"expression": m.group(1).strip()}))
        return parsed

    # 1. Desktop app + secondary action (fallback)
    m = re.match(r"^(?:open|launch|start|run|execute)\s+([^,]+?)(?:\s+and\s+|\s*,\s*|\s+then\s+)(?:do\s+|calculate\s+|type\s+|search\s+|find\s+)?(.+)$", cmd, re.IGNORECASE)
    if m:
        parsed.primary_intent = "application_workflow"
        app = m.group(1).strip()
        parsed.target_application = app
        if "browser" in app.lower() or app.lower() in ("chrome", "brave", "edge", "firefox"):
            parsed.environment = "browser"
        else:
            parsed.environment = "desktop"
        
        parsed.workflow_steps.append(WorkflowStep(action="open", target=parsed.target_application))
        
        second_part = m.group(2).strip()
        if re.search(r'\s+and\s+|\s+then\s+', second_part, re.IGNORECASE) and not re.search(r'^\s*(do|calculate)\s', second_part, re.IGNORECASE):
            parts = re.split(r'\s+and\s+|\s+then\s+', second_part, flags=re.IGNORECASE)
            for part in parts:
                parsed.workflow_steps.append(WorkflowStep(action="interact", raw_text=part.strip()))
        else:
            parsed.workflow_steps.append(WorkflowStep(action="secondary_action", parameters={"expression": second_part}, raw_text=second_part))
        return parsed

    return parsed
