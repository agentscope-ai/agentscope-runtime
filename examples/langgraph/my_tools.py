# -*- coding: utf-8 -*-
# pylint: disable=all

import json
import logging
import os
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import requests
from langchain_core.tools import tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _view_text_file(file_path: str, ranges: Optional[List[int]] = None) -> str:
    """Reads and returns part or all of a text file's contents."""
    logger.debug(
        f"view_text_file called with file_path: {file_path}",
    )

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        logger.debug(f"File has {total_lines} lines")

        if ranges is None:
            selected_lines = lines
            logger.debug("Returning entire file content")
        else:
            # Ensure ranges list has at least 2 elements
            if len(ranges) < 2:
                logger.warning(
                    f"Invalid ranges parameter: {ranges}.",
                )
                selected_lines = lines
            else:
                start, end = ranges[0], ranges[1]
                logger.debug(f"Requested range: {start} to {end}")

                # Handle negative indexing
                if start < 0:
                    start += total_lines
                if end < 0:
                    end += total_lines

                # Clamp indices within valid bounds
                start = max(1, min(start, total_lines))
                end = max(start, min(end, total_lines))

                # Convert to 0-based indexing for list slicing
                selected_lines = lines[start - 1 : end]
                logger.debug(f"Returning lines {start}-{end}")

        content = "".join(selected_lines)
        logger.debug(f"Returning content with {len(content)} characters")
        return content
    except FileNotFoundError as e:
        logger.error(f"File not found: {file_path}, error: {e}")
        return f"File not found: {file_path}"
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"Error reading file {file_path}: {e}"


@tool
def read_plan_file(
    file_path: Annotated[str, "The path to the plan file to read."],
) -> str:
    """Read the content of a plan file."""
    logger.info(f"read_plan_file called with file_path: {file_path}")
    logger.debug(f"Attempting to read plan file: {file_path}")

    # Validate input
    if not file_path:
        logger.error("File path is empty")
        return "Error: File path cannot be empty"

    try:
        if not os.path.exists(file_path):
            logger.warning(f"Plan file does not exist: {file_path}")
            return f"Plan file does not exist: {file_path}"

        file_size = os.path.getsize(file_path)
        logger.debug(f"Plan file size: {file_size} bytes")

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        logger.info(
            f"Successfully read plan file {file_path}",
        )
        logger.debug(f"First 200 characters of content: {content[:200]}...")
        return content
    except FileNotFoundError as e:
        logger.error(f"Plan file not found {file_path}: {e}")
        return f"Plan file not found {file_path}: {e}"
    except PermissionError as e:
        logger.error(f"Permission denied reading plan file {file_path}: {e}")
        return f"Permission denied reading plan file {file_path}: {e}"
    except Exception as e:
        logger.error(f"Failed to read plan file {file_path}: {e}")
        logger.exception(e)  # Log full traceback
        return f"Failed to read plan file {file_path}: {e}"


