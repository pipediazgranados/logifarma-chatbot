
from typing import Tuple
import logging
log = logging.getLogger(__name__)

def parse_incoming(payload:dict) -> tuple[str, str, str]:
    try:
        msg = (payload["entry"][0]["changes"][0]["value"]["messages"][0])
        sender = msg["from"]
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


    except (KeyError, IndexError) as err:
        log.debug("Unsupported payload shape: %s", err)


    return "unsupported", "", sender if 'sender' in locals() else ""
