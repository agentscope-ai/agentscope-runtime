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
(rag-service)=
# RAG

## Overview
This document introduces building a rag agent using Agentscope-runtime.

You can learn
1. How to build a complete RAG agent by Agenscope-runtime+LangChain+Milvus.
2. How to use Llamaindex as an alternative to LangChain.
3. How to use FAISS/Chroma/Pinecone/Weaviate as an alternative to Milvus.

Agentscope-runtime contains a lightweight service, called `RAGService`, which
1. provides the retrieval capability;
2. integrated by context manager.

It does not contain
1. the ability to process the doc;
2. the ability to index the doc;
3. the store of the knowledge base.

We suggest to use the popular framework (e.g. Langchain) and database (e.g. FAISS) to complete the task.
In most following cases, we use LangChain and Milvus.

The following of this document contains the following:
- pre-requisites: all requirements you need;
- document preparation;
- building a vectorstore index;
- building a rag_service;
- building a rag agent.
- how to use LlamaIndex.
- how to use other database.

### Pre-requisites
There are some prerequisites:
1. The key of DashScope: to access the DashScope API of Qwen model and embedding model.
The key should be set in the environment variable `DASHSCOPE_API_KEY`.
2. Install the dependencies: `pip install agentscope-runtime[langchain_rag]`. If use llamaindex, you need install `agentscope-runtime[llamaindex_rag]`.

### Document Preparation
The documents can be loaded from a variety of sources, including websites, PDFs, and other formats.
Check the API of Langchain to learn how to load documents from various sources.
Here, we load documents from a website.
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
In this code, we collect the website content by `WebBaseLoader` which supports bs4 to parse the website.
Then we split documents into chunks. The chunk size is 2000 and the chunk overlap is 200.
The `RecursiveCharacterTextSplitter`, from Langchain, is a text splitter that splits text into chunks of a given size.
The split documents are stored in the `docs` variable.

### Building a Vectorstore Index
The documents need to be indexed and stored in a vectorstore.
In Langchain, it supports many vector stores, including Milvus, Chroma, and Pinecone.
We use Milvus as the vectorstore in this example.
The embedding model is used to embed the documents and store them in the vectorstore.
Langchain also supports many embedding models, including OpenAI, HuggingFace, and DashScope.
We use `DashScopeEmbeddings` as the embedding model.

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
In this code, we initialize a Milvus vectorstore by its `from_documents`.
The connection args is the path to the Milvus database.
For more details, please refer to the [Milvus documentation](https://milvus.io/docs/).
Here we use a local database file (`milvus_demo.db`).

### Building a Rag Service

The `RAGService` is a basic class to provide retrieval augmented generation (RAG) capabilities.
When asked by an end-user, the agent may need to retrieve relevant information from the knowledge base.
The knowledge base can be a database or a collection of documents.
The `RAGService` contains the following methods:
- `retrieve`: retrieve relevant information from the knowledge base.

The `LangChainRAGService` is a concrete implementation of `RAGService` that uses LangChain to retrieve relevant information.
It can be initialized by:
- `vectorstore` the vectorstore to be indexed. Specifically, it can be a `VectorStore` instance of LangChain.
- `embedding` the embedding model to be used for indexing.


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
In this code, we initialize a `LangChainRAGService` by its `vectorstore` and `embedding`.
We can use the rag_service directly. It can be used to retrieve relevant information from the knowledge base. The results are returned as a list of documents.
```python
ret_docs = await rag_service.retrieve(
    "What is self-reflection of an AI Agent?",
)
```


### Building a Rag Agent

In Agentscope-runtime, rag_service is integrated in the `context_manager`.
It composes all data from memory, session and rag into context.


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
In this code we introduce a simple agent and build a runner with the help of `context_manager`.

### How To Use LlamaIndex.
LlamaIndex is a powerful toolkit for building large language model applications. It provides a variety of tools for building and querying indexes, including vector stores, text splitters, and query engines.
In Agentscope-runtime, we provide a `LlamaIndexRAGService` to integrate LlamaIndex into Agentscope-runtime. To use it, you need install `agentscope-runtime[llamaindex_rag]`. Here is a full example:
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

# Load documents from web pages
loader = SimpleWebPageReader()
documents = loader.load_data(
    urls=[
        "https://lilianweng.github.io/posts/2023-06-23-agent/",
        "https://lilianweng.github.io/posts/2023-03-15-prompt-"
        "engineering/",
    ],
)

# Split documents into nodes
splitter = SentenceSplitter(chunk_size=2000, chunk_overlap=200)
nodes = splitter.get_nodes_from_documents(documents)

# Convert nodes to documents
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

### How To Use Other Database.
Several vector databases are supported in Agentscope-runtime.
1. FAISS.
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

5. Tablestore
```python
from agentscope_runtime.engine.services.tablestore_rag_service import TablestoreRAGService
from agentscope_runtime.engine.services.utils.tablestore_service_utils import create_tablestore_client

tablestore_rag_service = TablestoreRAGService(
    tablestore_client=create_tablestore_client(
        end_point="your_endpoint",
        instance_name="your_instance_name",
        access_key_id="your_access_key_id",
        access_key_secret="your_access_key_secret",
    ),
)

await tablestore_rag_service.add_docs(docs)
```