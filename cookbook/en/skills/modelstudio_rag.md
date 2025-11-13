# Retrieval-Augmented Generation Components (RAGs)

This directory contains RAG (Retrieval-Augmented Generation) related components, providing knowledge base retrieval and enhanced generation capabilities.

## 📋 Component List

### 1. ModelstudioRag - DashScope RAG Component
Core retrieval-augmented generation service that can retrieve user knowledge base information from the DashScope platform and provide intelligent answers.

**Prerequisites:**
- Valid DashScope API key
- Configured DashScope HTTP base URL
- User has created knowledge base on DashScope platform
- Knowledge base contains relevant document content

**Input Parameters (RagInput):**
- `messages` (List): Conversation message list
- `rag_options` (Dict): RAG option configurations
  - `knowledge_base_id`: Knowledge base ID
  - `top_k`: Number of retrieval entries
  - `score_threshold`: Similarity threshold
  - `enable_citation`: Whether to enable citations
- `rest_token` (str): Authentication token
- `image_urls` (List[str], optional): Image URL list (multimodal support)
- `workspace_id` (str, optional): Workspace ID

**Output Parameters (RagOutput):**
- `raw_result` (str): Raw retrieval result
- `rag_result` (Dict): Structured RAG result
  - `answer`: Generated answer
  - `references`: Related document references
  - `confidence`: Confidence score
- `messages` (List): Processed message list

**Core Features:**
- **Intelligent Retrieval**: Document retrieval based on semantic similarity
- **Context Fusion**: Fuses retrieval content with conversation context
- **Answer Generation**: Generates accurate answers based on retrieval content
- **Citation Support**: Provides document references for answer sources
- **Multimodal Support**: Supports mixed text and image retrieval

### 2. ModelstudioRagLite - DashScope RAG Lite Version
Provides lightweight RAG functionality, suitable for resource-constrained or fast-response scenarios.

**Prerequisites:**
- Basic DashScope service configuration
- Smaller scale knowledge base

**Key Features:**
- Faster response speed
- Lower resource consumption
- Simplified configuration options
- Suitable for mobile or edge computing

## 🔧 Environment Variable Configuration

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope API key |
| `DASHSCOPE_HTTP_BASE_URL` | ✅ | - | DashScope service HTTP base URL |
| `DEFAULT_KNOWLEDGE_BASE_ID` | ❌ | - | Default knowledge base ID |
| `DEFAULT_TOP_K` | ❌ | 5 | Default number of retrieval entries |
| `DEFAULT_SCORE_THRESHOLD` | ❌ | 0.7 | Default similarity threshold |

## 🚀 Usage Examples

### Basic RAG Query Example

```python
from agentscope_runtime.common.skills.RAGs.modelstudio_rag import ModelstudioRag
import asyncio

# Initialize RAG component
rag = ModelstudioRag()


async def rag_query_example():
    result = await rag.arun({
        "messages": [
            {"role": "user", "content": "Please introduce the history of artificial intelligence development"}
        ],
        "rag_options": {
            "knowledge_base_id": "kb_12345",
            "top_k": 3,
            "score_threshold": 0.8,
            "enable_citation": True
        },
        "rest_token": "your_auth_token"
    })

    print("RAG answer:", result.rag_result["answer"])
    print("References:", result.rag_result["references"])


asyncio.run(rag_query_example())
```

### Multi-turn Conversation RAG Example
```python
async def multi_turn_rag_example():
    conversation_history = [
        {"role": "user", "content": "What is machine learning?"},
        {"role": "assistant", "content": "Machine learning is an important branch of artificial intelligence..."},
        {"role": "user", "content": "What are its main types?"}
    ]

    result = await rag.arun({
        "messages": conversation_history,
        "rag_options": {
            "knowledge_base_id": "kb_ai_encyclopedia",
            "top_k": 5,
            "enable_citation": True
        },
        "rest_token": "your_auth_token"
    })

    print("Context-based answer:", result.rag_result["answer"])

asyncio.run(multi_turn_rag_example())
```

### Multimodal RAG Example
```python
async def multimodal_rag_example():
    result = await rag.arun({
        "messages": [
            {"role": "user", "content": "Please analyze the technical architecture in this image"}
        ],
        "image_urls": [
            "https://example.com/architecture_diagram.png"
        ],
        "rag_options": {
            "knowledge_base_id": "kb_tech_docs",
            "top_k": 3,
            "enable_citation": True
        },
        "rest_token": "your_auth_token"
    })

    print("Multimodal analysis result:", result.rag_result["answer"])

asyncio.run(multimodal_rag_example())
```

## 🏗️ RAG Architecture Features

### Retrieval Strategies
- **Dense Retrieval**: Semantic retrieval based on vector similarity
- **Sparse Retrieval**: Exact retrieval based on keyword matching
- **Hybrid Retrieval**: Combines advantages of dense and sparse retrieval
- **Re-ranking**: Re-ranks retrieval results by relevance

### Generation Strategies
- **Context Injection**: Injects retrieval content into generation model
- **Answer Synthesis**: Synthesizes answers from multiple document fragments
- **Citation Generation**: Automatically generates document citations for answers
- **Fact Verification**: Performs factual checking on generated answers

## 📊 Performance Optimization

### Retrieval Optimization
- Use vector indexing to accelerate retrieval (e.g., FAISS, Milvus)
- Implement retrieval result caching
- Optimize document chunking and embedding strategies
- Parallel processing of multiple retrieval requests

### Generation Optimization
- Set reasonable context length limits
- Use streaming generation to improve user experience
- Implement answer quality scoring mechanisms
- Optimize model inference parameters

## 📦 Dependencies
- `aiohttp`: Async HTTP client
- `dashscope`: DashScope SDK
- `asyncio`: Async programming support
- `numpy`: Numerical computation (vector operations)
- `faiss`: Vector retrieval (optional)

## ⚠️ Usage Considerations

### Knowledge Base Management
- Regularly update knowledge base content to ensure information timeliness
- Design reasonable document chunking strategies, balancing retrieval precision and recall
- Monitor knowledge base query performance and hit rates
- Establish knowledge base version management mechanisms

### Query Optimization
- Set appropriate similarity thresholds to avoid retrieving irrelevant content
- Reasonably configure top_k parameters, balancing answer quality and response speed
- Preprocess and optimize long queries
- Implement query intent analysis and routing

### Answer Quality Control
- Establish answer quality assessment mechanisms
- Perform factual checking on generated answers
- Handle cases with insufficient retrieval results
- Provide answer confidence scoring

## 🔗 Related Components
- Can be combined with search components to expand knowledge sources
- Supports integration with memory components to provide personalized RAG experience
- Can work with intent recognition components for intelligent knowledge Q&A
- Supports integration with plugin systems to extend RAG functionality scope
