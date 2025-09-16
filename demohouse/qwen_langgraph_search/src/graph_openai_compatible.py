# -*- coding: utf-8 -*-
import asyncio
import json
import os
import time
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END
from langgraph.graph import StateGraph
from langgraph.types import Send


from configuration import Configuration
from custom_search_tool import CustomSearchTool
from llm_prompts import (
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
)
from llm_utils import call_dashscope, extract_json_from_qwen
from state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from utils import (
    get_research_topic,
    insert_citation_markers,
    custom_resolve_urls,
    custom_get_citations,
    get_current_date,
)

from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent
from agentscope_runtime.engine.helpers.helper import simple_call_agent_direct

load_dotenv("../.env")

if os.getenv("DASHSCOPE_API_KEY") is None:
    raise ValueError("DASHSCOPE_API_KEY is not set")


def format_search_results(search_results: List[Dict[str, Any]]) -> str:
    """
    Convert the search results
    :param search_results:
    :return:
    """

    formatted_results = []

    for i, result in enumerate(search_results, 1):
        formatted_result = f"""
Result Number {i}:
Title: {result.get('title', 'N/A')}
Label: {result.get('site_name', 'N/A')}
URL: {result.get('url', 'N/A')}
Snippet: {result.get('snippet', 'N/A')}
publish_date: {result.get('publish_date', 'N/A')}
---
"""
        formatted_results.append(formatted_result)

    return "\n".join(formatted_results)


