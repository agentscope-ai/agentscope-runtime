# -*- coding: utf-8 -*-
# pylint:disable=line-too-long, unused-argument, redefined-outer-name
# pylint:disable=consider-using-enumerate,too-many-branches,too-many-statements
# pylint:disable=too-many-nested-blocks

import copy
import datetime
import json
import os
import random
import re
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
import dashscope
from pydantic import BaseModel, Field

from ..base import Tool
from ...engine.schemas.modelstudio_llm import (
    KnowledgeHolder,
    OpenAIMessage,
    SearchOptions,
)
from ...engine.tracing import trace

SEARCH_TIMEOUT = 5
SEARCH_PAGE = 1
SEARCH_ROWS = 10
_HTML_TAG_RE = re.compile(r" ?</?(a|span|em|br).*?> ?")

SEARCH_STRATEGY_SETTING = {
    "lite": {"scene": "dolphin_search_bailian_lite", "timeout": 3000},
    "standard": {"scene": "dolphin_search_bailian_standard", "timeout": 3000},
    "pro": {"scene": "dolphin_search_bailian_pro", "timeout": 5000},
    "pro_max": {"scene": "dolphin_search_bailian_proMax", "timeout": 5000},
    "pro_ultra": {"scene": "dolphin_search_bailian_proUltra", "timeout": 6000},
    "image": {"scene": "dolphin_search_360_image", "timeout": 3000},
    "turbo": {"scene": "dolphin_search_bailian_turbo", "timeout": 5000},
    "max": {"scene": "dolphin_search_bailian_max", "timeout": 5000},
}
SEARCH_URL = "https://dashscope.aliyuncs.com/api/v1/indices/plugin/web_search"


class SearchInput(BaseModel):
    """
    Search Input.
    """

    messages: List[Union[OpenAIMessage, Dict]] = Field(
        ...,
        description="user query in the format of Message",
    )
    search_options: Union[SearchOptions, Dict] = Field(
        default=SearchOptions(),
        description=" Search options",
    )
    search_output_rules: dict = Field(
        default={},
        description="Search output rules for formatting the search result",
    )
    search_timeout: int = Field(
        default=SEARCH_TIMEOUT,
        description="Search timeout in seconds",
    )
    type: Optional[str] = Field(default=None, description="Search type")


class SearchOutput(BaseModel):
    """
    Search Output.
    """

    search_result: str = Field(
        ...,
        description="Search result in the format of string",
    )
    search_info: dict = Field(
        ...,
        description="Additional information about the search operation result",
    )


# for local use only
class SearchItem(BaseModel):
    title: str = ""
    image: str = ""
    body: str = ""
    href: str = ""
    time: int = 0
    exclusive: bool = False
    relevance: float = 0  # important items have higher scores
    original_order: int = -1  # for stable sort
    source: str = ""
    host_logo: str = ""
    web_main_body: str = ""
    csi_checked: bool = False


