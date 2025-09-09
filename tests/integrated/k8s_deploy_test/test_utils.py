# -*- coding: utf-8 -*-
"""
Test utilities for K8s deployment example
"""


def get_test_message():
    """Get a test message for LLM interaction"""
    return "Hello from test utilities! This is a test message from the k8s_deploy_test directory."


def calculate_test_result(a: int, b: int) -> int:
    """Simple calculation for testing"""
    return a + b


class TestHelper:
    """Test helper class"""

    def __init__(self):
        self.name = "TestHelper"

    def get_info(self):
        return f"I am {self.name} from the test directory"


# Test constant
TEST_CONSTANT = "This is a test constant from test_utils"