class WebSearchGraph:
    def __init__(
        self,
        config: RunnableConfig,
        call_llm_func,
        search_tool: CustomSearchTool,
    ):
        self.configurable = Configuration.from_runnable_config(config)
        self.call_llm_func = call_llm_func
        self.search_tool = search_tool
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.max_retries = 3
        self.retry_delay = 2
        self.current_date = get_current_date()

    def get_chat_completion(self, **args):
        completion = self.call_llm_func(**args)
        self.input_tokens += completion.usage.prompt_tokens
        self.output_tokens += completion.usage.completion_tokens
        self.total_tokens += completion.usage.total_tokens
        return completion.choices[0].message.content

    def generate_query(self, state: OverallState) -> QueryGenerationState:
        """LangGraph node that generates search queries
        based on the User's question.

        Uses QWen Max to create optimized search queries
         for web research based on the User's question.

        Args:
            state: Current graph state containing the User's question
            config: Configuration for the runnable,
             including LLM provider settings

        Returns:
            Dictionary with state update,
             including search_query key containing the
            generated queries
        """
        # check for custom initial search query count
        if state.get("initial_search_query_count") is None:
            state[
                "initial_search_query_count"
            ] = self.configurable.num_of_init_q

        # Format the prompt
        formatted_prompt = query_writer_instructions.format(
            current_date=self.current_date,
            research_topic=get_research_topic(state["messages"]),
            number_queries=state["initial_search_query_count"],
        )
        param = {
            "model": self.configurable.query_generator_model,
            "messages": [{"role": "user", "content": formatted_prompt}],
            **self.configurable.query_generator_param,
        }
        for attempt in range(self.max_retries):
            try:
                result = self.get_chat_completion(**param)
                result = extract_json_from_qwen(result)
                result = json.loads(result)
                query = result.get("query")
                if isinstance(query, str):
                    query = [query]
                assert isinstance(query, list)
                break
            except Exception as e:
                print(
                    f"Error occurred when generating search query (attempt"
                    f" {attempt + 1}/{self.max_retries}): {e}.",
                )
                if attempt == self.max_retries - 1:  # Last attempt failed
                    query = [get_research_topic(state["messages"])]
                    break
                time.sleep(self.retry_delay)
        return {"search_query": query}

    def continue_to_web_research(self, state: QueryGenerationState):
        """LangGraph node that sends the
         search queries to the web research node.

        This is used to spawn n number
        of web research nodes, one for each search query.
        """
        return [
            Send(
                "web_research",
                {"search_query": search_query, "id": str(idx)},
            )
            for idx, search_query in enumerate(state["search_query"])
        ]

    def web_research(self, state: WebSearchState):
        """LangGraph node that performs web research using the native Google
         Search API tool.

        Executes a web search using the native Google Search API tool in
        combination with Gemini 2.0 Flash.

        Args:
            state: Current graph state containing the
             search query and research loop count
            config: Configuration for the runnable,
            including search API settings

        Returns:
            Dictionary with state update,
            including sources_gathered, research_loop_count,
             and web_research_results
        """

        search_results = self.search_tool.search(
            state["search_query"],
        )

        search_context = format_search_results(search_results)

        formatted_prompt = (
            web_searcher_instructions.format(
                current_date=self.current_date,
                research_topic=state["search_query"],
            )
            + f"\n\nSearch Result:\n{search_context}"
        )

        param = {
            "model": self.configurable.query_generator_model,
            "messages": [{"role": "user", "content": formatted_prompt}],
            **self.configurable.query_generator_param,
        }

        sources_gathered = []
        for result in search_results:
            url = result.get("url")
            if url:
                sources_gathered.append(
                    {
                        "label": result.get("site_name"),
                        "short_url": url,
                        "value": url,
                    },
                )

        for attempt in range(self.max_retries):
            try:
                result = self.get_chat_completion(**param)
                resolved_urls = custom_resolve_urls(
                    search_results,
                    state["id"],
                )
                citations = custom_get_citations(search_results, resolved_urls)

                modified_text = insert_citation_markers(result, citations)
                return {
                    "sources_gathered": sources_gathered,
                    "search_query": [state["search_query"]],
                    "web_research_result": [modified_text],
                }
            except Exception as e:
                print(
                    f"Error occurred when web search query: "
                    f"`{state['search_query']}` "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}.",
                )

                summary = (
                    f"{len(search_results)} related results are found "
                    f"about search query '{state['search_query']}'"
                )
                if attempt == self.max_retries - 1:
                    return {
                        "sources_gathered": sources_gathered,
                        "search_query": [state["search_query"]],
                        "web_research_result": [summary],
                    }
                time.sleep(self.retry_delay)
        return None

    def reflection(self, state: OverallState) -> Optional[ReflectionState]:
        """LangGraph node that identifies knowledge gaps and generates
        potential follow-up queries.

        Analyzes the current summary to identify areas for further
        research and generates
        potential follow-up queries. Uses structured output to extract
        the follow-up query in JSON format.

        Args:
            state: Current graph state containing the running summary
            and research topic
            config: Configuration for the runnable, including LLM
            provider settings

        Returns:
            Dictionary with state update, including search_query key
            containing the generated follow-up query
        """
        state["research_loop_count"] = state.get("research_loop_count", 0) + 1
        reasoning_model = self.configurable.reflection_model

        # Format the prompt
        formatted_prompt = reflection_instructions.format(
            current_date=self.current_date,
            research_topic=get_research_topic(state["messages"]),
            summaries="\n\n---\n\n".join(state["web_research_result"]),
        )
        param = {
            "model": reasoning_model,
            "messages": [{"role": "user", "content": formatted_prompt}],
            **self.configurable.reflection_param,
        }
        for attempt in range(self.max_retries):
            try:
                result = self.get_chat_completion(**param)
                result = extract_json_from_qwen(result)
                result = json.loads(result)
                is_sufficient = result.get("is_sufficient", True)
                knowledge_gap = result.get("knowledge_gap", "")
                follow_up_queries = result.get("follow_up_queries", [])
                assert isinstance(follow_up_queries, list)
                return {
                    "is_sufficient": is_sufficient,
                    "knowledge_gap": knowledge_gap,
                    "follow_up_queries": follow_up_queries,
                    "research_loop_count": state["research_loop_count"],
                    "number_of_ran_queries": len(state["search_query"]),
                }
            except Exception as e:
                print(
                    f"Error occurred when reflection (attempt {attempt + 1}"
                    f"/{self.max_retries}): {e}.",
                )
                if attempt == self.max_retries - 1:  # Last attempt failed
                    return {
                        "is_sufficient": True,
                        "knowledge_gap": "",
                        "follow_up_queries": [],
                        "research_loop_count": state["research_loop_count"],
                        "number_of_ran_queries": len(state["search_query"]),
                    }
                time.sleep(self.retry_delay)
        return None

    def evaluate_research(
        self,
        state: ReflectionState,
        config: RunnableConfig,
    ):
        """LangGraph routing function that determines the next step in the
        research flow.

        Controls the research loop by deciding whether to continue gathering
         information
        or to finalize the summary based on the configured maximum number of
         research loops.

        Args:
            state: Current graph state containing the research loop count
            config: Configuration for the runnable, including
            max_research_loops setting

        Returns:
            String literal indicating the next node to visit ("web_research"
             or "finalize_summary")
        """
        configurable = Configuration.from_runnable_config(config)
        max_research_loops = (
            state.get("max_research_loops")
            if state.get("max_research_loops") is not None
            else configurable.max_research_loops
        )
        if (
            state["is_sufficient"]
            or state["research_loop_count"] >= max_research_loops
        ):
            return "finalize_answer"
        else:
            return [
                Send(
                    "web_research",
                    {
                        "search_query": follow_up_query,
                        "id": state["number_of_ran_queries"] + int(idx),
                    },
                )
                for idx, follow_up_query in enumerate(
                    state["follow_up_queries"],
                )
            ]

    def finalize_answer(self, state: OverallState):
        """LangGraph node that finalizes the research summary.

        Prepares the final output by deduplicating and formatting sources, then
        combining them with the running summary to create a well-structured
        research report with proper citations.

        Args:
            state: Current graph state containing the running summary
             and sources gathered

        Returns:
            Dictionary with state update, including running_summary
             key containing
            the formatted final summary with sources
        """
        answer_model = self.configurable.answer_model
        formatted_prompt = answer_instructions.format(
            current_date=self.current_date,
            research_topic=get_research_topic(state["messages"]),
            summaries="\n---\n\n".join(state["web_research_result"]),
        )

        param = {
            "model": answer_model,
            "messages": [{"role": "user", "content": formatted_prompt}],
            **self.configurable.answer_param,
        }
        for attempt in range(self.max_retries):
            try:
                result = self.get_chat_completion(**param)

                unique_sources = []
                for source in state["sources_gathered"]:
                    if source["short_url"] in result:
                        result = result.replace(
                            source["short_url"],
                            source["value"],
                        )
                        unique_sources.append(source)

                return {
                    "messages": [AIMessage(content=result)],
                    "sources_gathered": unique_sources,
                }
            except Exception as e:
                print(
                    f"Error occurred when generating answer (attempt "
                    f"{attempt + 1}/{self.max_retries}): {e}.",
                )
                if attempt == self.max_retries - 1:
                    return {
                        "messages": [
                            AIMessage(
                                content=f"Error occurred"
                                f" when generating answer. {e}",
                            ),
                        ],
                        "sources_gathered": [],
                    }
                time.sleep(self.retry_delay)
        return None

    async def run(self, user_question: str):
        # Create our Agent Graph
        builder = StateGraph(OverallState, config_schema=Configuration)

        # Define the nodes we will cycle between
        builder.add_node("generate_query", self.generate_query)
        builder.add_node("web_research", self.web_research)
        builder.add_node("reflection", self.reflection)
        builder.add_node("finalize_answer", self.finalize_answer)

        # Set the entrypoint as `generate_query`
        # This means that this node is the first one called
        builder.add_edge(START, "generate_query")
        # Add conditional edge to continue with search queries in a
        # parallel branch
        builder.add_conditional_edges(
            "generate_query",
            self.continue_to_web_research,
            ["web_research"],
        )
        # Reflect on the web research
        builder.add_edge("web_research", "reflection")
        # Evaluate the research
        builder.add_conditional_edges(
            "reflection",
            self.evaluate_research,
            ["web_research", "finalize_answer"],
        )
        # Finalize the answer
        builder.add_edge("finalize_answer", END)
        compiled_graph = builder.compile(name="pro-search-agent")

        def human_ai_message_to_dict(obj):
            if isinstance(obj, HumanMessage):
                return {
                    "sender": obj.type,
                    "content": obj.content,
                }
            if isinstance(obj, AIMessage):
                return {
                    "sender": obj.type,
                    "content": obj.content,
                }
            raise TypeError(
                f"Object of type {obj.__class__.__name__} is"
                f" not JSON serializable",
            )

        def state_folder(messages):
            if len(messages) > 0:
                return json.loads(messages[0]["content"])
            else:
                return []

        def state_unfolder(state):
            state_jsons = json.dumps(state, default=human_ai_message_to_dict)
            return state_jsons

        langgraph_agent = LangGraphAgent(
            compiled_graph,
            state_folder,
            state_unfolder,
        )

        input_state = {
            "messages": [{"role": "user", "content": user_question}],
            "max_research_loops": self.configurable.max_research_loops,
            "initial_search_query_count": self.configurable.num_of_init_q,
        }
        input_json = json.dumps(input_state)
        all_result = await simple_call_agent_direct(
            langgraph_agent,
            input_json,
        )

        state = json.loads(all_result)
        return state["messages"][-1]["content"]


async def main():
    custom_search_tool = CustomSearchTool(search_engine="quark")

    graph = WebSearchGraph(
        json.loads(Configuration().model_dump_json()),
        call_dashscope,
        custom_search_tool,
    )

    print(
        """Type in your question or q to quit.""",
    )

    user_input = input(">").strip()
    while user_input != "q":
        question = user_input
        item = await graph.run(question)
        print(item, end="", flush=True)
        print("\n")

        user_input = input(">")


if __name__ == "__main__":
    asyncio.run(main())
