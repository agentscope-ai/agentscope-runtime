#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify python_api_example.py works with relative directory structure
"""
import os
import sys
import tempfile
import shutil

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))


def test_python_api_example():
    """Test that python_api_example.py works correctly"""
    print("Testing python_api_example.py with relative directory structure...")

    try:
        # Import and run the example
        from python_api_example import package_path

        print(f"Package created at: {package_path}")

        # Verify the package structure
        expected_files = [
            "main.py",
            "agent_file.py",
            "requirements.txt",
            "otheers/other_project.py",
        ]

        all_files_found = True
        for expected_file in expected_files:
            file_path = os.path.join(package_path, expected_file)
            if os.path.exists(file_path):
                print(f"✓ {expected_file} exists")
            else:
                print(f"✗ {expected_file} missing")
                all_files_found = False

        # Show directory structure
        print("\nGenerated package structure:")
        for root, dirs, files in os.walk(package_path):
            level = root.replace(package_path, "").count(os.sep)
            indent = " " * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")

        # Clean up
        shutil.rmtree(package_path)

        if all_files_found:
            print("✅ python_api_example.py test passed!")
            return True
        else:
            print("❌ Some expected files were missing")
            return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_python_api_example()
