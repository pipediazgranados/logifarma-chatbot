import random


from enum import Enum
from enum import auto

from statemachine import State
from statemachine import StateMachine

# class states(Enum):
#     START           = auto()
#     DOCU_TIPO       = auto()
#     DOCU_NUM        = auto()
#     MENU            = auto()
#     ESTADO_MED      = auto()
#     ESTADO_NO       = auto()
#     ESTADO_GESTION  = auto()
#     ESTADO_REPARTO  = auto()
#     ESTADO_ENVIADO  = auto()
#     HORARIO_UBI     = auto()
#     HORARIO_RESP    = auto()
#     MED_AUTORIZAR   = auto()
#     MED_DOMICILIO   = auto()
#     OTROS           = auto()
#     MENU_REDIRECT   = auto()
#     AGENTE_REDIRECT = auto()
#     GEN_ERROR       = auto()
#     NUM_ERROR       = auto()
#     IDLE            = auto()
#     EOC             = auto()

class chatbot(StateMachine):
    # STATES
    start = State('Start', initial=True)
    docType = State('Tipo de Documento')
    docNum = State('Numero de Documento')
    menu  = State('Menu')
    estadoMed = State('Estado del Medicamento')
    estadoNO = State('Medicamento No Disponible')
    estadoGestion = State('Medicamento en Gestion')
    estadoReparto = State('Medicamento en Reparto')
    estadoEnviado = State('Medicamento Enviado')
    horarioUbicacion = State('Ubicacion del Punto')
    horarioRespuesta = State('Horario del Punto')
    medAutorizar = State('Medicamentos Autorizados')
    medDomicilio = State('Medicamentos para Domicilio')
    menuRedirect = State('Regreso a Menu')
    agentRedirect = State('Enviar a Agente')
    idle = State('Idle')
    eoc = State('Fin de Conversacion', final=True)

    documentQuery = start.to(docType, cond="datos_autorizaos") | start.to(eoc, unless="datos_autorizados")


    def datos_autorizados(self):
        