@tool
def update_plan_file(
    file_path: Annotated[str, "The path to the plan file to update."],
    content: Annotated[str, "The content to write to the plan file."],
    adjust_plan: Annotated[
        bool,
        "Whether to adjust the plan based on previous results.",
    ] = False,
    adjustment_reason: Annotated[str, "Reason for adjusting the plan."] = "",
) -> str:
    """Update or create a plan file with the given content."""
    logger.info(
        f"update_plan_file,file_path: {file_path},adjust_plan: {adjust_plan}",
    )
    logger.debug(f"Content length: {len(content)} characters")

    # Validate inputs
    if not file_path:
        logger.error("File path is empty")
        return "Error: File path cannot be empty"

    if content is None:
        logger.warning("Content is None, converting to empty string")
        content = ""

    if adjust_plan:
        logger.info(f"Plan adjustment requested. Reason: {adjustment_reason}")
    else:
        logger.debug("No plan adjustment requested")

    try:
        parent_dir = Path(file_path).parent
        logger.debug(f"Ensuring parent directory exists: {parent_dir}")
        parent_dir.mkdir(parents=True, exist_ok=True)

        file_exists = os.path.exists(file_path)
        if file_exists:
            original_size = os.path.getsize(file_path)
            logger.debug(
                f"Original plan file exists with size: {original_size} bytes",
            )
        else:
            logger.debug("Creating new plan file")

        if adjust_plan and adjustment_reason:
            adjusted_content = (
                f"# Plan Adjustment Reason: {adjustment_reason}\n\n{content}"
            )
            logger.info("Adding plan adjustment reason to content")
        else:
            adjusted_content = content

        logger.debug(f"Writing to plan file: {file_path}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(adjusted_content)

        new_size = os.path.getsize(file_path)
        logger.info(
            f"Successfully updated plan file {file_path}. "
            f"New size: {new_size} bytes",
        )
        return f"Successfully updated plan file {file_path}"
    except PermissionError as e:
        logger.error(f"Permission denied updating plan file {file_path}: {e}")
        return f"Permission denied updating plan file {file_path}: {e}"
    except Exception as e:
        logger.error(f"Failed to update plan file {file_path}: {e}")
        logger.exception(e)  # Log full traceback
        return f"Failed to update plan file {file_path}: {e}"


# Constants
IQS_API_KEY_ENDPOINT = "https://cloud-iqs.aliyuncs.com"


@tool
def iqs_generic_search(
    query: str,
    category: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Search the web using IQS-GenericSearch API with API key authentication.

    Args:
        query: The search query (2-100 characters)
        category: The category to search in.
        limit: Maximum number of results to return (default: 15)

    Returns:
        Dict containing search results with 'output' and 'scene_items' keys
    """
    logger.info(
        f"iqs_generic_search, query: {query}, category: {category}",
    )
    logger.debug(f"Query length: {len(query)} characters")

    api_key = os.environ.get("IQS_API_KEY")
    if not api_key:
        logger.warning("IQS_API_KEY environment variable not set")

    engine_type = "Generic"

    # Truncate query if too long
    if len(query) > 100:
        original_query = query
        query = query[:100]
        logger.info(f"Query truncated from '{original_query}' to '{query}'")

    url = f"{IQS_API_KEY_ENDPOINT}/search/unified"
    logger.info(f"Making request to URL: {url}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    logger.debug(f"Request headers: {headers}")

    data = {
        "query": query,
        "engineType": engine_type,
        "contents": {
            "mainText": True,
            "markdownText": True,
            "summary": True,
            "rerankScore": True,
        },
    }

    if category:
        data["category"] = category
        logger.info(f"Category specified: {category}")

    logger.debug(f"Request data: {data}")

    session = requests.Session()
    logger.info("Sending POST request to IQS API")
    try:
        response = session.post(url, headers=headers, json=data, timeout=30)
        logger.info(
            f"Received response with status code: {response.status_code}",
        )
        logger.debug(f"Response headers: {dict(response.headers)}")
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout error while making request to IQS API: {e}")
        raise RuntimeError(
            f"Timeout error while making request to IQS API: {e}",
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while making request to IQS API: {e}")
        raise RuntimeError(
            f"Request error while making request to IQS API: {e}",
        )

    if response.status_code != requests.codes.ok:
        logger.error(
            f"IQS UnifiedSearch error: {response}",
        )
        raise RuntimeError(
            f"IQS UnifiedSearch error: {response}",
        )

    try:
        response_dict = response.json()
        logger.info("Successfully parsed JSON response")
        logger.debug(f"Response keys: {response_dict.keys()}")
    except json.JSONDecodeError as e:
        logger.error(f"IQS UnifiedSearch Invalid JSON response: {e}")
        logger.debug(f"Response text: {response.text}")
        raise RuntimeError(f"IQS UnifiedSearch Invalid JSON response: {e}")

    # Extract results
    page_list = []
    page_items = response_dict.get("pageItems", [])
    logger.info(f"Found {len(page_items)} page items, limiting to {limit}")

    for i, item in enumerate(page_items[:limit]):
        page_item = {
            "title": item.get("title"),
            "link": item.get("link"),
            "summary": item.get("summary"),
            "content": item.get("mainText"),
            "markdown_text": item.get("markdownText"),
            "score": item.get("rerank_score"),
            "publish_time": item.get("publishedTime"),
            "host_logo": item.get("hostLogo"),
            "hostname": item.get("hostname"),
            "site_label": None,
        }
        page_list.append(page_item)

    logger.info(f"Returning {len(page_list)} results")
    logger.debug(
        f"Result structure: {len(page_list)} items in output, "
        f"{len(response_dict.get('sceneItems', []))} scene items",
    )

    result = {
        "output": page_list,
        "scene_items": response_dict.get("sceneItems", []),
    }

    # Ensure we return a proper dictionary
    if not isinstance(result, dict):
        logger.error(f"Expected dict result, got {type(result)}")
        result = {"output": [], "scene_items": []}

    return result
