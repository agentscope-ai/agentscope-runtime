# -*- coding: utf-8 -*-
"""
Web Server for AgentScope Runtime RAG Demo

This Flask application provides web API endpoints for the RAG (Retrieval-Augmented Generation)
chatbot demo, integrating with AgentScope Runtime for agent communication.
"""

import json
import logging
import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000"], "supports_credentials": True}})

# Configure database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    basedir,
    "ai_assistant.db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

# Configure file upload settings
app.config["UPLOAD_FOLDER"] = os.path.join(basedir, os.getenv("UPLOAD_FOLDER", "uploads"))
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize database and login manager
from models import db, init_app as init_db
init_db(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure Flask-Login for API requests
@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access for API requests."""
    return jsonify({"error": "Authentication required"}), 401

# Import models from the models package
from models.models import User, Conversation, Message

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Load a user by ID for Flask-Login."""
    return User.query.get(int(user_id))

# Create database tables
def create_tables():
    """Initialize database tables and create sample users."""
    with app.app_context():
        db.create_all()

        # Create sample users (if none exist)
        if not User.query.first():
            user1 = User(username="testuser1", name="Test User 1")
            user1.set_password("testpass1")
            user2 = User(username="testuser2", name="Test User 2")
            user2.set_password("testpass2")
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()
            logger.info("Created sample users: testuser1/testpass1, testuser2/testpass2")

# AgentScope Runtime communication functions
def parse_sse_line(line):
    """Parse Server-Sent Events (SSE) line."""
    line = line.decode("utf-8").strip()
    if line.startswith("data: "):
        return "data", line[6:]
    elif line.startswith("event:"):
        return "event", line[7:]
    elif line.startswith("id: "):
        return "id", line[4:]
    elif line.startswith("retry:"):
        return "retry", int(line[7:])
    return None, None

def sse_client(url, data=None):
    """Client for Server-Sent Events communication with AgentScope Runtime."""
    headers = {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
    }
    
    try:
        if data is not None:
            response = requests.post(
                url,
                stream=True,
                headers=headers,
                json=data,
                timeout=30,
            )
        else:
            response = requests.get(
                url,
                stream=True,
                headers=headers,
                timeout=30,
            )
        
        # Check if the request was successful
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.reason}"
            try:
                error_details = response.json()
                error_msg += f" - Details: {error_details}"
            except:
                if response.text:
                    error_msg += f" - Response: {response.text[:200]}"
            logger.error(f"AgentScope Runtime returned error: {error_msg}")
            yield f"Error: AgentScope Runtime service returned {error_msg}"
            return
            
        for line in response.iter_lines():
            if line:
                field, value = parse_sse_line(line)
                if field == "data":
                    try:
                        data = json.loads(value)
                        # Handle AgentScope Runtime response format
                        if data.get("object") == "content" and data.get("type") == "text":
                            yield data.get("text", "")
                        elif data.get("object") == "response" and data.get("status") == "failed":
                            # Surface upstream LLM/service error to the user explicitly
                            err = data.get("error") or {}
                            err_msg = err.get("message") or err.get("code") or "Unknown error"
                            yield f"Can't connect to LLM: {err_msg}"
                        elif data.get("object") == "message" and "content" in data:
                            # Handle content list format from AgentScope Runtime
                            content = data["content"]
                            if isinstance(content, list) and len(content) > 0:
                                # Extract text from the first content item
                                content_item = content[0]
                                if isinstance(content_item, dict) and content_item.get("type") == "text":
                                    text = content_item.get("text", "")
                                    if text:
                                        yield text
                            elif isinstance(content, str):
                                yield content
                        elif isinstance(data, str):
                            yield data
                    except json.JSONDecodeError:
                        # If not JSON, yield as plain text
                        if value:
                            yield value
                            
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error communicating with AgentScope Runtime at {url}: {e}")
        yield f"Error: Failed to connect to agent service at {url}. Connection error: {str(e)}"
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout error communicating with AgentScope Runtime: {e}")
        yield f"Error: Timeout while communicating with agent service. {str(e)}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error communicating with AgentScope Runtime: {e}")
        yield f"Error: Request failed with agent service. {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in SSE client: {e}", exc_info=True)
        yield f"Error: Unexpected error occurred in communication with agent service. {str(e)}"

