import re
from jarvis.voice.stt import STTProvider
from jarvis.voice.tts import FishAudioTTS, PiperTTS, WindowsTTS
from jarvis.voice.wake_word import strip_wake_word
from jarvis.voice.voice_config import VOICE_MODE, VOICE_PROVIDER
import time

def clean_response(text: str) -> str:
    """Removes internal tags and raw JSON so TTS speaks naturally."""
    if not text:
        return text
    
    # Remove standard tags
    tags = [
        r"\[ROUTER\]", r"\[PARSE\]", r"\[AGENT\]", r"\[PLAN\]", 
        r"\[OBSERVE\]", r"\[ACT\]", r"\[VERIFY\]", r"\[RESULT\]",
        r"\[OK\]", r"\[FAILED\]", r"\[DATA\]", r"\[QUESTION TYPE\]", r"\[HANDLER\]"
    ]
    for tag in tags:
        text = re.sub(tag, "", text, flags=re.IGNORECASE)
        
    # Remove raw JSON blocks loosely (anything inside large braces might be risky to speak)
    # Actually just remove formatting like ```json ... ```
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    
    # Humanize common ugly internal errors
    error_mappings = [
        (r"Planning failed:.*JSON parsing.*", "I'm sorry, I couldn't understand how to execute that task."),
        (r"PlaywrightTimeoutError.*", "I couldn't complete the action because the browser took too long to respond."),
        (r"FileNotFoundError.*", "I couldn't find that file or folder."),
        (r"PermissionError.*", "I found it, but Windows wouldn't let me access it."),
        (r"subprocess returned non-zero exit status.*", "I couldn't open that application.")
    ]
    for pattern, replacement in error_mappings:
        if re.search(pattern, text, re.IGNORECASE):
            return replacement
            
    # Remove multiple spaces/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text

class VoiceManager:
    def __init__(self, agent):
        self.agent = agent
        self.stt = STTProvider()
        
        provider = VOICE_PROVIDER.lower()
        if provider == "piper":
            self.tts = PiperTTS()
        elif provider == "windows":
            self.tts = WindowsTTS()
        else:
            self.tts = FishAudioTTS()
            
    def process_voice_command(self, text: str):
        # We need to import handle_command dynamically to avoid circular imports 
        # if voice_manager is imported inside jarvis_integration
        from jarvis_integration import handle_command
        
        command = strip_wake_word(text)
        if command is None:
            # Wake word was not present at all, ignore the speech.
            return
            
        if command == "":
            # Only the wake word was spoken
            self.tts.speak("Yes, I'm listening.")
            return
            
        print(f"[STT] {command}")
        
        # Check for interrupt/stop command
        if command.lower() in ["stop", "cancel", "never mind", "nevermind"]:
            self.tts.stop()
            self.tts.speak("Stopped.")
            return

        result = handle_command(self.agent, command)
        
        if result and result.text:
            spoken_text = clean_response(result.text)
            if spoken_text:
                self.tts.speak(spoken_text)

    def run_continuous(self):
        print("[VOICE] Starting continuous conversation mode...")
        
        # Diagnostic check
        if not self.stt.is_ready:
            print(f"[VOICE ERROR] {self.stt.init_error}")
            print("[VOICE] Falling back to text mode...")
            self.run_push_to_talk() # text-mode fallback
            return
            
        while True:
            try:
                res = self.stt.listen()
                if not res:
                    continue
                if "error" in res:
                    print(f"[VOICE ERROR] {res['error']}")
                    if "not available" in res['error']:
                        print("[VOICE] Falling back to text mode...")
                        self.run_push_to_talk()
                        break
                    time.sleep(1) # Prevent tight error loops
                    continue
                    
                text = res.get("text", "")
                if text:
                    self.process_voice_command(text)
            except KeyboardInterrupt:
                print("\n[VOICE] Exiting voice mode.")
                break
            except Exception as e:
                print(f"[VOICE EXCEPTION] {e}")
                time.sleep(1)

    def run_push_to_talk(self):
        print("[VOICE] Push-to-talk mode enabled. Press Enter to start speaking (or type a command).")
        print("[VOICE] (Ctrl+C to exit)")
        while True:
            try:
                user_input = input("JARVIS> ")
                if user_input.strip() == "":
                    # Empty input = activate microphone
                    res = self.stt.listen()
                    if res and "error" not in res and res.get("text"):
                        self.process_voice_command(res["text"])
                    elif res and "error" in res:
                        print(f"[VOICE ERROR] {res['error']}")
                else:
                    # Treat as typed command
                    self.process_voice_command(user_input)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[VOICE EXCEPTION] {e}")

    def start(self):
        if VOICE_MODE.upper() == "CONTINUOUS":
            self.run_continuous()
        else:
            self.run_push_to_talk()
