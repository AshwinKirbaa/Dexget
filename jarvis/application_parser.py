import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class ApplicationIntent:
    application: str
    action: str
    secondary_action: Optional[str] = None
    expression: Optional[str] = None

class ApplicationIntentParser:
    @staticmethod
    def parse(cmd: str) -> Optional[ApplicationIntent]:
        cmd = cmd.strip()
        
        # open calculator and do 2+2
        m = re.match(r"^(?:open|launch|start|run|execute)\s+([^,]+?)\s+(?:and\s+)?(?:do\s+|calculate\s+)(.+)$", cmd, re.IGNORECASE)
        if m:
            return ApplicationIntent(
                application=m.group(1).strip(),
                action="open",
                secondary_action="calculate",
                expression=m.group(2).strip()
            )
            
        # generic open
        m = re.match(r"^(?:open|launch|start|run|execute)\s+(.+?)(?:\s+in\s+browser)?[\s.!]*$", cmd, re.IGNORECASE)
        if m:
            app = m.group(1).strip()
            # If it has "and type", let the compound workflow handle it, or we can handle it here
            m_type = re.match(r"^(.+?)\s+and\s+(?:type|write|enter)\s+(.+)$", app, re.IGNORECASE)
            if m_type:
                return ApplicationIntent(
                    application=m_type.group(1).strip(),
                    action="open",
                    secondary_action="type",
                    expression=m_type.group(2).strip()
                )
                
            return ApplicationIntent(
                application=app,
                action="open"
            )
            
        # generic close
        m = re.match(r"^(?:close|kill|quit|exit|terminate)\s+(.+)$", cmd, re.IGNORECASE)
        if m:
            return ApplicationIntent(
                application=m.group(1).strip(),
                action="close"
            )
            
        return None