def call_agentscope_runtime(query, user_id, session_id):
    """
    Communicate with AgentScope Runtime deployed agent.
    
    Args:
        query: User's query text
        user_id: ID of the user
        session_id: Session/conversation ID
    
    Yields:
        str: Streamed response content from the agent
    """
    server_port = int(os.environ.get("SERVER_PORT", "8080"))
    server_endpoint = os.environ.get("SERVER_ENDPOINT", "agent")
    server_host = os.environ.get("SERVER_HOST", "localhost")

    url = f"http://{server_host}:{server_port}/{server_endpoint}"

    # Retrieve KB context for the user and include it in the prompt
    try:
        from services.rag_service import retrieve_context
        kb_context = retrieve_context(user_id, query, n_results=3) or ""
    except Exception as e:
        logger.error(f"Failed to retrieve KB context: {e}")
        kb_context = ""

    # Prepare AgentScope Runtime request format with context-first instruction
    input_messages = []
    input_messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Retrieved context:\n\n{kb_context}" if kb_context else "Retrieved context:\n\n",
                },
            ],
        }
    )
    input_messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": query,
                },
            ],
        }
    )

    data_arg = {
        "input": input_messages,
        "session_id": session_id,
        "user_id": user_id,
    }
    
    logger.info(f"Calling AgentScope Runtime at {url} with session {session_id} and user {user_id}")
    
    try:
        has_content = False
        last_error_detail = None
        error_count = 0
        for content in sse_client(url, data=data_arg):
            # Capture the last error-like detail emitted by the SSE client
            if content and any(sub in content for sub in ('Error:', "Can't connect to LLM")):
                last_error_detail = content
            # Check if we got an error message
            if content and "Can't connect to LLM" in content:
                error_count += 1
                # If we get multiple error messages, it might be the AgentScope Runtime bug
                if error_count > 1:
                    logger.warning("Detected possible AgentScope Runtime bug, providing fallback response")
                    yield "I'm experiencing technical difficulties with the language model service. This might be due to a known issue with AgentScope Runtime where it has trouble processing multiple interactions in the same session. As a workaround, you might want to start a new conversation to continue asking questions about your documents."
                    return
            
            if content:  # Only yield non-empty content
                has_content = True
                yield content
        
        # If no content was received, provide appropriate error message
        if not has_content:
            details = f" Details: {last_error_detail}" if last_error_detail else ""
            yield f"Can't connect to LLM: No response received from the AgentScope Runtime service.{details}"
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error communicating with AgentScope Runtime: {e}")
        # Provide detailed error information
        if hasattr(e, 'response') and e.response is not None:
            status_code = e.response.status_code
            reason = e.response.reason
            try:
                error_details = e.response.json()
            except:
                error_details = e.response.text[:200] if e.response.text else "No additional details"
            
            yield f"Can't connect to LLM: Network error with AgentScope Runtime service (Status: {status_code} - {reason}). Details: {error_details}"
        elif hasattr(e, 'request'):
            yield f"Can't connect to LLM: Failed to establish connection to AgentScope Runtime service at {url}. Error: {str(e)}"
        else:
            yield f"Can't connect to LLM: Network error occurred while communicating with AgentScope Runtime service. Error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in AgentScope Runtime communication: {e}", exc_info=True)
        
        # Return appropriate error message with explicit details
        yield f"Can't connect to LLM: Unexpected error occurred with AgentScope Runtime service. Error: {str(e)}"

# API routes

# Authentication routes
@app.route("/api/login", methods=["POST"])
def login():
    """User login endpoint."""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password cannot be empty"}), 400

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        login_user(user)
        logger.info(f"User {username} logged in successfully")
        return (
            jsonify(
                {
                    "id": user.id,
                    "username": user.username,
                    "name": user.name,
                    "created_at": user.created_at.isoformat(),
                },
            ),
            200,
        )
    else:
        logger.warning(f"Failed login attempt for username: {username}")
        return jsonify({"error": "Invalid username or password"}), 401

@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    """User logout endpoint."""
    username = current_user.username
    logout_user()
    logger.info(f"User {username} logged out")
    return jsonify({"message": "Logged out successfully"}), 200

# User information routes
@app.route("/api/users/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    """Get user information."""
    if current_user.id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
        
    user = User.query.get_or_404(user_id)
    return (
        jsonify(
            {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "created_at": user.created_at.isoformat(),
            },
        ),
        200,
    )

# Import and register API blueprints
try:
    from api.conversation_routes import conversation_bp
    from api.upload_routes import upload_bp
    from api.export_routes import export_bp
    
    app.register_blueprint(conversation_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(export_bp)
    
    logger.info("API blueprints registered successfully")
except ImportError as e:
    logger.warning(f"Some API blueprints could not be imported: {e}")
    logger.warning("The application will run with limited functionality")

# Health check endpoint
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "AgentScope Runtime RAG Web Server",
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


@app.route("/api/diagnostics/kb", methods=["GET"])
def kb_diagnostics():
    """Return diagnostics about the on-disk KB metadata and index."""
    try:
        from services.rag_service import get_or_create_metadata
        from config import Config
        meta = get_or_create_metadata()
        index_exists = os.path.exists(os.path.join(Config.UPLOAD_FOLDER, "faiss_index.bin"))
        meta_exists = os.path.exists(os.path.join(Config.UPLOAD_FOLDER, "faiss_metadata.pkl"))
        return jsonify({
            "chunks": len(meta.get("text_chunks", [])),
            "files": len(set(meta.get("file_ids", []))),
            "index_exists": index_exists,
            "metadata_exists": meta_exists,
        }), 200
    except Exception as e:
        logger.error(f"Error fetching KB diagnostics: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch diagnostics"}), 500

# Error handling
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    logger.error(f"404 Error: {error}")
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"500 Error: {error}")
    db.session.rollback()
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(401)
def unauthorized(error):
    """Handle 401 errors."""
    logger.warning(f"401 Error: {error}")
    return jsonify({"error": "Authentication required"}), 401

@app.errorhandler(403)
def forbidden(error):
    """Handle 403 errors."""
    logger.warning(f"403 Error: {error}")
    return jsonify({"error": "Access forbidden"}), 403

# Initialize the application
def init_app():
    """Initialize the Flask application."""
    logger.info("Initializing AgentScope Runtime RAG Web Server...")
    create_tables()
    logger.info("Web server initialization complete")

if __name__ == "__main__":
    init_app()
    
    # Get configuration from environment
    host = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_SERVER_PORT", "5100"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in ["1", "true", "yes"]
    
    logger.info(f"Starting web server on {host}:{port} (debug={debug})")
    app.run(debug=debug, host=host, port=port)
