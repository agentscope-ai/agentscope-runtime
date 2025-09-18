---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---
(rag-service-zh)=
# RAG

## 概述
本文档介绍了如何使用Agentscope-runtime构建一个RAG代理。

你可以学习到：
1. 如何通过Agenscope-runtime+LangChain+Milvus构建一个完整的RAG代理。
2. 如何使用Llamaindex作为LangChain的替代方案。
3. 如何使用FAISS/Chroma/Pinecone/Weaviate作为Milvus的替代方案。

Agentscope-runtime包含一个轻量级的服务，称为`RAGService`，它
1. 提供检索功能；
2. 通过上下文管理器集成。

它不包含以下功能：
1. 处理文档的能力；
2. 索引文档的能力；
3. 知识库的存储。

我们建议使用流行的框架（例如Langchain）和数据库（例如FAISS）来完成任务。在大多数情况下，我们将使用LangChain和Milvus。

本文档的其余部分包含以下内容：
- 前提条件：所需的所有要求；
- 文档准备；
- 构建向量存储索引；
- 构建RAGService；
- 构建RAG代理。
- 如何使用LlamaIndex。
- 如何使用其他数据库。

### 前提条件
有一些前提条件：
1. DashScope的密钥：用于访问Qwen模型和嵌入模型的DashScope API。该密钥应设置在环境变量`DASHSCOPE_API_KEY`中。
2. 安装依赖项：`pip install agentscope-runtime[langchain_rag]`。如果使用Llamaindex，则需要安装`agentscope-runtime[llamaindex_rag]`。

### 文档准备
文档可以从多种来源加载，包括网站、PDF和其他格式。请参阅Langchain的API以了解如何从各种来源加载文档。这里，我们从网站加载文档。
```python
import bs4
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

loader = WebBaseLoader(
    web_paths=(
        "https://lilianweng.github.io/posts/2023-06-23-agent/",
        "https://lilianweng.github.io/posts/2023-03-15-prompt"
        "-engineering/",
    ),
    bs_kwargs={
        "parse_only": bs4.SoupStrainer(
            class_=("post-content", "post-title", "post-header"),
        ),
    },
)
documents = loader.load()
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=200,
)

docs = text_splitter.split_documents(documents)
```
在这段代码中，我们使用支持bs4解析网站的`WebBaseLoader`收集网站内容。然后我们将文档分割成块，块大小为2000，重叠为200。`RecursiveCharacterTextSplitter`是Langchain中的文本分割器，可以将文本分割成指定大小的块。分割后的文档存储在`docs`变量中。

### 构建向量存储索引
文档需要被索引并存储在向量存储中。在Langchain中，它支持许多向量存储，包括Milvus、Chroma和Pinecone。在这个例子中，我们使用Milvus作为向量存储。嵌入模型用于嵌入文档并将它们存储在向量存储中。Langchain还支持许多嵌入模型，包括OpenAI、HuggingFace和DashScope。我们使用`DashScopeEmbeddings`作为嵌入模型。

