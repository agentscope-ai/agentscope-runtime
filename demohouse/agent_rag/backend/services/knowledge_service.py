# services/knowledge_service.py
import os
from flask import current_app
from werkzeug.utils import secure_filename
from models.models import db, KnowledgeFile
import logging

logger = logging.getLogger(__name__)

def save_and_process_files(user_id, files):
    """Save uploaded files, process them, add to KB, and database."""
    # LAZY IMPORT - Avoid circular dependency
    from services.rag_service import add_file_to_kb
    from utils.file_utils import extract_text_from_file
    
    # Use the Flask app config to determine upload folder (available via current_app in request context)
    upload_root = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    user_upload_dir = os.path.join(upload_root, str(user_id))
    os.makedirs(user_upload_dir, exist_ok=True)

    saved_files_info = []
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(user_upload_dir, filename)
            file.save(filepath)

            try:
                # 1. Extract text from the document
                text = extract_text_from_file(filepath, filename)
                
                if not text.strip():
                    raise Exception("No text extracted from document")
                
                # 2. Add to FAISS via rag_service
                success, result = add_file_to_kb(user_id, filename, filepath)
                if not success:
                     raise Exception(f"Failed to add to KB: {result}")

                # 3. Check if file already exists in database to prevent duplicates
                existing_file = KnowledgeFile.query.filter_by(
                    filename=filename, 
                    user_id=user_id
                ).first()
                
                if existing_file:
                    # File already exists, just return the existing record info
                    saved_files_info.append({
                        "id": existing_file.id,
                        "filename": existing_file.filename,
                        "uploaded_at": existing_file.uploaded_at.isoformat(),
                        "note": "File already existed in knowledge base"
                    })
                    logger.info(f"File {filename} already exists for user {user_id}, skipping database insertion")
                else:
                    # 4. Save new file info to database
                    kb_file = KnowledgeFile(
                        filename=filename,
                        filepath=filepath,
                        user_id=user_id
                    )
                    db.session.add(kb_file)
                    db.session.flush()
                    saved_files_info.append({
                        "id": kb_file.id,
                        "filename": kb_file.filename,
                        "uploaded_at": kb_file.uploaded_at.isoformat()
                    })
                    logger.info(f"Processed and saved file {filename} for user {user_id}")

            except Exception as e:
                 logger.error(f"Error processing file {filename} for user {user_id}: {e}")
                 saved_files_info.append({
                    "filename": filename,
                    "error": str(e)
                 })

    db.session.commit()
    return saved_files_info

def get_user_knowledge_files(user_id):
    """Get list of files in the user's knowledge base."""
    kb_files = KnowledgeFile.query.filter_by(user_id=user_id).all()
    result = []
    for file in kb_files:
        result.append({
            "id": file.id,
            "name": file.filename,
            "uploaded_at": file.uploaded_at.isoformat(),
        })
    return result

def delete_knowledge_file(file_id, user_id):
    """Delete a knowledge base file."""
    # LAZY IMPORT - Avoid circular dependency
    from services.rag_service import remove_file_from_kb
    
    kb_file = KnowledgeFile.query.get_or_404(file_id)
    # In production, add ownership check
    # if kb_file.user_id != user_id:
    #     raise PermissionError("User does not own this file")

    try:
        # 1. Remove from FAISS
        success = remove_file_from_kb(kb_file.user_id, kb_file.filename)
        if not success:
             logger.warning(f"Failed to remove {kb_file.filename} from FAISS.")

        # 2. Delete physical file
        if os.path.exists(kb_file.filepath):
            os.remove(kb_file.filepath)
            logger.info(f"Deleted physical file: {kb_file.filepath}")

        # 3. Delete database record
        db.session.delete(kb_file)
        db.session.commit()
        logger.info(f"Deleted knowledge file record {file_id} for user {user_id}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting knowledge file {file_id}: {e}")
        raise e