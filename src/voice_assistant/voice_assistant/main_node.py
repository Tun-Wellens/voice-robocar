import rclpy
from rclpy.node import Node
import threading
import sys
import io
import queue
import sounddevice as sd
import soundfile as sf
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
        self.gnss_sub = self.create_subscription(GNSS, '/robocar/gnss', self.gnss_callback, 10)
        self.path_sub = self.create_subscription(Path, '/robocar/path', self.path_callback, 10)

    def gnss_callback(self, msg):
        self.current_gnss = msg

    def path_callback(self, msg):
        self.current_path = msg

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
    
    print("\n" + "="*50)
    print("Junior Voice Assistant is Ready!")
    print("="*50)

    try:
        while True:
            # Push-to-talk trigger
            input("\n[Push-to-Talk] Press ENTER to START recording...")
            
            target_device = setup_audio_device()

            try:
                device_info = sd.query_devices(target_device, 'input')
            except Exception as e:
                print(f"Error accessing device {target_device}. Falling back to default. Error: {e}")
                target_device = sd.default.device[0]
                device_info = sd.query_devices(target_device, 'input')

            samplerate = int(device_info['default_samplerate'])
            
            print(f"Using Microphone: {device_info['name']} (Sample Rate: {samplerate})")
            
            q = queue.Queue()

            def callback(indata, frames, time, status):
                if status:
                    print(status, file=sys.stderr)
                q.put(indata.copy())

            # Initialize and start the audio input stream
            stream = sd.InputStream(device=target_device, samplerate=samplerate, channels=1, callback=callback)
            with stream:
                input("[Recording...] Press ENTER to STOP recording...\n")
                
            print("Processing audio...")

            # Aggregate recorded audio chunks
            audio_data = []
            while not q.empty():
                audio_data.append(q.get())
            
            import numpy as np
            if len(audio_data) == 0:
                continue
                
            audio_concat = np.concatenate(audio_data, axis=0)
            
            duration = len(audio_concat) / samplerate
            print(f"Recorded {len(audio_concat)} frames ({duration:.2f} seconds).")

            # Encode raw PCM to in-memory WAV buffer for STT consumption
            wav_io = io.BytesIO()
            sf.write(wav_io, audio_concat, samplerate, format='WAV', subtype='PCM_16')
            wav_bytes = wav_io.getvalue()
            
            # STT inference
            print("Transcribing (LuxASR)...")
            text = stt_luxasr.transcribe(wav_bytes)
            if not text:
                print("Failed to transcribe or no speech detected.")
                continue
            
            print(f"User: '{text}'")

            # LLM generation
            print("Thinking (Gemini)...")
            response = llm.process_prompt(text, node)
            print(f"Assistant: {response}")

            # TTS execution
            tts_zls.speak(response)

    except KeyboardInterrupt:
        print("\nShutting down Voice Assistant...")
    finally:
        rclpy.shutdown()
        spin_thread.join()

if __name__ == '__main__':
    main()