# app.py - Updated with proper Chatwoot integration
from dotenv import load_dotenv
import os
from flask import Flask, request, abort
from datetime import datetime, timedelta

from utils import parse_incoming
from botFSM import ChatBot
from whatsappAPI import send_text, AGENTS
from chatwootWebhook import cw_bp

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "fallback")
WA_PHONE_ID = os.getenv("WA_PHONE_ID")
WA_TOKEN = os.getenv("WA_TOKEN")

MACHINE_TIMEOUT = timedelta(hours=1)
machine_timestamps = {}

if not all((WA_PHONE_ID, WA_TOKEN)):
    raise RuntimeError("WA_PHONE_ID and WA_TOKEN must be in en vars or .env")

app = Flask(__name__)
machines: dict[str, ChatBot] = {}

def cleanup_old_machines():
    cutoff = datetime.now() - MACHINE_TIMEOUT
    expired = [k for k, v in machine_timestamps.items() if v < cutoff]
    for k in expired:
        machines.pop(k, None)
        machine_timestamps.pop(k, None)

@app.route("/webhook", methods=["GET", "POST"])
def incoming():
    try:
        if request.method == "GET":
            if (request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN):
                return request.args["hub.challenge"], 200
            return abort(403)

        payload = request.get_json()
        if not payload:
            return "No payload", 400

        msg_type, value, sender = parse_incoming(payload)
        
        if not sender:
            return "EVENT_RECIEVED", 200
        
        if sender in AGENTS:
            # Agents reply with “@<customer> mensaje…”
            if value.startswith("@"):
                dest, msg = value[1:].split(maxsplit=1)
                send_text(dest, msg)
            return "ok", 200
        
        bot = machines.setdefault(sender, ChatBot(sender=sender))

        if msg_type == "text":
            bot.text_op(value)
        elif msg_type == "button":
            bot.button_op(value)
        elif msg_type == "list":
            bot.list_op(value)
        else:
            bot.unsupported()

        return "ok", 200
    
    except Exception as e:
        print(f"Webhook error: {e}")
        return "Internal error", 500

if __name__ == "__main__":
    app.register_blueprint(cw_bp)
    app.run(port=5000, debug=True)