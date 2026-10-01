"""
JARVIS Agent -- terminal entry point.

Usage:
  python main.py                   # full agent (local Ollama by default)
  python main.py --tools-only      # tools REPL, no LLM -- useful for quick testing
  python main.py --command "..."   # run one command non-interactively and exit

Environment variables (all optional):
  JARVIS_OLLAMA_MODEL   Ollama model name (default: gemma3:4b)
  JARVIS_OLLAMA_HOST    Ollama base URL  (default: http://localhost:11434)
  JARVIS_OPENAI_MODEL   OpenAI model     (default: gpt-4o-mini)
  OPENAI_API_KEY        OpenAI API key   (no default -- set for cloud LLM)
  JARVIS_FS_ROOT        Filesystem roots allowed for file tools (default: *)
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
    parser.add_argument("--doctor", action="store_true", help="Check dependencies, tools and the local model.")
    parser.add_argument("--accounts", "--setup-accounts", action="store_true", help="Interactive account setup for browser tasks")
    parser.add_argument("--test-accounts", action="store_true", help="Test configured browser accounts")
    parser.add_argument("--chrome-profiles", action="store_true", help="Inspect running Chrome processes and physical profiles")
    parser.add_argument("--test-browser-profile", type=str, help="Test a logical account for proper session attachment and Gmail auth")
    parser.add_argument("--test-gmail-account", type=str, help="Alias for --test-browser-profile")
    parser.add_argument("--test-system-controls", action="store_true", help="Test Windows system controls (Wi-Fi, Bluetooth, etc)")
    parser.add_argument("--inspect-quick-settings", action="store_true", help="Open Win+A and dump discovered controls")
    parser.add_argument("--test-wifi", action="store_true", help="Test Wi-Fi commands")
    parser.add_argument("--test-bluetooth", action="store_true", help="Test Bluetooth commands")
    parser.add_argument("--bluetooth-devices", action="store_true", help="Discover Bluetooth devices only")
    parser.add_argument("--test-audio", action="store_true", help="Test Audio Output commands")
    parser.add_argument("--test-audio-list", action="store_true", help="List all local audio output endpoints")
    parser.add_argument("--test-brightness", action="store_true", help="Test Brightness commands")
    parser.add_argument("--test-volume", action="store_true", help="Test Volume commands")
    parser.add_argument("--test-volume-set", type=int, help="Set volume to given percentage")
    parser.add_argument("--test-volume-mute", action="store_true", help="Mute volume")
    parser.add_argument("--test-volume-unmute", action="store_true", help="Unmute volume")
    parser.add_argument("--test-airplane", action="store_true", help="Run airplane mode diagnostics")
    parser.add_argument("--test-energy-saver", action="store_true", help="Run energy saver diagnostics")
    args = parser.parse_args()

    if args.doctor:
        import json
        from jarvis.diagnostics import check
        print(json.dumps(check(), indent=2))
    elif args.chrome_profiles:
        from jarvis.account_cli import do_chrome_profiles
        do_chrome_profiles()
    elif args.test_browser_profile or args.test_gmail_account:
        from jarvis.account_cli import do_test_browser_profile
        do_test_browser_profile(args.test_browser_profile or args.test_gmail_account)
    elif args.accounts:
        from jarvis.account_cli import do_account_setup
        do_account_setup()
    elif args.test_accounts:
        from jarvis.account_cli import do_test_accounts
        do_test_accounts()
    elif args.inspect_quick_settings:
        from jarvis.capabilities.windows_system import open_quick_settings
        import uiautomation as auto
        import time
        print("Opening Quick Settings (Win+A)...")
        open_quick_settings()
        
        print("\nTop-level windows:")
        children = auto.GetRootControl().GetChildren()
        shell_windows = []
        for c in children:
            if c.ControlType in (auto.ControlType.WindowControl, auto.ControlType.PaneControl):
                if c.ClassName in ("Windows.UI.Core.CoreWindow", "Shell_TrayWnd", "NotifyIconOverflowWindow") or "shell" in c.ClassName.lower() or "center" in c.ClassName.lower() or "quick" in c.ClassName.lower() or "flyout" in c.ClassName.lower():
                    shell_windows.append(c)
                elif c.Name and ("quick settings" in c.Name.lower() or "action center" in c.Name.lower() or "control center" in c.Name.lower()):
                    shell_windows.append(c)
                print(f"  {c.ClassName} '{c.Name}'")
                
        print("\nPossible Quick Settings controls (searching everywhere):")
        # Global search for known buttons
        for btn_name in ["Wi-Fi", "Bluetooth", "Airplane mode", "Battery saver", "Accessibility"]:
            btn = auto.ButtonControl(searchDepth=3, RegexName=f".*{btn_name}.*")
            if btn.Exists(1, 1):
                state = "Unknown"
                if hasattr(btn, "CurrentToggleState"):
                    try: state = "On" if btn.CurrentToggleState() == 1 else "Off"
                    except: pass
                print(f"  Found '{btn.Name}' inside '{btn.GetParentControl().ClassName}'. State: {state}")
            else:
                print(f"  Did not find button for: {btn_name}")
                
        auto.SendKeys('{Win}a')
    elif args.test_system_controls:
        from jarvis.capabilities.windows_system import wifi_get_status, bluetooth_get_status, brightness_get, volume_get, audio_output_get, airplane_mode_get_status, energy_saver_get_status
        def _fmt(r): return r.observation if hasattr(r, 'observation') else r
        print("[TEST SYSTEM CONTROLS]")
        print(f"Wi-Fi Status: {_fmt(wifi_get_status())}")
        print(f"Bluetooth Status: {_fmt(bluetooth_get_status())}")
        print(f"Brightness: {_fmt(brightness_get())}")
        print(f"Volume: {_fmt(volume_get())}")
        print(f"Audio Output: {_fmt(audio_output_get())}")
        print(f"Airplane Mode: {_fmt(airplane_mode_get_status())}")
        print(f"Energy Saver: {_fmt(energy_saver_get_status())}")
    elif args.test_wifi:
        from jarvis.capabilities.windows_system import wifi_get_status, wifi_list_networks
        st = wifi_get_status()
        print(f"Wi-Fi Status: {st.output if st.success else st.error}")
        net = wifi_list_networks()
        if net.success:
            print(f"Networks:\n" + "\n".join(net.output))
        else:
            print("Could not list networks.")
    elif args.test_bluetooth:
        from jarvis.capabilities.windows_system import bluetooth_get_status, bluetooth_discover_devices, bluetooth_get_connected_devices
        st = bluetooth_get_status()
        print(f"Bluetooth Radio: {st.output}")
        
        disc = bluetooth_discover_devices()
        print(f"\nPaired Devices:")
        if disc.success:
            for d in disc.output:
                if d['status'] != 'Connected':
                    print(f"- {d['name']} [{d['status'].upper()}]")
        
        conn = bluetooth_get_connected_devices()
        print(f"\nConnected Devices:")
        if conn.success and conn.output:
            for d in conn.output:
                print(f"- {d['name']}")
        else:
            print("- None")
    elif args.bluetooth_devices:
        from jarvis.capabilities.windows_system import bluetooth_discover_devices
        disc = bluetooth_discover_devices()
        print(f"{disc.observation if hasattr(disc, 'observation') else disc}")
    elif args.test_audio:
        from jarvis.capabilities.windows_system import audio_output_get, audio_output_list
        res_get = audio_output_get()
        res_list = audio_output_list()
        print(f"Current Output: {res_get.observation if hasattr(res_get, 'observation') else res_get}")
        print(f"Outputs:\n{res_list.observation if hasattr(res_list, 'observation') else res_list}")
    elif args.test_audio_list:
        from jarvis.capabilities.windows_system import audio_output_list
        res_list = audio_output_list()
        print(f"Outputs:\n{res_list.observation if hasattr(res_list, 'observation') else res_list}")
    elif args.test_brightness:
        from jarvis.capabilities.windows_system import brightness_get
        res = brightness_get()
        print(f"Brightness: {res.observation if hasattr(res, 'observation') else res}")
    elif args.test_volume:
        from jarvis.capabilities.windows_system import volume_get
        res = volume_get()
        print(f"Volume: {res.observation if hasattr(res, 'observation') else res}")
    elif args.test_volume_set is not None:
        from jarvis.capabilities.windows_system import volume_set
        res = volume_set(args.test_volume_set)
        print(f"Set Volume to {args.test_volume_set}: {res.observation if hasattr(res, 'observation') else res}")
    elif args.test_volume_mute:
        from jarvis.capabilities.windows_system import volume_mute
        res = volume_mute()
        print(f"Mute Volume: {res.observation if hasattr(res, 'observation') else res}")
    elif args.test_volume_unmute:
        from jarvis.capabilities.windows_system import volume_unmute
        res = volume_unmute()
        print(f"Unmute Volume: {res.observation if hasattr(res, 'observation') else res}")
    elif args.test_airplane:
        from jarvis.capabilities.windows_system import airplane_mode_get_status
        res = airplane_mode_get_status()
        print(f"Airplane Mode: {res.observation if hasattr(res, 'observation') else res}")
    elif args.test_energy_saver:
        from jarvis.capabilities.windows_system import energy_saver_get_status
        res = energy_saver_get_status()
        print(f"Energy Saver: {res.observation if hasattr(res, 'observation') else res}")
    elif args.tools_only:
        run_tools_only()
    else:
        run_full(args.command)
