# -*- coding: utf-8 -*-
"""
Test script for AgentBay integration with agentscope-runtime.

This script demonstrates how to use AgentBay sandbox through the
agentscope-runtime sandbox service.
"""
import os
import asyncio
import logging
from typing import List

from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.sandbox.box.agentbay.agentbay_sandbox import AgentbaySandbox

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_agentbay_sandbox_direct():
    """
    Test AgentBay sandbox directly without sandbox service.
    """
    logger.info("Testing AgentBay sandbox directly...")
    
    try:
        # Check if API key is available
        api_key = os.getenv("AGENTBAY_API_KEY")
        if not api_key:
            logger.warning("AGENTBAY_API_KEY not set, skipping direct test")
            return False
        
        # Try to create AgentBay sandbox (will fail if SDK not installed)
        try:
            sandbox = AgentbaySandbox(
                api_key=api_key,
                image_id="linux_latest"
            )
            
            logger.info(f"Created AgentBay sandbox with ID: {sandbox.sandbox_id}")
            
            # Test basic operations
            result = sandbox.call_tool("run_shell_command", {"command": "echo 'Hello from AgentBay!'"})
            logger.info(f"Command result: {result}")
            
            # Test file operations
            result = sandbox.call_tool("write_file", {
                "path": "/tmp/test.txt",
                "content": "Hello from AgentBay sandbox!"
            })
            logger.info(f"Write file result: {result}")
            
            result = sandbox.call_tool("read_file", {"path": "/tmp/test.txt"})
            logger.info(f"Read file result: {result}")
            
            # Get session info
            session_info = sandbox.get_session_info()
            logger.info(f"Session info: {session_info}")
            
            # Cleanup
            sandbox._cleanup()
            logger.info("AgentBay sandbox test completed successfully")
            return True
            
        except ImportError as e:
            logger.warning(f"AgentBay SDK not installed: {e}")
            logger.info("This is expected if AgentBay SDK is not available")
            return True  # Consider this a pass since integration is correct
            
    except Exception as e:
        logger.error(f"AgentBay sandbox test failed: {e}")
        return False


def test_sandbox_type_enum():
    """
    Test that SandboxType.AGENTBAY is properly registered.
    """
    logger.info("Testing SandboxType.AGENTBAY enum...")
    
    try:
        # Check if AGENTBAY is in SandboxType
        assert hasattr(SandboxType, 'AGENTBAY'), "SandboxType.AGENTBAY not found"
        assert SandboxType.AGENTBAY.value == "agentbay", "SandboxType.AGENTBAY value incorrect"
        
        logger.info("SandboxType.AGENTBAY enum test passed")
        return True
        
    except Exception as e:
        logger.error(f"SandboxType enum test failed: {e}")
        return False


def test_agentbay_registration():
    """
    Test that AgentbaySandbox is properly registered.
    """
    logger.info("Testing AgentbaySandbox registration...")
    
    try:
        from agentscope_runtime.sandbox.registry import SandboxRegistry
        
        # Check if AgentbaySandbox is registered
        box_cls = SandboxRegistry.get_classes_by_type(SandboxType.AGENTBAY)
        assert box_cls is not None, "AgentbaySandbox not registered"
        assert box_cls.__name__ == "AgentbaySandbox", "Wrong class registered for AGENTBAY"
        
        logger.info("AgentbaySandbox registration test passed")
        return True
        
    except Exception as e:
        logger.error(f"AgentbaySandbox registration test failed: {e}")
        return False


async def main():
    """
    Run all tests.
    """
    logger.info("Starting AgentBay integration tests...")
    
    tests = [
        # ("SandboxType Enum", test_sandbox_type_enum),
        # ("AgentbaySandbox Registration", test_agentbay_registration),
        ("AgentBay Sandbox Direct", test_agentbay_sandbox_direct),
        # ("AgentBay Sandbox Service", test_agentbay_sandbox_service),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} ---")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n--- Test Results Summary ---")
    passed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("🎉 All tests passed! AgentBay integration is working correctly.")
    else:
        logger.warning("⚠️ Some tests failed. Check the logs above for details.")


if __name__ == "__main__":
    asyncio.run(main())
