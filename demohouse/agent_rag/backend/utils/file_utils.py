# utils/file_utils.py
import os
import logging
import base64
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
from PIL import Image
import io
import numpy as np
from config import Config
from services.model_studio_embedding import ModelStudioEmbedding

logger = logging.getLogger(__name__)

def extract_text_from_file(file_path, filename):
    """
    Extract text from various file types using appropriate methods.
    For PDFs and images, uses Model Studio's Qwen-VL for visual understanding.
    """
    logger.info(f"Starting text extraction from {filename}")
    
    # Get the file extension
    _, ext = os.path.splitext(filename.lower())
    ext = ext.lstrip('.')
    
    # For simple text files, read directly
    if ext in ['txt', 'md', 'csv', 'json']:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            if text.strip():
                logger.info(f"Successfully extracted text directly from {ext} file: {len(text)} characters")
                return text
            else:
                logger.warning(f"Text file {filename} appears to be empty")
                return "Empty text file"
        except Exception as e:
            logger.warning(f"Error reading text file directly: {e}, falling back to Qwen-VL")
    
    # For PDF files, extract text using PyMuPDF first
    if ext == 'pdf':
        if fitz is not None:
            try:
                # Try to extract text directly from PDF
                text = _extract_text_from_pdf(file_path)
                if text.strip():
                    logger.info("Successfully extracted text directly from PDF")
                    return text
                logger.info("No text extracted directly from PDF, falling back to Qwen-VL")
            except Exception as e:
                logger.warning(f"Error extracting text directly from PDF: {e}")
        else:
            logger.info("PyMuPDF (fitz) not available; skipping direct PDF text extraction")
    
    # For image files, use OCR capabilities
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff']:
        try:
            logger.info(f"Processing image file {filename} with OCR")
            with open(file_path, 'rb') as f:
                image_data = f.read()
            return _extract_text_with_qwen_vl(image_data)
        except Exception as e:
            logger.error(f"Error processing image file {filename} with OCR: {e}")
            # Return a descriptive message about the image
            return f"Image file: {filename}. Processed with OCR but no text was extracted."
    
    # For all other document types,
    # use Qwen-VL for visual understanding
    try:
        # Convert file to image for Qwen-VL processing
        image_data = _convert_file_to_image(file_path, ext)
        if not image_data:
            logger.error(f"Failed to convert file {filename} to image for Qwen-VL processing")
            raise ValueError("Failed to convert file to image for processing")
        
        # Use Model Studio's Qwen-VL for visual understanding
        return _extract_text_with_qwen_vl(image_data)
    except Exception as e:
        logger.error(f"Error extracting text with Qwen-VL: {e}")
        raise

def _extract_text_from_pdf(pdf_path):
    """Extract text directly from PDF using PyMuPDF."""
    text = ""
    try:
        if fitz is None:
            raise RuntimeError("fitz not available")
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
    return text

def _convert_file_to_image(file_path, file_ext):
    """Convert various file types to image data for Qwen-VL processing."""
    try:
        if file_ext in ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'tiff']:
            # For image files, just read the binary data
            with open(file_path, 'rb') as f:
                return f.read()
        
        elif file_ext == 'pdf' and fitz is not None:
            # For PDFs, convert first page to image
            doc = fitz.open(file_path)
            if doc.page_count > 0:
                page = doc.load_page(0)  # Get first page
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                return img_byte_arr.getvalue()
            doc.close()
        
        # For other file types, we could add more converters here
        # For now, just return the file as is
        with open(file_path, 'rb') as f:
            return f.read()
            
    except Exception as e:
        logger.error(f"Error converting file to image: {e}")
        return None

def _extract_text_with_qwen_vl(image_data):
    """
    Use Model Studio's Qwen-VL model to extract text from image data.
    """
    try:
        # Initialize the embedding service in production mode
        embedding_service = ModelStudioEmbedding(Config, is_test=False)
        
        # If we're in test mode, return mock text
        if embedding_service.is_test:
            return "Mock extracted text for testing purposes. This document contains important information for the knowledge base."
        
        # Get the OpenAI client
        client = embedding_service.client
        if not client:
            logger.warning("Model Studio client not initialized, falling back to direct extraction")
            return ""
        
        # Encode the image data as base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        image_url = f"image/png;base64,{base64_image}"
        
        # Call the Qwen-VL model
        response = client.chat.completions.create(
            model="qwen-vl-plus-2025-08-15",  # Use the specified model
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "You are a document processing assistant. Extract all text content from the provided document image."}]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        },
                        {"type": "text", "text": "Extract all text from this document."}
                    ]
                }
            ],
            max_tokens=1024
        )
        
        # Get the extracted text
        extracted_text = response.choices[0].message.content
        logger.info(f"Successfully extracted text with Qwen-VL: {extracted_text[:100]}...")
        return extracted_text
        
    except Exception as e:
        logger.error(f"Error extracting text with Qwen-VL: {str(e)}")
        # Fallback to simple text if available
        if 'image_data' in locals():
            try:
                # Try to decode as UTF-8 if it's text
                return image_data.decode('utf-8', errors='ignore')
            except:
                pass
        raise Exception(f"Failed to extract text from document: {str(e)}")

def chunk_text(text, chunk_size=500, overlap=100):
    """
    Split text into chunks with specified size and overlap.
    """
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if len(chunk) > 100:  # Only add meaningful chunks
            chunks.append(chunk)
    return chunks