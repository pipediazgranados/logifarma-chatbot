import random

from enum import Enum
from enum import auto

from statemachine import State
from statemachine import StateMachine

from whatsappAPI import send_text

class ChatBot(StateMachine):
    # ── transitions (= real events) ────────
    start   = State(initial=True)
    docType = State()
    docNum  = State()
    idle    = State(final=True)  

    # ─────────── transitions (= events) ─────
    ask_doc_type = start.to(docType)
    ask_doc_num  = docType.to(docNum)
    finish       = docNum.to(idle)

    # ── constructor ────────────────────────
    def __init__(self, sender: str):
        super().__init__()
        self.sender = sender
        self.fallback_counter = 0
        self.ask_doc_type()

    # ── plain Python “event” methods ───────
    def text_received(self, body: str):
        send_text(self.sender, f"Echo: {body}")

    def button_pressed(self, btn_id: str):
        pass

    def list_op(self, row_id: str):
        pass

    def unsupported(self):
        send_text(self.sender, "Lo siento, no entendí.")