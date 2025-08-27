# services/model_studio_embedding.py
import os
import logging
import numpy as np
from openai import OpenAI
import time
from config import Config


# Add at the top of app.py
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

logger = logging.getLogger(__name__)

class ModelStudioEmbedding:
    def __init__(self, config, is_test=False):
        self.config = config
        self.client = None
        self.embedding_dim = 1024  # Default dimension for text-embedding-v3
        self.is_test = is_test
        self.is_dev_mode = os.getenv('FLASK_ENV') == 'development' or os.getenv('FLASK_DEBUG') == '1'
        self.api_key_error_logged = False  # To prevent repeated error logging
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the OpenAI client for Model Studio API."""
        api_key = os.getenv("DASHSCOPE_API_KEY")
        
        # In test mode, don't initialize the real client
        if self.is_test:
            logger.info("Running in test mode - not initializing real Model Studio client")
            return
        
        # In development mode without API key, use mock embeddings
        if self.is_dev_mode and not api_key:
            if not self.api_key_error_logged:
                logger.info("Development mode detected without API key - using mock embeddings")
                self.api_key_error_logged = True
            self.client = None
            return
        
        if not api_key:
            if not self.api_key_error_logged:
                logger.warning("DASHSCOPE_API_KEY environment variable not set. "
                              "Will use mock embeddings in production mode.")
                self.api_key_error_logged = True
            self.client = None
            return
    
        # Use the base URL from environment or default to international endpoint
        base_url = os.getenv("DASHSCOPE_EMBEDDING_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
        
        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info(f"Model Studio embedding client initialized with base URL: {base_url}")
        except Exception as e:
            if not self.api_key_error_logged:
                logger.error(f"Failed to initialize Model Studio client: {str(e)}")
                logger.warning("Will use mock embeddings in production mode due to client initialization failure")
                self.api_key_error_logged = True
            self.client = None
    
    def get_embeddings(self, texts):
        """Get embeddings from Model Studio API or mock in test mode."""
        # Handle single string input by wrapping it in a list
        if isinstance(texts, str):
            texts = [texts]
        
        if self.is_test:
            logger.info(f"Generating mock embeddings for {len(texts)} texts with dimension {self.embedding_dim} in test mode")
            # Return simple mock embeddings with the correct dimension
            return np.array([np.ones(self.embedding_dim) * i for i in range(len(texts))])
        
        if not self.client:
            self._initialize_client()
            # If still no client (e.g., no API key or initialization failed), return mock embeddings
            if not self.client:
                logger.warning("No client available, using mock embeddings in production mode")
                # Use more diverse mock embeddings that better simulate real embeddings
                import hashlib
                embeddings = []
                for i, text in enumerate(texts):
                    # Create pseudo-random embeddings based on text content hash
                    text_hash = hashlib.md5(text.encode()).hexdigest()
                    # Convert hash to numbers and normalize
                    seed = int(text_hash[:8], 16) % 1000
                    np.random.seed(seed)
                    embedding = np.random.normal(0, 0.1, self.embedding_dim).astype(np.float32)
                    # Normalize the embedding
                    embedding = embedding / np.linalg.norm(embedding)
                    embeddings.append(embedding)
                return np.array(embeddings)
        
        # Model Studio has rate limits, add a small delay to avoid hitting them
        time.sleep(0.1)
        
        try:
            response = self.client.embeddings.create(
                model="text-embedding-v3",  # Model Studio embedding model
                input=texts,
                dimensions=self.embedding_dim,  # Default dimension
                encoding_format="float"
            )
            
            # Extract embeddings from response
            embeddings = [data.embedding for data in response.data]
            
            logger.info(f"Successfully got embeddings for {len(texts)} texts")
            return np.array(embeddings)
            
        except Exception as e:
            # Only log the error once to avoid spam
            if not self.api_key_error_logged:
                logger.error(f"Error getting embeddings from Model Studio: {str(e)}")
                logger.info("Using mock embeddings due to API error")
                self.api_key_error_logged = True
            # Return mock embeddings in case of error
            return np.array([np.ones(self.embedding_dim) * i for i in range(len(texts))])

    def get_embedding_dimension(self):
        """Return the dimension of the embeddings."""
        return self.embedding_dim
    
    def extract_document_text(self, image_data):
        """
        Use Qwen-VL model to extract text from document images.
        This is separate from the embedding functionality.
        """
        if self.is_test:
            logger.info("Running in test mode - returning mock document text")
            return "Mock extracted text for testing purposes. This document contains important information for the knowledge base."
        
        if not self.client:
            self._initialize_client()
            if not self.client:
                logger.warning("No client available for document extraction")
                return ""
        
        try:
            # Encode the image data as base64
            import base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            image_url = f"image/png;base64,{base64_image}"
            
            # Call the Qwen-VL model for document understanding
            response = self.client.chat.completions.create(
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
            return ""