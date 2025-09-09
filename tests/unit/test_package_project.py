# -*- coding: utf-8 -*-
"""
Unit tests for package_project module.
"""

import os
import tempfile
import shutil
import tarfile
import pytest
from pathlib import Path

from agentscope_runtime.engine.deployers.ack_deployment.package_project import (
    package_project,
    create_tar_gz,
    _find_agent_source_file,
)


class MockAgent:
    """Mock agent class for testing."""

    def __init__(self, name="test_agent"):
        self.name = name


class TestCreateTarGz:
    """Test cases for create_tar_gz function."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def test_directory(self, temp_dir):
        """Create a test directory with some files."""
        test_dir = os.path.join(temp_dir, "test_project")
        os.makedirs(test_dir)

        # Create some test files
        with open(os.path.join(test_dir, "main.py"), "w") as f:
            f.write("print('Hello World')")

        with open(os.path.join(test_dir, "config.json"), "w") as f:
            f.write('{"key": "value"}')

        # Create a subdirectory with files
        sub_dir = os.path.join(test_dir, "subdir")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "helper.py"), "w") as f:
            f.write("def helper(): pass")

        # Create an empty directory
        empty_dir = os.path.join(test_dir, "empty_dir")
        os.makedirs(empty_dir)

        return test_dir

    def test_create_tar_gz_basic(self, test_directory, temp_dir):
        """Test basic tar.gz creation."""
        output_path = create_tar_gz(test_directory)

        # Check that the tar.gz file was created
        assert os.path.exists(output_path)
        assert output_path.endswith(".tar.gz")

        # Verify the contents by extracting
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir)

        with tarfile.open(output_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        # Check that all files are present
        assert os.path.exists(os.path.join(extract_dir, "main.py"))
        assert os.path.exists(os.path.join(extract_dir, "config.json"))
        assert os.path.exists(os.path.join(extract_dir, "subdir", "helper.py"))
        assert os.path.exists(os.path.join(extract_dir, "empty_dir"))

        # Verify file contents
        with open(os.path.join(extract_dir, "main.py")) as f:
            assert f.read() == "print('Hello World')"

    def test_create_tar_gz_custom_output_path(self, test_directory, temp_dir):
        """Test tar.gz creation with custom output path."""
        custom_output = os.path.join(temp_dir, "custom_archive.tar.gz")
        output_path = create_tar_gz(test_directory, custom_output)

        assert output_path == custom_output
        assert os.path.exists(custom_output)

    def test_create_tar_gz_nonexistent_directory(self):
        """Test tar.gz creation with non-existent directory."""
        with pytest.raises(ValueError, match="Directory does not exist"):
            create_tar_gz("/nonexistent/directory")

    def test_create_tar_gz_file_instead_of_directory(self, temp_dir):
        """Test tar.gz creation when path points to a file."""
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        with pytest.raises(ValueError, match="Path is not a directory"):
            create_tar_gz(test_file)

    def test_create_tar_gz_empty_directory(self, temp_dir):
        """Test tar.gz creation with empty directory."""
        empty_dir = os.path.join(temp_dir, "empty")
        os.makedirs(empty_dir)

        output_path = create_tar_gz(empty_dir)
        assert os.path.exists(output_path)

        # Verify it's a valid tar.gz file
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getmembers()
            assert (
                len(members) == 0
            )  # Empty directory should result in empty archive

    def test_create_tar_gz_cleanup_on_error(
        self,
        test_directory,
        temp_dir,
        monkeypatch,
    ):
        """Test that partial files are cleaned up on error."""
        custom_output = os.path.join(temp_dir, "error_archive.tar.gz")

        # Mock tarfile.open to raise an exception
        original_open = tarfile.open

        def mock_open(*args, **kwargs):
            # Create a partial file to test cleanup
            with open(custom_output, "w") as f:
                f.write("partial")
            raise OSError("Mocked error")

        monkeypatch.setattr(tarfile, "open", mock_open)

        with pytest.raises(OSError, match="Failed to create tar.gz file"):
            create_tar_gz(test_directory, custom_output)

        # Verify the partial file was cleaned up
        assert not os.path.exists(custom_output)


class TestPackageProject:
    """Test cases for package_project function."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        return MockAgent("test_agent")

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    def test_package_project_basic(self, mock_agent):
        """Test basic package_project functionality."""
        # This test requires a more complex setup since it analyzes the call stack
        # For now, we'll test the basic structure
        try:
            result_dir = package_project(mock_agent)
            assert os.path.exists(result_dir)
            assert os.path.isdir(result_dir)

            # Check that main.py was created
            main_py = os.path.join(result_dir, "main.py")
            assert os.path.exists(main_py)

            # Verify main.py contains expected content
            with open(main_py, "r") as f:
                content = f.read()
                assert "FastAPI" in content
                assert "from agent_file import" in content
        finally:
            # Clean up the temporary directory
            if "result_dir" in locals() and os.path.exists(result_dir):
                shutil.rmtree(result_dir)

    def test_package_project_with_requirements(self, mock_agent):
        """Test package_project with custom requirements."""
        requirements = ["numpy", "pandas", "requests"]

        try:
            result_dir = package_project(mock_agent, requirements=requirements)

            # Check that requirements.txt was created
            req_file = os.path.join(result_dir, "requirements.txt")
            assert os.path.exists(req_file)

            # Verify requirements content
            with open(req_file, "r") as f:
                content = f.read()
                # Base requirements should be present
                assert "fastapi" in content
                assert "uvicorn" in content
                assert "agentscope-runtime" in content
                # Custom requirements should be present
                assert "numpy" in content
                assert "pandas" in content
                assert "requests" in content
        finally:
            if "result_dir" in locals() and os.path.exists(result_dir):
                shutil.rmtree(result_dir)

    def test_package_project_with_extras(self, mock_agent, temp_dir):
        """Test package_project with extra files."""
        # Create some extra files
        extra_file = os.path.join(temp_dir, "config.yaml")
        with open(extra_file, "w") as f:
            f.write("debug: true")

        extra_dir = os.path.join(temp_dir, "utils")
        os.makedirs(extra_dir)
        with open(os.path.join(extra_dir, "helper.py"), "w") as f:
            f.write("def help(): pass")

        extras = [extra_file, extra_dir]

        try:
            result_dir = package_project(mock_agent, extras_package=extras)

            # Check that extra files were copied
            assert os.path.exists(os.path.join(result_dir, "config.yaml"))
            assert os.path.exists(
                os.path.join(result_dir, "utils", "helper.py"),
            )

        finally:
            if "result_dir" in locals() and os.path.exists(result_dir):
                shutil.rmtree(result_dir)


class TestFindAgentSourceFile:
    """Test cases for _find_agent_source_file function."""

    def test_find_agent_source_file_basic(self):
        """Test basic functionality of _find_agent_source_file."""
        # Create a mock frame
        import inspect

        frame = inspect.currentframe()

        # This is a simplified test - the actual function requires complex frame analysis
        # In a real scenario, this would need more sophisticated mocking
        result = _find_agent_source_file("test_agent", frame)

        # Should at least return the current file as fallback
        assert result is not None
        assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__])
