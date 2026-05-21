import requests
import json
import time

BASE_URL = "https://luxasr.uni.lu"

def transcribe(wav_file_bytes: bytes) -> str:
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
    try:
        parsed = json.loads(res_text)
        if isinstance(parsed, dict):
            return parsed.get("text", str(parsed))
        return str(parsed)
    except json.JSONDecodeError:
        return res_text