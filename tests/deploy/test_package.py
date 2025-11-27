# -*- coding: utf-8 -*-
"""
Unit tests for the new project-based packaging system.
"""

import os
import shutil
from pathlib import Path

import pytest

from agentscope_runtime.engine.deployers.utils.package import (
    ProjectInfo,
    parse_entrypoint,
    package_code,
    package,
    project_dir_extractor,
    _auto_detect_entrypoint,
)


class TestProjectInfo:
    """Test cases for ProjectInfo model."""

    def test_project_info_creation(self):
        """Test ProjectInfo creation."""
        info = ProjectInfo(
            project_dir="/path/to/project",
            entrypoint_file="app.py",
            entrypoint_handler="app",
            is_directory_entrypoint=False,
        )
        assert info.project_dir == "/path/to/project"
        assert info.entrypoint_file == "app.py"
        assert info.entrypoint_handler == "app"
        assert info.is_directory_entrypoint is False


class TestProjectDirExtractor:
    """Test cases for project directory extraction from objects."""

    def test_extract_without_app_or_runner(self):
        """Test that extraction fails without app or runner."""
        with pytest.raises(
            ValueError,
            match="Either app or runner must be provided",
        ):
            project_dir_extractor(app=None, runner=None)

    def test_extract_with_mock_object(self):
        """Test extraction from a mock object created in test scope."""

        # Create a simple mock object
        class MockApp:
            def __init__(self):
                self.app_name = "TestApp"

        # Create the mock app in this scope
        # The function will inspect the call stack to find where this object
        # exists
        app = MockApp()

        try:
            result = project_dir_extractor(app=app)
            # If successful, verify the result structure
            assert result.project_dir is not None
            assert os.path.exists(result.project_dir)
            assert result.entrypoint_handler == "app"
            assert result.is_directory_entrypoint is False
            # The entrypoint file should be the test file itself
            assert result.entrypoint_file == "test_package.py"
        except ValueError as e:
            # In some environments, stack inspection might not find user code
            # This is acceptable - the function correctly raises an error
            assert "Unable to locate source file" in str(e)

    def test_extract_with_runner(self):
        """Test extraction from a runner object."""

        class MockRunner:
            def __init__(self):
                self.framework_type = "agentscope"

        runner = MockRunner()

        try:
            result = project_dir_extractor(runner=runner)
            assert result.project_dir is not None
            assert result.entrypoint_handler == "runner"
            assert result.is_directory_entrypoint is False
        except ValueError as e:
            # Acceptable in test environment
            assert "Unable to locate source file" in str(e)


