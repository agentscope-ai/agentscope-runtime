# services/notion_service.py
import json
import requests
from datetime import datetime
from config import Config
import logging
from models.models import Conversation, Message

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

def _export_via_direct_api(export_type, content_data):
    """Fallback function to export directly to Notion API when MCP is not available."""
    headers = {
        "Authorization": f"Bearer {Config.NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # Check if we have a database ID or page ID
    parent_id = Config.NOTION_DATABASE_ID
    logger.info(f"[NOTION] Using parent_id: {parent_id} (from Config.NOTION_DATABASE_ID)")
    
    # First, let's determine if it's a database or page
    check_url = f"https://api.notion.com/v1/databases/{parent_id}"
    check_response = requests.get(check_url, headers=headers)
    
    is_database = check_response.status_code == 200
    logger.info(f"[NOTION] Database check result: {check_response.status_code}, is_database: {is_database}")
    
    if not is_database:
        # It's likely a page, so we'll append to it
        logger.info(f"ID {parent_id} appears to be a page, appending content to it")
        
        # Append blocks to the existing page
        append_url = f"https://api.notion.com/v1/blocks/{parent_id}/children"
        
        # Add a separator first
        separator_blocks = [
            {
                "object": "block",
                "type": "divider",
                "divider": {}
            }
        ]
        
        append_data = {
            "children": separator_blocks + content_data["blocks"]
        }
        
        response = requests.patch(append_url, headers=headers, json=append_data)
        
        if response.status_code == 200:
            # Get the page info
            page_response = requests.get(f"https://api.notion.com/v1/pages/{parent_id}", headers=headers)
            page_info = page_response.json() if page_response.status_code == 200 else {}
            
            logger.info(f"Successfully appended {export_type} to Notion page via direct API: {parent_id}")
            
            return {
                "page_id": parent_id,
                "page_url": page_info.get('url', f"https://notion.so/{parent_id}"),
                "status": "success_direct_api_append",
                "message": "Content appended to existing page"
            }
        else:
            logger.error(f"[NOTION] Failed to append to page {parent_id}: {response.status_code} - {response.text}")
            raise requests.exceptions.HTTPError(f"{response.status_code} Client Error: {response.text} for url: {append_url}")
    else:
        # It's a database, create a new page
        page_data = {
            "parent": {"database_id": parent_id},
            "properties": {
                "Name": {
                    "title": [{
                        "text": {"content": content_data["title"]}
                    }]
                }
            },
            "children": content_data["blocks"]
        }
        
        # Call Notion API
        create_page_url = "https://api.notion.com/v1/pages"
        response = requests.post(create_page_url, headers=headers, json=page_data)
        response.raise_for_status()
        
        page_info = response.json()
        logger.info(f"Successfully created new page for {export_type} in Notion database via direct API: {page_info.get('id')}")
        
        return {
            "page_id": page_info.get('id'),
            "page_url": page_info.get('url'),
            "status": "success_direct_api_new_page"
        }

def export_conversation_to_notion(conversation_id):
    """Export a conversation to Notion using MCP via agent service, with direct API fallback."""
    if not Config.NOTION_API_KEY:
        raise ValueError("Notion API key not configured")
    
    if not Config.NOTION_DATABASE_ID:
        raise ValueError("Notion Database ID not configured")

    conversation = Conversation.query.get_or_404(conversation_id)
    
    try:
        # Try MCP first
        from services.agent_service import call_mcp_tool
        
        # Fetch conversation messages
        messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at.asc()).all()
        
        # Format content for Notion export request
        export_content = {
            "title": f"Chat Export: {conversation.title}",
            "database_id": Config.NOTION_DATABASE_ID,
            "content": {
                "conversation_title": conversation.title,
                "export_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S Local'),
                "messages": [
                    {
                        "sender": "User" if msg.sender == "user" else "AI Assistant",
                        "content": msg.text,
                        "timestamp": msg.created_at.strftime('%H:%M')
                    } for msg in messages
                ]
            }
        }
        
        # Use agent service to call Notion via MCP
        result = call_mcp_tool("notion_export", export_content)
        
        # Check if MCP actually worked
        if isinstance(result, dict) and result.get("status") == "success":
            logger.info(f"Exported conversation {conversation_id} to Notion via MCP agent service")
            return {"mcp_result": result, "status": "success"}
        else:
            # MCP failed or was simulated, fall back to direct API
            logger.info(f"MCP failed for conversation {conversation_id}: {result.get('message', 'Unknown error')}, falling back to direct API")
            raise ImportError("MCP failed, using direct API fallback")
    
    except (ImportError, Exception) as e:
        # Fallback to direct Notion API
        logger.info(f"Using direct Notion API fallback for conversation {conversation_id}: {str(e)[:100]}")
        
        try:
            # Fetch messages again if needed
            messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at.asc()).all()
            
            # Format blocks for direct API
            notion_blocks = []
            
            # Title block
            notion_blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"Conversation: {conversation.title}"}
                    }]
                }
            })
            
            # Export date block
            notion_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"Exported on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"}
                    }]
                }
            })
            
            # Message blocks
            for msg in messages:
                sender_text = "User" if msg.sender == "user" else "AI Assistant"
                
                notion_blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": f"{sender_text} ({msg.created_at.strftime('%H:%M')}):"}
                        }]
                    }
                })
                
                # Split message content if too long for Notion's 2000 char limit (using 1900 for safety)
                message_content = msg.text
                max_length = 1900
                
                if len(message_content) <= max_length:
                    # Single paragraph if content fits
                    notion_blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": message_content}
                            }]
                        }
                    })
                else:
                    # Split into multiple paragraphs if content is too long
                    chunks = [message_content[i:i+max_length] for i in range(0, len(message_content), max_length)]
                    for chunk in chunks:
                        notion_blocks.append({
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": chunk}
                                }]
                            }
                        })
            
            # Use direct API fallback
            return _export_via_direct_api("conversation", {
                "title": f"Chat Export: {conversation.title}",
                "blocks": notion_blocks
            })
            
        except Exception as api_error:
            logger.error(f"Direct API export also failed for conversation {conversation_id}: {api_error}")
            raise Exception(f"Both MCP and direct API export failed: {str(api_error)}")

