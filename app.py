from dotenv import load_dotenv
import os
from flask import Flask, request, abort

from utils import parse_incoming
from botFSM import ChatBot

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "fallback")
WA_PHONE_ID = os.getenv("WA_PHONE_ID")
WA_TOKEN = os.getenv("WA_TOKEN")

if not all((WA_PHONE_ID, WA_TOKEN)):
    raise RuntimeError("WA_PHONE_ID and WA_TOKEN must be in en vars or .env")

app = Flask(__name__)
machines: dict[str, ChatBot] = {}

@app.route("/webhook", methods=["GET", "POST"])
def incoming():
    if request.method == "GET":
        if (request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN):
            return request.args["hub.challenge"], 200
        return abort(403)

    payload = request.get_json()
    msg_type, value, sender = parse_incoming(payload)
    
    if not sender:
        return "EVENT_RECIEVED", 200
    
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

if __name__ == "__main__":
    app.run(port=5000, debug=True)