```python
from langchain_milvus import Milvus
from langchain_community.embeddings import DashScopeEmbeddings
vectorstore=Milvus.from_documents(
    documents=docs,
    embedding=DashScopeEmbeddings(),
    connection_args={
        "uri": "milvus_demo.db",
    },
),
```
在这段代码中，我们通过其`from_documents`初始化了一个Milvus向量存储。连接参数是Milvus数据库的路径。更多详细信息，请参阅[Milvus文档](https://milvus.io/docs/)。这里我们使用一个本地数据库文件（`milvus_demo.db`）。

### 构建RAGService

`RAGService`是一个提供检索增强生成（RAG）能力的基本类。当终端用户询问时，代理可能需要从知识库中检索相关信息。知识库可以是数据库或文档集合。`RAGService`包含以下方法：
- `retrieve`：从知识库中检索相关信息。

`LangChainRAGService`是`RAGService`的一个具体实现，它使用LangChain来检索相关信息。可以通过以下方式初始化：
- `vectorstore` 要索引的向量存储。特别是，它可以是LangChain的`VectorStore`实例。
- `embedding` 用于索引的嵌入模型。

```python
from langchain_milvus import Milvus
from langchain_community.embeddings import DashScopeEmbeddings
from agentscope_runtime.engine.services.rag_service import LangChainRAGService

# langchain+Milvus
rag_service = LangChainRAGService(
    vectorstore=vectorstore,
    embedding=DashScopeEmbeddings()
)
```
在这段代码中，我们通过其`vectorstore`和`embedding`初始化了一个`LangChainRAGService`。我们可以直接使用`rag_service`。它可以用来从知识库中检索相关信息。结果以文档列表的形式返回。
```python
ret_docs = await rag_service.retrieve(
    "What is self-reflection of an AI Agent?",
)
```

### 构建RAG代理

在Agentscope-runtime中，`rag_service`集成在`context_manager`中。它组合了来自内存、会话和rag的所有数据到上下文中。

```python
from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM
from agentscope_runtime.engine.schemas.agent_schemas import (
    MessageType,
    AgentRequest,
    RunStatus,
)
from agentscope_runtime.engine.services.context_manager import (
    create_context_manager,
)
USER_ID = "user1"
SESSION_ID = "session1"
query = "What is self-reflection of an AI Agent?"

llm_agent = LLMAgent(
    model=QwenLLM(),
    name="llm_agent",
    description="A simple LLM agent",
)

async with create_context_manager(
    rag_service=rag_service,
) as context_manager:
    runner = Runner(
        agent=llm_agent,
        context_manager=context_manager,
        environment_manager=None,
    )

    all_result = ""
    request = AgentRequest(
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": query,
                    },
                ],
            },
        ],
        session_id=SESSION_ID,
    )

    async for message in runner.stream_query(
        user_id=USER_ID,
        request=request,
    ):
        if (
            message.object == "message"
            and MessageType.MESSAGE == message.type
            and RunStatus.Completed == message.status
        ):
            all_result = message.content[0].text
    print(all_result)
```
在这段代码中，我们引入了一个简单的代理，并借助`context_manager`构建了一个运行器。

### 如何使用LlamaIndex
LlamaIndex是一个强大的工具包，用于构建大型语言模型应用程序。它提供了多种工具来构建和查询索引，包括向量存储、文本分割器和查询引擎。在Agentscope-runtime中，我们提供了一个`LlamaIndexRAGService`来将LlamaIndex集成到Agentscope-runtime中。要使用它，你需要安装`agentscope-runtime[llamaindex_rag]`。这是一个完整的示例：
```python
from llama_index.core.schema import Document
from llama_index.readers.web import SimpleWebPageReader
from llama_index.core.node_parser import SentenceSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.core import Settings

from agentscope_runtime.engine.services.rag_service import   LlamaIndexRAGService

# llamaindex+Milvus

# 从网页加载文档
loader = SimpleWebPageReader()
documents = loader.load_data(
    urls=[
        "https://lilianweng.github.io/posts/2023-06-23-agent/",
        "https://lilianweng.github.io/posts/2023-03-15-prompt-"
        "engineering/",
    ],
)

# 将文档分割成节点
splitter = SentenceSplitter(chunk_size=2000, chunk_overlap=200)
nodes = splitter.get_nodes_from_documents(documents)

# 将节点转换为文档
docs = [Document(text=node.text) for node in nodes]


Settings.embed_model = DashScopeEmbeddings()
vector_store = MilvusVectorStore(
    uri="milvus_llamaindex_demo.db",
    dim=1536,
)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_documents(
    documents=docs,
    storage_context=storage_context,
)
rag_service = LlamaIndexRAGService(
    vectorstore=index,
    embedding=DashScopeEmbeddings(),
)

ret_docs = await rag_service.retrieve(
    "What is self-reflection of an AI Agent?",
)
```

### 如何使用其他数据库
Agentscope-runtime支持几种向量数据库。
1. FAISS
```python
from langchain.vectorstores import FAISS
from langchain.embeddings import DashScopeEmbeddings
vectorstore = FAISS.from_documents(docs, DashScopeEmbeddings())
```
2. Chroma
```python
from langchain.vectorstores import Chroma
from langchain.embeddings import DashScopeEmbeddings
vectorstore = Chroma.from_documents(docs, DashScopeEmbeddings())
```
3. Weaviate
```python
import weaviate
from langchain.vectorstores import Weaviate
from langchain.embeddings import DashScopeEmbeddings

client = weaviate.Client("http://localhost:8080")  # URI
class_name = "YourClassName"
if not client.schema.exists(class_name):
    class_obj = {
        "class": class_name,
        "vectorizer": "none"
    }
    client.schema.create_class(class_obj)
vectorstore = Weaviate.from_documents(docs, DashScopeEmbeddings(), client, class_name)
```
4. Pinecone
```python
import pinecone
from langchain.vectorstores import Pinecone
from langchain.embeddings import DashScopeEmbeddings

pinecone.init(api_key="YOUR_PINECONE_API_KEY", environment="YOUR_PINECONE_ENVIRONMENT")

index_name = "your-index-name"
if index_name not in pinecone.list_indexes():
    pinecone.create_index(index_name, dimension=768)

index = pinecone.Index(index_name)

vectorstore = Pinecone.from_documents(docs, DashScopeEmbeddings(), index_name=index_name)
```