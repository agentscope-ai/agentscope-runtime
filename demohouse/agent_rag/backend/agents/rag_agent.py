# agents/rag_agent.py
"""Minimal RAG Agent using AgentScope-runtime without sandbox/tools.

This version avoids importing sandbox modules (and their optional deps)
by using a plain LLM agent with a RAG-oriented system prompt. Retrieval
augmentation is handled upstream in the web layer by injecting context
when calling the agent service.
"""

import os
import logging
from typing import Optional

# Configure DashScope base URL for international region
import dashscope
dashscope.base_http_api_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/api/v1")

# AgentScope Runtime imports
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM

logger = logging.getLogger(__name__)

# No sandbox tools are used in this minimal implementation

class RAGAgent:
    """
    Custom RAG Agent that combines knowledge retrieval with conversational AI.
    
    This agent uses AgentScope's ReActAgent as the base and integrates RAG tools
    for knowledge retrieval, Notion export, and other utilities.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the RAG Agent.
        
        Args:
            api_key: DashScope API key. If None, will try to get from environment.
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            logger.warning("No DashScope API key provided. Agent will use mock responses.")
        
        # Define the system prompt for the RAG agent
        self.system_prompt = self._get_system_prompt()
        
        logger.info("RAG Agent initialized (no sandbox tools)")
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the RAG agent.
        
        Returns:
            Formatted system prompt
        """
        return """
You are an AI Assistant. When provided with a section called "Retrieved context" you must use it to answer.
If the retrieved context is empty or irrelevant, clearly state that no relevant knowledge base data was found and answer based on your general knowledge.
Be concise and factual. Do not fabricate sources.
"""
    
    def create_llm_agent(self):
        """Create a simple LLM agent (no sandbox)."""
        try:
            model_name = os.getenv("DASHSCOPE_MODEL", "qwen-max")
            llm_agent = LLMAgent(
                model=QwenLLM(
                    model_name=model_name,
                    api_key=self.api_key,
                ),
                name="RAG_LLM_Agent",
                description="LLM agent with RAG prompt (context injected upstream)",
                sys_prompt=self.system_prompt,
            )
            logger.info("LLM agent created successfully")
            return llm_agent
        except Exception as e:
            logger.error(f"Failed to create LLM agent: {str(e)}", exc_info=True)
            raise
    

# Custom wrapper to handle AgentScope Runtime bugs
def create_rag_agent_with_error_handling(agent_type: str = "llm", api_key: Optional[str] = None):
    """
    Factory function to create a RAG agent with error handling for known AgentScope Runtime bugs.
    
    Args:
        agent_type: Type of agent to create ('agentscope' or 'llm')
        api_key: DashScope API key
    
    Returns:
        Configured agent instance
    """
    try:
        rag_agent_factory = RAGAgent(api_key=api_key)
        
        if agent_type == "llm":
            return rag_agent_factory.create_llm_agent()
        else:
            raise ValueError(f"Unsupported agent type: {agent_type}. Use 'agentscope' or 'llm'.")
    except AttributeError as e:
        if "'DataContent' object has no attribute 'text'" in str(e):
            logger.warning("Known AgentScope Runtime bug encountered. Falling back to LLM agent.")
            # Try to create a simpler LLM agent as fallback
            try:
                rag_agent_factory = RAGAgent(api_key=api_key)
                return rag_agent_factory.create_llm_agent()
            except Exception as fallback_error:
                logger.error(f"Fallback agent creation also failed: {fallback_error}")
                raise
        else:
            # Re-raise if it's a different AttributeError
            raise
    except Exception as e:
        logger.error(f"Failed to create RAG agent: {str(e)}", exc_info=True)
        raise

def create_rag_agent(agent_type: str = "agentscope", api_key: Optional[str] = None):
    """
    Factory function to create a RAG agent.
    
    Args:
        agent_type: Type of agent to create ('agentscope' or 'llm')
        api_key: DashScope API key
    
    Returns:
        Configured agent instance
    """
    return create_rag_agent_with_error_handling(agent_type, api_key)

# Export the main functions
__all__ = [
    "RAGAgent",
    "create_rag_agent",
]