class ModelstudioSearch(Tool[SearchInput, SearchOutput]):
    """
    Search tool that calling dashscope for llm search result.
    """

    description = (
        "中文搜索可用于查询百科知识、时事新闻、天气。但它不适用于解决编程问题。它仅收录中文信息，不收录英文资料。"  # noqa E501
    )

    name = "modelstudio_search_pro"

    @trace(trace_type="SEARCH", trace_name="modelstudio_search")
    async def _arun(self, args: SearchInput, **kwargs: Any) -> SearchOutput:
        """Modelstudio Web Search component

        This method performs web search using DashScope's search service,
        processes the results, and returns formatted search output. It handles
        the complete search pipeline including payload generation, API calls,
        and result post-processing.

        Args:
            args: SearchInput containing user messages, search options, output
                rules, and timeout settings.
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - user_id: Required user ID from Modelstudio platform
                - use_green_net: Whether to use green network (defaults to
                True)
                - trace_event: Optional trace event for logging

        Returns:
            SearchOutput containing the formatted search result string and
            additional search information.

        Raises:
            ValueError: If user_id is not provided, as it's required for the
                search component.
        """
        if not isinstance(args.search_options, SearchOptions):
            args.search_options = SearchOptions(**args.search_options)
        request_id = kwargs.get("request_id", str(uuid.uuid4()))
        user_id = kwargs.get("user_id", None)
        if user_id is None:
            raise ValueError(
                "user_id is required for search component, "
                "please find it on Modelstudio platform",
            )
        use_green_net = kwargs.get("use_green_net", True)
        trace_event = kwargs.pop("trace_event", None)

        # call search engine to get search result
        payload: dict = ModelstudioSearch.generate_search_payload(
            search_input=args,
            search_options=args.search_options,
            search_payload={},
            request_id=request_id,
            use_green_net=use_green_net,
            user_id=user_id,
        )

        header = {
            "Content-Type": "application/json",
            "Accept-Encoding": "utf-8",
            "Authorization": "Bearer "
            + os.getenv("DASHSCOPE_API_KEY", dashscope.api_key),
        }
        payload_string = json.dumps(payload)
        kwargs["context"] = {
            "payload": payload_string,
            "search_strategy": args.search_options.search_strategy,
            "timeout": args.search_timeout,
        }
        try:
            (
                search_result,
                extra_tool_info,
            ) = await ModelstudioSearch.dashscope_search_kernel(
                url=SEARCH_URL,
                payload=payload_string,
                headers=header,
                timeout=args.search_timeout,
            )
            if trace_event:
                trace_event.on_log(
                    "",
                    **{
                        "step_suffix": "results",
                        "payload": {
                            "search_result": search_result,
                            "extra_tool_info": extra_tool_info,
                        },
                    },
                )

        except Exception:
            return SearchOutput()

        # post process search results
        (
            search_items,
            search_info,
        ) = ModelstudioSearch.post_process_search_detail(
            search_results=search_result,
            extra_tool_info=extra_tool_info,
            search_options=args.search_options,
            search_output_rules=args.search_output_rules,
        )

        # post process search string
        search_string = ModelstudioSearch.post_process_search_string(
            search_input=args,
            search_items=search_items,
            search_options=args.search_options,
        )

        return SearchOutput(
            search_result=search_string,
            search_info=search_info,
        )

    @staticmethod
    def generate_search_payload(
        search_input: SearchInput,
        search_options: Union[SearchOptions, Dict],
        search_payload: Dict,
        request_id: str,
        use_green_net: bool,
        **kwargs: Any,
    ) -> Dict:
        """Generate the payload for DashScope search API request.

        This method constructs the request payload for the search API by
        processing the input messages, search options, and other parameters.
        It handles different search strategies and configurations.

        Args:
            search_input: SearchInput containing user messages and search
                configuration.
            search_options: SearchOptions or dict containing search strategy
                and other search-related settings.
            search_payload: Existing payload dict to modify, or empty dict
                for new payload.
            request_id: Unique request identifier for tracking.
            use_green_net: Whether to enable content inspection/filtering.
            **kwargs: Additional keyword arguments including:
                - user_id: Required user ID for the search request
                - is_xinwen_label: Whether to set news search intention

        Returns:
            Dict: The complete payload ready for API request, containing
                scene, query, user info, and configuration parameters.
        """
        user_id = kwargs.get("user_id")
        is_xinwen_label = kwargs.get("is_xinwen_label", False)
        if isinstance(search_options, dict):
            search_options = SearchOptions(**search_options)
        search_strategy = search_options.search_strategy
        messages = ModelstudioSearch.preprocess_messages(search_input.messages)
        query = messages[-1].content
        string_query = ""
        if isinstance(query, list):
            for item in query:
                query_dict = item.model_dump()
                if "text" in query_dict and query_dict["text"]:
                    string_query = query_dict["text"]
                    break
        else:
            string_query = query

        history = [message.model_dump() for message in messages[:-1]]
        tool_use = search_options.enable_search_extension
        if search_payload != {}:
            payload = copy.deepcopy(search_payload.get("payload", {}))
            payload["rid"] = request_id
            payload["uq"] = string_query.strip()
            payload["customConfigInfo"]["qpMultiQueryHistory"] = history
            payload["uid"] = user_id
        else:
            # refactor based on
            # https://project.aone.alibaba-inc.com/v2/project/2018866/req/62839770    # noqa E501
            payload = {
                "scene": SEARCH_STRATEGY_SETTING[search_strategy]["scene"],
                "uid": user_id,
                "uq": string_query.strip(),
                "rid": request_id,
                "fields": [],
                "page": int(SEARCH_PAGE),
                "rows": int(SEARCH_ROWS),
                "customConfigInfo": {
                    "qpToolPlan": False,
                    "readpage": False,
                    "readpageConfig": {
                        "onlyCache": False,
                        "topK": 10,
                        "tokens": 4000,
                    },
                    "qpMultiQueryHistory": history,
                },
                "headers": {
                    "__d_head_qto": SEARCH_STRATEGY_SETTING[search_strategy][
                        "timeout"
                    ],
                },
            }

        if use_green_net:
            payload["customConfigInfo"]["inspection"] = use_green_net

        if tool_use:
            payload["customConfigInfo"]["qpToolPlan"] = tool_use

        if is_xinwen_label:
            payload["customConfigInfo"]["searchIntention"] = ["xinwen"]

        if search_input.type == "image":
            payload["type"] = search_input.type
            payload["customConfigInfo"]["qpMultiQuery"] = False
        return payload

    @staticmethod
    async def dashscope_search_kernel(
        url: str,
        payload: str,
        headers: Dict,
        timeout: int,
        **kwargs: Any,
    ) -> Tuple[List, List]:
        """Execute the core search request to DashScope API.

        This method makes the HTTP POST request to the DashScope search
        service and processes the response to extract search results and
        additional tool information.

        Args:
            url: The DashScope search API endpoint URL.
            payload: JSON string containing the search request payload.
            headers: HTTP headers for the request including authorization.
            timeout: Request timeout in seconds.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            Tuple containing:
                - List of search result documents
                - List of extra tool information from the response
        """
        extra_tool_info = []
        results_list = []

        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(
                timeout=timeout_config,
            ) as session:
                async with session.post(
                    url,
                    headers=headers,
                    data=payload,
                ) as response:
                    results = await response.json()
            if results["status"] == 0:
                extra_tool_info = results["data"]["extras"].get(
                    "toolResult",
                    [],
                )
                results_list = results["data"]["docs"]
        except Exception as e:
            print(f"Error: {e}")

        return results_list, extra_tool_info

    @staticmethod
    def post_process_search_detail(
        search_results: List,
        extra_tool_info: List,
        search_options: Union[SearchOptions, Dict],
        search_output_rules: Dict,
        **kwargs: Any,
    ) -> Tuple[List[SearchItem], Dict]:
        """Process and validate search results into structured format.

        This method converts raw search results from the API into SearchItem
        objects, applies validation rules, and prepares additional search
        information for the response.

        Args:
            search_results: List of raw search result documents from API.
            extra_tool_info: Additional tool information from the search
                response.
            search_options: SearchOptions or dict containing search
                configuration.
            search_output_rules: Dict containing validation rules for
                filtering results.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            Tuple containing:
                - List of processed SearchItem objects
                - Dict with search information including extra tool info
        """
        if isinstance(search_options, dict):
            search_options = SearchOptions(**search_options)
        field_validator = FieldValidator(search_output_rules)
        enable_source = search_options.enable_source
        search_items = []

        def convert_to_timestamp(
            input_val: Any,
            time_format: str = "%Y-%m-%d %H:%M:%S",
        ) -> int:
            """Convert various time formats to timestamp.

            Args:
                input_val: Time value in various formats (int, float, string).
                time_format: Expected string time format for parsing.

            Returns:
                Unix timestamp as integer, or 0 if conversion fails.
            """
            if isinstance(input_val, (int, float)):
                return int(input_val)
            elif input_val.isdigit():
                # Assume the timestamp string consists entirely of digits.
                return int(input_val)
            elif input_val == " ":
                return 0
            else:
                try:
                    datetime_obj = datetime.datetime.strptime(
                        input_val,
                        time_format,
                    )
                    return int(datetime_obj.timestamp())
                except Exception:
                    # If the timestamp format is incorrect, return 0.
                    return 0

        try:
            for doc in search_results:
                tmp_search_result = {
                    "url": doc.get("url", "") or "",
                    "title": doc.get("title", "") or "",
                    "icon": doc.get("hostlogo", "") or "",
                    "site_name": doc.get("hostname", "") or "",
                    "image": doc.get("image", "") or "",
                }
                filtered_search_result = field_validator.validate(
                    tmp_search_result,
                )
                if filtered_search_result:
                    search_items.append(
                        SearchItem(
                            title=doc.get("title", "") or "",
                            body=doc.get("snippet", "") or "",
                            href=doc.get("url", "") or "",
                            time=convert_to_timestamp(
                                doc.get("timestamp_format", "0"),
                            ),
                            source=doc.get("hostname", "") or "",
                            relevance=doc.get("_score", 0.0) or 0.0,
                            host_logo=doc.get("hostlogo", "") or "",
                            web_main_body=doc.get("web_main_body", "") or "",
                            image=doc.get("image", "") or "",
                            csi_checked=doc.get("_csi_checked", False)
                            or False,
                        ),
                    )
        except Exception as e:
            print(f"Error: {e}")

        for i, item in enumerate(search_items):
            item.original_order = i
            item.href = item.href.replace(" ", "%20").strip() or "expired_url"
            item.href = item.href.replace("chatm6.sm.cn", "quark.sm.cn")

        search_info = {"extra_tool_info": extra_tool_info}
        if enable_source is True:
            raw_results = []
            i = 1
            if isinstance(search_results, list):
                for doc in search_results:
                    if not doc.get("_csi_checked", True):
                        continue
                    tmp_search_result = {
                        "url": doc.get("url", "") or "",
                        "title": doc.get("title", "") or "",
                        "index": i,
                        "icon": doc.get("hostlogo", "") or "",
                        "site_name": doc.get("hostname", "") or "",
                    }
                    filtered_search_result = field_validator.validate(
                        tmp_search_result,
                    )
                    if filtered_search_result:
                        raw_results.append(filtered_search_result)
                        i = i + 1
            search_info["search_results"] = raw_results
        return search_items, search_info

    @staticmethod
    def post_process_search_string(
        search_input: SearchInput,
        search_items: List[SearchItem],
        search_options: Union[SearchOptions, Dict],
        **kwargs: Any,
    ) -> str:
        if isinstance(search_options, dict):
            search_options = SearchOptions(**search_options)
        citation_format = search_options.citation_format
        search_strategy = search_options.search_strategy
        enable_citation = search_options.enable_citation
        enable_source = search_options.enable_source
        query = ModelstudioSearch.preprocess_messages(search_input.messages)[
            -1
        ].content

        # Determine whether it is an image search
        if search_input.type == "image":
            images = []
            top_n = (
                int(os.getenv("TOP_N", "5"))
                if search_options.top_n == 0
                else search_options.top_n
            )
            image_count = (
                top_n if len(search_items) > top_n else len(search_items)
            )
            for index in range(image_count):
                image_url = search_items[index].image
                images.append(image_url)
            text_result_str = json.dumps(images)
            return text_result_str

        timestamp_templates = [
            "（搜索结果收录于{}年{}月{}日）",
            "（{}年{}月{}日）",
            "（来自{}年{}月{}日的资料）",
            "（{}年{}月{}日的资料）",
            "（该信息的时间戳是{}年{}月{}日）",
            "（资料日期为{}年{}月{}日）",
            "（消息于{}年{}月{}日发布）",
            "（发布时间是{}年{}月{}日）",
            "（撰于{}年{}月{}日）",
            "（截至{}年{}月{}日）",
        ]
        random.shuffle(timestamp_templates)

        cnt_char = 0
        text_result = []
        other_text_result = []
        search_top = kwargs.get("web_main_body_cnt", 3)
        search_nlp_total_char = search_options.item_cnt

        nlp_web_main_body_cnt = 0

        def _rm_html(text: str) -> str:
            text = text.replace("\xa0", " ")
            text = text.replace(
                "\t",
                "",
            )  # quark uses \t to split chinese words
            text = text.replace("...", "……")
            text = _HTML_TAG_RE.sub("", text)
            text = text.strip()
            if text.endswith("……"):
                text = text[: -len("……")]
            return text

        for i, item in enumerate(search_items):
            if item.time > 0:
                t = time.localtime(item.time)
                if i < len(timestamp_templates):
                    k = i
                else:
                    k = random.randint(0, len(timestamp_templates) - 1)
                text_timestamp = timestamp_templates[k].format(
                    t.tm_year,
                    t.tm_mon,
                    t.tm_mday,
                )
            else:
                text_timestamp = ""

            if (
                len(item.body) < len(item.web_main_body)
                and nlp_web_main_body_cnt < search_top
            ):
                nlp_web_main_body_cnt += 1
                content = item.web_main_body
            else:
                content = item.body
            snippet = f"{_rm_html(item.title)}\n{_rm_html(content)}".strip()
            text_snippet = snippet.replace("\n", "\\n")
            text_result_cur = text_snippet[:] + text_timestamp

            # Place into corresponding collection based on whether it
            # passes the check
            if item.csi_checked:
                text_result.append(text_result_cur)
            else:
                other_text_result.append(text_result_cur)

            cnt_char += len(snippet)
            if cnt_char > search_nlp_total_char:
                # Currently limit search characters to 4k.
                break

        text_result_str = ""
        match = re.search("<number>", citation_format)
        if not match:
            citation_format = "[<number>]"  # Fallback for incorrect input
        if enable_citation and enable_source:
            for i in range(len(text_result)):
                cite_form = re.sub("<number>", str(i + 1), citation_format)
                text_result[i] = cite_form + text_result[i] + "\n\n"
                text_result_str += text_result[i]
                if len(text_result_str) > search_nlp_total_char:
                    break

            if other_text_result:
                # 1. Content removed by the green-net filter will not have
                #   [ref_x] citation numbers.
                # 2. After normally citing web pages, add "## Other Internet
                #   Information:" and put the content removed by the
                #   green-net filter here.
                text_result_str += "## 其他互联网信息：\n\n```"
                for i, text in enumerate(other_text_result):
                    text = text + "\n\n"
                    text_result_str += text
                    if len(text_result_str) > search_nlp_total_char:
                        break
                text_result_str += "```\n"
            return text_result_str

        text_result_str = "\n\n".join(text_result).strip()
        while (
            len(text_result) > 1
            and len(text_result_str) > search_nlp_total_char
        ):
            text_result.pop(-1)
            text_result_str = "\n\n".join(text_result).strip()

        if search_strategy == "pro_ultra":
            text_result_str = (
                text_result_str.strip()
                + f"# # 参考大纲\n\n{query}\n# 输出要求\n\n请做出有深度的回答，"
                f"不少于1000字，回答时引用上述内容中的细节。"
            )

        return text_result_str

    @staticmethod
    def preprocess_messages(
        messages: List[Union[OpenAIMessage, Dict]],
    ) -> List[Union[OpenAIMessage, Dict]]:
        for i, message in reversed(list(enumerate(messages))):
            if isinstance(message, dict):
                message = OpenAIMessage(**message)
            if message.role == "user":
                return messages[: i + 1]
        raise RuntimeError("Input unknown")

    @staticmethod
    def build_knowledge_for_search(
        search_output: SearchOutput,
        **kwargs: Any,
    ) -> List[KnowledgeHolder]:
        search_strategy = kwargs.get("search_strategy", "pro_max")
        tool_output = {
            "search": search_output.search_result,
            "extra_tool_info": search_output.search_info.get(
                "extra_tool_info",
                [],
            ),
        }

        def tool_call_knowledge(_tool_output: List, **kwargs: Any) -> str:
            prompt = (
                """以下通过权威渠道的实时信息可能有助于你回答问题，请优先参考：#以下根据实际返回选择"""  # noqa E501
            )
            for item in _tool_output:
                if "result" not in item:
                    continue
                if item.get("tool", "") == "oil_price":
                    prompt = prompt + "\n 油价信息:" + item.get("result", "")
                elif item.get("tool", "") == "gold_price":
                    prompt = prompt + "\n 金价信息:" + item.get("result", "")
                elif item.get("tool", "") == "exchange":
                    prompt = prompt + "\n 汇率信息:" + item.get("result", "")
                elif item.get("tool", "") == "stock":
                    prompt = prompt + "\n 股市信息:" + item.get("result", "")
                elif item.get("tool", "") == "silver_price":
                    prompt = prompt + "\n 银价信息:" + item.get("result", "")
                elif item.get("tool", "") == "weather":
                    prompt = prompt + "\n 天气信息:" + item.get("result", "")
                elif item.get("tool", "") == "calendar":
                    prompt = prompt + "\n 万年历信息:" + item.get("result", "")
            return prompt

        def get_current_date_str() -> str:
            beijing_time = datetime.datetime.utcnow() + datetime.timedelta(
                hours=8,
            )
            cur_time = beijing_time.timetuple()
            date_str = (
                f"当前时间：{cur_time.tm_year}年{cur_time.tm_mon}月"
                f"{cur_time.tm_mday}日，星期"
            )
            date_str += ["一", "二", "三", "四", "五", "六", "日"][cur_time.tm_wday]
            date_str += f"{cur_time.tm_hour}时{cur_time.tm_min}分"
            date_str += "。"
            return date_str

        # Add time to all app requests.
        knowledge = []
        for tool_name, result in tool_output.items():
            if tool_name == "search":
                result = f"{result}".strip()
                if result:
                    enable_citation = kwargs.get("enable_citation", False)
                    enable_source = kwargs.get("enable_source", False)
                    if enable_source and enable_citation:
                        citation_format = kwargs.get("citation_format", "")

                        if search_strategy == "pro_ultra":
                            result += (
                                f'# # 参考大纲\n\n{kwargs.get("query", "")}\n# 输出要求\n\n请做出有深度的回答，不少于1000字，回答时引用上述内容中的细节，并在引用处使用如`'  # noqa E501
                                + re.sub(
                                    "<number>",
                                    "1",
                                    citation_format,
                                )  # noqa E501
                                + re.sub(
                                    "<number>",
                                    "2",
                                    citation_format,
                                )  # noqa E501
                                + "`, 的格式标记来源，每一处引用最多引用1个来源。"
                            )
                        else:
                            result += (
                                "输出要求\n\n请在回答时引用上述内容，并在引用处使用 `"
                                + citation_format
                                + "` 的格式标记来源，如果有多个来源，则用多个[]来表示，如`"  # noqa E501
                                + re.sub(
                                    "<number>",
                                    "1",
                                    citation_format,
                                )  # noqa E501
                                + re.sub(
                                    "<number>",
                                    "2",
                                    citation_format,
                                )  # noqa E501
                                + "`，如果回答没有引用上述内容则不用输出角标，禁止输出`"
                                + re.sub(
                                    "<number>",
                                    "无",
                                    citation_format,
                                )  # noqa E501
                                + "`或者`"
                                + re.sub(
                                    "<number>",
                                    "not_found",
                                    citation_format,  # noqa E501
                                )
                                + "`"
                            )
                    knowledge.append(
                        KnowledgeHolder(source="你的知识库", content=result),
                    )
            elif tool_name == "extra_tool_info":
                result = tool_call_knowledge(result, **kwargs)
                if result:
                    knowledge.append(
                        KnowledgeHolder(
                            source="系统",
                            content=get_current_date_str(),
                        ),
                    )
                    knowledge.append(
                        KnowledgeHolder(source="你的知识库", content=result),
                    )
        return knowledge


