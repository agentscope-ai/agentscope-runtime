# Search Components

This directory contains various search service components that provide intelligent search, information retrieval, and content discovery capabilities.

## 📋 Component List

### 1. ModelstudioSearch - DashScope Search Component
Core intelligent search service that supports multiple search strategies and information sources.

**Prerequisites:**
- Valid DashScope API key, **This component is currently in beta testing phase, please contact developers and provide DASHSCOPE_API_KEY**
- Configured search service strategy
- Stable network connection

**Input Parameters (SearchInput):**
- `messages` (List): Search-related conversation messages
- `search_options` (Dict): Search option configurations
  - `search_strategy`: Search strategy (web, news, academic, etc.)
  - `max_results`: Maximum number of search results
  - `time_range`: Time range limitation
  - `language`: Search language
  - `region`: Geographic region limitation
- `search_output_rules` (Dict): Output format rules
- `search_timeout` (int): Search timeout duration
- `type` (str): Search type

**Output Parameters (SearchOutput):**
- `search_result` (str): Search result summary
- `search_info` (Dict): Detailed search information
  - `sources`: List of information sources
  - `relevance_score`: Relevance scoring
  - `search_time`: Search duration
  - `result_count`: Number of results

**Core Features:**
- **Intelligent Search**: Semantic understanding-based intelligent search
- **Multi-source Integration**: Integrates search results from multiple information sources
- **Real-time Search**: Retrieves latest real-time information
- **Result Filtering**: Filters results based on relevance and quality
- **Search Optimization**: Automatically optimizes search queries and strategies

### 2. ModelstudioSearchLite - DashScope Search Lite Version
Provides lightweight search functionality, suitable for quick queries and resource-constrained scenarios.

