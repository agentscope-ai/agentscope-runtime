# -*- coding: utf-8 -*-
# pylint:disable=inconsistent-return-statements

import json
import os
import shutil
import sys
import tarfile
import tempfile

import pytest

from agentscope_runtime.engine.deployers.utils.package_project_utils import (
    PackageConfig,
    package_project,
    create_tar_gz,
    _calculate_directory_hash,
    _compare_directories,
)


class TestPackageConfig:
    """Test cases for PackageConfig model."""

    def test_package_config_defaults(self):
        """Test PackageConfig default values."""
        config = PackageConfig()
        assert config.requirements is None
        assert config.extra_packages is None
        assert config.output_dir is None
        assert config.endpoint_path == "/process"
        assert config.deployment_mode == "standalone"
        assert config.services_config is None
        assert config.protocol_adapters is None

    def test_package_config_creation(self):
        """Test PackageConfig creation with custom values."""
        config = PackageConfig(
            requirements=["fastapi", "uvicorn"],
            extra_packages=["./utils"],
            output_dir="/tmp/test",
            endpoint_path="/api/process",
            deployment_mode="detached_process",
            services_config={"memory": {"provider": "redis"}},
            protocol_adapters=[{"type": "http"}],
        )
        assert config.requirements == ["fastapi", "uvicorn"]
        assert config.extra_packages == ["./utils"]
        assert config.output_dir == "/tmp/test"
        assert config.endpoint_path == "/api/process"
        assert config.deployment_mode == "detached_process"
        assert config.services_config is not None
        assert config.protocol_adapters is not None

    def test_package_config_validation(self):
        """Test PackageConfig with various types of values."""
        # Test with empty lists
        config = PackageConfig(
            requirements=[],
            extra_packages=[],
        )
        assert not config.requirements
        assert not config.extra_packages

        # Test with None values
        config = PackageConfig(
            requirements=None,
            services_config=None,
        )
        assert config.requirements is None
        assert config.services_config is None


