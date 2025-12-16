# -*- coding: utf-8 -*-
import os
from enum import Enum
from typing import Any, Optional


class ApiNames(Enum):
    """Enumeration of API key names."""

    dashscope_api_key = "DASHSCOPE_API_KEY"


def get_api_key(
    api_enum: ApiNames,
    key: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Get API key from both input, kwargs, and env sources with priority
    order.

    Args:
        api_enum (ApiNames): Enum of API name to retrieve.
        key (Optional[str]): Default key value. Defaults to None.
        **kwargs (Any): Additional keyword arguments that might contain the
                API key.

    Returns:
        str: The API key value.

    Raises:
        AssertionError: If no API key is found from any source.
    """
    api_key = ""
    if key is not None:
        if kwargs.get(api_enum.name, "") != "":
            if key != kwargs.get(api_enum.name):
                # use runtime key instead of init key
                api_key = kwargs.get(api_enum.name)
        else:
            api_key = key
    else:
        api_key = kwargs.get(api_enum.name, os.environ.get(api_enum.value, ""))

    assert api_key != "", f"{api_enum.name} must be acquired"
    return api_key
