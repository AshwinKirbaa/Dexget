from pycaw.pycaw import AudioUtilities

try:
    spk = AudioUtilities.GetSpeakers()
    print("Speakers object:", spk)
    print("EndpointVolume:", spk.EndpointVolume)
    vol = spk.EndpointVolume
    print("Current volume scalar:", vol.GetMasterVolumeLevelScalar())
    
    # Test setting volume
    vol.SetMasterVolumeLevelScalar(0.6, None)
    print("Volume set to 0.6 successfully!")
except Exception as e:
    print(f"Error: {e}")