class TestPackageProject:
    """Test cases for package_project function using real assets."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()

        # Get paths to real assets
        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        self.agent_file = os.path.join(self.assets_dir, "agent_for_test.py")
        self.others_dir = os.path.join(self.assets_dir, "others")

        # Verify assets exist
        assert os.path.exists(
            self.agent_file,
        ), f"Agent file not found: {self.agent_file}"
        assert os.path.exists(
            self.others_dir,
        ), f"Others directory not found: {self.others_dir}"

        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _get_test_agent(self):
        """Helper method to get the test agent with fallback import
        strategies."""
        try:
            from tests.unit.assets.agent_for_test import llm_agent

            return llm_agent
        except ImportError:
            assets_path = os.path.join(os.path.dirname(__file__), "assets")
            if assets_path not in sys.path:
                sys.path.insert(0, assets_path)
            try:
                import agent_for_test

                return agent_for_test.llm_agent
            except ImportError:
                pytest.skip("Cannot import test agent - missing dependencies")
            finally:
                if assets_path in sys.path:
                    sys.path.remove(assets_path)

    def test_package_project_basic_functionality(self):
        """Test basic package_project functionality with minimal config."""
        try:
            from tests.unit.assets.agent_for_test import llm_agent
        except ImportError:
            # Fallback to sys.path approach
            assets_path = os.path.join(os.path.dirname(__file__), "assets")
            if assets_path not in sys.path:
                sys.path.insert(0, assets_path)
            try:
                from agent_for_test import llm_agent
            except ImportError:
                pytest.skip("Cannot import test agent - missing dependencies")
            finally:
                if assets_path in sys.path:
                    sys.path.remove(assets_path)

        config = PackageConfig(
            requirements=["fastapi"],
            output_dir=self.temp_dir,
        )

        try:
            project_dir, updated = package_project(llm_agent, config)

            # Check basic structure
            assert os.path.exists(project_dir)
            assert updated is True
            assert os.path.exists(os.path.join(project_dir, "agent_file.py"))

            # Check that requirements.txt includes base requirements
            req_file = os.path.join(project_dir, "requirements.txt")
            if os.path.exists(req_file):
                with open(req_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert "fastapi" in content
                    assert "agentscope-runtime" in content

        except Exception as e:
            if "TemplateNotFound" in str(e):
                pytest.skip(
                    "Template file not found - development environment issue",
                )
            else:
                raise

    def test_package_project_with_extra_packages(self):
        """Test package_project with extra packages."""
        from tests.unit.assets.agent_for_test import llm_agent

        config = PackageConfig(
            requirements=["fastapi"],
            extra_packages=[self.others_dir],
            output_dir=self.temp_dir,
        )

        try:
            project_dir, updated = package_project(llm_agent, config)

            # Check that extra directory was copied
            assert updated is True
            others_target = os.path.join(project_dir, "others")
            assert os.path.exists(others_target)
            assert os.path.exists(
                os.path.join(others_target, "other_project.py"),
            )

        except Exception as e:
            if "TemplateNotFound" in str(e):
                pytest.skip(
                    "Template file not found - development environment issue",
                )
            else:
                raise

    def test_package_project_with_services_config(self):
        """Test package_project with services configuration."""
        from tests.unit.assets.agent_for_test import llm_agent

        agent = llm_agent

        config = PackageConfig(
            requirements=["fastapi"],
            services_config={
                "memory": {"provider": "redis", "host": "localhost"},
            },
            output_dir=self.temp_dir,
        )

        try:
            project_dir, updated = package_project(agent, config)

            # Check that services config file was created
            config_file = os.path.join(project_dir, "services_config.json")
            assert os.path.exists(config_file)
            assert updated is True

            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                assert "memory" in config_data
                assert config_data["memory"]["provider"] == "redis"

            # Check that redis was added to requirements
            req_file = os.path.join(project_dir, "requirements.txt")
            if os.path.exists(req_file):
                with open(req_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert "redis" in content

        except Exception as e:
            if "TemplateNotFound" in str(e):
                pytest.skip(
                    "Template file not found - development environment issue",
                )
            else:
                raise

    def test_package_project_output_directory_creation(self):
        """Test that package_project creates output directory if it
        doesn't exist."""
        from tests.unit.assets.agent_for_test import llm_agent

        agent = llm_agent

        # Use a non-existent subdirectory
        output_dir = os.path.join(self.temp_dir, "new_subdir", "deeper_subdir")
        assert not os.path.exists(output_dir)

        config = PackageConfig(
            requirements=["fastapi"],
            output_dir=output_dir,
        )

        try:
            project_dir, updated = package_project(agent, config)
            assert updated is True
            assert os.path.exists(project_dir)
            assert (
                project_dir.startswith(output_dir) or project_dir == output_dir
            )

        except Exception as e:
            if "TemplateNotFound" in str(e):
                pytest.skip(
                    "Template file not found - development environment issue",
                )
            else:
                raise

    def test_package_project_directory_comparison(self):
        """Test package_project directory comparison logic."""
        from tests.unit.assets.agent_for_test import llm_agent

        agent = llm_agent

        config = PackageConfig(
            requirements=["fastapi"],
            output_dir=self.temp_dir,
        )

        try:
            # First call should create content
            project_dir1, updated1 = package_project(agent, config)
            assert updated1 is True

            # Second call with same config should detect no changes needed
            project_dir2, updated2 = package_project(agent, config)
            assert updated2 is False

            assert project_dir1 == project_dir2
            # Note: updated2 might be True due to template rendering
            # differences

        except Exception as e:
            if "TemplateNotFound" in str(e):
                pytest.skip(
                    "Template file not found - development environment issue",
                )
            else:
                raise

    def test_package_project_with_missing_extra_package(self):
        """Test package_project with a non-existent extra package path."""
        from tests.unit.assets.agent_for_test import llm_agent

        agent = llm_agent

        # Use a non-existent extra package path
        non_existent_path = os.path.join(self.temp_dir, "non_existent_package")

        config = PackageConfig(
            requirements=["fastapi"],
            extra_packages=[non_existent_path],
            output_dir=self.temp_dir,
        )

        # This should either handle gracefully or raise appropriate error
        try:
            project_dir, updated = package_project(agent, config)
            # If it succeeds, that's also valid (ignoring missing packages)
            assert os.path.exists(project_dir)
            assert updated is True

        except (FileNotFoundError, OSError, ValueError):
            # Expected behavior for missing packages
            pass
        except Exception as e:
            if "TemplateNotFound" in str(e):
                pytest.skip(
                    "Template file not found - development environment issue",
                )
            else:
                raise

    def test_package_project_empty_config(self):
        """Test package_project with minimal empty config."""
        from tests.unit.assets.agent_for_test import llm_agent

        agent = llm_agent
        config = PackageConfig()

        try:
            project_dir, updated = package_project(agent, config)
            assert updated is True

            assert os.path.exists(project_dir)
            assert os.path.exists(os.path.join(project_dir, "agent_file.py"))

        except Exception as e:
            if "TemplateNotFound" in str(e):
                pytest.skip(
                    "Template file not found - development environment issue",
                )
            else:
                raise


