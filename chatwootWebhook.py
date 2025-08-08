from __future__ import annotations

import logging
import os
import json
import requests

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify

from botFSM import ChatBot
from whatsappAPI import AGENTS
from utils import clean_phone_number

load_dotenv()

logger = logging.getLogger(__name__)

# ────────────────────────────── Configuration ─────────────────────────────
# Environment variables needed:
# CHATWOOT_URL - Base URL of your Chatwoot instance (default: http://localhost:3000)
# CHATWOOT_ACCOUNT_ID - Your Chatwoot account ID
# CHATWOOT_BOT_TOKEN - Bot access token from Chatwoot
# CHATWOOT_WEBHOOK_TOKEN - Webhook verification token (optional, set to "SKIP" to disable)
# AGENT_ASSIGNMENT - Strategy for agent assignment: "round_robin", "least_busy", or "specific" (default: round_robin)
# DEFAULT_AGENT_ID - Default agent ID for "specific" assignment strategy (optional)

# ────────────────────────────── Configuration ─────────────────────────────
class ChatwootConfig:
    BASE_URL = os.getenv("CHATWOOT_URL", "http://localhost:3000")
    ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID")
    BOT_TOKEN = os.getenv("CHATWOOT_BOT_TOKEN")
    WEBHOOK_TOKEN = os.getenv("CHATWOOT_WEBHOOK_TOKEN")
    TIMEOUT = 15
    
    @classmethod
    def validate(cls):
        missing = []
        if not cls.ACCOUNT_ID:
            missing.append("CHATWOOT_ACCOUNT_ID")
        if not cls.BOT_TOKEN:
            missing.append("CHATWOOT_BOT_TOKEN")
        if not cls.WEBHOOK_TOKEN:
            missing.append("CHATWOOT_WEBHOOK_TOKEN")
            
        if missing:
            raise RuntimeError(f"Missing Chatwoot config: {', '.join(missing)}")

