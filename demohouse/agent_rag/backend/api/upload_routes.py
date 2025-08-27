# api/upload_routes.py
"""
File Upload API routes for AgentScope Runtime RAG Demo.

Handles file upload functionality and knowledge base management.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import logging
from services.rag_service import add_file_to_kb, remove_file_from_kb
from models.models import KnowledgeFile, db

logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload', __name__)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc', 'md', 'csv', 'json', 'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@upload_bp.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """Upload a file to the knowledge base."""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                "error": f"File type not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        # Secure the filename
        filename = secure_filename(file.filename)
        
        # Create user-specific upload directory
        user_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(current_user.id))
        os.makedirs(user_upload_dir, exist_ok=True)
        
        # Save file
        filepath = os.path.join(user_upload_dir, filename)
        file.save(filepath)
        
        # Add to knowledge base
        logger.info(f"Starting to process file '{filename}' for user {current_user.id}")
        success, message = add_file_to_kb(current_user.id, filename, filepath)
        
        if success:
            # Save to database
            kb_file = KnowledgeFile(
                filename=filename,
                filepath=filepath,
                user_id=current_user.id
            )
            db.session.add(kb_file)
            db.session.commit()
            
            logger.info(f"File '{filename}' uploaded and processed successfully for user {current_user.id}")
            return jsonify({
                "message": "File uploaded and processed successfully",
                "filename": filename,
                "details": message
            }), 201
        else:
            # Remove file if processing failed
            if os.path.exists(filepath):
                os.remove(filepath)
            logger.error(f"Failed to process file '{filename}' for user {current_user.id}: {message}")
            return jsonify({"error": f"Failed to process file: {message}"}), 500
            
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@upload_bp.route('/api/knowledge-files', methods=['GET'])
@login_required
def list_knowledge_files():
    """List all knowledge files for the current user."""
    try:
        files = KnowledgeFile.query.filter_by(user_id=current_user.id).all()
        
        result = []
        for file in files:
            result.append({
                "id": file.id,
                "filename": file.filename,
                "uploaded_at": file.uploaded_at.isoformat() + 'Z',
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error listing knowledge files: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@upload_bp.route('/api/knowledge-files/<int:file_id>', methods=['DELETE'])
@login_required
def delete_knowledge_file(file_id):
    """Delete a knowledge file."""
    try:
        file = KnowledgeFile.query.get_or_404(file_id)
        
        # Verify user owns this file
        if file.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Remove from FAISS index first
        success = remove_file_from_kb(file.user_id, file.filename)
        if not success:
            logger.warning(f"Failed to remove {file.filename} from FAISS index")
        
        # Remove from file system
        if os.path.exists(file.filepath):
            os.remove(file.filepath)
        
        # Remove from database
        db.session.delete(file)
        db.session.commit()
        
        logger.info(f"File '{file.filename}' deleted for user {current_user.id}")
        return jsonify({"message": "File deleted successfully"}), 200
        
    except Exception as e:
        logger.error(f"Error deleting knowledge file: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500