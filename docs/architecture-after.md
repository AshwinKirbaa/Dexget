# JARVIS Architecture Post-Migration (100% Local / Free)

## Core Principles

1. **100% Local**: No cloud dependencies. Uses Ollama for planning and classification.
2. **Deterministic Fast Path First**: Common commands bypass the LLM entirely, saving time and tokens.
3. **Structured Semantic Routing**: Tier 1 classification maps natural language to structured intents (`YOUTUBE_PLAY`, `WINDOWS_APP_OPEN`, etc.).
4. **Agentic Planning**: Tier 2 planning uses structured JSON output to coordinate tools, strictly validated by the registry.

## Tiers of Execution

### TIER 0: Deterministic Router (`jarvis/router.py`)
Regex-based routing for fast, O(1) matching of exact phrasing (e.g. "mute audio").

### TIER 1: Semantic Local Model (`jarvis/semantic/classifier.py` + `local_router.py`)
Uses `JARVIS_SEMANTIC_TIMEOUT` (8s) and the fast model (`JARVIS_FAST_MODEL`, e.g., qwen2.5:3b) to classify natural language into `StructuredIntent` JSON, which is then handled by task handlers.

### TIER 2: Complex Agent Planning (`jarvis/agent/planner.py`)
Uses `JARVIS_AGENT_TIMEOUT` (20s) and the agent model (`JARVIS_AGENT_MODEL`, e.g., qwen2.5:7b) to generate multi-step JSON tool plans.

## Components Updated

1. **Capability Registry (`jarvis/automation/capabilities.py`)**
   Standardized, granular tools (`browser_open`, `windows_click`, `system_volume`, etc.) map to underlying automation modules. Replaces previous monolithic tool injections.

2. **Model Config (`jarvis/config/models.py`)**
   Exposes functions for `get_fast_model()`, `get_agent_model()`, `get_vision_model()` and standardized timeouts (`JARVIS_MODEL_TIMEOUT`, `JARVIS_AGENT_TIMEOUT`).

3. **Memory Storage (`jarvis/memory/store.py`)**
   Expanded SQLite schema includes `preferences`, `accounts_metadata`, `task_history`, `successful_strategies`, `failures`, and `automation_preferences`.

4. **Task Scheduler (`jarvis/tasks/scheduler.py`)**
   Replaced previous custom JSON file implementation with APScheduler for robust run-once, cron, and interval background task support.

5. **Diagnostic Doctor (`jarvis/diagnostics.py` / `jarvis/doctor.py`)**
   Added detailed readiness checks for SQLite schemas and PyAudio device I/O, maintaining zero-paid-API design.

6. **Automation Backends**
   - Browser: Built-in local Playwright logic handles both DevTools direct-attach (via `DevToolsActivePort`) and subprocess fallbacks.
   - Windows: Fully integrated with `uiautomation` for semantic UI-tree extraction and interaction, with Win32 fallback.
