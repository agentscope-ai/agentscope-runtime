# -*- coding: utf-8 -*-
"""
K8s deployment test package
"""

from .test_utils import (
    get_test_message,
    calculate_test_result,
    TestHelper,
    TEST_CONSTANT,
)

__version__ = "1.0.0"
__all__ = [
    "get_test_message",
    "calculate_test_result",
    "TestHelper",
    "TEST_CONSTANT",
]