# ────────────────────────────── Chatwoot API Client ─────────────────────────────
class ChatwootClient:
    def __init__(self, config: ChatwootConfig):
        self.config = config
        self.base_url = f"{config.BASE_URL}/api/v1/accounts/{config.ACCOUNT_ID}"
        self.headers = {
            "api_access_token": config.BOT_TOKEN,
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=self.config.TIMEOUT,
                **kwargs
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.RequestException as e:
            logger.error(f"Chatwoot API error {method} {endpoint}: {e}")
            return None
    
    def send_message(self, conversation_id: int, content: str, 
                    message_type: str = "outgoing") -> bool:
        """Send a message to a Chatwoot conversation"""
        data = {
            "content": content,
            "message_type": message_type,
            "content_type": "text"
        }
        
        # If it's a private message, set private flag
        if message_type == "private":
            data["private"] = True
            data["message_type"] = "outgoing"  # Private messages are still outgoing
        
        result = self._request("POST", f"/conversations/{conversation_id}/messages", json=data)
        return result is not None
    
    def send_interactive_message(self, conversation_id: int, content: str, 
                               options: list[str]) -> bool:
        """Send message with interactive options"""
        formatted_options = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        full_content = f"{content}\n\n{formatted_options}"
        return self.send_message(conversation_id, full_content)
    
    def update_conversation_status(self, conversation_id: int, status: str) -> bool:
        """Update conversation status (open, resolved, pending)"""
        data = {"status": status}
        result = self._request("PATCH", f"/conversations/{conversation_id}", json=data)
        return result is not None
    
    def add_labels(self, conversation_id: int, labels: list[str]) -> bool:
        """Add labels to conversation for routing/filtering"""
        data = {"labels": labels}
        result = self._request("POST", f"/conversations/{conversation_id}/labels", json=data)
        return result is not None
    
    def assign_agent(self, conversation_id: int, agent_id: int) -> bool:
        """Assign conversation to specific agent"""
        data = {"assignee_id": agent_id}
        result = self._request("PATCH", f"/conversations/{conversation_id}", json=data)
        return result is not None

# ────────────────────────────── Bot Interface Adapter ─────────────────────────────
class ChatwootBotInterface:
    """Adapter that implements WhatsApp API interface for Chatwoot"""
    
    def __init__(self, client: ChatwootClient):
        self.client = client
        self.conversation_map: Dict[str, int] = {}
    
    def set_conversation(self, contact_id: str, conversation_id: int):
        """Map contact to conversation ID"""
        self.conversation_map[contact_id] = conversation_id
    
    def send_text(self, to: str, body: str, preview_url: bool = False) -> str:
        """WhatsApp API compatible text sending"""
        conv_id = self.conversation_map.get(to)
        if conv_id:
            success = self.client.send_message(conv_id, body)
            return "msg_sent" if success else "msg_failed"
        return "no_conversation"
    
    def send_two_buttons(self, to: str, question: str, yes_id: str, no_id: str, 
                        str1: str, str2: str) -> str:
        """Send interactive buttons (simplified for Chatwoot)"""
        conv_id = self.conversation_map.get(to)
        if conv_id:
            options = [f"{str1} (responde: {yes_id})", f"{str2} (responde: {no_id})"]
            success = self.client.send_interactive_message(conv_id, question, options)
            return "buttons_sent" if success else "buttons_failed"
        return "no_conversation"
    
    def sendDocType(self, to: str, body: str):
        """Send document type selection"""
        conv_id = self.conversation_map.get(to)
        if conv_id:
            options = [
                "CC - Cédula de Ciudadanía",
                "TI - Tarjeta de Identidad", 
                "CE - Cédula de Extranjería",
                "RC - Registro Civil",
                "PT - Permiso de Trabajo",
                "SC - Salvoconducto",
                "AS - Adulto Sin I.D."
            ]
            self.client.send_interactive_message(conv_id, body, options)
    
    def sendMenu(self, to: str, body: str):
        """Send main menu options"""
        conv_id = self.conversation_map.get(to)
        if conv_id:
            options = [
                "ESTADO_MED - Estado del Medicamento",
                "HORARIO_UBI - Horarios y Ubicaciones", 
                "MED_AUTORIZAR - Medicamento a Domicilio",
                "OTROS - Hablar con un agente"
            ]
            self.client.send_interactive_message(conv_id, body, options)

# ────────────────────────────── Session Management ─────────────────────────────
class SessionManager:
    def __init__(self, bot_interface: ChatwootBotInterface, timeout_hours: int = 2):
        self.bot_interface = bot_interface
        self.sessions: Dict[str, ChatBot] = {}
        self.session_timestamps: Dict[str, datetime] = {}
        self.timeout = timedelta(hours=timeout_hours)
    
    def get_or_create_bot(self, contact_id: str, conversation_id: int) -> ChatBot:
        """Get existing bot session or create new one"""
        self.bot_interface.set_conversation(contact_id, conversation_id)
        
        if contact_id in self.sessions:
            # Update timestamp
            self.session_timestamps[contact_id] = datetime.now()
            return self.sessions[contact_id]
        
        # Create new bot with Chatwoot interface
        bot = ChatBot(sender=contact_id)
        
        # Replace bot's WhatsApp methods with Chatwoot methods
        import whatsappAPI as wa
        wa.send_text = self.bot_interface.send_text
        wa.send_two_buttons = self.bot_interface.send_two_buttons  
        wa.sendDocType = self.bot_interface.sendDocType
        wa.sendMenu = self.bot_interface.sendMenu
        
        self.sessions[contact_id] = bot
        self.session_timestamps[contact_id] = datetime.now()
        
        return bot
    
    def cleanup_expired_sessions(self):
        """Remove expired bot sessions"""
        cutoff = datetime.now() - self.timeout
        expired = [
            contact_id for contact_id, timestamp 
            in self.session_timestamps.items() 
            if timestamp < cutoff
        ]
        
        for contact_id in expired:
            self.sessions.pop(contact_id, None)
            self.session_timestamps.pop(contact_id, None)
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired bot sessions")

# ────────────────────────────── Agent Handoff ─────────────────────────────
class AgentHandoff:
    def __init__(self, client: ChatwootClient):
        self.client = client
        self.agent_assignment_strategy = os.getenv("AGENT_ASSIGNMENT", "round_robin")  # round_robin, least_busy, or specific
        self.default_agent_id = os.getenv("DEFAULT_AGENT_ID")  # Fallback agent ID
    
    def get_available_agents(self) -> Optional[list]:
        """Get list of available agents"""
        try:
            # Get all agents
            agents = self.client._request("GET", "/agents")
            if not agents:
                return None
            
            # Filter for available/online agents
            available = [
                agent for agent in agents 
                if agent.get("availability_status") == "online" 
                and agent.get("id") != 1  # Exclude bot agent (usually ID 1)
            ]
            
            return available if available else agents  # Return all if none online
            
        except Exception as e:
            logger.error(f"Failed to get agents: {e}")
            return None
    
    def get_agent_conversations_count(self, agent_id: int) -> int:
        """Get number of open conversations for an agent"""
        try:
            # Get conversations assigned to this agent
            params = {
                "assignee_type": "assigned",
                "assignee_id": agent_id,
                "status": "open"
            }
            result = self.client._request("GET", "/conversations", params=params)
            return len(result.get("data", [])) if result else 0
            
        except Exception as e:
            logger.error(f"Failed to get agent conversation count: {e}")
            return 0
    
    def select_agent(self, available_agents: list) -> Optional[int]:
        """Select an agent based on assignment strategy"""
        if not available_agents:
            return None
        
        if self.agent_assignment_strategy == "least_busy":
            # Find agent with least open conversations
            agent_loads = []
            for agent in available_agents:
                count = self.get_agent_conversations_count(agent["id"])
                agent_loads.append((agent["id"], count, agent))
            
            # Sort by conversation count
            agent_loads.sort(key=lambda x: x[1])
            return agent_loads[0][0] if agent_loads else None
            
        elif self.agent_assignment_strategy == "specific":
            # Use specific agent if available
            if self.default_agent_id:
                agent_id = int(self.default_agent_id)
                if any(a["id"] == agent_id for a in available_agents):
                    return agent_id
            # Fall back to first available
            return available_agents[0]["id"]
            
        else:  # round_robin (default)
            # For now, just pick first available
            # TODO: Implement proper round-robin with persistence
            return available_agents[0]["id"]
    
    def handoff_to_agent(self, conversation_id: int, contact_id: str, 
                        bot_context: Dict[str, Any]) -> bool:
        """Hand conversation over to human agent"""
        try:
            # Get available agents
            available_agents = self.get_available_agents()
            if not available_agents:
                logger.error("No agents available for handoff")
                self.client.send_message(
                    conversation_id,
                    "Lo siento, no hay agentes disponibles en este momento. "
                    "Por favor intenta más tarde o deja tu mensaje."
                )
                return False
            
            # Select an agent
            selected_agent_id = self.select_agent(available_agents)
            if not selected_agent_id:
                logger.error("Failed to select an agent")
                return False
            
            # Find agent name for logging
            agent_name = next(
                (a.get("name", "Unknown") for a in available_agents if a["id"] == selected_agent_id),
                "Unknown"
            )
            logger.info(f"Assigning conversation {conversation_id} to agent {agent_name} (ID: {selected_agent_id})")
            
            # Add labels for agent routing
            self.client.add_labels(conversation_id, ["bot-handoff", "needs-agent"])
            
            # Send context to agents first (before assignment)
            context_msg = self._format_context_message(bot_context)
            self.client.send_message(conversation_id, context_msg, message_type="private")
            
            # Assign to selected agent
            assignment_success = self.client.assign_agent(conversation_id, selected_agent_id)
            if not assignment_success:
                logger.error(f"Failed to assign conversation to agent {selected_agent_id}")
            
            # Update conversation status to open
            self.client.update_conversation_status(conversation_id, "open")
            
            # Send handoff confirmation to customer
            handoff_msg = (
                f"Te estoy conectando con uno de nuestros agentes. "
                f"Un momento por favor... 👨‍💼"
            )
            self.client.send_message(conversation_id, handoff_msg)
            
            # Add a note for the agent
            agent_note = (
                f"🤖 Bot handoff completed. Customer was in state: {bot_context.get('current_state', 'unknown')}. "
                f"Please review the context message above."
            )
            self.client.send_message(conversation_id, agent_note, message_type="private")
            
            return True
            
        except Exception as e:
            logger.error(f"Agent handoff failed for conversation {conversation_id}: {e}")
            return False
    
    def _format_context_message(self, context: Dict[str, Any]) -> str:
        """Format bot context for agent"""
        lines = ["🤖 **Contexto del Bot:**"]
        
        if context.get("doc_type") and context.get("doc_num"):
            lines.append(f"📄 Documento: {context['doc_type']} {context['doc_num']}")
        
        if context.get("first_name"):
            lines.append(f"👤 Nombre: {context['first_name']}")
            
        if context.get("status"):
            lines.append(f"📊 Estado: {context['status']}")
            
        if context.get("current_state"):
            lines.append(f"🔄 Último estado: {context['current_state']}")
            
        if context.get("last_query"):
            lines.append(f"💬 Última consulta: {context['last_query']}")
        
        lines.append("\n_El usuario ahora está conectado con un agente humano._")
        
        return "\n".join(lines)

# ────────────────────────────── Message Processing Helpers ─────────────────────────────
def extract_menu_option(content: str) -> Optional[str]:
    """Extract menu option from user input"""
    content_clean = content.strip()
    content_upper = content_clean.upper()
    
    # Map full display text to menu IDs
    menu_text_map = {
        "ESTADO_MED - Estado del Medicamento": "ESTADO_MED",
        "Estado del Medicamento": "ESTADO_MED",
        "HORARIO_UBI - Horarios y Ubicaciones": "HORARIO_UBI",
        "Horarios y Ubicaciones": "HORARIO_UBI",
        "MED_AUTORIZAR - Medicamento a Domicilio": "MED_AUTORIZAR",
        "Medicamento a Domicilio": "MED_AUTORIZAR",
        "OTROS - Hablar con un agente": "OTROS",
        "Hablar con un agente": "OTROS"
    }
    
    # Check for exact matches first (case-insensitive)
    for text, menu_id in menu_text_map.items():
        if content_clean.lower() == text.lower():
            return menu_id
    
    # Direct menu option IDs
    menu_ids = ["ESTADO_MED", "HORARIO_UBI", "MED_AUTORIZAR", "OTROS"]
    for menu_id in menu_ids:
        if menu_id in content_upper:
            return menu_id
    
    # Check for number selections (1-4)
    if content_upper in ["1", "1.", "1)"]:
        return "ESTADO_MED"
    elif content_upper in ["2", "2.", "2)"]:
        return "HORARIO_UBI"
    elif content_upper in ["3", "3.", "3)"]:
        return "MED_AUTORIZAR"
    elif content_upper in ["4", "4.", "4)"]:
        return "OTROS"
    
    # Check for partial matches or keywords
    keywords = {
        "ESTADO_MED": ["estado", "medicamento", "medicina", "med"],
        "HORARIO_UBI": ["horario", "ubicacion", "ubicaciones", "direccion"],
        "MED_AUTORIZAR": ["domicilio", "autorizar", "casa", "envio"],
        "OTROS": ["agente", "asesor", "ayuda", "hablar", "persona"]
    }
    
    for menu_id, words in keywords.items():
        for word in words:
            if word.upper() in content_upper:
                return menu_id
    
    return None

def extract_doc_type(content: str) -> Optional[str]:
    """Extract document type from user input"""
    content_clean = content.strip()
    content_upper = content_clean.upper()
    
    # Map full display text to document type codes
    doc_text_map = {
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
    
    # Check for exact matches first (case-insensitive)
    for text, code in doc_text_map.items():
        if content_clean.lower() == text.lower():
            return code
    
    # Direct document type codes
    doc_codes = ["CC", "TI", "CE", "RC", "PT", "SC", "AS"]
    
    # Check if content starts with a doc code
    first_word = content_upper.split()[0] if content_upper.split() else ""
    if first_word in doc_codes:
        return first_word
    
    # Check for exact match
    if content_upper in doc_codes:
        return content_upper
    
    # Check for number selections (1-7)
    number_to_doc = {
        "1": "CC", "1.": "CC", "1)": "CC",
        "2": "TI", "2.": "TI", "2)": "TI",
        "3": "CE", "3.": "CE", "3)": "CE",
        "4": "RC", "4.": "RC", "4)": "RC",
        "5": "PT", "5.": "PT", "5)": "PT",
        "6": "SC", "6.": "SC", "6)": "SC",
        "7": "AS", "7.": "AS", "7)": "AS"
    }
    
    if content_upper in number_to_doc:
        return number_to_doc[content_upper]
    
    # Check for full names
    full_names = {
        "CEDULA": "CC", "CÉDULA": "CC", "CIUDADANIA": "CC", "CIUDADANÍA": "CC",
        "TARJETA": "TI", "IDENTIDAD": "TI",
        "EXTRANJERIA": "CE", "EXTRANJERÍA": "CE",
        "REGISTRO": "RC", "CIVIL": "RC",
        "PERMISO": "PT", "TRABAJO": "PT",
        "SALVOCONDUCTO": "SC",
        "ADULTO": "AS"
    }
    
    for name, code in full_names.items():
        if name in content_upper:
            return code
    
    return None

# ────────────────────────────── Flask Blueprint ─────────────────────────────
def create_chatwoot_blueprint() -> Blueprint:
    # Validate configuration
    ChatwootConfig.validate()
    
    # Initialize components
    client = ChatwootClient(ChatwootConfig)
    bot_interface = ChatwootBotInterface(client)
    session_manager = SessionManager(bot_interface)
    agent_handoff = AgentHandoff(client)
    
    bp = Blueprint("chatwoot", __name__, url_prefix="/chatwoot")
    
    @bp.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "ok", "service": "chatwoot-bot"}), 200
    
    @bp.route("/webhook", methods=["POST"])
    def webhook():
        """Main webhook endpoint for Chatwoot"""
        try:
            # Skip token verification for now
            if ChatwootConfig.WEBHOOK_TOKEN and ChatwootConfig.WEBHOOK_TOKEN != "SKIP":
                webhook_token = request.headers.get("X-Chatwoot-Webhook-Token")
                if webhook_token != ChatwootConfig.WEBHOOK_TOKEN:
                    logger.warning("Invalid webhook token received")
                    return jsonify({"error": "Invalid webhook token"}), 401
            
            payload = request.get_json()
            if not payload:
                return jsonify({"error": "No JSON payload"}), 400
            
            # Extract event type
            event = payload.get("event")
            logger.info(f"Received webhook event: {event}")
            
            # Only process message creation events
            if event != "message_created":
                return jsonify({"status": "ignored", "reason": f"not message_created, got {event}"}), 200
            
            # IMPORTANT: Chatwoot sends message data at the root level, not nested
            content = payload.get("content", "").strip()
            message_type = payload.get("message_type")
            conversation = payload.get("conversation", {})
            sender = payload.get("sender", {})
            inbox = payload.get("inbox", {})
            
            logger.info(f"Message type: {message_type}, Content: '{content}'")
            logger.info(f"Sender: {sender.get('name')} ({sender.get('phone_number')})")
            
            # Skip messages from bots
            if sender.get("type") == "agent_bot":
                logger.info("Skipping message from bot itself")
                return jsonify({"status": "ignored", "reason": "from bot"}), 200
            
            # Only process incoming messages
            if message_type != "incoming":
                logger.info(f"Skipping non-incoming message: {message_type}")
                return jsonify({"status": "ignored", "reason": f"not incoming, type: {message_type}"}), 200
            
            # Ensure we have content
            if not content:
                logger.warning("No content in message")
                return jsonify({"status": "ignored", "reason": "no content"}), 200
            
            # Get conversation ID
            conversation_id = conversation.get("id")
            if not conversation_id:
                logger.error("No conversation ID found")
                return jsonify({"status": "error", "reason": "no conversation_id"}), 200
            
            # Get contact ID from sender
            contact_id = str(sender.get("id", ""))
            if not contact_id:
                # Fallback to phone number
                contact_id = sender.get("phone_number", "")
                
            if not contact_id:
                logger.error("No contact ID found")
                return jsonify({"status": "error", "reason": "no contact_id"}), 200
            
            # Get phone number for WhatsApp sending
            phone_number = sender.get("phone_number", "")
            if phone_number:
                # Clean the phone number format for WhatsApp API
                phone_number = clean_phone_number(phone_number)
                logger.info(f"Using phone number: {phone_number}")
            
            logger.info(f"Processing message: '{content}' from contact {contact_id} in conversation {conversation_id}")
            
            # Clean up expired sessions
            session_manager.cleanup_expired_sessions()
            
            # Get or create bot session - use cleaned phone number
            bot = session_manager.get_or_create_bot(phone_number or contact_id, conversation_id)
            logger.info(f"Bot state before processing: {bot.current_state.name}")
            
            # Process message based on content and bot state
            try:
                processed = False
                
                # If bot is in docType state, check for document type
                if bot.current_state.name == "docType":
                    doc_type = extract_doc_type(content)
                    if doc_type:
                        logger.info(f"Document type detected: {doc_type}")
                        bot.list_op(doc_type)
                        processed = True
                    else:
                        # Let bot handle invalid input
                        bot.text_op(content)
                        processed = True
                
                # If bot is in menu state, check for menu option
                elif bot.current_state.name == "menu":
                    menu_option = extract_menu_option(content)
                    if menu_option:
                        logger.info(f"Menu option detected: {menu_option}")
                        bot.list_op(menu_option)
                        processed = True
                    else:
                        # For unrecognized input in menu state, show menu again
                        bot.sendMenu(bot.sender, "Por favor selecciona una opción del menú:")
                        processed = True
                
                # For other states or if no specific handler matched
                if not processed:
                    # Check for button responses
                    content_lower = content.lower()
                    if content_lower in ["acepto", "si", "sí", "yes"]:
                        bot.button_op("yes")
                        processed = True
                    elif content_lower in ["no acepto", "no", "rechazar"]:
                        bot.button_op("no")
                        processed = True
                    else:
                        # Default text processing
                        bot.text_op(content)
                        processed = True
                
                logger.info(f"Message processed successfully. Bot state after: {bot.current_state.name}")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                processed = False
            
            # Handle agent handoff if bot is in human state or menu selection is OTROS
            if bot.current_state.name == "human" or (
                bot.current_state.name == "menu" and 
                extract_menu_option(content) == "OTROS"
            ):
                # First process the menu selection to move to human state
                if bot.current_state.name == "menu":
                    bot.list_op("OTROS")
                
                # Prepare context for handoff
                context = {
                    "doc_type": getattr(bot, "doc_type", None),
                    "doc_num": getattr(bot, "doc_num", None),
                    "current_state": bot.current_state.name,
                    "last_query": content,
                    "customer_name": sender.get("name"),
                    "phone": sender.get("phone_number"),
                    "first_name": getattr(bot, "_first_name", None) if hasattr(bot, "_first_name") else None,
                    "status": getattr(bot, "_status", None) if hasattr(bot, "_status") else None
                }
                
                # Perform the handoff
                success = agent_handoff.handoff_to_agent(conversation_id, contact_id, context)
                logger.info(f"Agent handoff {'successful' if success else 'failed'}")
                
                # If handoff successful, remove bot session to prevent further processing
                if success:
                    session_manager.sessions.pop(phone_number or contact_id, None)
                    session_manager.session_timestamps.pop(phone_number or contact_id, None)
            
            return jsonify({
                "status": "processed",
                "message_processed": processed,
                "bot_state": bot.current_state.name
            }), 200
            
        except Exception as e:
            logger.error(f"Webhook processing error: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500
    
    return bp

# ────────────────────────────── Export ─────────────────────────────────
# Create the blueprint instance
cw_bp = create_chatwoot_blueprint()

# Backward compatibility function  
def _cw_api(path: str, **kwargs):
    """Legacy function for backward compatibility"""
    client = ChatwootClient(ChatwootConfig)
    return client._request(kwargs.get("method", "GET"), path, **kwargs)