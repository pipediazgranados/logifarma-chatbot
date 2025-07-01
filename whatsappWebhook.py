from flask import Flask, request, abort

app = Flask(__name__)

VERIFY_TOKEN = "token" #replace with actual token when you get it!
@app.route("/webhook", mehods=["GET", "POST"])

def whatsappWebhook():
    if request.method == "GET":
        mode        = request.args.get("hub.mode")
        token       = request.args.get("hub.verify_token")
        challenge   = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return abort(403)
    
    if request.method == "POST":
        payload = request.get_json()
        type, value, sender = parse_incoming(payload)

        bot = #initialize state machine        

        if type == "text":
            bot.text_recieved(value)
        if type == "button":
            bot.button_pressed(value)
        if type == "list":
            bot.list_op(value)
        else:
            bot.unsupported()

    return "EVENT_RECIEVED", 200

def parse_incoming(payload:dict) -> tuple[str, str, str]:
    msg = (payload["entry"][0]["changes"][0]["value"]["messages"][0])
    sender = msg["from"]

    try:
        if msg["type"] == "text":
            return "text", msg["text"]["body"], sender

        if msg["type"] == "interactive":
            itype = msg["interactive"]["type"]

            if itype == "button_reply":
                data = msg["interactive"]["button_reply"]
                return "button", data["id"], sender

            if itype == "list_reply":
                data = msg["interactive"]["list_reply"]
                return "list", data["id"], sender

        return "unsupported", ""
    except (keyError, indexError):
        return "unsupported", "", ""

