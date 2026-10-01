import pycaw
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL, GUID, COMError
import ctypes

print("Pycaw version/module:", pycaw)

print("\n1. Testing AudioUtilities.GetSpeakers()...")
try:
    spk = AudioUtilities.GetSpeakers()
    print("Speakers object:", spk, type(spk))
    print("Attributes:", dir(spk))
except Exception as e:
    print(f"GetSpeakers error: {e}")

print("\n2. Testing spk.EndpointVolume...")
try:
    vol = spk.EndpointVolume
    print("EndpointVolume:", vol)
    print("Scalar volume:", vol.GetMasterVolumeLevelScalar())
except Exception as e:
    print(f"spk.EndpointVolume error: {e}")

print("\n3. Testing alternative IMMDeviceEnumerator / IAudioEndpointVolume via comtypes...")
try:
    from comtypes import CoCreateInstance, MMDeviceEnumerator
    CLSID_MMDeviceEnumerator = GUID('{BCDE0385-4640-443E-A03A-B4B48A613726}')
    IID_IMMDeviceEnumerator = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
    IID_IAudioEndpointVolume = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')
    
    # Standard WASAPI activation
    # 0 = eRender, 0 = eMultimedia
    enumerator = AudioUtilities.GetDeviceEnumerator()
    device = enumerator.GetDefaultAudioEndpoint(0, 0)
    print("Default device:", device)
    interface = device.Activate(IID_IAudioEndpointVolume, CLSCTX_ALL, None)
    volume = interface.QueryInterface(IAudioEndpointVolume)
    print("Direct WASAPI volume scalar:", volume.GetMasterVolumeLevelScalar())
except Exception as e:
    print(f"Direct WASAPI error: {e}")
