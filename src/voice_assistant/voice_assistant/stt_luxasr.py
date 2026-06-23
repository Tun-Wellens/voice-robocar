import requests
import json
import time
from std_msgs.msg import String

BASE_URL = "https://luxasr.uni.lu"

def transcribe(wav_file_bytes: bytes, log_publisher=None) -> str:
    # Notify UI that speech processing has started
    if log_publisher is not None:
        log_data = {"type": "speech_detected", "status": "Sending audio to LuxASR..."}
        msg = String(data=json.dumps(log_data))
        log_publisher.publish(msg)

    submit_url = f"{BASE_URL}/asr2?language=lb&diarization=Disabled&outfmt=text"
    r = requests.post(submit_url, data=wav_file_bytes, headers={"Content-Type": "audio/wav"})

    if r.status_code != 202:
        print("LuxASR error:", r.text)
        return ""

    job_id = r.json().get("job_id")
    if not job_id:
        return ""

    job_url = f"{BASE_URL}/v3/asr/jobs/{job_id}"
    while True:
        status_req = requests.get(job_url)
        if status_req.status_code not in (200, 202):
            return ""
            
        status = status_req.json().get("status")
        if status == "completed":
            break
        if status == "failed":
            return ""
            
        time.sleep(1)

    result_req = requests.get(f"{job_url}/result")
    if result_req.status_code != 200:
        return ""
        
    res_text = result_req.text.strip()
    
    # Parse the text safely
    final_text = res_text
    try:
        parsed = json.loads(res_text)
        if isinstance(parsed, dict):
            final_text = parsed.get("text", str(parsed))
        else:
            final_text = str(parsed)
    except json.JSONDecodeError:
        final_text = res_text

    # Publish transcribed text to UI
    if log_publisher is not None and final_text:
        log_data = {"type": "asr", "text": final_text, "job_id": job_id}
        msg = String(data=json.dumps(log_data))
        log_publisher.publish(msg)

    return final_text