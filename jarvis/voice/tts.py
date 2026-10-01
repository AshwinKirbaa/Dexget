import os
import requests
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod

from jarvis.voice.voice_config import FISH_API_KEY, FISH_VOICE_ID, FISH_MODEL

class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str):
        pass

    @abstractmethod
    def speak(self, text: str):
        pass

    @abstractmethod
    def stop(self):
        pass


class WindowsTTS(TTSProvider):
    def __init__(self):
        self._process = None

    def synthesize(self, text: str):
        pass

    def speak(self, text: str):
        print(f"[TTS] {text}")
        # Use powershell for simple TTS fallback
        ps_script = f"Add-Type -AssemblyName System.speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak('{text.replace(chr(39), chr(39)+chr(39))}')"
        self._process = subprocess.Popen(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
        self._process.wait()

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()


class FishAudioTTS(TTSProvider):
    def __init__(self):
        self.api_key = FISH_API_KEY
        self.voice_id = FISH_VOICE_ID
        self.model = FISH_MODEL
        self._stop_event = threading.Event()
        self._playing_process = None

    def synthesize(self, text: str):
        # Using Fish Audio v1 TTS API
        # We request mp3 or wav.
        url = "https://api.fish.audio/v1/tts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if self.model:
            headers["model"] = self.model
            
        payload = {
            "text": text,
            "reference_id": self.voice_id,
            "format": "wav",
        }
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                print(f"[TTS ERROR] Fish API failed: {response.status_code} {response.text}")
                return None
                
            return response.content
        except Exception as e:
            print(f"[TTS ERROR] {e}")
            return None

    def speak(self, text: str):
        self._stop_event.clear()
        print(f"[TTS] {text}")
        
        if not self.api_key:
            print("[TTS FALLBACK] No Fish Audio API Key configured. Using Windows TTS.")
            return WindowsTTS().speak(text)
            
        audio_data = self.synthesize(text)
        if not audio_data:
            print("[TTS FALLBACK] Fish Audio synthesis failed. Using Windows TTS.")
            return WindowsTTS().speak(text)
            
        # Play the wav file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            f.write(audio_data)
            temp_name = f.name
            
        try:
            import sys
            try:
                import pyaudiowpatch
                sys.modules['pyaudio'] = pyaudiowpatch
            except ImportError:
                pass
            import pyaudio
            import wave
            from jarvis.voice.voice_config import SPEAKER_DEVICE_INDEX
            
            wf = wave.open(temp_name, 'rb')
            p = pyaudio.PyAudio()
            out_idx = SPEAKER_DEVICE_INDEX
            if out_idx is None:
                try:
                    out_idx = p.get_default_output_device_info()['index']
                except:
                    pass
            
            try:
                try:
                    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                                    channels=wf.getnchannels(),
                                    rate=wf.getframerate(),
                                    output=True,
                                    output_device_index=out_idx)
                    
                    data = wf.readframes(1024)
                    while len(data) > 0 and not self._stop_event.is_set():
                        stream.write(data)
                        data = wf.readframes(1024)
                        
                except Exception as stream_e:
                    # Fallback to device's max output channels if there's a channel mismatch
                    print(f"[TTS DEBUG] Native channels failed ({stream_e}). Trying device default channels...")
                    out_info = p.get_device_info_by_index(out_idx)
                    dev_channels = int(out_info.get('maxOutputChannels', 2))
                    
                    if dev_channels > 0:
                        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                                        channels=dev_channels,
                                        rate=wf.getframerate(),
                                        output=True,
                                        output_device_index=out_idx)
                        
                        data = wf.readframes(1024)
                        while len(data) > 0 and not self._stop_event.is_set():
                            if wf.getnchannels() == 1 and dev_channels == 2 and wf.getsampwidth() == 2:
                                # Duplicate mono to stereo for 16-bit
                                stereo_data = bytearray()
                                for i in range(0, len(data), 2):
                                    stereo_data.extend(data[i:i+2])
                                    stereo_data.extend(data[i:i+2])
                                stream.write(bytes(stereo_data))
                            else:
                                stream.write(data)
                            data = wf.readframes(1024)
                    else:
                        raise stream_e
                        
                stream.stop_stream()
                stream.close()
            except Exception as e:
                print(f"[TTS ERROR] PyAudio playback failed: {e}")
                print("[TTS FALLBACK] Using Windows TTS instead.")
                WindowsTTS().speak(text)
            finally:
                p.terminate()
                wf.close()
        finally:
            if os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except:
                    pass

    def stop(self):
        self._stop_event.set()
        if self._playing_process and self._playing_process.poll() is None:
            self._playing_process.terminate()

class PiperTTS(TTSProvider):
    # Stub for piper
    def synthesize(self, text: str):
        pass
    def speak(self, text: str):
        WindowsTTS().speak(text)
    def stop(self):
        pass