def export_message_to_notion(message, conversation):
    """Export a specific message to Notion using MCP via agent service, with direct API fallback."""
    if not Config.NOTION_API_KEY:
        raise ValueError("Notion API key not configured")
    
    if not Config.NOTION_DATABASE_ID:
        raise ValueError("Notion Database ID not configured")

    try:
        # Try MCP first
        from services.agent_service import call_mcp_tool
        
        # Format message for Notion export
        sender_text = "User" if message.sender == "user" else "AI Assistant"
        
        export_content = {
            "title": f"{sender_text} Message: {conversation.title[:50]}{'...' if len(conversation.title) > 50 else ''}",
            "database_id": Config.NOTION_DATABASE_ID,
            "content": {
                "message_type": sender_text,
                "conversation_title": conversation.title,
                "export_date": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                "message": {
                    "content": message.text,
                    "timestamp": message.created_at.strftime('%H:%M')
                }
            }
        }
        
        # Use agent service to call Notion via MCP
        result = call_mcp_tool("notion_export_message", export_content)
        
        # Check if MCP actually worked
        if isinstance(result, dict) and result.get("status") == "success":
            logger.info(f"Exported message {message.id} to Notion via MCP agent service")
            return {"mcp_result": result, "status": "success"}
        else:
            # MCP failed, fall back to direct API
            logger.info(f"MCP failed for message {message.id}: {result.get('message', 'Unknown error')}, falling back to direct API")
            raise ImportError("MCP failed, using direct API fallback")
    
    except (ImportError, Exception) as e:
        # Fallback to direct Notion API
        logger.info(f"Using direct Notion API fallback for message {message.id}: {str(e)[:100]}")
        
        try:
            sender_text = "User" if message.sender == "user" else "AI Assistant"
            
            # Format blocks for direct API
            notion_blocks = []
            
            # Title block
            notion_blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"{sender_text} Message from: {conversation.title}"}
                    }]
                }
            })
            
            # Export date block
            notion_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"Saved on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"}
                    }]
                }
            })
            
            # Message header
            notion_blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"{sender_text} ({message.created_at.strftime('%H:%M')}):"}
                    }]
                }
            })
            
            # Message content - split if too long for Notion's 2000 char limit (using 1900 for safety)
            message_content = message.text
            max_length = 1900
            
            if len(message_content) <= max_length:
                # Single paragraph if content fits
                logger.info(f"[NOTION] Message content fits in single block: {len(message_content)} chars")
                notion_blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": message_content}
                        }]
                    }
                })
            else:
                # Split into multiple paragraphs if content is too long
                chunks = [message_content[i:i+max_length] for i in range(0, len(message_content), max_length)]
                logger.info(f"[NOTION] Splitting message into {len(chunks)} chunks (total: {len(message_content)} chars)")
                for i, chunk in enumerate(chunks):
                    logger.info(f"[NOTION] Chunk {i+1}: {len(chunk)} chars")
                    notion_blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": chunk}
                            }]
                        }
                    })
            
            # Use direct API fallback
            return _export_via_direct_api("message", {
                "title": f"{sender_text} Message: {conversation.title[:50]}{'...' if len(conversation.title) > 50 else ''}",
                "blocks": notion_blocks
            })
            
        except Exception as api_error:
            logger.error(f"Direct API export also failed for message {message.id}: {api_error}")
            raise Exception(f"Both MCP and direct API export failed: {str(api_error)}")
