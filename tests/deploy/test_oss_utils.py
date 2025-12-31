"""Unit tests for OSS utilities."""

import os
import pathlib
from unittest.mock import MagicMock, patch, call

import pytest

from agentscope_runtime.engine.deployers.utils.oss_utils import (
    _get_default_ignore_patterns,
    _read_ignore_file,
    _should_ignore,
    parse_oss_uri,
    upload,
)


class TestParseOssUri:
    """Test parse_oss_uri function."""

    def test_parse_basic_oss_uri(self):
        """Test parsing basic OSS URI without endpoint."""
        bucket_name, endpoint, object_key = parse_oss_uri(
            "oss://my-bucket/path/to/file.txt"
        )
        assert bucket_name == "my-bucket"
        assert endpoint is None
        assert object_key == "path/to/file.txt"

    def test_parse_oss_uri_with_endpoint(self):
        """Test parsing OSS URI with endpoint."""
        bucket_name, endpoint, object_key = parse_oss_uri(
            "oss://my-bucket.oss-cn-hangzhou.aliyuncs.com/path/to/file.txt"
        )
        assert bucket_name == "my-bucket"
        assert endpoint == "oss-cn-hangzhou.aliyuncs.com"
        assert object_key == "path/to/file.txt"

    def test_parse_oss_uri_with_leading_slash(self):
        """Test parsing OSS URI with leading slash."""
        bucket_name, endpoint, object_key = parse_oss_uri(
            "oss://my-bucket//path/to/file.txt"
        )
        assert bucket_name == "my-bucket"
        assert endpoint is None
        assert object_key == "path/to/file.txt"

    def test_parse_invalid_uri_scheme(self):
        """Test parsing invalid URI scheme."""
        with pytest.raises(ValueError, match="require oss uri"):
            parse_oss_uri("http://my-bucket/path/to/file.txt")


class TestGetDefaultIgnorePatterns:
    """Test _get_default_ignore_patterns function."""

    def test_default_patterns_exist(self):
        """Test that default ignore patterns are returned."""
        patterns = _get_default_ignore_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_common_patterns_included(self):
        """Test that common ignore patterns are included."""
        patterns = _get_default_ignore_patterns()
        
        # Check for virtual environment directories
        assert "venv" in patterns
        assert ".venv" in patterns
        assert "virtualenv" in patterns
        assert "env" in patterns
        
        # Check for Python cache
        assert "__pycache__" in patterns
        assert "*.pyc" in patterns
        
        # Check for version control
        assert ".git" in patterns
        
        # Check for IDE directories
        assert ".vscode" in patterns
        assert ".idea" in patterns


class TestReadIgnoreFile:
    """Test _read_ignore_file function."""

    def test_read_existing_file(self, tmp_path):
        """Test reading an existing ignore file."""
        ignore_file = tmp_path / ".gitignore"
        ignore_file.write_text(
            "# Comment\n"
            "*.pyc\n"
            "__pycache__\n"
            "\n"
            "# Another comment\n"
            "venv/\n"
        )
        
        patterns = _read_ignore_file(ignore_file)
        assert "*.pyc" in patterns
        assert "__pycache__" in patterns
        assert "venv/" in patterns
        # Comments should be excluded
        assert "# Comment" not in patterns
        # Empty lines should be excluded
        assert "" not in patterns

    def test_read_non_existing_file(self, tmp_path):
        """Test reading a non-existing ignore file."""
        ignore_file = tmp_path / ".gitignore"
        patterns = _read_ignore_file(ignore_file)
        assert patterns == []


class TestShouldIgnore:
    """Test _should_ignore function."""

    def test_ignore_exact_directory_name(self):
        """Test ignoring exact directory name."""
        patterns = ["__pycache__", "venv"]
        assert _should_ignore("__pycache__/test.pyc", patterns)
        assert _should_ignore("src/__pycache__/test.pyc", patterns)
        assert _should_ignore("venv/lib/python3.10", patterns)

    def test_ignore_wildcard_patterns(self):
        """Test ignoring wildcard patterns."""
        patterns = ["*.pyc", "*.log", "test_*.py"]
        assert _should_ignore("test.pyc", patterns)
        assert _should_ignore("app.log", patterns)
        assert _should_ignore("test_example.py", patterns)
        assert not _should_ignore("app.py", patterns)

    def test_ignore_exact_path(self):
        """Test ignoring exact path."""
        patterns = [".git", ".venv"]
        assert _should_ignore(".git", patterns)
        assert _should_ignore(".git/config", patterns)
        assert _should_ignore(".venv", patterns)

    def test_ignore_with_leading_slash(self):
        """Test ignoring patterns with leading slash."""
        patterns = ["/build", "/.cache"]
        assert _should_ignore("build", patterns)
        assert _should_ignore("build/output", patterns)

    def test_ignore_nested_paths(self):
        """Test ignoring nested paths."""
        patterns = ["node_modules", "*.egg-info"]
        assert _should_ignore("node_modules/package/index.js", patterns)
        assert _should_ignore("project.egg-info/PKG-INFO", patterns)

    def test_not_ignore_unmatched_patterns(self):
        """Test not ignoring unmatched patterns."""
        patterns = ["*.pyc", "venv", ".git"]
        assert not _should_ignore("app.py", patterns)
        assert not _should_ignore("src/main.py", patterns)
        assert not _should_ignore("requirements.txt", patterns)


