
from typing import Tuple
import logging
log = logging.getLogger(__name__)

def parse_incoming(payload:dict) -> tuple[str, str, str]:
    try:
        change = payload["entry"][0]["changes"][0]["value"]

        # 1) real user message
        if "messages" in change:
            msg = change["messages"][0]
            sender = msg["from"]               # always present here

            if msg["type"] == "text":
                return "text", msg["text"]["body"], sender

            if msg["type"] == "interactive":
                itype = msg["interactive"]["type"]
                if itype == "button_reply":
                    return "button", msg["interactive"]["button_reply"]["id"], sender
                if itype == "list_reply":
                    return "list", msg["interactive"]["list_reply"]["id"], sender

            return "unsupported", "", sender

        # 2) delivery/read status → ignore
        if "statuses" in change:
            return "status", "", ""            # no reply!

    except (KeyError, IndexError) as err:
        log.debug("Unhandled payload: %s", err)

    return "unsupported", "", ""