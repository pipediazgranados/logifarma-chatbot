import os
import requests
from dotenv import load_dotenv
from typing import Dict, TypedDict, Optional, Any

from typing import Tuple, Dict, List, Optional, Iterable
import logging
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)
load_dotenv()

_API_URL    = os.environ["DOC_API_URL"]
_API_BASE = os.environ["MEDICAR_BASE_URL"]
LOGIN_EP = f"{_API_BASE}/auth/login"
DATA_EP = f"{_API_BASE}/historico-dispensaciones/client/6"
DATE_FMT = "%d/%m/%Y"
INV_EP = os.environ["INV_URL"]

TIMEOUT = 15

EMAIL = os.getenv("MEDICAR_EMAIL")
PASSWORD = os.getenv("MEDICAR_PASSWORD")

RIGHTS_TOKEN_URL    = os.getenv("RIGHTS_TOKEN_URL")
RIGHTS_VALIDATE_URL = os.getenv("RIGHTS_VALIDATE_URL")

@dataclass
class DocRecord(TypedDict, total=False):
    TIPODOCUMENTO: str
    DOCUMENTO: str
    PRIMER_NOMBRE: str
    SEGUNDO_NOMBRE: str
    PRIMER_APELLIDO: str
    SEGUNDO_APELLIDO: str

from dataclasses import dataclass

@dataclass
class HistoryRecord:
    plu: str
    descripcion: str
    cant_pendiente: int
    inventario_centro: int
    centro: str
    total_pendiente_centro: int
    fecha_solicitud: Optional[datetime] = None
    cod_mol: str = ""
    nom_centro: str = ""

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

def clean_phone_number(phone: str) -> str:
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    if cleaned.startswith('+'):
        cleaned = cleaned[1:]
    
    return cleaned

def _parse_date(raw: str | None) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], DATE_FMT)
    except ValueError:
        return None


