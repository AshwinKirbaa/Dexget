"""
Integration layer for the JARVIS agent architecture.

This module builds a fully-operational Agent using only the code already
inside the `jarvis/` package -- no `legacy_jarvis.py` required.

Optionally, with JARVIS_USE_LEGACY=true and `legacy_jarvis.py` in the project root (your
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
from jarvis.config.environment import load_environment


class ModelUnavailable(RuntimeError):
    """Actionable model connection errors, surfaced by every frontend."""

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

def _make_ollama_fn(model: str = "gemma3:4b", host: str = "http://localhost:11434") -> Callable[[str], Optional[str]]:
    import urllib.request
    import json as _json

    def _call(prompt: str, schema=None) -> Optional[str]:
        try:
            body = {
                "model": model,
                "prompt": prompt,
                "stream": schema is not None,
                "options": {"temperature": float(os.getenv("JARVIS_LLM_TEMPERATURE", "0.5")), "num_ctx": 16384, "num_predict": 1024},
            }
            if schema is not None:
                body["format"] = schema
            elif prompt.rstrip().endswith("JSON RESPONSE:"):
                body["format"] = "json"
            payload = _json.dumps(body).encode()
            req = urllib.request.Request(
                f"{host.rstrip('/')}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=float(os.getenv("JARVIS_MODEL_TIMEOUT", "300"))) as resp:
                if schema is not None:
                    response = ""
                    for line in resp:
                        cancel_event = getattr(_call, "cancel_event", None)
                        if cancel_event is not None and cancel_event.is_set():
                            raise ModelUnavailable("Task stopped.")
                        if not line.strip():
                            continue
                        event = _json.loads(line)
                        if event.get("error"):
                            raise ModelUnavailable(event["error"])
                        response += event.get("response", "")
                        try:
                            if isinstance(_json.loads(response), dict):
                                # A complete action is enough. Closing the stream
                                # also avoids waiting for generated trailing spaces.
                                return response.strip()
                        except _json.JSONDecodeError:
                            pass
                        if event.get("done"):
                            break
                    response = response.strip()
                else:
                    data = _json.loads(resp.read())
                    response = data.get("response", "").strip()
                if not response:
                    raise ModelUnavailable("Ollama returned an empty response.")
                return response
        except Exception as exc:
            cancel_event = getattr(_call, "cancel_event", None)
            if cancel_event is not None and cancel_event.is_set():
                raise ModelUnavailable("Task stopped.") from exc
            if isinstance(exc, ModelUnavailable):
                raise
            if isinstance(exc, TimeoutError):
                raise ModelUnavailable(
                    f"Local model '{model}' timed out. It may be loading or busy. "
                    "Close other model workloads or increase JARVIS_MODEL_TIMEOUT."
                ) from exc
            raise ModelUnavailable(
                f"Local model '{model}' is unavailable at {host}. "
                f"Start Ollama and run 'ollama pull {model}'. Detail: {exc}"
            ) from exc

    _call.structured = _call
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
                "temperature": float(os.getenv("JARVIS_LLM_TEMPERATURE", "0.5")),
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
    ollama_model = os.environ.get("JARVIS_OLLAMA_MODEL", "gemma3:4b")
    ollama_host  = os.environ.get("JARVIS_OLLAMA_HOST",  "http://localhost:11434")
    openai_model = os.environ.get("JARVIS_OPENAI_MODEL", "gpt-4o-mini")

    ollama_fn = _make_ollama_fn(model=ollama_model, host=ollama_host)
    openai_fn = _make_openai_fn(model=openai_model)

    def _combined(prompt: str, schema=None) -> Optional[str]:
        ollama_fn.cancel_event = getattr(_combined, "cancel_event", None)
        provider = os.environ.get("JARVIS_LLM_PROVIDER", "ollama").lower()
        if provider not in ("ollama", "openai", "auto"):
            raise ModelUnavailable("JARVIS_LLM_PROVIDER must be ollama, openai or auto.")
        if provider == "openai":
            result = openai_fn(prompt)
            if not result:
                raise ModelUnavailable("OpenAI is unavailable. Check OPENAI_API_KEY and JARVIS_OPENAI_MODEL.")
            return result
        try:
            return ollama_fn(prompt, schema) if schema is not None else ollama_fn(prompt)
        except ModelUnavailable:
            if ollama_fn.cancel_event is not None and ollama_fn.cancel_event.is_set():
                raise
            if provider == "auto":
                result = openai_fn(prompt)
                if result:
                    return result
            raise

    _combined.structured = _combined
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

def build_agent(on_progress: Optional[Callable[[str], None]] = None,
                confirm_fn: Optional[Callable[[str], bool]] = None) -> Agent:
    load_environment()
    legacy = _try_import_legacy() if os.getenv("JARVIS_USE_LEGACY", "false").lower() == "true" else None

    if legacy is not None:
        require_confirmation = legacy.CONFIG.get("require_confirmation", True)
    else:
        env_val = os.environ.get("JARVIS_REQUIRE_CONFIRMATION", "true").lower()
        require_confirmation = env_val not in ("false", "0", "no")

    confirm_fn = (confirm_fn or terminal_confirm_fn(True)) if require_confirmation else (lambda prompt: True)
    registry = build_default_registry(confirm_fn=confirm_fn)

    from jarvis.tools import filesystem as _fs
    fs_root = os.environ.get("JARVIS_FS_ROOT", "*").strip() or os.path.expanduser("~")
    _fs.ALLOWED_ROOTS = None if fs_root == "*" else [
        os.path.expandvars(os.path.expanduser(root.strip()))
        for root in fs_root.split(os.pathsep) if root.strip()
    ]

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

    config = ExecutorConfig(max_steps=int(os.getenv("JARVIS_MAX_STEPS", "10")), max_retries_per_action=3)
    
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
    if hasattr(llm_fn, "structured"):
        llm_fn.cancel_event = registry.cancel_event
    return agent


def handle_command(agent: Agent, command: str, *, reset_cancel: bool = True) -> AgentResponse:
    command = (command or "").strip()
    if command.lower().rstrip(".!") in ("stop", "cancel", "never mind", "nevermind"):
        agent.cancel()
        return AgentResponse("Task stopped.", False)
    if not agent.command_lock.acquire(blocking=False):
        return AgentResponse("A task is running. Use Stop before starting another task.", False)
    try:
        if reset_cancel:
            agent.registry.cancel_event.clear()
        if agent.registry.cancel_event.is_set():
            return AgentResponse("Task stopped.", False)
        
        from jarvis.semantic.context import context

        if agent.executor.pending_task:
            outcome = agent.executor.run(command)
            res = AgentResponse(outcome.final_message, True, outcome)
            context.add_interaction(command, res.text)
            return res

        res = _handle_command(agent, command)
        context.add_interaction(command, res.text)
        return res
    except ModelUnavailable as exc:
        return AgentResponse(str(exc), False)
    finally:
        agent.command_lock.release()


def _handle_command(agent: Agent, command: str) -> AgentResponse:
    """
    Hybrid router entry point (per spec requirements 1, 10, 13, 28).
    Classifies command -> FAST | CHAT | AGENT.
    """
    command = (command or "").strip()
    if not command:
        return AgentResponse(text="I didn't catch a command.", used_agent_loop=False)

    from jarvis.tasks.accounts import account_manager
    command, explicit_account = account_manager.extract_account_alias(command)
    
    if explicit_account and explicit_account not in account_manager.accounts:
        configured = ", ".join(account_manager.accounts.keys()) or "none"
        return AgentResponse(text=f"I don't have a '{explicit_account}' account configured. Configured accounts: {configured}", used_agent_loop=False)

    # We attach explicit_account to the command state via a global/thread-local or simply pass it to route
    # Let's pass it to route()
    route_res = route(command, explicit_account)

    # If deterministic route is AGENT (meaning complex or unknown), try semantic classifier
    if route_res.route_type == RouteType.AGENT:
        from jarvis.semantic.classifier import classify_intent, Intent
        if agent.executor.on_progress:
            agent.executor.on_progress("[SEMANTIC CLASSIFIER] Analyzing intent...")
            
        intent_data = classify_intent(command, agent.llm_fn)
        
        if intent_data.intent != Intent.UNKNOWN:
            if agent.executor.on_progress:
                agent.executor.on_progress(f"[SEMANTIC CLASSIFIER] Found {intent_data.intent.value}")
                
                
            from jarvis.router import RouteResult, _fast, _browser, _windows
            if intent_data.intent == Intent.BROWSER_RESEARCH:
                if not intent_data.topic or intent_data.topic.lower() in ["none", "null", ""]:
                    route_res = RouteResult(RouteType.CHAT, text="Sure. What would you like me to research?")
                else:
                    route_res = _fast("win_browser_search", {"browser": intent_data.browser or "chrome", "profile": "default", "query": intent_data.topic}, f"Researching {intent_data.topic}")
            elif intent_data.intent == Intent.BROWSER_OPEN:
                route_res = _windows("win_open_application", {"app_name": intent_data.browser or intent_data.application or "chrome"}, "Opening browser")
            elif intent_data.intent == Intent.MUSIC_PLAY:
                if intent_data.query and intent_data.query.lower() not in ["none", "null", ""]:
                    # YOUTUBE_PLAY task
                    route_res = RouteResult(RouteType.TASK, tool_name="youtube_play", tool_args={"query": intent_data.query}, label=f"Playing {intent_data.query}")
            elif intent_data.intent == Intent.APPLICATION_OPEN:
                if intent_data.application and intent_data.application.lower() not in ["none", "null", ""]:
                    route_res = _windows("win_open_application", {"app_name": intent_data.application}, f"Opening {intent_data.application}")
            elif intent_data.intent == Intent.TIMEOUT:
                route_res = RouteResult(RouteType.CHAT, text="The local AI model is currently busy or taking too long to respond. Please try a simpler command or wait a moment.")

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
        
        result = execute_filesystem_route(route_res.tool_args, agent.filesystem_context,
                                          agent.executor.on_progress, registry=agent.registry)
        
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
        if not calls and route_res.text:
            return AgentResponse(route_res.text, False)
        for call in calls:
            if agent.registry.cancel_event.is_set():
                return AgentResponse("Task stopped.", False)
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

    elif route_res.route_type == RouteType.TASK:
        if agent.executor.on_progress:
            agent.executor.on_progress(f"[TASK HANDLER] {route_res.tool_name}")
            
        if route_res.tool_name == "youtube_play":
            from jarvis.tasks.youtube import YouTubePlayTask
            task = YouTubePlayTask(agent.registry)
            result = task.execute(**route_res.tool_args)
        elif route_res.tool_name == "youtube_music_play":
            from jarvis.tasks.youtube import YouTubeMusicPlayTask
            task = YouTubeMusicPlayTask(agent.registry)
            result = task.execute(**route_res.tool_args)
        elif route_res.tool_name == "web_open":
            from jarvis.tasks.browser import WebOpenTask
            task = WebOpenTask(agent.registry)
            result = task.execute(**route_res.tool_args)
        else:
            result = AgentResponse(text=f"[FAILED] Unknown task handler '{route_res.tool_name}'", used_agent_loop=False)
            return result
            
        if not result.success:
            if agent.executor.on_progress:
                agent.executor.on_progress(f"[FAILED] {result.observation}")
            return AgentResponse(text=result.observation, used_agent_loop=False)
            
        if agent.executor.on_progress:
            agent.executor.on_progress("[OK]")
        return AgentResponse(text=result.observation, used_agent_loop=False)

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
            sys_prompt = "You are JARVIS, a helpful AI and software development assistant. Assume technical acronyms relate to computer science, AI, or software engineering unless specified otherwise. Answer the user's question directly and concisely."
            
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
        # Preserve original casing, URLs and text to type. Regex parser hints
        # are normalized and must not replace the user's literal content.
        if agent.executor.on_progress:
            agent.executor.on_progress(f"[AGENT] Executing structured workflow for: {route_res.text[:50]}...")
    else:
        if agent.executor.on_progress:
            agent.executor.on_progress(f"[AGENT] Task: {command}")
        
    outcome = agent.executor.run(command)
    return AgentResponse(text=outcome.final_message, used_agent_loop=True, outcome=outcome)
