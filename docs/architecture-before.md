# JARVIS Architecture Before Migration

## Overview
The existing JARVIS architecture provides a desktop-integrated AI assistant widget for Windows. It uses a combination of deterministic routing and an LLM-based planner for executing tasks. It features browser automation using Playwright, Windows automation, filesystem operations, and voice capabilities.

## Key Components

### 1. Router (`jarvis/router.py`)
- **Deterministic Routing**: A fast-path routing mechanism that uses regex matching to classify user intents (e.g., `FAST`, `CHAT`, `AGENT`, `WINDOWS`, `BROWSER`, `FILESYSTEM`).
- **Lookups**: Static dictionaries map known application names and website URLs to standard formats.
- **Workflow Interception**: Simple operations bypass the LLM and are matched to direct tool calls.

### 2. Planner (`jarvis/agent/planner.py`)
- Receives a user goal and a list of tool specifications.
- **`make_plan`**: Interacts with the LLM to generate a high-level list of steps.
- **`next_action`**: Interacts with the LLM to decide the exact tool and arguments for the next step, using JSON schema validation to ensure the tool call matches known capabilities.

### 3. Executor (`jarvis/agent/executor.py`)
- Manages the execution loop: `plan -> execute -> observe -> verify -> replan`.
- Takes the planner's structured output, executes the selected tool via the `ToolRegistry`, and validates the result.
- Provides a basic retry mechanism (max 3 retries per identical action).
- Detects infinite loops (repeating identical action-observation sequences).

### 4. Tool Registry (`jarvis/agent/tool_registry.py`)
- Maintains a registry of executable tools/capabilities.
- Validates parameters against a schema before execution.

### 5. Browser Automation (`jarvis/automation/browser_backend.py`)
- Uses Playwright for browser interactions.
- Has capabilities to connect to existing Chrome sessions via CDP if remote debugging is enabled.
- Uses `DevToolsActivePort` to attempt to find the correct WebSocket path.
- Handles observations by extracting interactive elements (links, buttons, inputs) into a structured format.

### 6. Verifier (`jarvis/automation/verifier.py`)
- A simple module to confirm actions based on observations (e.g., verifying if a URL is active or a window is focused).
- Provides basic authentication status detection (e.g., for Gmail).

### 7. Memory (`jarvis/memory/store.py`)
- SQLite-based key-value store for user preferences and facts.
- Single `preferences` table.

### 8. Voice and Input
- Uses Vosk for local STT and Fish Audio / native Windows speech for TTS.

## Limitations Addressed by the Target Architecture
- **Memory**: The SQLite database only has a single `preferences` table and does not store tasks, strategies, or failures.
- **Model Usage**: Configuration for specific tiers of models (`FAST_MODEL`, `AGENT_MODEL`, `VISION_MODEL`) is lacking.
- **Capabilities**: The capability registry needs cleanup for finer composability.
- **Browser Agent**: Lacks higher-level browser reasoning through an integrated local browser agent library (e.g., BrowserUse).
- **Vision Fallback**: Does not currently implement a structured visual fallback mechanism for non-UIA apps.
- **Recovery & Execution**: Recovery strategy is rudimentary. Planner/Executor boundaries need strictly enforcing according to the new tiers.
- **Scheduler**: No sign of `APScheduler` integration for recurring background tasks.
