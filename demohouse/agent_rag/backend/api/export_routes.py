# api/export_routes.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.notion_service import export_conversation_to_notion, export_message_to_notion
from models.models import Conversation, Message
import logging

export_bp = Blueprint('export', __name__)
logger = logging.getLogger(__name__)

@export_bp.route("/api/export/notion", methods=["POST"])
@login_required
def export_to_notion():
    # Add authentication check
    data = request.get_json()
    conversation_id = data.get("conversation_id")

    if not conversation_id:
        return jsonify({"error": "Conversation ID is required"}), 400

    # Verify user owns this conversation
    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
    
    if conversation.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        result = export_conversation_to_notion(conversation_id)
        return jsonify({"message": "Exported to Notion", **result}), 200
    except ValueError as e: # Specific config error
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"Error exporting conversation {conversation_id} to Notion: {e}")
        return jsonify({"error": str(e)}), 500 # Or 500 for internal error

@export_bp.route("/api/export/notion/message", methods=["POST"])
@login_required
def export_message_route():
    """Export a specific message to Notion."""
    data = request.get_json()
    message_id = data.get("message_id")
    conversation_id = data.get("conversation_id")

    if not message_id:
        return jsonify({"error": "Message ID is required"}), 400

    # Verify user owns this conversation
    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
    
    if conversation.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    # Get the specific message
    message = Message.query.filter_by(id=message_id, conversation_id=conversation_id).first()
    if not message:
        return jsonify({"error": "Message not found"}), 404

    try:
        result = export_message_to_notion(message, conversation)
        return jsonify({"message": "Message exported to Notion", **result}), 200
    except ValueError as e: # Specific config error
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"Error exporting message {message_id} to Notion: {e}")
        return jsonify({"error": str(e)}), 500
