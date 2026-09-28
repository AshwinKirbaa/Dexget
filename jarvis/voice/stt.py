import os
import sys
import time
import wave
import struct
import tempfile
import array

try:
    import pyaudiowpatch
    sys.modules['pyaudio'] = pyaudiowpatch
except ImportError:
    pass

import pyaudio

try:
    import vosk
    vosk.SetLogLevel(-1)
except ImportError:
    vosk = None

from faster_whisper import WhisperModel

VOSK_SAMPLE_RATE = 16000

def get_vosk_path():
    return r"C:\Users\ashwi\.jarvis\vosk-model-small-en-us-0.15"

VOSK_MODEL_PATH = get_vosk_path()

def resample_pcm(pcm_data, in_rate, out_rate=16000):
    if in_rate == out_rate:
        return pcm_data
    in_samples = array.array('h', pcm_data)
    out_len = int(len(in_samples) * out_rate / in_rate)
    out_samples = array.array('h', [0] * out_len)
    ratio = in_rate / out_rate
    for i in range(out_len):
        in_idx = int(i * ratio)
        if in_idx >= len(in_samples):
            in_idx = len(in_samples) - 1
        out_samples[i] = in_samples[in_idx]
    return out_samples.tobytes()

class STTProvider:
    def __init__(self):
        self.pyaudio_instance = pyaudio.PyAudio()
        self.mic_stream = None
        self.capture_rate = 16000
        
        self.vosk_model = None
        self.vosk_recognizer = None
        self.whisper_model = None
        self.is_ready = False
        self.init_error = None
        
        self.initialize_models()

    def initialize_models(self):
        print("[VOICE] Initializing Voice Pipeline...")
        
        if vosk is None:
            self.init_error = "Vosk package not installed."
            return
            
        # 1. Load Vosk
        if not os.path.exists(VOSK_MODEL_PATH):
            self.init_error = f"Vosk model not found at {VOSK_MODEL_PATH}.\nPlease download vosk-model-en-us-0.22 and extract it there."
            print(f"[VOICE ERROR] {self.init_error}")
            return
            
        try:
            self.vosk_model = vosk.Model(VOSK_MODEL_PATH)
            self.vosk_recognizer = vosk.KaldiRecognizer(self.vosk_model, VOSK_SAMPLE_RATE)
            print("[VOICE] Vosk model: ready")
        except Exception as e:
            self.init_error = f"Failed to load Vosk model: {e}"
            print(f"[VOICE ERROR] {self.init_error}")
            return

        # 2. Open Microphone
        try:
            self._open_microphone()
            print(f"[VOICE] Microphone: ready (Capture rate: {self.capture_rate} Hz)")
        except Exception as e:
            self.init_error = f"Failed to open microphone: {e}"
            print(f"[VOICE ERROR] {self.init_error}")
            return
            
        # 3. Load Whisper
        try:
            print("[VOICE] Loading local STT model (faster-whisper base.en)...")
            self.whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
            print("[VOICE] Whisper: ready")
        except Exception as e:
            print(f"[VOICE ERROR] Whisper load failed: {e}")
            # We can still fallback to Vosk if Whisper fails to load.
        
        self.is_ready = True

    def _open_microphone(self):
        from jarvis.voice.voice_config import MIC_DEVICE_INDEX
        default_idx = None
        default_channels = 1
        
        if MIC_DEVICE_INDEX is not None:
            default_idx = MIC_DEVICE_INDEX
            info = self.pyaudio_instance.get_device_info_by_index(default_idx)
            self.capture_rate = int(info['defaultSampleRate'])
            default_channels = int(info.get('maxInputChannels', 1))
        else:
            # Find a suitable real microphone
            try:
                default_info = self.pyaudio_instance.get_default_input_device_info()
                default_idx = default_info['index']
                self.capture_rate = int(default_info['defaultSampleRate'])
                default_channels = int(default_info.get('maxInputChannels', 1))
            except IOError:
                # Search manually
                for i in range(self.pyaudio_instance.get_device_count()):
                    info = self.pyaudio_instance.get_device_info_by_index(i)
                    if info['maxInputChannels'] > 0:
                        default_idx = i
                        self.capture_rate = int(info['defaultSampleRate'])
                        default_channels = int(info.get('maxInputChannels', 1))
                        break
        
        if default_idx is None:
            raise Exception("No input devices found.")
            
        print(f"[VOICE DEBUG] Opening mic - Index: {default_idx}, Channels: {default_channels}, Rate: {self.capture_rate}")
        # Try native rate, fallback to 16000
        try:
            self.mic_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=default_channels,
                rate=self.capture_rate,
                input=True,
                input_device_index=default_idx,
                frames_per_buffer=4096
            )
        except Exception as e:
            print(f"[VOICE DEBUG] Native rate failed: {e}. Trying fallback rate 16000.")
            # Fallback
            self.capture_rate = 16000
            self.mic_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=default_channels,
                rate=self.capture_rate,
                input=True,
                input_device_index=default_idx,
                frames_per_buffer=4096
            )

    def listen(self):
        """Persistent listen loop. Returns transcribed text when a phrase ends."""
        if not self.is_ready:
            return {"error": "Voice recognition isn't available because the Vosk model could not be loaded."}
            
        if not self.mic_stream or not self.mic_stream.is_active():
            try:
                self._open_microphone()
            except Exception:
                return {"error": "I couldn't access the microphone."}
                
        print("[VOICE] Listening...")
        accumulated_pcm = bytearray()
        
        # Flush any existing buffer to avoid processing old speech
        try:
            while self.mic_stream.get_read_available() > 0:
                self.mic_stream.read(self.mic_stream.get_read_available(), exception_on_overflow=False)
        except Exception:
            pass
            
        while True:
            try:
                data = self.mic_stream.read(4096, exception_on_overflow=False)
                resampled_data = resample_pcm(data, self.capture_rate, VOSK_SAMPLE_RATE)
                accumulated_pcm.extend(resampled_data)
                
                if self.vosk_recognizer.AcceptWaveform(resampled_data):
                    # Phrase completed
                    vosk_result = self.vosk_recognizer.Result()
                    
                    if len(accumulated_pcm) > 0:
                        # Convert to WAV
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                            with wave.open(f, 'wb') as wav_file:
                                wav_file.setnchannels(1)
                                wav_file.setsampwidth(2)
                                wav_file.setframerate(VOSK_SAMPLE_RATE)
                                wav_file.writeframes(accumulated_pcm)
                            temp_path = f.name
                            
                        final_text = ""
                        try:
                            if self.whisper_model:
                                print("[VOICE] Transcribing with Whisper...")
                                start = time.time()
                                segments, _ = self.whisper_model.transcribe(temp_path, language="en", beam_size=5, vad_filter=True)
                                final_text = " ".join([s.text for s in segments]).strip()
                                print(f"[WHISPER] {final_text}")
                        except Exception as e:
                            print(f"[VOICE ERROR] Whisper couldn't transcribe that phrase, so I'll try the local fallback. ({e})")
                        finally:
                            if os.path.exists(temp_path):
                                try:
                                    os.unlink(temp_path)
                                except:
                                    pass
                                    
                        if not final_text:
                            # Fallback to vosk
                            import json
                            res_dict = json.loads(vosk_result)
                            final_text = res_dict.get("text", "").strip()
                            print(f"[VOSK] {final_text}")
                            
                        if final_text:
                            return {"text": final_text}
                        else:
                            # False start or silent phrase
                            accumulated_pcm.clear()
                            print("[VOICE] Listening...")
                            
            except Exception as e:
                print(f"[VOICE ERROR] Capture loop failed: {e}")
                return {"error": "I couldn't access the microphone."}
