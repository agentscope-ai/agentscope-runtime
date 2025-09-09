#!/bin/bash
# -*- coding: utf-8 -*-
"""
Setup and run script for Kubernetes Deployer Example
"""

set -e

echo "=== Kubernetes Deployer Example Setup ==="

# Check if we're in the right directory
if [[ ! -f "kubernetes_deployer_example.py" ]]; then
    echo "Error: Please run this script from the k8s_deploy_test directory"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "Python version: $python_version"

# Check if kubectl is available
if command -v kubectl &> /dev/null; then
    echo "✓ kubectl is installed"
    kubectl cluster-info --request-timeout=5s > /dev/null 2>&1 && echo "✓ Kubernetes cluster is accessible" || echo "⚠ Warning: Cannot connect to Kubernetes cluster"
else
    echo "⚠ Warning: kubectl not found. Please install kubectl for Kubernetes deployment."
fi

# Check if docker is available
if command -v docker &> /dev/null; then
    echo "✓ Docker is installed"
    docker info > /dev/null 2>&1 && echo "✓ Docker daemon is running" || echo "⚠ Warning: Docker daemon is not running"
else
    echo "⚠ Warning: Docker not found. Please install Docker for image building."
fi

# Check environment variables
echo ""
echo "=== Environment Check ==="
if [[ -z "${DASHSCOPE_API_KEY}" ]]; then
    echo "⚠ Warning: DASHSCOPE_API_KEY is not set"
    echo "Please set your DashScope API key:"
    echo "export DASHSCOPE_API_KEY=your_api_key_here"
    echo ""
    echo "Or create a .env file with:"
    echo "DASHSCOPE_API_KEY=your_api_key_here"
else
    echo "✓ DASHSCOPE_API_KEY is set"
fi

# Check if .env file exists
if [[ -f "../../../.env" ]]; then
    echo "✓ Found .env file in project root"
elif [[ -f ".env" ]]; then
    echo "✓ Found .env file in current directory"
else
    echo "ℹ No .env file found. You can create one with your API keys."
fi

echo ""
echo "=== Setup Complete ==="
echo ""

# Ask user if they want to run the example
read -p "Do you want to run the example now? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running Kubernetes Deployer Example..."
    echo "Note: This will attempt to build and deploy to your Kubernetes cluster"
    echo ""

    # Run the example
    python3 kubernetes_deployer_example.py
else
    echo "Setup complete! You can run the example manually with:"
    echo "python3 kubernetes_deployer_example.py"
fi

echo ""
echo "For more information, see README.md"