**Prerequisites:**
- Visit [DashScope Search](https://bailian.console.aliyun.com/?tab=mcp#/mcp-market/detail/WebSearch) to enable the service
- Low network latency requirements

**Key Features:**
- Faster response speed
- Lower resource consumption
- Simplified search options
- Suitable for mobile applications

## 🔧 Environment Variable Configuration

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope API key |
| `SEARCH_DEFAULT_STRATEGY` | ❌ | web | Default search strategy |
| `SEARCH_MAX_RESULTS` | ❌ | 10 | Default maximum search results |
| `SEARCH_TIMEOUT` | ❌ | 30 | Search timeout (seconds) |
| `SEARCH_ENABLE_CACHE` | ❌ | true | Enable search cache |
| `SEARCH_REGION` | ❌ | global | Default search region |

## 🚀 Usage Examples

### Basic Search Example

```python
from agentscope_runtime.tools.searches import ModelstudioSearch
import asyncio

# Initialize search component
search = ModelstudioSearch()


async def basic_search_example():
    result = await search.arun({
        "messages": [
            {"role": "user", "content": "Latest artificial intelligence development trends"}
        ],
        "search_options": {
            "search_strategy": "news",
            "max_results": 5,
            "time_range": "last_month",
            "language": "en-US"
        },
        "search_timeout": 20
    })

    print("Search result summary:", result.search_result)
    print("Information sources:", result.search_info["sources"])


asyncio.run(basic_search_example())
```

### Multi-strategy Search Example
```python
async def multi_strategy_search_example():
    # Academic search
    academic_result = await search.arun({
        "messages": [
            {"role": "user", "content": "Deep learning applications in medical diagnosis"}
        ],
        "search_options": {
            "search_strategy": "academic",
            "max_results": 10,
            "language": "en"
        }
    })

    # News search
    news_result = await search.arun({
        "messages": [
            {"role": "user", "content": "Latest AI policy updates"}
        ],
        "search_options": {
            "search_strategy": "news",
            "time_range": "last_week",
            "region": "global"
        }
    })

    print("Academic search results:", academic_result.search_result)
    print("News search results:", news_result.search_result)

asyncio.run(multi_strategy_search_example())
```

### Advanced Search Configuration Example
```python
async def advanced_search_example():
    result = await search.arun({
        "messages": [
            {"role": "user", "content": "Compare performance of different machine learning algorithms"},
            {"role": "assistant", "content": "I'll search for comparative information for you"},
            {"role": "user", "content": "Focus on accuracy and efficiency"}
        ],
        "search_options": {
            "search_strategy": "comprehensive",
            "max_results": 15,
            "filters": {
                "content_type": ["article", "paper", "report"],
                "quality_threshold": 0.8,
                "exclude_domains": ["low-quality-site.com"]
            },
            "ranking_criteria": ["relevance", "authority", "freshness"]
        },
        "search_output_rules": {
            "include_citations": True,
            "summarize_results": True,
            "highlight_key_points": True
        }
    })

    print("Comprehensive search results:", result.search_result)
    print("Search statistics:", result.search_info)

asyncio.run(advanced_search_example())
```

## 🔍 Supported Search Strategies

### Web Search
- **General Web Search**: Searches web content across the entire internet
- **Real-time Search**: Retrieves latest published web information
- **Deep Search**: Multi-level content mining and analysis

### Professional Search
- **Academic Search**: Searches academic papers and research reports
- **News Search**: Searches news reports and current affairs
- **Technical Search**: Searches technical documentation and API references
- **Product Search**: Searches product information and user reviews

### Multimedia Search
- **Image Search**: Searches related images based on descriptions
- **Video Search**: Searches related video content
- **Document Search**: Searches PDF, Word and other documents

## 🏗️ Search Architecture

### Query Processing
1. **Query Understanding**: Analyzes user query intent and key information
2. **Query Expansion**: Adds synonyms and related vocabulary
3. **Query Optimization**: Optimizes search queries to improve accuracy
4. **Multi-strategy Routing**: Selects optimal search strategy based on query type

### Result Processing
1. **Result Aggregation**: Integrates results from multiple search sources
2. **Deduplication**: Removes duplicate and similar results
3. **Quality Assessment**: Evaluates result quality and credibility
4. **Relevance Ranking**: Ranks results by relevance
5. **Content Summarization**: Generates result summaries and key points

### Caching Mechanism
- **Query Cache**: Caches results for common queries
- **Result Cache**: Caches high-quality search results
- **Smart Updates**: Automatically updates cache based on content timeliness

## 📊 Search Optimization

### Performance Optimization
- **Parallel Search**: Simultaneously queries multiple information sources
- **Result Prefetching**: Prefetches potentially relevant search results
- **Smart Caching**: Intelligent caching strategy based on user behavior
- **Load Balancing**: Distributes search requests to different service nodes

### Quality Control
- **Source Credibility Assessment**: Evaluates information source credibility
- **Content Quality Check**: Checks content accuracy and completeness
- **Timeliness Verification**: Verifies information timeliness
- **Bias Detection**: Detects and flags potentially biased content

## 📦 Dependencies
- `aiohttp`: Async HTTP client
- `dashscope`: DashScope SDK
- `beautifulsoup4`: HTML parsing
- `lxml`: XML/HTML processing
- `nltk`: Natural language processing (optional)
- `elasticsearch`: Search engine (optional)

## ⚠️ Usage Considerations

### Search Strategy Selection
- Choose appropriate search strategy based on query type
- Consider timeliness requirements of results
- Balance search depth and response speed
- Adjust search parameters based on user scenarios

### Result Quality Management
- Set appropriate relevance thresholds
- Verify accuracy of search results
- Handle cases with insufficient search results
- Establish user feedback mechanism to improve search quality

### API Usage Limitations
- Follow search service call frequency limits
- Set reasonable timeout durations to avoid long waits
- Implement error handling and retry mechanisms
- Monitor API usage and costs

## 🔗 Related Components
- Can be combined with RAG components to provide retrieval-augmented generation
- Supports integration with intent recognition components for intelligent search routing
- Can work with memory components to record user search history
- Supports integration with plugin systems to extend domain-specific search
