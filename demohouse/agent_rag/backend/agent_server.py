# agent_server.py
# -*- coding: utf-8 -*-
"""
AgentScope Runtime RAG Agent Server

This server deploys a RAG (Retrieval-Augmented Generation) agent using AgentScope Runtime.
The agent has knowledge retrieval capabilities, tool usage, and conversation management.
"""

import asyncio
import os
import logging
from dotenv import load_dotenv
import dashscope

# AgentScope Runtime imports
from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.deployers import LocalDeployManager
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import (
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.services.memory_service import (
    InMemoryMemoryService,
)

# Local imports
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure DashScope base URL for international region if not set
# Force DashScope URLs to use the OpenAI-compatible endpoint
os.environ["DASHSCOPE_BASE_URL"] = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

def local_deploy():
    """Entry point for local deployment."""
    asyncio.run(_local_deploy())

async def _local_deploy():
    """
    Deploy the RAG agent using AgentScope Runtime.
    
    This function:
    1. Creates the RAG agent with knowledge retrieval capabilities
    2. Sets up AgentScope Runtime services (context, memory, environment)
    3. Deploys the agent as a streaming service
    4. Runs the service until interrupted
    """
    # --- Configuration ---
    server_port = int(os.environ.get("SERVER_PORT", "8080"))
    server_endpoint = os.environ.get("SERVER_ENDPOINT", "agent")
    server_host = os.environ.get("SERVER_HOST", "localhost")
    agent_type = os.environ.get("AGENT_TYPE", "agentscope")  # 'agentscope' or 'llm'
    
    logger.info(f"Starting RAG Agent Server with configuration:")
    logger.info(f"  Host: {server_host}")
    logger.info(f"  Port: {server_port}")
    logger.info(f"  Endpoint: /{server_endpoint}")
    logger.info(f"  Agent Type: {agent_type}")
    
    try:
        # --- Create minimal LLM Agent (no sandbox/tools) ---
        logger.info(f"Creating minimal LLM agent...")
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            logger.warning("No DASHSCOPE_API_KEY found. Agent will use mock responses.")

        model_name = os.getenv("DASHSCOPE_MODEL", "qwen-turbo")
        sys_prompt = (
            "You are an AI Assistant. When provided with a section called 'Retrieved context' you must use it to answer. "
            "If the retrieved context is empty or irrelevant, clearly state that no relevant knowledge base data was found "
            "and answer based on your general knowledge. Be concise and factual. Do not fabricate sources."
        )
        rag_agent = LLMAgent(
            model=QwenLLM(model_name=model_name, api_key=api_key),
            name="RAG_LLM_Agent",
            description="LLM agent with RAG prompt (context injected upstream)",
            sys_prompt=sys_prompt,
        )
        logger.info("Minimal LLM agent created successfully")
        
        # --- Set up AgentScope Runtime Services ---
        logger.info("Setting up AgentScope Runtime services...")
        
        # Session history service for conversation management
        session_history_service = InMemorySessionHistoryService()
        
        # Memory service for agent memory
        memory_service = InMemoryMemoryService()
        await memory_service.start()
        
        # Context manager to coordinate services
        context_manager = ContextManager(
            memory_service=memory_service,
            session_history_service=session_history_service,
        )
        
        logger.info("AgentScope Runtime services initialized")
        
        # --- Create Runner ---
        logger.info("Creating AgentScope Runtime runner...")
        runner = Runner(
            agent=rag_agent,
            context_manager=context_manager,
        )
        
        # --- Deploy Agent Service ---
        logger.info("Deploying RAG agent service...")
        deploy_manager = LocalDeployManager(
            host=server_host, 
            port=server_port
        )
        
        try:
            deployment_info = await runner.deploy(
                deploy_manager,
                endpoint_path=f"/{server_endpoint}",
                stream=True,  # Enable streaming responses
            )
            
            logger.info("✅ RAG Agent Service deployed successfully!")
            logger.info(f"   🔗 Service URL: {deployment_info['url']}")
            logger.info(f"   📡 Agent Endpoint: {deployment_info['url']}/{server_endpoint}")
            logger.info(f"   🤖 Agent Type: {agent_type.upper()}")
            logger.info(f"   📄 Features: RAG, Knowledge Retrieval, Tool Usage, Notion Export")
            logger.info("")
            logger.info("🎆 RAG Agent Service is running! Press Ctrl+C to stop.")
            logger.info("")
            
            # Keep the service running
            while True:
                await asyncio.sleep(1)
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            # Graceful shutdown
            logger.info("\n🚨 Shutdown signal received. Stopping the RAG Agent Service...")
            
            if deploy_manager.is_running:
                await deploy_manager.stop()
                
            # Cleanup services
            if memory_service:
                await memory_service.stop()
                
            logger.info("✅ RAG Agent Service stopped gracefully.")
            
        except Exception as e:
            logger.error(f"❌ Error during deployment: {e}", exc_info=True)
            
            # Cleanup on error
            if deploy_manager and deploy_manager.is_running:
                await deploy_manager.stop()
            if memory_service:
                await memory_service.stop()
                
            raise
            
    except Exception as e:
        logger.error(f"❌ Failed to start RAG Agent Server: {e}", exc_info=True)
        raise

async def test_agent_locally():
    """
    Test the RAG agent locally without deployment.
    
    This function can be used for testing the agent functionality
    without starting the full service.
    """
    logger.info("Testing RAG agent locally...")
    
    try:
        # Create agent
        api_key = os.getenv("DASHSCOPE_API_KEY")
        rag_agent = create_rag_agent(agent_type="agentscope", api_key=api_key)
        
        # Set up minimal services
        session_history_service = InMemorySessionHistoryService()
        memory_service = InMemoryMemoryService()
        await memory_service.start()
        
        context_manager = ContextManager(
            memory_service=memory_service,
            session_history_service=session_history_service,
        )
        
        runner = Runner(
            agent=rag_agent,
            context_manager=context_manager,
        )
        
        # Test query
        from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
        
        test_request = AgentRequest(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello! Can you tell me about your capabilities?",
                        },
                    ],
                },
            ],
            session_id="test_session",
        )
        
        logger.info("Sending test query to agent...")
        response_parts = []
        async for message in runner.stream_query(
            user_id="test_user",
            request=test_request,
        ):
            if hasattr(message, 'content'):
                response_parts.append(message.content)
                print(message.content, end="", flush=True)
        
        logger.info(f"\nTest completed. Response length: {len(''.join(response_parts))} characters")
        
        # Cleanup
        await memory_service.stop()
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise

def main():
    """
    Main entry point.
    
    Supports both deployment and testing modes.
    """
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test mode
        asyncio.run(test_agent_locally())
    else:
        # Deployment mode
        local_deploy()

if __name__ == "__main__":
    main()
