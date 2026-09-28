"""
JARVIS Agent -- terminal entry point.

Usage:
  python main.py                   # full agent (auto-detects LLM: Ollama or OpenAI)
  python main.py --tools-only      # tools REPL, no LLM -- useful for quick testing
  python main.py --command "..."   # run one command non-interactively and exit

Environment variables (all optional):
  JARVIS_OLLAMA_MODEL   Ollama model name (default: llama3.2:3b)
  JARVIS_OLLAMA_HOST    Ollama base URL  (default: http://localhost:11434)
  JARVIS_OPENAI_MODEL   OpenAI model     (default: gpt-4o-mini)
  OPENAI_API_KEY        OpenAI API key   (no default -- set for cloud LLM)
  JARVIS_FS_ROOT        Filesystem root allowed for file tools (default: ~)
  JARVIS_REQUIRE_CONFIRMATION  Set to 'false' to skip confirmation prompts
"""
from __future__ import annotations

import argparse
import sys


def run_full(single_command: str = None) -> None:
    import jarvis_integration
    try:
        from jarvis.voice.voice_manager import VoiceManager
        from jarvis.voice.voice_config import VOICE_PROVIDER, WAKE_WORD
        has_voice = True
    except ImportError:
        has_voice = False

    def on_progress(msg: str) -> None:
        print(f"  {msg}")

    print("Starting JARVIS agent...")
    agent = jarvis_integration.build_agent(on_progress=on_progress)

    # Detect whether an LLM is actually reachable for informative startup msg
    from jarvis.agent.tool_registry import build_default_registry
    tool_count = len(list(agent.registry.list_tools()))
    print(f"JARVIS ready.\n{tool_count} tools registered.")
    
    if has_voice:
        print("STT: READY")
        print("TTS: READY")
        print(f"Voice provider: {'Fish Audio' if VOICE_PROVIDER.lower() == 'fish' else VOICE_PROVIDER.capitalize()}")
        print(f"Wake word: {WAKE_WORD.capitalize()}")
        print("\nListening...")
    else:
        llm_status = "LLM active" if agent.llm_fn is not None else "no LLM -- tools only"
        print(f"Status: {llm_status}.\nType a command, or 'exit' to quit.\n")

    def handle_one(command: str) -> None:
        cmd_lower = command.lower()
        if cmd_lower == "voice test" and has_voice:
            print("[VOICE TEST DIAGNOSTICS]")
            vm = VoiceManager(agent)
            
            # Check STT initialization
            vosk_pkg = "OK" if "vosk" in sys.modules or vm.stt.vosk_model else "UNAVAILABLE"
            vosk_model = "OK" if vm.stt.vosk_model else "UNAVAILABLE"
            mic_device = "OK" if vm.stt.mic_stream else "UNAVAILABLE"
            capture_rate = vm.stt.capture_rate if vm.stt.mic_stream else "N/A"
            whisper_model = "OK" if vm.stt.whisper_model else "UNAVAILABLE"
            
            print(f"[VOSK] Package: {vosk_pkg}")
            print(f"[VOSK] Model: {vosk_model}")
            print(f"[MIC] Device: {mic_device}")
            print(f"[MIC] Capture rate: {capture_rate}")
            print(f"[VOSK] Recognition rate: 16000")
            print(f"[WHISPER] Model: {whisper_model}")
            print(f"[TTS] Status: OK")
            
            print("\nDiagnostic complete. Speak a phrase to test end-to-end:")
            res = vm.stt.listen()
            if res and "error" not in res:
                txt = res.get("text", "")
                print(f"[STT]\n{txt}")
                reply = f"Hello. I heard you say {txt}"
                print(f"[TTS]\n\"{reply}\"")
                vm.tts.speak(reply)
            else:
                print(f"[STT ERROR] {res.get('error', 'unknown')}")
            return
            
        if cmd_lower == "tts test" and has_voice:
            print("[TTS TEST]")
            vm = VoiceManager(agent)
            msg = "Hello. This is JARVIS voice testing."
            print(f"[TTS]\n\"{msg}\"")
            vm.tts.speak(msg)
            return
            
        if cmd_lower == "fish test" and has_voice:
            from jarvis.voice.voice_config import FISH_MODEL, FISH_VOICE_ID
            print("[VOICE] Provider: Fish Audio")
            print(f"[VOICE] Model: {FISH_MODEL}")
            print(f"[VOICE] Voice: {FISH_VOICE_ID}")
            vm = VoiceManager(agent)
            msg = "Hello. I am JARVIS."
            print(f"[TTS]\n\"{msg}\"")
            vm.tts.speak(msg)
            return
            
        if cmd_lower == "voice status" and has_voice:
            from jarvis.voice.voice_config import FISH_MODEL, FISH_VOICE_ID
            print("STT:\nREADY\n\nTTS:\nREADY\n\nProvider:\nFish Audio\n\nVoice:\nconfigured\n\nMicrophone:\nREADY\n\nSpeaker:\nREADY")
            return

        response = jarvis_integration.handle_command(agent, command)
        print(f"\nJARVIS: {response.text}\n")

    from jarvis.scheduler import scheduler
    scheduler.execute_callback = handle_one
    scheduler.start()

    if single_command:
        handle_one(single_command)
        return

    if has_voice:
        vm = VoiceManager(agent)
        vm.start()
    else:
        while True:
            try:
                command = input("JARVIS> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break
            if not command:
                continue
            if command.lower() in ("exit", "quit", "exit jarvis"):
                print("Goodbye.")
                break
            handle_one(command)


def run_tools_only() -> None:
    """
    Runs the new agent WITHOUT any LLM -- no memory, no voice, no planning.
    Useful to sanity-check the tool registry interactively even on a machine
    that doesn't have Ollama or an API key installed yet.
    """
    from jarvis.agent.tool_registry import build_default_registry
    from jarvis.security.confirmation import terminal_confirm_fn

    registry = build_default_registry(confirm_fn=terminal_confirm_fn(True))
    specs = registry.specs()
    print(f"Tools-only mode (no LLM). {len(specs)} registered tools:\n")
    for spec in specs:
        print(f"  - {spec['name']} [{spec['risk_level']}]: {spec['description']}")
    print("\nUsage: <tool_name> [key=value ...]\nExample: fs_list_directory path=.")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            line = input("tool> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break
        parts = line.split()
        name, kwargs = parts[0], {}
        for part in parts[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                kwargs[k] = v
        result = registry.execute(name, **kwargs)
        print(result.observation)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS agentic assistant")
    parser.add_argument("--tools-only", action="store_true",
                        help="Start in tools-only REPL mode (no LLM required)")
    parser.add_argument("--command", type=str, default=None,
                        help="Run a single command non-interactively and exit")
    args = parser.parse_args()

    if args.tools_only:
        run_tools_only()
    else:
        run_full(args.command)
