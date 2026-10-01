from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class SemanticIntent(str, Enum):
    APPLICATION_OPEN = "APPLICATION_OPEN"
    APPLICATION_FOCUS = "APPLICATION_FOCUS"
    APPLICATION_WORKFLOW = "APPLICATION_WORKFLOW"

    BROWSER_OPEN = "BROWSER_OPEN"
    BROWSER_SEARCH = "BROWSER_SEARCH"
    BROWSER_NAVIGATE = "BROWSER_NAVIGATE"
    BROWSER_WORKFLOW = "BROWSER_WORKFLOW"

    YOUTUBE_SEARCH = "YOUTUBE_SEARCH"
    YOUTUBE_PLAY = "YOUTUBE_PLAY"

    YOUTUBE_MUSIC_SEARCH = "YOUTUBE_MUSIC_SEARCH"
    YOUTUBE_MUSIC_PLAY = "YOUTUBE_MUSIC_PLAY"

    LOCAL_MEDIA_PLAY = "LOCAL_MEDIA_PLAY"

    FILESYSTEM_OPEN = "FILESYSTEM_OPEN"
    FILESYSTEM_SEARCH = "FILESYSTEM_SEARCH"
    FILESYSTEM_CREATE = "FILESYSTEM_CREATE"
    FILESYSTEM_MOVE = "FILESYSTEM_MOVE"
    FILESYSTEM_DELETE = "FILESYSTEM_DELETE"

    MEMORY_SET = "MEMORY_SET"
    MEMORY_GET = "MEMORY_GET"
    MEMORY_RECALL = "MEMORY_RECALL"

    SYSTEM_ACTION = "SYSTEM_ACTION"
    WINDOWS_ACTION = "WINDOWS_ACTION"

    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"

    CONVERSATION = "CONVERSATION"

    AGENT_TASK = "AGENT_TASK"

    UNKNOWN = "UNKNOWN"

class SemanticDecision(BaseModel):
    intent: SemanticIntent = Field(description="The primary intent of the user's command.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")
    application: Optional[str] = Field(None, description="Target application name (e.g., 'chrome', 'calculator').")
    query: Optional[str] = Field(None, description="Search query or media name.")
    workflow: Optional[str] = Field(None, description="Action or workflow to perform within the app/browser.")
    folder: Optional[str] = Field(None, description="Target folder or directory.")
    media: Optional[str] = Field(None, description="Specific media file or episode name.")
    target: Optional[str] = Field(None, description="Target entity for system, windows, memory, or fs actions.")
    value: Optional[str] = Field(None, description="Value to set for memory or other commands.")
    url: Optional[str] = Field(None, description="Specific URL to navigate to.")
