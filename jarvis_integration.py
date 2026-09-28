"""
Integration layer for the JARVIS agent architecture.

This module builds a fully-operational Agent using only the code already
inside the `jarvis/` package -- no `legacy_jarvis.py` required.

Optionally, if you have a `legacy_jarvis.py` in the project root (your
original jarvis.py, renamed), this module will:
  - Reuse its ask_ollama/ask_openai as the LLM backend
  - Reuse its detect_task/execute_task fast-path router
  - Reuse its confirm_action security UX

Startup is NEVER blocked because legacy_jarvis.py doesn't exist.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

from jarvis.agent.agent import Agent, AgentResponse
from jarvis.agent.executor import ExecutorConfig
from jarvis.agent.tool_registry import build_default_registry
from jarvis.security.confirmation import terminal_confirm_fn
from jarvis.router import route, RouteType

# ---------------------------------------------------------------------------
# Optional legacy import -- never raises, returns None if unavailable
# ---------------------------------------------------------------------------

def _try_import_legacy():
    """Attempt to import legacy_jarvis. Returns the module or None."""
    try:
        import legacy_jarvis  # noqa: PLC0415
        return legacy_jarvis
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Built-in LLM connectors (no legacy_jarvis required)
# ---------------------------------------------------------------------------

def _make_ollama_fn(model: str = "llama3.2:3b", host: str = "http://localhost:11434") -> Callable[[str], Optional[str]]:
    import urllib.request
    import json as _json

    def _call(prompt: str) -> Optional[str]:
        try:
            payload = _json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                f"{host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = _json.loads(resp.read())
                return data.get("response", "").strip() or None
        except Exception:  # noqa: BLE001
            return None

    return _call


def _make_openai_fn(api_key: Optional[str] = None, model: str = "gpt-4o-mini") -> Callable[[str], Optional[str]]:
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return lambda prompt: None

    import urllib.request
    import json as _json

    def _call(prompt: str) -> Optional[str]:
        try:
            payload = _json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = _json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip() or None
        except Exception:  # noqa: BLE001
            return None

    return _call


def _build_standalone_llm_fn() -> Callable[[str], Optional[str]]:
    ollama_model = os.environ.get("JARVIS_OLLAMA_MODEL", "llama3.2:3b")
    ollama_host  = os.environ.get("JARVIS_OLLAMA_HOST",  "http://localhost:11434")
    openai_model = os.environ.get("JARVIS_OPENAI_MODEL", "gpt-4o-mini")

    ollama_fn = _make_ollama_fn(model=ollama_model, host=ollama_host)
    openai_fn = _make_openai_fn(model=openai_model)

    def _combined(prompt: str) -> Optional[str]:
        result = ollama_fn(prompt)
        if result:
            return result
        return openai_fn(prompt)

    return _combined


def _build_legacy_llm_fn(legacy) -> Callable[[str], Optional[str]]:
    def _llm(prompt: str) -> Optional[str]:
        provider = legacy.CONFIG.get("llm_provider", "ollama")
        if provider == "openai":
            return (
                legacy.ask_openai("Respond now.", extra_system=prompt)
                or legacy.ask_ollama("Respond now.", extra_system=prompt)
            )
        return (
            legacy.ask_ollama("Respond now.", extra_system=prompt)
            or legacy.ask_openai("Respond now.", extra_system=prompt)
        )
    return _llm


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_agent(on_progress: Optional[Callable[[str], None]] = None) -> Agent:
    legacy = _try_import_legacy()

    if legacy is not None:
        require_confirmation = legacy.CONFIG.get("require_confirmation", True)
    else:
        env_val = os.environ.get("JARVIS_REQUIRE_CONFIRMATION", "true").lower()
        require_confirmation = env_val not in ("false", "0", "no")

    confirm_fn = terminal_confirm_fn(require_confirmation)
    registry = build_default_registry(confirm_fn=confirm_fn)

    from jarvis.tools import filesystem as _fs
    fs_root = os.environ.get("JARVIS_FS_ROOT", os.path.expanduser("~"))
    _fs.ALLOWED_ROOTS = [fs_root]

    if legacy is not None:
        llm_fn: Optional[Callable[[str], Optional[str]]] = _build_legacy_llm_fn(legacy)
    else:
        llm_fn = _build_standalone_llm_fn()

    # We intentionally do not ping the LLM at startup here.
    # If Ollama is slow to load the model (especially on CPU), a startup ping
    # could time out and permanently disable the LLM for the session.
    fast_path_fn = None
    if legacy is not None:
        def _fast_path(command: str) -> Optional[str]:
            task = legacy.detect_task(command)
            if not task:
                return None
            return legacy.execute_task(task, command, speak_fn=None, listen_fn=None)
        fast_path_fn = _fast_path

    config = ExecutorConfig(max_steps=30, max_retries_per_action=3)
    
    # We monkey-patch the agent a bit so we can access the original legacy object
    # for the CHAT route, if available.
    agent = Agent(
        registry,
        llm_fn=llm_fn,
        fast_path_fn=fast_path_fn,
        config=config,
        on_progress=on_progress,
    )
    agent._legacy = legacy
    return agent


def handle_command(agent: Agent, command: str) -> AgentResponse:
    """
    Hybrid router entry point (per spec requirements 1, 10, 13, 28).
    Classifies command -> FAST | CHAT | AGENT.
    """
    command = (command or "").strip()
    if not command:
        return AgentResponse(text="I didn't catch a command.", used_agent_loop=False)

    # 1. New deterministic router
    route_res = route(command)

    fast_routes = {
        RouteType.FAST, RouteType.WINDOWS, RouteType.APPLICATION, 
        RouteType.BROWSER, RouteType.SEARCH
    }

    if agent.executor.on_progress:
        agent.executor.on_progress(f"[ROUTER] {route_res.route_type.name.upper()}")

    # 2. Execute based on route
    if route_res.route_type == RouteType.FILESYSTEM:
        from jarvis.filesystem_executor import execute_filesystem_route
        if not hasattr(agent, "filesystem_context"):
            agent.filesystem_context = {"current_directory": None, "last_opened_directory": None}
        
        result = execute_filesystem_route(route_res.tool_args, agent.filesystem_context, agent.executor.on_progress)
        
        # Filesystem commands never fall back to AGENT if they fail (Rule 23)
        return AgentResponse(text=result["observation"], used_agent_loop=False)

    if route_res.route_type in fast_routes:
        # Determine the sequence of tools to run
        calls = route_res.tool_calls if route_res.tool_calls else []
        if route_res.tool_name and not calls:
            calls = [{"name": route_res.tool_name, "args": route_res.tool_args, "label": route_res.label}]
        else:
            calls = [{"name": c.name, "args": c.args, "label": c.label} for c in calls]

        last_observation = ""
        for call in calls:
            if agent.executor.on_progress and call["label"]:
                agent.executor.on_progress(f"[{route_res.route_type.name.upper()}] {call['label']}")
                
            result = agent.registry.execute(call["name"], **call["args"])
            
            if not result.success:
                if agent.executor.on_progress:
                    agent.executor.on_progress(f"[FAILED] {result.observation}. Falling back to AGENT.")
                # Fall through to AGENT
                return AgentResponse(text=f"[FAILED] {result.observation}", used_agent_loop=False)
            
            last_observation = result.observation
            if agent.executor.on_progress:
                agent.executor.on_progress("[OK]")

        return AgentResponse(text=last_observation or "Done", used_agent_loop=False)

    elif route_res.route_type == RouteType.INFORMATION:
        if agent.executor.on_progress:
            agent.executor.on_progress(f"[QUESTION TYPE] {route_res.label}")
            agent.executor.on_progress(f"[HANDLER] {route_res.tool_name}")
            
        result = agent.registry.execute(route_res.tool_name, **route_res.tool_args)
        
        if not result.success:
            if agent.executor.on_progress:
                agent.executor.on_progress(f"[FAILED] {result.observation}")
            return AgentResponse(text=result.observation, used_agent_loop=False)
            
        import json
        data_str = json.dumps(result.output, indent=2) if not isinstance(result.output, str) else result.output
        if agent.executor.on_progress:
            agent.executor.on_progress(f"[DATA] \n{data_str[:200]}...")
            agent.executor.on_progress("[VERIFY] Information retrieved successfully")
            agent.executor.on_progress("[OK]")
            
        if agent.llm_fn:
            sys_prompt = "You are JARVIS. Answer the user's question concisely using ONLY the provided SYSTEM DATA. Format numbers clearly. Do not invent information."
            prompt = f"{sys_prompt}\n\nUSER QUESTION: {command}\nSYSTEM DATA:\n{data_str}\n\nJARVIS:"
            reply = agent.llm_fn(prompt)
            if reply:
                return AgentResponse(text=reply, used_agent_loop=False)
                
        return AgentResponse(text=result.observation, used_agent_loop=False)

    elif route_res.route_type == RouteType.MEMORY:
        from jarvis.memory.store import get_preference, set_preference
        if agent.executor.on_progress and route_res.label:
            agent.executor.on_progress(f"[MEMORY] {route_res.label}")
        
        action = route_res.tool_name
        key = route_res.tool_args.get("key")
        val = route_res.tool_args.get("value")
        
        if action == "set":
            set_preference(key, val)
            if agent.executor.on_progress:
                agent.executor.on_progress("[OK] Saved to memory")
            return AgentResponse(text=f"Got it. I'll remember that your {key} is {val}.", used_agent_loop=False)
        elif action == "get":
            stored_val = get_preference(key)
            if stored_val:
                if agent.executor.on_progress:
                    agent.executor.on_progress("[OK] Found stored preference")
                # format a nice response based on key
                if key == "name":
                    text = f"Your name is {stored_val}."
                elif "favorite" in key or "preference" in key:
                    text = f"Your {key.replace('_', ' ')} is {stored_val}."
                else:
                    text = f"Your {key} is {stored_val}."
                return AgentResponse(text=text, used_agent_loop=False)
            else:
                if agent.executor.on_progress:
                    agent.executor.on_progress("[FAILED] Not found in memory")
                return AgentResponse(text=f"I don't have your {key} saved yet.", used_agent_loop=False)

    elif route_res.route_type in (RouteType.CHAT, RouteType.CONVERSATION):
        if agent.executor.on_progress:
            agent.executor.on_progress("[CHAT]")
            
        if route_res.text:
            return AgentResponse(text=route_res.text, used_agent_loop=False)
            
        cmd_lower = command.lower()
        if "what can you do" in cmd_lower or "capabilities" in cmd_lower or "help" in cmd_lower:
            categories = {}
            for t in agent.registry.list_tools():
                cat = getattr(t, "category", "general")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(t.name)
            
            lines = ["I can help you with:"]
            for cat, tools in categories.items():
                lines.append(f"- **{cat.title()}**: {', '.join(tools[:5])}{'...' if len(tools) > 5 else ''}")
            lines.append("\nYou can also ask me general knowledge questions, or ask me to 'remember' things.")
            return AgentResponse(text="\n".join(lines), used_agent_loop=False)
            
        # Standalone conversational fallback
        if agent.llm_fn:
            sys_prompt = "You are JARVIS, a helpful AI assistant. Answer the user's question directly and concisely."
            
            # Retrieve RAG evidence
            try:
                from jarvis.memory.rag import rag_system
                rag_results = rag_system.query(command)
                if rag_results:
                    evidence = "\n\n".join([r['doc']['content'][:1000] for r in rag_results])
                    sys_prompt += f"\n\nContext information:\n{evidence}"
                    if agent.executor.on_progress:
                        agent.executor.on_progress("[RAG] Found relevant context in memory")
            except Exception as e:
                pass
                
            prompt = f"{sys_prompt}\n\nUser: {command}\nJARVIS:"
            reply = agent.llm_fn(prompt)
            if reply:
                return AgentResponse(text=reply, used_agent_loop=False)
                
        return AgentResponse(text="Hello! (LLM unavailable for conversation)", used_agent_loop=False)

    # 3. Legacy pipeline fast path (fallback if route() didn't match but legacy might)
    if agent.fast_path_fn is not None:
        fast_result = agent.fast_path_fn(command)
        if fast_result:
            return AgentResponse(text=fast_result, used_agent_loop=False)

    # 4. AGENT path
    if agent.llm_fn is None:
        return AgentResponse(
            text="The AI planner is currently unavailable, so I cannot safely execute this complex task.",
            used_agent_loop=False,
        )

    # Intercept COMPOUND_WORKFLOW structured data
    if route_res.route_type == RouteType.AGENT and route_res.label == "COMPOUND_WORKFLOW" and route_res.text:
        # Replace the command with the structured version so the LLM acts on the parsed intent
        structured_workflow = route_res.text
        command = f"Execute this structured workflow:\n{structured_workflow}"
        if agent.executor.on_progress:
            agent.executor.on_progress(f"[AGENT] Executing structured workflow for: {route_res.text[:50]}...")
    else:
        if agent.executor.on_progress:
            agent.executor.on_progress(f"[AGENT] Task: {command}")
        
    outcome = agent.executor.run(command)
    return AgentResponse(text=outcome.final_message, used_agent_loop=True, outcome=outcome)