def get_token(email: str, password: str) -> str:
    payload = {"email": email, "password": password}

    try:
        r = requests.post(LOGIN_EP, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        log.error("login request failed: %s", exc)
        raise
    except ValueError:
        log.error("login response is not valid JSON")
        raise

    token = data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError(f"Login JSON has no access token: {data}")

    return token

def get_rights_token() -> str:
    payload = {
        "grant_type": "password",
        "client_id": os.getenv("RIGHTS_CLIENT_ID", "right-validation"),
        "username": os.getenv("RIGHTS_USERNAME"),
        "password": os.getenv("RIGHTS_PASSWORD"),
        "client_secret": os.getenv("RIGHTS_CLIENT_SECRET")
    }
    r = requests.post(
        RIGHTS_TOKEN_URL,
        data=payload,
        timeout=TIMEOUT,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    return r.json()["access_token"]

def validate_rights(doc_type: str, doc_id: str) -> Optional[Dict[str, Any]]:
    token = get_rights_token()
    body = {
        "resourceType": "Parameters",
        "id": "CorrelationId",
        "parameter": [
            {"name": "documentType", "valueString": doc_type},
            {"name": "documentId", "valueString": doc_id},
        ],
    }

    r = requests.post(
        RIGHTS_VALIDATE_URL,
        json=body,
        headers= {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )
    r.raise_for_status()
    bundle = r.json()

    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") == "OperationOutcome":
            msg = res["issue"][0]["details"]["text"].lower()
            if "no encontrado" in msg:
                return None
            
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") == "Patient":
            return res
    
    return bundle

def post_json(endpoint: str,
              token: str | None,
              json_body: dict | None = None,
              *, timeout: int = TIMEOUT) -> dict | list | None:

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        r = requests.post(endpoint,
                          json=json_body or {},
                          headers=headers,
                          timeout=timeout)
        r.raise_for_status()

    except requests.RequestException as exc:
        log.error("POST %s failed: %s", endpoint, exc)
        return None

    try:
        return r.json()
    except ValueError:
        log.error("POST %s returned non‑JSON: %s", endpoint, r.text[:400])
        return None

def fetch_record(doc_type: str, doc_id: str) -> Optional[DocRecord]:
    record = None

    try:
        payload = {
            "function": "obtenerafiliados",
            "tipodocumento": doc_type.upper(),
            "documento": doc_id
        }

        data = post_json(_API_URL, token=None, json_body=payload)

        if data and isinstance(data, dict):
            if data.get("CODIGO", 0) != 1 and "TIPODOCUMENTO" in data:
                record = data
            elif "data" in data and data["data"]:
                record = data["data"][0]
            elif isinstance(data, list) and data:
                record = data[0]

    except Exception as exc:
        print(f"Error fetching record: {exc}")
    
    if record is None:
        try:
            record = validate_rights(doc_type.upper(), doc_id)
            print(f"{record}")
        except Exception as exc:
            print(f"Error validating rights: {exc}")

    return record

def get_inventory(centro: str, cod_mol: str, token: str,
                  *, timeout: int = TIMEOUT) -> int:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    data = {"Centro": centro, "CodMol": cod_mol}

    try:
        resp = requests.post(INV_EP, headers=headers, data=data, timeout=timeout)
        resp.raise_for_status()
        inv_json: Any = resp.json()
    except Exception as exc:
        log.warning("Inventory lookup failed for (%s, %s): %s", centro, cod_mol, exc)
        return 0

    if isinstance(inv_json, list) and inv_json:
        node = inv_json[0]
        if isinstance(node, dict):
            return int(node.get("Inventario", 0) or node.get("InventarioMoleculaCentro", 0) or 0)
    if isinstance(inv_json, dict):
        node = inv_json.get("data", inv_json)
        if isinstance(node, dict):
            return int(node.get("Inventario", 0) or node.get("InventarioMoleculaCentro", 0) or 0)

    return 0
def fetch_history(doc_num: str) -> list[HistoryRecord]:
    token = get_token(EMAIL, PASSWORD)

    body = {
        "NumeroDocumento": doc_num,
        "DiasDispensacion": 90,
        "PendientesActivos": True,
    }
    data = post_json(DATA_EP, token, body)
    if data is None:
        raise RuntimeError("historial: respuesta vacia")
        return []
       
    afiliados = data["data"] if isinstance(data, dict) else data
    if not isinstance(afiliados, list):
        raise RuntimeError(f"historial: formato inesperado ({type(afiliados)})")

    records: list[HistoryRecord] = []

    for ssc in afiliados[0].get("SSCs", []):
        centro = ssc.get("Centro", "")
        for art in ssc.get("Articulos", []):
            rec = HistoryRecord(
                plu                     = art.get("Plu", ""),
                descripcion             = art.get("Descripcion", ""),
                cant_pendiente          = int(art.get("CantidadPendiente") or 0),
                inventario_centro       = int(art.get("InventarioMoleculaCentro") or 0),
                centro                  = centro,
                total_pendiente_centro  = int(art.get("TotalPendienteMoleculaCentro") or 0),
                fecha_solicitud         = _parse_date(ssc.get("FecSol")),
                cod_mol                 = art.get("CodMol", ""),
                nom_centro              = ssc.get("NombCaf")
            )
            records.append(rec)

    print(f"records built: %d → %s", len(records), records[:3])
    return records

def med_status_msg(recs: Iterable[HistoryRecord]) -> str | None:
    pending = [r for r in recs if r.cant_pendiente]
    if not pending:
        return "No tienes medicamentos pendientes en este momento."
    
    token = get_token(EMAIL, PASSWORD)

    lines = []
    for r in pending:
        available = get_inventory(r.centro, r.cod_mol, token) or 0
        print(f"Medicamento disponible: {available}")#DEBUG
        if r.centro == "920" and r.cant_pendiente <= available:
            lines.append(
                f"*{r.descripcion.capitalize()}* se encuentra disponible en la central de domicilio!\n"
            )
        elif r.centro == "920" and r.cant_pendiente > available:
            lines.append(
                f"*{r.descripcion.capitalize()}* todavia sigue en gestion de compra en la central de domicilio.\n"
            )
        elif r.cant_pendiente <= available:
            lines.append(
                f"*{r.descripcion.capitalize()}* esta *disponible* en el punto {r.nom_centro[:-6]}\n"
                f"*Puedes ir a reclamarlo!*"
            )
        elif r.cant_pendiente > available:
            lines.append(
                f"*{r.descripcion.capitalize()}* sigue en gestion de compra.\n"
                f"*Por favor intentalo mas tarde*"
            )
    return "\n\n".join(lines)

