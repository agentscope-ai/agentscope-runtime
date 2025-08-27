# api/conversation_routes.py
"""
Conversation API routes for AgentScope Runtime RAG Demo.

Handles conversation management and message processing with integrated
AgentScope Runtime communication.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.models import Conversation, Message, db
import logging

logger = logging.getLogger(__name__)

conversation_bp = Blueprint('conversation', __name__)

@conversation_bp.route('/api/conversations', methods=['GET'])
@login_required
def list_conversations():
    """List all conversations for the current user."""
    try:
        conversations = Conversation.query.filter_by(
            user_id=current_user.id
        ).order_by(
            Conversation.updated_at.desc()
        ).all()
        
        result = []
        for conv in conversations:
            # Build a lightweight preview for the frontend
            preview = None
            if conv.messages and len(conv.messages) > 0:
                # Take the last message text as preview
                last_message = conv.messages[-1]
                preview = last_message.text[:100] + ("..." if len(last_message.text) > 100 else "")
            
            result.append({
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() + 'Z',
                "updated_at": conv.updated_at.isoformat() + 'Z',
                "preview": preview,
                "message_count": len(conv.messages),
            })

        logger.info(f"Retrieved {len(result)} conversations for user {current_user.id}")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error retrieving conversations for user {current_user.id}: {e}")
        return jsonify({"error": "Failed to retrieve conversations"}), 500

@conversation_bp.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation():
    """Create a new conversation for the current user."""
    try:
        data = request.get_json()
        title = data.get('title', 'New Conversation')
        
        conversation = Conversation(title=title, user_id=current_user.id)
        db.session.add(conversation)
        db.session.commit()
        
        logger.info(f"Created new conversation {conversation.id} for user {current_user.id}")
        
        return jsonify({
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat() + 'Z',
            "updated_at": conversation.updated_at.isoformat() + 'Z',
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating conversation for user {current_user.id}: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to create conversation"}), 500

@conversation_bp.route('/api/conversations/<int:conversation_id>/messages', methods=['POST'])
@login_required
def send_message(conversation_id):
    """Send a message in a conversation and get AI response via AgentScope Runtime."""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verify user owns this conversation
        if conversation.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        
        data = request.get_json()
        text = data.get('text')
        sender = data.get('sender', 'user')
        
        if not text:
            return jsonify({"error": "Message content cannot be empty"}), 400
        
        # Create user message
        user_message = Message(
            text=text,
            sender=sender,
            conversation_id=conversation_id,
        )
        db.session.add(user_message)
        
        # Update conversation title (if it's the first user message)
        if sender == "user" and len(conversation.messages) <= 1:
            conversation.title = text[:20] + ("..." if len(text) > 20 else "")
        
        db.session.commit()
        
        # If this is a user message, generate AI response using AgentScope Runtime
        if sender == "user":
            ai_response_text = ""
            question = text
            
            logger.info(f"Processing user message: '{question}' in conversation {conversation_id}")
            
            try:
                # Import AgentScope Runtime communication function
                from web_server import call_agentscope_runtime
                
                # Generate AI response using AgentScope Runtime
                logger.info("Calling AgentScope Runtime for response generation...")
                
                # Use conversation ID as session ID for AgentScope Runtime
                session_id = f"conv_{conversation_id}"
                user_id = str(current_user.id)
                
                chunk_count = 0
                ai_response_text = ""
                last_chunk = ""
                error_occurred = False
                for chunk in call_agentscope_runtime(question, user_id, session_id):
                    # Check if chunk contains an error message
                    if chunk and "Can't connect to LLM" in chunk:
                        error_occurred = True
                        ai_response_text = chunk  # Store the error message
                        break  # Stop processing on error
                    
                    # AgentScope Runtime sends full accumulated text in each chunk
                    # So we only keep the last (most complete) chunk
                    last_chunk = chunk
                    chunk_count += 1
                    if chunk_count <= 3:  # Log first few chunks
                        logger.info(f"Received chunk {chunk_count}: '{chunk[:50]}...'")
                
                # Use the final complete response if no error occurred
                if not error_occurred:
                    ai_response_text = last_chunk
                
                logger.info(f"AgentScope Runtime response complete. Total chunks: {chunk_count}, Final length: {len(ai_response_text)}")
                
                # Only provide fallback if we truly got no response
                if not ai_response_text.strip():
                    ai_response_text = "Can't connect to LLM: No response received from the language model service."
                
            except Exception as e:
                logger.error(f"Error generating AI response via AgentScope Runtime: {str(e)}", exc_info=True)
                ai_response_text = f"Can't connect to LLM: {str(e)}"
            
            # Save AI response
            ai_message = Message(
                text=ai_response_text,
                sender="ai",
                conversation_id=conversation_id,
            )
            db.session.add(ai_message)
            db.session.commit()
            
            logger.info(f"Saved AI response for conversation {conversation_id}")
        
        # Return the appropriate message (AI response if generated, otherwise user message)
        if sender == "user" and 'ai_message' in locals():
            return jsonify({
                "id": ai_message.id,
                "text": ai_message.text,
                "sender": ai_message.sender,
                "created_at": ai_message.created_at.isoformat() + 'Z',
            }), 201
        else:
            return jsonify({
                "id": user_message.id,
                "text": user_message.text,
                "sender": user_message.sender,
                "created_at": user_message.created_at.isoformat() + 'Z',
            }), 201
        
    except Exception as e:
        logger.error(f"Error processing message in conversation {conversation_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": f"Failed to process message: {str(e)}"}), 500

@conversation_bp.route('/api/conversations/<int:conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """Get a specific conversation with all messages."""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verify user owns this conversation
        if conversation.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Convert to dictionary
        conversation_data = {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat() + 'Z',
            "updated_at": conversation.updated_at.isoformat() + 'Z',
            "messages": [
                {
                    "id": message.id,
                    "text": message.text,
                    "sender": message.sender,
                    "created_at": message.created_at.isoformat() + 'Z'
                } for message in conversation.messages
            ]
        }
        
        logger.info(f"Retrieved conversation {conversation_id} with {len(conversation_data['messages'])} messages")
        return jsonify(conversation_data), 200
        
    except Exception as e:
        logger.error(f"Error retrieving conversation {conversation_id}: {e}")
        return jsonify({"error": "Failed to retrieve conversation"}), 500

@conversation_bp.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    """Delete a specific conversation and all its messages."""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verify user owns this conversation
        if conversation.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Delete all messages in the conversation first (due to foreign key constraints)
        Message.query.filter_by(conversation_id=conversation_id).delete()
        
        # Delete the conversation
        db.session.delete(conversation)
        db.session.commit()
        
        logger.info(f"Deleted conversation {conversation_id} for user {current_user.id}")
        return jsonify({"message": "Conversation deleted successfully"}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to delete conversation"}), 500

@conversation_bp.route('/api/conversations/<int:conversation_id>/title', methods=['PUT'])
@login_required
def update_conversation_title(conversation_id):
    """Update the title of a conversation."""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verify user owns this conversation
        if conversation.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        
        data = request.get_json()
        new_title = data.get('title')
        
        if not new_title:
            return jsonify({"error": "Title cannot be empty"}), 400
        
        conversation.title = new_title
        db.session.commit()
        
        logger.info(f"Updated title for conversation {conversation_id} to '{new_title}'")
        
        return jsonify({
            "id": conversation.id,
            "title": conversation.title,
            "updated_at": conversation.updated_at.isoformat() + 'Z',
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating conversation {conversation_id} title: {e}")
        return jsonify({"error": "Failed to update conversation title"}), 500