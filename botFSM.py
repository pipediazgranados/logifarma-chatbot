import random
import re

from enum import Enum
from enum import auto

from statemachine import State
from statemachine import StateMachine

from whatsappAPI import send_text, confirm_text, send_two_buttons, sendDocType, sendMenu

ALLOWED = (
        "Tarjeta de Identidad",
        "Cédula de Ciudadanía",
        "Cédula de Extranjería",
        "Adulto Sin I.D.",
        "Permiso de Trabajo",
        "Salvoconducto",
        "Registro Civil",
        "TI", "CC", "AS", "CE", "PT", "SC", "RC",
)
ALLOWED_CASEFOLDED = {v.casefold() for v in ALLOWED}

TEN_RE = re.compile(r"^\d{10}$")
EIGHT_RE = re.compile(r"^\d{1,8}$")
CLEAN_RE = re.compile(r"[.\-\s]")

class ChatBot(StateMachine):
    #states
    start       = State(initial=True)
    welcome     = State(enter="sendWelcome")
    docType     = State(enter="promptType")
    docNum      = State(enter="promptDocNum")
    menu        = State(enter="promptMenu")
    sscNum      = State(enter="promptSsc")
    medState    = State()
    idle        = State(final=True)  

    #guards
    def isYes(self, txt: str) -> bool:
        return txt.lower() in {"si", "sí", "Acepto" "acepto", "yes"}
    
    def isNo(self, txt:str) -> bool:
        return txt.lower() in {"no", "no", "No Acepto", "No acepto", "no Acepto", "no acepto"}

    def isValidDocType(self, txt: str) -> bool:
        return txt.strip().casefold() in ALLOWED_CASEFOLDED

    def isClean(self, raw: str) -> str:
        return CLEAN_RE.sub("", raw)
    
    def isTenDigits(self, txt: str) -> bool:
        digits = txt.strip()
        return digits.isdigit() and len(digits) == 10

    def isEightDigits(self, txt: str) -> bool:
        digits = txt.strip()
        return digits.isdigit() and len(digits) <= 8
    
    #transitions
    toWelcome   = start.to(welcome)

    toYesTerms  = welcome.to(docType, cond="isYes")
    toNoTerms   = welcome.to(idle, cond="isNo")

    toDocNum    = docType.to(docNum)
    toMenu      = docNum.to(menu)

    toSsc       = menu.to(sscNum) 
    toMedState  = sscNum.to(medState)
   
    toIdle      = medState.to(idle)

    #constructor
    def __init__(self, sender: str):
        super().__init__()
        self.sender = sender
        self.fallback_counter = 0

    #on-enter
    def sendWelcome(self):
        question = (
            "Hola!\n\n"
            "Bienvenido al servicio al cliente WhatsApp de Logifarma.\n\n"
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
        sendDocType(self.sender, "Por favor ingrese el tipo de documento")
    
    def promptDocNum(self):
        send_text(self.sender, "Por favor ingrese el numero de documento")
    
    def promptMenu(self):
        sendMenu(self.sender, "En que lo podemos ayudar?")
    
    def promptSsc(self):
        send_text(self.sender, "Por favor ingrese su numero SSC")

    #event methods
    def text_op(self, body: str):
        if self.current_state is self.start:
            self.toWelcome()
            return

        if self.current_state is self.welcome:
            if self.isYes(body):
                self.toYesTerms(body)
            elif self.isNo(body):
                self.toNoTerms(body)
            else:
                send_text(self.sender, "Responde Acepto o No Acepto, por favor.")
            return

        if self.current_state is self.docType:
            if self.isValidDocType(body):
                self.toDocNum(body)
            else:
                send_text(self.sender, "Ingrese un tipo de documento valido")
            return
        
        if self.current_state is self.docNum:
            clean = self.isClean(body)

            if self.isTenDigits(clean):
                self.toMenu(clean)
            elif self.isEightDigits(clean):
                self.toMenu(clean)
            else:
                send_text(self.sender, "Ingrese un numero de documento valido")

    def button_op(self, btn_id: str):
        if self.current_state is self.welcome:
            if self.isYes(btn_id):
                self.toYesTerms(btn_id)
            elif self.isNo(btn_id):
                self.toNoTerms(btn_id)
            else:
                send_text(self.sender, "Por favor elige Acepto o No Acepto.")
            return
        
    def list_op(self, row_id: str):
        if self.current_state is self.docType:
            if self.isValidDocType(row_id):
                self.toDocNum(row_id) 
            else:
                send_text(self.sender,
                        "Por favor elige un tipo de documento válido.")
        else:
            self.unsupported()

        def unsupported(self):
            send_text(self.sender, "Lo siento, no entendí.")

        if self.current_state is self.menu:
            if row_id == "ESTADO_MED":
                self.toSsc(row_id)
            elif row_id == "HORARIO_UBI":
                send_text(self.sender, "")
            elif row_id == "MED_AUTORIZAR":
                send_text(self.sender, "")
            elif row_id == "OTROS":
                send_text(self.sender, "Redirigiendo a asesor")
            else: 
                send_text(self.sender, "Por favor ingrese una opcion valida")
            return
