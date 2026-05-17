import requests
import time
import numpy as np
import wave
import io
import base64

BASE_URL = "https://sproochmaschinn.lu"

# Global session cache to prevent 10-minute inactivity timeouts
_session_id = None
_last_active = 0

def _get_active_session():
    """Returns a valid session ID, recreating it if expired due to inactivity."""
    global _session_id, _last_active
    
    # Refresh session if inactive for more than 9 minutes (540s)
    if not _session_id or (time.time() - _last_active) > 540:
        res = requests.post(f"{BASE_URL}/api/session")
        res.raise_for_status()
        _session_id = res.json()["session_id"]
        
    _last_active = time.time()
    return _session_id

def generate_tts(text: str, model: str = "max"):
    """
    Synthesizes TTS via sproochmaschinn.lu API.
    Returns a tuple of (sample_rate, audio_array) formatted for fastrtc.
    """
    session_id = _get_active_session()

    # Initiate asynchronous TTS generation
    tts_res = requests.post(
        f"{BASE_URL}/api/tts/{session_id}",
        json={"text": text, "model": model}
    )
    tts_res.raise_for_status()
    request_id = tts_res.json()["request_id"]

    # Poll the result endpoint until completion
    while True:
        res = requests.get(f"{BASE_URL}/api/result/{request_id}")
        res.raise_for_status()
        data = res.json()
        
        if data["status"] == "completed":
            b64_audio = data["result"]["data"]
            break
        elif data["status"] in ["failed", "error"]:
            raise RuntimeError(f"TTS API Error: {data}")
        
        # Backoff to respect API polling limits
        time.sleep(1)

    # Decode base64 payload into a raw byte stream
    wav_bytes = base64.b64decode(b64_audio)

    # Parse WAV header and extract PCM frames
    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        sample_rate = wf.getframerate()
        num_frames = wf.getnframes()
        raw_audio = wf.readframes(num_frames)
        
        # Convert 16-bit PCM buffer directly to int16 numpy array
        audio_int16 = np.frombuffer(raw_audio, dtype=np.int16)
        
        # Reshape to (1, N) to satisfy fastrtc 2D array requirements
        audio_int16 = audio_int16.reshape(1, -1)

    return sample_rate, audio_int16

def speak(text: str, model: str = "max"):
    """
    Synthesizes text and streams the resulting audio through the default output device.
    """
    import sounddevice as sd
    
    print(f"Generating audio for: '{text}'")
    sample_rate, audio_data = generate_tts(text, model)
    
    # Transpose from (1, frames) to (frames, channels) as expected by sounddevice
    audio_out = audio_data.T
    
    print("Playing audio...")
    sd.play(audio_out, sample_rate)
    sd.wait()