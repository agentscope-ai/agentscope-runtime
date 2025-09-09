#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick start script for K8s LLM Agent deployment
"""

import os
import sys
import asyncio

# Add agentscope_runtime to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(current_dir, "../../../")
src_dir = os.path.join(repo_root, "src")
sys.path.insert(0, src_dir)

# Import the main example
from kubernetes_deployer_example import main

if __name__ == "__main__":
    print("🚀 Starting Kubernetes LLM Agent Deployment Example")
    print("📁 Repository root:", os.path.abspath(repo_root))
    print("📁 Source directory:", os.path.abspath(src_dir))
    print("📁 Test directory:", current_dir)
    print()

    # Check API key
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("⚠️  Warning: DASHSCOPE_API_KEY not set!")
        print("   Please set your DashScope API key:")
        print("   export DASHSCOPE_API_KEY=your_api_key_here")
        print()

    # Run the main example
    asyncio.run(main())
