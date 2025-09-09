#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test import functionality for K8s deployment
"""


def test_imports():
    """Test that imports work correctly"""
    print("Testing imports from k8s_deploy_test directory...")

    try:
        # Test direct import
        from test_utils import (
            get_test_message,
            calculate_test_result,
            TestHelper,
            TEST_CONSTANT,
        )

        print("✓ Direct imports from test_utils successful")

        # Test functionality
        message = get_test_message()
        print(f"✓ get_test_message(): {message}")

        result = calculate_test_result(5, 3)
        print(f"✓ calculate_test_result(5, 3): {result}")

        helper = TestHelper()
        info = helper.get_info()
        print(f"✓ TestHelper.get_info(): {info}")

        print(f"✓ TEST_CONSTANT: {TEST_CONSTANT}")

        print("All imports and functionality tests passed!")
        return True

    except Exception as e:
        print(f"✗ Import test failed: {e}")
        return False


if __name__ == "__main__":
    test_imports()