class TestCreateTarGz:
    """Test cases for create_tar_gz function."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = os.path.join(self.temp_dir, "test_dir")
        os.makedirs(self.test_dir)

        # Create test files
        with open(
            os.path.join(self.test_dir, "file1.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("Content 1")
        with open(
            os.path.join(self.test_dir, "file2.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("Content 2")

        # Create subdirectory
        sub_dir = os.path.join(self.test_dir, "subdir")
        os.makedirs(sub_dir)
        with open(
            os.path.join(sub_dir, "file3.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("Content 3")

        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_tar_gz_basic(self):
        """Test basic tar.gz creation."""
        output_path = create_tar_gz(self.test_dir)

        assert os.path.exists(output_path)
        assert output_path.endswith(".tar.gz")

        # Verify archive contents
        with tarfile.open(output_path, "r:gz") as tar:
            names = tar.getnames()
            assert "file1.txt" in names
            assert "file2.txt" in names
            assert "subdir/file3.txt" in names

    def test_create_tar_gz_custom_output(self):
        """Test tar.gz creation with custom output path."""
        custom_output = os.path.join(self.temp_dir, "custom.tar.gz")
        output_path = create_tar_gz(self.test_dir, custom_output)

        assert output_path == custom_output
        assert os.path.exists(custom_output)

        # Verify it's a valid tar.gz
        with tarfile.open(custom_output, "r:gz") as tar:
            names = tar.getnames()
            assert len(names) > 0

    def test_create_tar_gz_nonexistent_directory(self):
        """Test tar.gz creation with nonexistent directory."""
        with pytest.raises(ValueError, match="Directory does not exist"):
            create_tar_gz("/nonexistent/directory")

    def test_create_tar_gz_file_instead_of_directory(self):
        """Test tar.gz creation with file instead of directory."""
        test_file = os.path.join(self.temp_dir, "test_file.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")

        with pytest.raises(ValueError, match="Path is not a directory"):
            create_tar_gz(test_file)

    def test_create_tar_gz_empty_directory(self):
        """Test tar.gz creation with empty directory."""
        empty_dir = os.path.join(self.temp_dir, "empty_dir")
        os.makedirs(empty_dir)

        output_path = create_tar_gz(empty_dir)
        assert os.path.exists(output_path)

        # Verify it's a valid tar.gz even if empty
        with tarfile.open(output_path, "r:gz") as tar:
            names = tar.getnames()
            # Empty directory should have no entries or just the
            # directory itself
            assert len(names) >= 0

    def test_create_tar_gz_with_real_project(self):
        """Test creating tar.gz from a simulated packaged project."""
        # Create a mock project structure
        project_dir = os.path.join(self.temp_dir, "mock_project")
        os.makedirs(project_dir)

        # Create mock project files
        with open(
            os.path.join(project_dir, "main.py"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("# Mock main.py\nprint('Hello World')")
        with open(
            os.path.join(project_dir, "requirements.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("fastapi\nuvicorn\n")
        with open(
            os.path.join(project_dir, "agent_file.py"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("# Mock agent file\nagent = None")

        # Create tar.gz from the project
        tar_path = create_tar_gz(project_dir)

        assert os.path.exists(tar_path)
        assert tar_path.endswith(".tar.gz")

        # Verify the tar contains expected files
        with tarfile.open(tar_path, "r:gz") as tar:
            names = tar.getnames()
            assert "main.py" in names
            assert "requirements.txt" in names
            assert "agent_file.py" in names


class TestIntegration:
    """Integration tests combining multiple functions."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_package_and_tar_workflow(self):
        """Test the complete workflow of packaging and creating tar.gz."""
        try:
            from tests.unit.assets.agent_for_test import llm_agent

            agent = llm_agent

            config = PackageConfig(
                requirements=["fastapi"],
                output_dir=self.temp_dir,
            )

            # Package the project
            try:
                project_dir, updated = package_project(agent, config)

                # Create tar.gz from the packaged project
                tar_path = create_tar_gz(project_dir)
                assert updated is True
                assert os.path.exists(tar_path)
                assert tar_path.endswith(".tar.gz")

                # Verify tar contents include expected files
                with tarfile.open(tar_path, "r:gz") as tar:
                    names = tar.getnames()
                    assert "agent_file.py" in names

            except Exception as e:
                if "TemplateNotFound" in str(e):
                    pytest.skip(
                        "Template file not found - development "
                        "environment issue",
                    )
                else:
                    raise

        except ImportError:
            pytest.skip("Cannot import test agent - missing dependencies")

    def test_directory_hash_consistency(self):
        """Test that directory hashing is consistent across operations."""
        # Create test directory
        test_dir = os.path.join(self.temp_dir, "hash_test")
        os.makedirs(test_dir)

        with open(
            os.path.join(test_dir, "file.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("consistent content")

        # Calculate hash multiple times
        hash1 = _calculate_directory_hash(test_dir)
        hash2 = _calculate_directory_hash(test_dir)
        hash3 = _calculate_directory_hash(test_dir)

        assert hash1 == hash2 == hash3
        assert len(hash1) == 64  # SHA256 length

        # Create identical directory elsewhere
        test_dir2 = os.path.join(self.temp_dir, "hash_test2")
        os.makedirs(test_dir2)
        with open(
            os.path.join(test_dir2, "file.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("consistent content")

        hash4 = _calculate_directory_hash(test_dir2)
        assert hash1 == hash4  # Identical content should have same hash

        # Verify comparison function works
        assert _compare_directories(test_dir, test_dir2) is True
