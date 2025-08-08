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
AGENTS = os.getenv("HUMAN_AGENTS", "").split(",")

def send_chatwoot_reply(convo_id: int, text: str):
    # Local import avoids circular dependency
    from chatwootWebhook import _cw_api as cw_api
    cw_api(
        f"/conversations/{convo_id}/messages",
        method="POST",
        json={
            "content": text,
            "message_type": "outgoing",
            "content_type": "text",
        },
    )

def notify_agent(user_phone: str, doc_num: str):
    """Ping all agents when a hand‑off starts."""
    body = f"⚠️ Nuevo chat 👉 {user_phone}  (doc {doc_num})"
    for a in filter(None, AGENTS):
        send_text(a, body)

def forward_to_agent(user_phone: str, text: str):
    """Relay every customer message to the agents."""
    for a in filter(None, AGENTS):
        send_text(a, f"[{user_phone}] {text}")

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

def confirm_text(body: str, toConfirm: str) -> bool:
    if (str == toConfirm):
        return True
    else:
        return False


def send_two_buttons(to: str,
                    question: str,
                    yes_id: str,
                    no_id: str,
                    str1: str,
                    str2: str) -> str:
    if not to:
        raise ValueError("send_two_buttons(): 'to' phone num is empty")

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": { "text": question },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": { "id": yes_id, "title": str1 }
                    },
                    {
                        "type": "reply",
                        "reply": { "id": no_id,  "title": str2 }
                    }
                ]
            }
        }
    }
    return _post(payload)["messages"][0]["id"]

def sendDocType(to: str, body: str):
    if not to:
        raise ValueError("sendDocType(): 'to' phone num is empty")
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
            "text": body
            },
            "action": {
            "button": "Tipos de Documento",
            "sections": [
                {
                "title": "Tipo de Documento",
                "rows": [
                    { "id": "CC",   "title": "Cedula de Ciudadania"  },
                    { "id": "TI",   "title": "Tarjeta de Identidad" },
                    { "id": "RC",   "title": "Registro Civil"  },
                    { "id": "CE",   "title": "Cedula de Extranjeria"  },
                    { "id": "PT",   "title": "PT"  },
                    { "id": "SC",   "title": "Salvoconducto"  },
                    { "id": "AS",   "title": "Adulto Sin I.D."  },
                    ]
                    }
                ]
            }
        }
    }
    return _post(payload)["messages"][0]["id"]

def sendMenu(to: str, body:str):
    if not to:
        raise ValueError("sendDocType(): 'to' phone num is empty")
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
            "text": body
            },
            "action": {
            "button": "Menu",
            "sections": [
                {
                "title": "Menu",
                "rows": [
                    { "id": "ESTADO_MED",     "title": "Estado del Medicamento"  },
                    { "id": "HORARIO_UBI",    "title": "Horarios"  },
                    { "id": "MED_AUTORIZAR",  "title": "Medicamento a Domicilio"  },
                    { "id": "OTROS",          "title": "Otros"  }
                    ]
                    }
                ]
            }
        }
    }
    return _post(payload)["messages"][0]["id"]
