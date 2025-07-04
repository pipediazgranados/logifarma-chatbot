import random

from enum import Enum
from enum import auto

from statemachine import State
from statemachine import StateMachine

from whatsappAPI import send_text, confirm_text, send_two_buttons

class ChatBot(StateMachine):
    #states
    start   = State(initial=True)
    welcome = State(enter="sendWelcome")
    docType = State(enter="promptType")
    docNum  = State()
    idle    = State(final=True)  

    #guards
    def isYes(self, txt: str) -> bool:
        return txt.lower() in {"si", "sí", "Acepto" "acepto", "yes"}
    
    def isNo(self, txt:str) -> bool:
        return txt.lower() in {"no", "no", "No Acepto", "No acepto", "no Acepto", "no acepto"}

    #transitions
    trans_welcome = start.to(welcome)

    accept_terms = welcome.to(docType, cond="isYes")
    reject_terms = welcome.to(idle, cond="isNo")

    ask_doc_num  = docType.to(docNum)
    finish       = docNum.to(idle)

    #constructor
    def __init__(self, sender: str):
        super().__init__()
        self.sender = sender
        self.fallback_counter = 0

    #on-enter
    def sendWelcome(self):
        question = (
            "Hola!\n"
            "Bienvenido al servicio al cliente WhatsApp de Logifarma.\n"
            "Antes de iniciar, es necesario que aceptes los términos y "
            "condiciones de WhatsApp."
        )

        send_two_buttons(
            self.sender,
            question,
            "yes",
            "no",
            "Acepto",
            "No Acepto",
        ) 
    
    def promptType(self):
        send_text(self.sender, "Por favor ingrese su tipo de documento")

    #event methods
    def text_received(self, body: str):
        if self.current_state is self.start:
            self.trans_welcome()
        return

        if self.current_state is self.welcome:
            if not self.accept_terms(body):
                send("Finalizando conversacion")
            return

        # if self.current_state is self.docType:




    def button_pressed(self, btn_id: str):
        if self.current_state is self.welcome:
            if self.isYes(btn_id):
                self.accept_terms(btn_id)
                # send_text(self.sender, "To docType")
            elif self.isNo(btn_id):
                self.reject_terms(btn_id)
            else:
                send_text(self.sender, "Por favor eliga Acepto o No Acepto.")
            return

    def list_op(self, row_id: str):
        pass

    def unsupported(self):
        send_text(self.sender, "Lo siento, no entendí.")
