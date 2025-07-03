import os, json, logging, requests
from typing import List
from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger(__name__)

PHONE_ID     = os.getenv("WA_PHONE_ID")
ACCESS_TOKEN = os.getenv("WA_TOKEN")
API_ROOT     = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"
HEADERS      = {"Authorization": f"Bearer {ACCESS_TOKEN}",
                "Content-Type": "application/json"}

def _post(payload:dict) -> dict:
    resp = requests.post(API_ROOT, headers=HEADERS, data=json.dumps(payload))
    try:
        data = resp.json()
    
    except ValueError:
        resp.raise_for_status()
    if resp.status_code>= 300:
        log.error("WA error %s -> %s", resp.status_code, data)
        raise RuntimeError(data)
    return data



def send_text(to: str, body: str, preview_url: bool = False) -> str:
    if not to:
        log.warning("send_text called with empty 'to'; skipping")
        return ""

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body, "preview_url": preview_url}
    }
    return _post(payload)["messages"][0]["id"]