# for validator search item only
class ValidationMode(Enum):
    NORMAL = "normal"
    AVOID_EMPTY = "avoid_empty"
    EXCLUDE = "exclude"
    FORCE = "force"
    DROPOUT_ENTIRE_IF_MISSING = "dropout_entire_if_missing"
    FILTER_ITEMS_FROM_LIST = "filter_items_from_list"


class FieldValidator:
    def __init__(self, modes: Optional[Dict] = None) -> None:
        self.modes = modes if modes is not None else {}
        if not isinstance(modes, dict) or not modes:
            self.modes = {}

    def validate(self, input_dict: dict) -> dict:
        output_dict = {}

        for key, mode in self.modes.items():
            value = input_dict.get(key)

            if isinstance(mode, dict):
                for mode_key, mode_value in mode.items():
                    if (
                        mode_key
                        == ValidationMode.DROPOUT_ENTIRE_IF_MISSING.name
                    ):
                        if value not in (None, "", []):
                            output_dict[key] = value
                        else:
                            return {}
                    elif mode_key == ValidationMode.AVOID_EMPTY.name:
                        if value not in (None, "", []):
                            output_dict[key] = value

                    elif mode_key == ValidationMode.EXCLUDE.name:
                        continue  # Do not add the key to output_dict

                    elif mode_key == ValidationMode.FORCE.name:
                        if value is None:
                            raise ValueError(
                                f"Key '{key}' is required but not provided.",
                            )
                        output_dict[key] = value

                    elif (
                        mode_key == ValidationMode.FILTER_ITEMS_FROM_LIST.name
                    ):
                        if value not in (None, "", []) and isinstance(
                            mode_value,
                            list,
                        ):
                            for filter_item in mode_value:
                                if value.startswith(filter_item):
                                    return {}

                    else:  # NORMAL behavior
                        if value is not None:  # Keep it if it exists
                            output_dict[key] = value

            else:
                if mode == ValidationMode.DROPOUT_ENTIRE_IF_MISSING.name:
                    if value not in (None, "", []):
                        output_dict[key] = value
                    else:
                        return {}
                elif mode == ValidationMode.AVOID_EMPTY.name:
                    if value not in (None, "", []):
                        output_dict[key] = value

                elif mode == ValidationMode.EXCLUDE.name:
                    continue  # Do not add the key to output_dict

                elif mode == ValidationMode.FORCE.name:
                    if value is None:
                        raise ValueError(
                            f"Key '{key}' is required but not provided.",
                        )
                    output_dict[key] = value

                else:  # NORMAL behavior
                    if value is not None:  # Keep it if it exists
                        output_dict[key] = value

        # Add keys with NORMAL mode if not explicitly defined in modes
        for key, value in input_dict.items():
            if key not in self.modes:
                output_dict[key] = value

        return output_dict