class TestUpload:
    """Test upload function."""

    @pytest.fixture
    def temp_source_dir(self, tmp_path):
        """Create a temporary source directory with test files."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create regular files
        (source_dir / "app.py").write_text("print('hello')")
        (source_dir / "README.md").write_text("# README")
        (source_dir / "requirements.txt").write_text("requests==2.28.0")
        
        # Create files that should be ignored
        (source_dir / ".git").mkdir()
        (source_dir / ".git" / "config").write_text("git config")
        
        pycache = source_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "app.cpython-310.pyc").write_text("bytecode")
        
        venv = source_dir / ".venv"
        venv.mkdir()
        (venv / "lib").mkdir()
        (venv / "lib" / "python3.10").mkdir()
        
        # Create subdirectory with files
        subdir = source_dir / "src"
        subdir.mkdir()
        (subdir / "module.py").write_text("def func(): pass")
        (subdir / "test.log").write_text("log content")
        
        return source_dir

    @pytest.fixture
    def mock_bucket(self):
        """Create a mock OSS bucket."""
        bucket = MagicMock()
        bucket.bucket_name = "test-bucket"
        return bucket

    def test_upload_basic_functionality(
        self, temp_source_dir, mock_bucket
    ):
        """Test basic upload functionality."""
        with patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils._get_bucket_instance",
            return_value=mock_bucket,
        ), patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils.oss2.resumable_upload"
        ) as mock_upload:
            result = upload(
                source_path=str(temp_source_dir),
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
            )
            
            # Check return value
            assert result == "oss://test-bucket/upload/path/"
            
            # Check that upload was called (but not for ignored files)
            assert mock_upload.called
            
            # Get all uploaded file paths
            uploaded_files = [
                call_args[1]["filename"]
                for call_args in mock_upload.call_args_list
            ]
            
            # Convert to relative paths for easier checking
            uploaded_relative = [
                str(pathlib.Path(f).relative_to(temp_source_dir))
                for f in uploaded_files
            ]
            
            # Check that regular files were uploaded
            assert any("app.py" in f for f in uploaded_relative)
            assert any("README.md" in f for f in uploaded_relative)
            
            # Check that ignored files were NOT uploaded
            assert not any(".git" in f for f in uploaded_relative)
            assert not any("__pycache__" in f for f in uploaded_relative)
            assert not any(".venv" in f for f in uploaded_relative)
            assert not any(".pyc" in f for f in uploaded_relative)

    def test_upload_with_custom_exclude_patterns(
        self, temp_source_dir, mock_bucket
    ):
        """Test upload with custom exclude patterns."""
        with patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils._get_bucket_instance",
            return_value=mock_bucket,
        ), patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils.oss2.resumable_upload"
        ) as mock_upload:
            result = upload(
                source_path=str(temp_source_dir),
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
                exclude_file_patterns=["*.md", "*.log"],
            )
            
            # Get all uploaded file paths
            uploaded_files = [
                call_args[1]["filename"]
                for call_args in mock_upload.call_args_list
            ]
            
            # Convert to relative paths
            uploaded_relative = [
                str(pathlib.Path(f).relative_to(temp_source_dir))
                for f in uploaded_files
            ]
            
            # Check that .md and .log files were NOT uploaded
            assert not any(".md" in f for f in uploaded_relative)
            assert not any(".log" in f for f in uploaded_relative)
            
            # Check that .py files were uploaded
            assert any("app.py" in f for f in uploaded_relative)

    def test_upload_with_gitignore(
        self, temp_source_dir, mock_bucket
    ):
        """Test upload respects .gitignore file."""
        # Create .gitignore file
        gitignore = temp_source_dir / ".gitignore"
        gitignore.write_text("*.txt\nsrc/")
        
        with patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils._get_bucket_instance",
            return_value=mock_bucket,
        ), patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils.oss2.resumable_upload"
        ) as mock_upload:
            result = upload(
                source_path=str(temp_source_dir),
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
            )
            
            # Get all uploaded file paths
            uploaded_files = [
                call_args[1]["filename"]
                for call_args in mock_upload.call_args_list
            ]
            
            # Convert to relative paths
            uploaded_relative = [
                str(pathlib.Path(f).relative_to(temp_source_dir))
                for f in uploaded_files
            ]
            
            # Check that .txt files were NOT uploaded (from .gitignore)
            assert not any(".txt" in f for f in uploaded_relative)
            
            # Check that src/ directory was NOT uploaded (from .gitignore)
            assert not any(f.startswith("src") for f in uploaded_relative)
            
            # Check that .py files were uploaded
            assert any("app.py" in f for f in uploaded_relative)

    def test_upload_with_dockerignore(
        self, temp_source_dir, mock_bucket
    ):
        """Test upload respects .dockerignore file."""
        # Create .dockerignore file
        dockerignore = temp_source_dir / ".dockerignore"
        dockerignore.write_text("*.md\nREADME*")
        
        with patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils._get_bucket_instance",
            return_value=mock_bucket,
        ), patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils.oss2.resumable_upload"
        ) as mock_upload:
            result = upload(
                source_path=str(temp_source_dir),
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
            )
            
            # Get all uploaded file paths
            uploaded_files = [
                call_args[1]["filename"]
                for call_args in mock_upload.call_args_list
            ]
            
            # Convert to relative paths
            uploaded_relative = [
                str(pathlib.Path(f).relative_to(temp_source_dir))
                for f in uploaded_files
            ]
            
            # Check that .md files were NOT uploaded (from .dockerignore)
            assert not any(".md" in f for f in uploaded_relative)

    def test_upload_non_existing_source(self):
        """Test upload with non-existing source path."""
        with pytest.raises(ValueError, match="Source path is not exist"):
            upload(
                source_path="/non/existing/path",
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
            )

    def test_upload_file_instead_of_directory(self, tmp_path):
        """Test upload with a file instead of a directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        with pytest.raises(ValueError, match="Source path is not a directory"):
            upload(
                source_path=str(test_file),
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
            )

    def test_upload_trailing_slash_handling(
        self, temp_source_dir, mock_bucket
    ):
        """Test that OSS URI trailing slash is handled correctly."""
        with patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils._get_bucket_instance",
            return_value=mock_bucket,
        ), patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils.oss2.resumable_upload"
        ):
            # Test without trailing slash
            result1 = upload(
                source_path=str(temp_source_dir),
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
            )
            
            # Test with trailing slash
            result2 = upload(
                source_path=str(temp_source_dir),
                oss_uri="oss://test-bucket/upload/path/",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
            )
            
            # Both should return the same result with trailing slash
            assert result1 == result2
            assert result1.endswith("/")

    def test_upload_empty_directory(self, tmp_path, mock_bucket):
        """Test upload with empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        with patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils._get_bucket_instance",
            return_value=mock_bucket,
        ), patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils.oss2.resumable_upload"
        ) as mock_upload:
            result = upload(
                source_path=str(empty_dir),
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
            )
            
            # No files should be uploaded
            assert mock_upload.call_count == 0
            # But function should still return success
            assert result == "oss://test-bucket/upload/path/"

    def test_upload_ignore_patterns_combination(
        self, temp_source_dir, mock_bucket
    ):
        """Test that default, .gitignore, .dockerignore, and custom patterns are combined."""
        # Create both ignore files
        gitignore = temp_source_dir / ".gitignore"
        gitignore.write_text("*.txt")
        
        dockerignore = temp_source_dir / ".dockerignore"
        dockerignore.write_text("*.md")
        
        with patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils._get_bucket_instance",
            return_value=mock_bucket,
        ), patch(
            "agentscope_runtime.engine.deployers.utils.oss_utils.oss2.resumable_upload"
        ) as mock_upload:
            result = upload(
                source_path=str(temp_source_dir),
                oss_uri="oss://test-bucket/upload/path",
                oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
                access_key_id="test_key_id",
                access_key_secret="test_key_secret",
                exclude_file_patterns=["*.log"],
            )
            
            # Get all uploaded file paths
            uploaded_files = [
                call_args[1]["filename"]
                for call_args in mock_upload.call_args_list
            ]
            
            # Convert to relative paths
            uploaded_relative = [
                str(pathlib.Path(f).relative_to(temp_source_dir))
                for f in uploaded_files
            ]
            
            # All ignore patterns should be respected
            assert not any(".txt" in f for f in uploaded_relative)  # .gitignore
            assert not any(".md" in f for f in uploaded_relative)   # .dockerignore
            assert not any(".log" in f for f in uploaded_relative)  # custom
            assert not any(".venv" in f for f in uploaded_relative)  # default
            assert not any("__pycache__" in f for f in uploaded_relative)  # default
            
            # Only .py files should be uploaded
            assert any("app.py" in f for f in uploaded_relative)

