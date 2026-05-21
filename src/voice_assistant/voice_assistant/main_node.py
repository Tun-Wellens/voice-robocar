import rclpy
from rclpy.node import Node
import threading
import sys
import io
import queue
import sounddevice as sd
import soundfile as sf
import numpy as np
import webrtcvad
import openwakeword
from openwakeword.model import Model
from robocar_msgs.msg import GNSS, Path

from voice_assistant.gemini_llm import GeminiAssistant
from voice_assistant import stt_luxasr
from voice_assistant import tts_zls

class VoiceAssistantNode(Node):
    def __init__(self):
        super().__init__('voice_assistant_node')
        
        # State caching for vehicle telemetry
        self.current_gnss = None
        self.current_path = None
        
        # ROS 2 Subscriptions
        self.gnss_sub = self.create_subscription(GNSS, '/sensors/gnss', self.gnss_callback, 10)
        self.path_sub = self.create_subscription(Path, '/robocar/path', self.path_callback, 10)

    def gnss_callback(self, msg):
        self.current_gnss = msg

    def path_callback(self, msg):
        self.current_path = msg

def play_ding():
    try:
        fs = 16000
        t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
        samples = (np.sin(2 * np.pi * 880 * t) * 0.1).astype(np.float32)
        sd.play(samples, samplerate=fs)
        sd.wait()
    except Exception as e:
        print(f"Could not play ding: {e}")

def setup_audio_device():
    """
    Detects and configures the default ALSA/PulseAudio device.
    Prioritizes 'pulse' or 'default' devices mapped through the Docker container.
    """
    try:
        devices = sd.query_devices()
        target_idx = None
        for i, dev in enumerate(devices):
            name = dev['name'].lower()
            if 'pulse' in name or 'default' in name:
                if dev['max_input_channels'] > 0:
                    target_idx = i
                    break
        
        if target_idx is not None:
            print(f"Found PulseAudio/Default device at index {target_idx}: {devices[target_idx]['name']}")
            sd.default.device = target_idx
            return target_idx
        else:
            print("'pulse' or 'default' device not found. Using system default.")
            return sd.default.device[0]
            
    except Exception as e:
        print(f"Error setting up audio device: {e}")
        return sd.default.device[0]

def main(args=None):
    rclpy.init(args=args)
    node = VoiceAssistantNode()
    
    # Offload ROS 2 spinning to a background thread to prevent blocking the audio I/O loop
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,))
    spin_thread.start()

    llm = GeminiAssistant()
    
    print("Loading Wake Word Model...")
    owwModel = Model(wakeword_model_paths=["/workspace/models/moien_junior.onnx"])
    
    vad = webrtcvad.Vad(3) # High sensitivity
    
    print("\n" + "="*50)
    print("Junior Voice Assistant is Ready! Listening for 'Moien Junior'...")
    print("="*50)

    try:
        target_device = setup_audio_device()
        samplerate = 16000 # Required by OpenWakeWord
        blocksize = 1280   # Standard blocksize for OpenWakeWord
        
        q = queue.Queue()

        def callback(indata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            q.put(indata.copy())

        state = "IDLE"
        audio_buffer = []
        silence_frames = 0
        max_silence_frames = int(1.5 * samplerate / blocksize) # 1.5 seconds

        # Initialize and start the audio input stream
        stream = sd.InputStream(device=target_device, samplerate=samplerate, channels=1, dtype='int16', blocksize=blocksize, callback=callback)
        with stream:
            while True:
                chunk = q.get()
                
                if state == "IDLE":
                    # Check for wake word
                    audio_frame = chunk.flatten()
                    prediction = owwModel.predict(audio_frame)
                    
                    # The prediction dict is {model_name: score}
                    score = list(prediction.values())[0]
                    print(f"Listening... Model Score: {score:.4f}", end='\r')
                    if score > 0.05:
                        print("\n[Wake Word Detected!] Listening for command...")
                        play_ding()
                        state = "RECORDING"
                        audio_buffer = []
                        silence_frames = 0
                        
                elif state == "RECORDING":
                    audio_buffer.append(chunk)
                    
                    # WebRTC VAD check
                    chunk_bytes = chunk.tobytes()
                    is_speech = False
                    for i in range(0, 2560, 640):
                        vad_chunk = chunk_bytes[i:i+640]
                        if vad.is_speech(vad_chunk, samplerate):
                            is_speech = True
                            break
                    
                    if is_speech:
                        silence_frames = 0
                    else:
                        silence_frames += 1
                        
                    if silence_frames >= max_silence_frames:
                        print("[Silence Detected] Processing command...")
                        state = "PROCESSING"
                        
                        # Empty remaining items in queue so we don't process delayed audio
                        with q.mutex:
                            q.queue.clear()
                            
                        # Aggregate recorded audio chunks
                        audio_concat = np.concatenate(audio_buffer, axis=0)
                        
                        duration = len(audio_concat) / samplerate
                        print(f"Recorded {len(audio_concat)} frames ({duration:.2f} seconds).")

                        # Convert our raw audio data into a standard WAV format in memory so the Speech-to-Text engine can read it
                        wav_io = io.BytesIO()
                        sf.write(wav_io, audio_concat, samplerate, format='WAV', subtype='PCM_16')
                        wav_bytes = wav_io.getvalue()
                        
                        # STT inference
                        print("Transcribing (LuxASR)...")
                        text = stt_luxasr.transcribe(wav_bytes)
                        if not text:
                            print("Failed to transcribe or no speech detected.")
                        else:
                            print(f"User: '{text}'")

                            # LLM generation
                            print("Thinking (Gemini)...")
                            response = llm.process_prompt(text, node)
                            print(f"Assistant: {response}")

                            # TTS execution
                            tts_zls.speak(response)
                            
                        print("\nListening for 'Moien Junior'...")
                        # Reset the wake word model state so it doesn't immediately trigger again
                        owwModel.reset()
                        state = "IDLE"

    except KeyboardInterrupt:
        print("\nShutting down Voice Assistant...")
    finally:
        rclpy.shutdown()
        spin_thread.join()

if __name__ == '__main__':
    main()