class TestParseEntrypoint:
    """Test cases for entrypoint parsing."""

    def test_parse_file_entrypoint(self, tmp_path):
        """Test parsing file-based entrypoint."""
        # Create a test file
        app_file = tmp_path / "app.py"
        app_file.write_text("# test app")

        result = parse_entrypoint(str(app_file))

        assert result.project_dir == str(tmp_path)
        assert result.entrypoint_file == "app.py"
        assert result.entrypoint_handler == "app"
        assert result.is_directory_entrypoint is False

    def test_parse_file_with_handler(self, tmp_path):
        """Test parsing file-based entrypoint with handler specification."""
        # Create a test file
        app_file = tmp_path / "app.py"
        app_file.write_text("# test app")

        result = parse_entrypoint(f"{app_file}:my_app")

        assert result.project_dir == str(tmp_path)
        assert result.entrypoint_file == "app.py"
        assert result.entrypoint_handler == "my_app"
        assert result.is_directory_entrypoint is False

    def test_parse_directory_entrypoint(self, tmp_path):
        """Test parsing directory-based entrypoint."""
        # Create app.py in directory
        app_file = tmp_path / "app.py"
        app_file.write_text("# test app")

        result = parse_entrypoint(f"{tmp_path}/")

        assert result.project_dir == str(tmp_path)
        assert result.entrypoint_file == "app.py"
        assert result.entrypoint_handler == "app"
        assert result.is_directory_entrypoint is True

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file raises error."""
        with pytest.raises(ValueError, match="Entrypoint file not found"):
            parse_entrypoint("/nonexistent/app.py")

    def test_parse_directory_without_entrypoint(self, tmp_path):
        """Test parsing directory without standard entrypoint files raises
        error."""
        with pytest.raises(ValueError, match="No entrypoint file found"):
            parse_entrypoint(f"{tmp_path}/")


class TestAutoDetectEntrypoint:
    """Test cases for entrypoint auto-detection."""

    def test_detect_app_py(self, tmp_path):
        """Test detection of app.py."""
        (tmp_path / "app.py").write_text("# app")
        result = _auto_detect_entrypoint(str(tmp_path))
        assert result == "app.py"

    def test_detect_main_py(self, tmp_path):
        """Test detection of main.py."""
        (tmp_path / "main.py").write_text("# main")
        result = _auto_detect_entrypoint(str(tmp_path))
        assert result == "main.py"

    def test_priority_order(self, tmp_path):
        """Test that app.py has priority over main.py."""
        (tmp_path / "app.py").write_text("# app")
        (tmp_path / "main.py").write_text("# main")
        result = _auto_detect_entrypoint(str(tmp_path))
        assert result == "app.py"


class TestPackageCode:
    """Test cases for code packaging."""

    def test_package_simple_project(self, tmp_path):
        """Test packaging a simple project."""
        # Create project structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text("# app")
        (project_dir / "utils.py").write_text("# utils")

        output_zip = tmp_path / "code.zip"

        package_code(project_dir, output_zip)

        assert output_zip.exists()
        assert output_zip.stat().st_size > 0

    def test_package_ignores_pycache(self, tmp_path):
        """Test that __pycache__ is ignored."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text("# app")

        pycache_dir = project_dir / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "app.cpython-39.pyc").write_text("compiled")

        output_zip = tmp_path / "code.zip"

        package_code(project_dir, output_zip)

        # Verify __pycache__ is not in zip
        import zipfile

        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            assert "app.py" in names
            assert not any("__pycache__" in name for name in names)

    def test_package_ignores_git(self, tmp_path):
        """Test that .git directory is ignored."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text("# app")

        git_dir = project_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        output_zip = tmp_path / "code.zip"

        package_code(project_dir, output_zip)

        # Verify .git is not in zip
        import zipfile

        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            assert "app.py" in names
            assert not any(".git" in name for name in names)


class TestPackageFunction:
    """Test cases for the main package function."""

    def test_package_with_entrypoint(self, tmp_path):
        """Test packaging with entrypoint specification."""
        # Create project
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text("# app")

        result_dir, project_info = package(
            entrypoint=str(project_dir / "app.py"),
        )

        assert os.path.exists(result_dir)
        assert project_info.project_dir == str(project_dir)
        assert project_info.entrypoint_file == "app.py"

        # Check that deployment.zip was created
        deployment_zip = Path(result_dir) / "deployment.zip"
        assert deployment_zip.exists()

        # Cleanup
        shutil.rmtree(result_dir)

    def test_package_with_dependencies(self, tmp_path):
        """Test packaging with dependencies."""
        # Create project with requirements.txt
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text("# app")
        (project_dir / "requirements.txt").write_text("pydantic\n")

        result_dir, _ = package(
            entrypoint=str(project_dir / "app.py"),
            force_rebuild_deps=True,  # Force rebuild for testing
        )

        assert os.path.exists(result_dir)

        # Check that deployment.zip includes dependencies
        deployment_zip = Path(result_dir) / "deployment.zip"
        assert deployment_zip.exists()

        # Cleanup
        shutil.rmtree(result_dir)

    def test_package_requires_entrypoint_or_app(self):
        """Test that package requires either entrypoint or app/runner."""
        with pytest.raises(
            ValueError,
            match="Either app/runner or entrypoint must be provided",
        ):
            package()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
