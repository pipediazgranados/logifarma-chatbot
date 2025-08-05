from statemachine import StateMachine, State

import random
import re

from enum import Enum
from enum import auto

from whatsappAPI import (
    send_text, confirm_text, send_two_buttons, sendDocType,
    sendMenu, forward_to_agent
    )
from utils import fetch_record, fetch_history, med_status_msg

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
    menu        = State()
    medState    = State()
    human       = State()
    idle        = State(final=True)  

    #guards
    def isYes(self, txt: str) -> bool:
        return txt.lower() in {"si", "sí", "acepto", "yes"}

    def isNo(self, txt:str) -> bool:
        return txt.lower() in {"no", "no", "No Acepto", "No acepto", "no Acepto", "no acepto"}

    def isValidDocType(self, txt: str) -> bool:
        # Check if it's a valid document type including full names
        txt_clean = txt.strip()
        
        # Map full text to codes
        doc_map = {
            "CC - Cédula de Ciudadanía": "CC",
            "Cédula de Ciudadanía": "CC",
            "Cedula de Ciudadania": "CC",
            "TI - Tarjeta de Identidad": "TI",
            "Tarjeta de Identidad": "TI",
            "CE - Cédula de Extranjería": "CE",
            "Cédula de Extranjería": "CE",
            "Cedula de Extranjeria": "CE",
            "RC - Registro Civil": "RC",
            "Registro Civil": "RC",
            "PT - Permiso de Trabajo": "PT",
            "Permiso de Trabajo": "PT",
            "SC - Salvoconducto": "SC",
            "Salvoconducto": "SC",
            "AS - Adulto Sin I.D.": "AS",
            "Adulto Sin I.D.": "AS",
            "Adulto Sin ID": "AS"
        }
        
        # Check if it's a full name
        if txt_clean in doc_map:
            return True
        
        # Original check for codes
        token = txt_clean.split()[0]
        return token.casefold() in ALLOWED_CASEFOLDED

    def extractDocType(self, txt: str) -> str:
        """Extract the document type code from the input text"""
        txt_clean = txt.strip()
        
        # Map full text to codes
        doc_map = {
            "CC - Cédula de Ciudadanía": "CC",
            "Cédula de Ciudadanía": "CC",
            "Cedula de Ciudadania": "CC",
            "TI - Tarjeta de Identidad": "TI",
            "Tarjeta de Identidad": "TI",
            "CE - Cédula de Extranjería": "CE",
            "Cédula de Extranjería": "CE",
            "Cedula de Extranjeria": "CE",
            "RC - Registro Civil": "RC",
            "Registro Civil": "RC",
            "PT - Permiso de Trabajo": "PT",
            "Permiso de Trabajo": "PT",
            "SC - Salvoconducto": "SC",
            "Salvoconducto": "SC",
            "AS - Adulto Sin I.D.": "AS",
            "Adulto Sin I.D.": "AS",
            "Adulto Sin ID": "AS"
        }
        
        # Return the code if it's a full name
        if txt_clean in doc_map:
            return doc_map[txt_clean]
        
        # Otherwise return the first token (should be the code)
        return txt_clean.split()[0].upper()

    def isClean(self, raw: str) -> str:
        return CLEAN_RE.sub("", raw)
    
    def isTenDigits(self, txt: str) -> bool:
        digits = txt.strip()
        return digits.isdigit() and len(digits) == 10

    def isEightDigits(self, txt: str) -> bool:
        digits = txt.strip()
        return digits.isdigit() and len(digits) <= 8

    def get_first_name(self, rec: dict) -> str:
        if "PRIMER_NOMBRE" in rec:
            return rec["PRIMER_NOMBRE"].capitalize()

        if rec.get("resourceType") == "Patient":
            names = rec.get("name", [])
            if names and names[0].get("given"):
                return names[0]["given"][0].capitalize()

        return ""

    def get_status(self, rec: dict) -> str:
        if "ESTADO" in rec:
            return rec["ESTADO"].title()

        if rec.get("resourceType") == "Patient":
            for ext in rec.get("extension", []):
                if ext.get("url", "").endswith("/afilliateStatus"):
                    coding = ext.get("valueCoding", {})
                    return (coding.get("display") or coding.get("code", "")).title()

        return "Activo"

    def get_valid_history(self, rec: dict) -> bool:
        if "Paceiente no existe" in rec:
            return False
        
        else:
            return True

    #transitions
    toWelcome   = start.to(welcome)

    toYesTerms  = welcome.to(docType, cond="isYes")
    toNoTerms   = welcome.to(idle, cond="isNo")

    toDocNum    = docType.to(docNum)
    toMenu      = docNum.to(menu)

    toMedState  = menu.to(medState)
    toHuman     = menu.to(human)

    backToBot   = human.to(menu)
   
    toIdle      = medState.to(idle)

    def __init__(self, sender: str):
        super().__init__()
        self.sender = sender
        self.doc_type = None
        self.doc_num = None
        self.pending_records = []  # Changed from list[HistoryRecord]

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
                self.doc_type = self.extractDocType(body)
                self.toDocNum(body)
            else:
                send_text(self.sender, "Ingrese un tipo de documento valido")
            return
        
        if self.current_state is self.docNum:
            doc_num = self.isClean(body)

            if not doc_num.isdigit():
                send_text(self.sender, "Por favor ingrese un numero de identificacion valido")
                return
            
            record = fetch_record(self.doc_type, doc_num)
            print(f"{record}")

            if not record:
                send_text(
                    self.sender, 
                    f"No encontramos un afiliado con el numero de identificacion {self.doc_num}.\n"
                    "Verifica que el numero sea correcto e intentalo de nuevo."
                )
                return

            self.doc_num = doc_num

            first_name = self.get_first_name(record)
            estado = self.get_status(record)
            
            # Store these for handoff context
            self._first_name = first_name
            self._status = estado
            
            print(f"Nombre de Usuario: {first_name}\nEstado: {estado}")

            sendMenu(self.sender, 
                      f"Hola {first_name}!\n"
                      f"Como podemos ayudarte hoy?"
                    ) 
            self.toMenu()
            return

        if self.current_state is self.human:
            if body.strip().lower() == "bot":
                sendMenu(self.sender, "¡De vuelta! ¿Cómo puedo ayudarte?")
                self.backToBot()
            else:
                forward_to_agent(self.sender, body)        # relay
            return

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
            # Handle both codes and full text
            if self.isValidDocType(row_id):
                self.doc_type = self.extractDocType(row_id)
                self.toDocNum(row_id) 
            else:
                send_text(self.sender,
                        "Por favor elige un tipo de documento válido.")
            return

        if self.current_state is self.menu:
            # Map full menu text to IDs (including WhatsApp exact titles)
            menu_map = {
                # Full text from Chatwoot
                "ESTADO_MED - Estado del Medicamento": "ESTADO_MED",
                "Estado del Medicamento": "ESTADO_MED",
                "HORARIO_UBI - Horarios y Ubicaciones": "HORARIO_UBI",
                "Horarios y Ubicaciones": "HORARIO_UBI",
                "MED_AUTORIZAR - Medicamento a Domicilio": "MED_AUTORIZAR",
                "Medicamento a Domicilio": "MED_AUTORIZAR",
                "OTROS - Hablar con un agente": "OTROS",
                "Hablar con un agente": "OTROS",
                # WhatsApp exact titles from whatsappAPI.py
from statemachine import StateMachine, State

import random
import re

from enum import Enum
from enum import auto

from whatsappAPI import (
    send_text, confirm_text, send_two_buttons, sendDocType,
    sendMenu, forward_to_agent
    )
from utils import fetch_record, fetch_history, med_status_msg, HistoryRecord

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
    menu        = State()
    medState    = State()
    human       = State()
    idle        = State(final=True)  

    #guards
    def isYes(self, txt: str) -> bool:
        return txt.lower() in {"si", "sí", "acepto", "yes"}

    def isNo(self, txt:str) -> bool:
        return txt.lower() in {"no", "no", "No Acepto", "No acepto", "no Acepto", "no acepto"}

    def isValidDocType(self, txt: str) -> bool:
        # Check if it's a valid document type including full names
        txt_clean = txt.strip()
        
        # Map full text to codes
        doc_map = {
            "CC - Cédula de Ciudadanía": "CC",
            "Cédula de Ciudadanía": "CC",
            "Cedula de Ciudadania": "CC",
            "TI - Tarjeta de Identidad": "TI",
            "Tarjeta de Identidad": "TI",
            "CE - Cédula de Extranjería": "CE",
            "Cédula de Extranjería": "CE",
            "Cedula de Extranjeria": "CE",
            "RC - Registro Civil": "RC",
            "Registro Civil": "RC",
            "PT - Permiso de Trabajo": "PT",
            "Permiso de Trabajo": "PT",
            "SC - Salvoconducto": "SC",
            "Salvoconducto": "SC",
            "AS - Adulto Sin I.D.": "AS",
            "Adulto Sin I.D.": "AS",
            "Adulto Sin ID": "AS"
        }
        
        # Check if it's a full name
        if txt_clean in doc_map:
            return True
        
        # Original check for codes
        token = txt_clean.split()[0]
        return token.casefold() in ALLOWED_CASEFOLDED

    def extractDocType(self, txt: str) -> str:
        """Extract the document type code from the input text"""
        txt_clean = txt.strip()
        
        # Map full text to codes
        doc_map = {
            "CC - Cédula de Ciudadanía": "CC",
            "Cédula de Ciudadanía": "CC",
            "Cedula de Ciudadania": "CC",
            "TI - Tarjeta de Identidad": "TI",
            "Tarjeta de Identidad": "TI",
            "CE - Cédula de Extranjería": "CE",
            "Cédula de Extranjería": "CE",
            "Cedula de Extranjeria": "CE",
            "RC - Registro Civil": "RC",
            "Registro Civil": "RC",
            "PT - Permiso de Trabajo": "PT",
            "Permiso de Trabajo": "PT",
            "SC - Salvoconducto": "SC",
            "Salvoconducto": "SC",
            "AS - Adulto Sin I.D.": "AS",
            "Adulto Sin I.D.": "AS",
            "Adulto Sin ID": "AS"
        }
        
        # Return the code if it's a full name
        if txt_clean in doc_map:
            return doc_map[txt_clean]
        
        # Otherwise return the first token (should be the code)
        return txt_clean.split()[0].upper()

    def isClean(self, raw: str) -> str:
        return CLEAN_RE.sub("", raw)
    
    def isTenDigits(self, txt: str) -> bool:
        digits = txt.strip()
        return digits.isdigit() and len(digits) == 10

    def isEightDigits(self, txt: str) -> bool:
        digits = txt.strip()
        return digits.isdigit() and len(digits) <= 8

    def get_first_name(self, rec: dict) -> str:
        if "PRIMER_NOMBRE" in rec:
            return rec["PRIMER_NOMBRE"].capitalize()

        if rec.get("resourceType") == "Patient":
            names = rec.get("name", [])
            if names and names[0].get("given"):
                return names[0]["given"][0].capitalize()

        return ""

    def get_status(self, rec: dict) -> str:
        if "ESTADO" in rec:
            return rec["ESTADO"].title()

        if rec.get("resourceType") == "Patient":
            for ext in rec.get("extension", []):
                if ext.get("url", "").endswith("/afilliateStatus"):
                    coding = ext.get("valueCoding", {})
                    return (coding.get("display") or coding.get("code", "")).title()

        return "Activo"

    def get_valid_history(self, rec: dict) -> bool:
        if "Paceiente no existe" in rec:
            return False
        
        else:
            return True

    #transitions
    toWelcome   = start.to(welcome)

    toYesTerms  = welcome.to(docType, cond="isYes")
    toNoTerms   = welcome.to(idle, cond="isNo")

    toDocNum    = docType.to(docNum)
    toMenu      = docNum.to(menu)

    toMedState  = menu.to(medState)
    toHuman     = menu.to(human)

    backToBot   = human.to(menu)
   
    toIdle      = medState.to(idle)

    def __init__(self, sender: str):
        super().__init__()
        self.sender = sender
        self.doc_type = None
        self.doc_num = None
        self.pending_records: list[HistoryRecord] = []

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
                self.doc_type = self.extractDocType(body)
                self.toDocNum(body)
            else:
                send_text(self.sender, "Ingrese un tipo de documento valido")
            return
        
        if self.current_state is self.docNum:
            doc_num = self.isClean(body)

            if not doc_num.isdigit():
                send_text(self.sender, "Por favor ingrese un numero de identificacion valido")
                return
            
            record = fetch_record(self.doc_type, doc_num)
            print(f"{record}")

            if not record:
                send_text(
                    self.sender, 
                    f"No encontramos un afiliado con el numero de identificacion {self.doc_num}.\n"
                    "Verifica que el numero sea correcto e intentalo de nuevo."
                )
                return

            self.doc_num = doc_num

            first_name = self.get_first_name(record)
            estado = self.get_status(record)
            
            # Store these for handoff context
            self._first_name = first_name
            self._status = estado
            
            print(f"Nombre de Usuario: {first_name}\nEstado: {estado}")

            sendMenu(self.sender, 
                      f"Hola {first_name}!\n"
                      f"Como podemos ayudarte hoy?"
                    ) 
            self.toMenu()
            return

        if self.current_state is self.human:
            if body.strip().lower() == "bot":
                sendMenu(self.sender, "¡De vuelta! ¿Cómo puedo ayudarte?")
                self.backToBot()
            else:
                forward_to_agent(self.sender, body)        # relay
            return

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
            # Handle both codes and full text
            if self.isValidDocType(row_id):
                self.doc_type = self.extractDocType(row_id)
                self.toDocNum(row_id) 
            else:
                send_text(self.sender,
                        "Por favor elige un tipo de documento válido.")
            return

        if self.current_state is self.menu:
            # Map full menu text to IDs
            menu_map = {
                "ESTADO_MED - Estado del Medicamento": "ESTADO_MED",
                "Estado del Medicamento": "ESTADO_MED",
                "HORARIO_UBI - Horarios y Ubicaciones": "HORARIO_UBI",
                "Horarios y Ubicaciones": "HORARIO_UBI",
                "MED_AUTORIZAR - Medicamento a Domicilio": "MED_AUTORIZAR",
                "Medicamento a Domicilio": "MED_AUTORIZAR",
                "OTROS - Hablar con un agente": "OTROS",
                "Hablar con un agente": "OTROS"
            }
            
            # Get the actual menu ID
            menu_id = menu_map.get(row_id, row_id)
            
            if menu_id == "ESTADO_MED":
                history = fetch_history(self.doc_num)

                if history is None:
                    send_text(self.sender,
                              "Lo siento, no pude consultar su historial.")
                    return
                elif self.get_valid_history(history) is False:
                    send_text(self.sender,
                              f"El paceiente con el numero de identificacion {self.doc_num} no existe. "
                              "Por favor verifica el numero de documento.")
                    return

                self.pending_records = history
                send_text(self.sender, med_status_msg(history))

                self.toMedState()
                return

            elif menu_id == "HORARIO_UBI":
                send_text(self.sender, "Nuestros horarios de atención son:\n\n"
                         "📍 Sede Principal:\n"
                         "Lunes a Viernes: 7:00 AM - 6:00 PM\n"
                         "Sábados: 8:00 AM - 12:00 PM\n\n"
                         "📍 Sucursal Norte:\n"
                         "Lunes a Viernes: 8:00 AM - 5:00 PM\n"
                         "Sábados: 9:00 AM - 1:00 PM")
                return
            elif menu_id == "MED_AUTORIZAR":
                send_text(self.sender, "Para autorizar medicamentos a domicilio, "
                         "necesitamos validar tu solicitud. Un agente te contactará pronto.")
                self.toHuman()
                return
            elif menu_id == "OTROS":
                send_text(self.sender, "Te voy a conectar con uno de nuestros agentes...")
                self.toHuman()
                return
            else: 
                send_text(self.sender, "Por favor ingrese una opcion valida")
            return
                "Horarios": "HORARIO_UBI",
                "Otros": "OTROS"
            }
            
            # Get the actual menu ID
            menu_id = menu_map.get(row_id, row_id)
            
            # Also check if row_id is already a menu ID
            if row_id in ["ESTADO_MED", "HORARIO_UBI", "MED_AUTORIZAR", "OTROS"]:
                menu_id = row_id
            
            if menu_id == "ESTADO_MED":
                history = fetch_history(self.doc_num)

                if history is None:
                    send_text(self.sender,
                              "Lo siento, no pude consultar su historial.")
                    return
                elif self.get_valid_history(history) is False:
                    send_text(self.sender,
                              f"El paciente con el numero de identificacion {self.doc_num} no existe. "
                              "Por favor verifica el numero de documento.")
                    return

                self.pending_records = history
                send_text(self.sender, med_status_msg(history))
                self.toMedState()  # Move to medState after showing status
                return

            elif menu_id == "HORARIO_UBI":
                send_text(self.sender, "Nuestros horarios de atención son:\n\n"
                         "📍 Sede Principal:\n"
                         "Lunes a Viernes: 7:00 AM - 6:00 PM\n"
                         "Sábados: 8:00 AM - 12:00 PM\n\n"
                         "📍 Sucursal Norte:\n"
                         "Lunes a Viernes: 8:00 AM - 5:00 PM\n"
                         "Sábados: 9:00 AM - 1:00 PM")
                # Stay in menu state
                return
            elif menu_id == "MED_AUTORIZAR":
                send_text(self.sender, "Para autorizar medicamentos a domicilio, "
                         "necesitamos validar tu solicitud. Un agente te contactará pronto.")
                self.toHuman()
                return
            elif menu_id == "OTROS":
                send_text(self.sender, "Te voy a conectar con uno de nuestros agentes...")
                self.toHuman()
                return
            else: 
                send_text(self.sender, "Por favor ingrese una opcion valida")
            return