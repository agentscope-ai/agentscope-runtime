# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'ai_assistant.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Model Studio API configuration
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')

    # File Upload Settings
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), os.environ.get("UPLOAD_FOLDER", "uploads"))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # Notion Settings (for MCP integration)
    NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
    NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
    
    # MCP Settings
    MCP_ENABLED = os.environ.get("MCP_ENABLED", "true").lower() == "true"
    MCP_NOTION_SERVER = os.environ.get("MCP_NOTION_SERVER", "mcp-server-notion")

    # Agent Server Settings
    AGENT_SERVER_HOST = os.environ.get("AGENT_SERVER_HOST", "localhost")
    AGENT_SERVER_PORT = int(os.environ.get("AGENT_SERVER_PORT", "8090"))
    AGENT_SERVER_ENDPOINT = os.environ.get("AGENT_SERVER_ENDPOINT", "agent")
    
