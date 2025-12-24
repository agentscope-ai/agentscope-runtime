# -*- coding: utf-8 -*-
"""Tests for build cache functionality."""
# pylint:disable=protected-access, redefined-outer-name

import tempfile
from pathlib import Path

import pytest

from agentscope_runtime.engine.deployers.utils.build_cache import BuildCache


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_project():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create a simple project structure
        (project_dir / "app.py").write_text("print('hello')")
        (project_dir / "requirements.txt").write_text("requests==2.31.0")

        yield project_dir


class TestBuildCache:
    """Test BuildCache functionality."""

    def test_cache_initialization(self, temp_workspace):
        """Test that cache initializes correctly."""
        cache = BuildCache(workspace=temp_workspace)

        assert cache.workspace.resolve() == temp_workspace.resolve()
        assert (
            cache.cache_root
            == cache.workspace / ".agentscope_runtime" / "builds"
        )
        assert cache.cache_root.exists()

    def test_cache_initialization_with_env_var(
        self,
        temp_workspace,
        monkeypatch,
    ):
        """Test cache initialization with environment variable."""
        monkeypatch.setenv("AGENTSCOPE_RUNTIME_WORKSPACE", str(temp_workspace))

        cache = BuildCache()

        assert cache.workspace.resolve() == temp_workspace.resolve()
        assert (
            cache.cache_root
            == cache.workspace / ".agentscope_runtime" / "builds"
        )

    def test_cache_miss(self, temp_workspace, temp_project):
        """Test cache miss returns None."""
        cache = BuildCache(workspace=temp_workspace)

        result = cache.lookup(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        assert result is None

    def test_cache_hit(self, temp_workspace, temp_project):
        """Test cache hit returns cached directory."""
        cache = BuildCache(workspace=temp_workspace)

        # Create a fake build directory
        build_hash = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        cache_dir = cache.cache_root / build_hash
        cache_dir.mkdir(parents=True)

        # Create required files
        (cache_dir / "deployment.zip").write_text("fake zip content")

        # Add metadata entry
        metadata = cache._load_metadata()
        metadata[build_hash] = {
            "content_hash": build_hash,
            "type": "build",
            "timestamp": "2024-01-01T00:00:00",
        }
        cache._save_metadata(metadata)

        # Lookup should find the cache
        result = cache.lookup(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        assert result is not None
        assert result == cache_dir

    def test_cache_corrupted(self, temp_workspace, temp_project):
        """Test that corrupted cache is detected and removed."""
        cache = BuildCache(workspace=temp_workspace)

        # Create a fake build directory without required files
        build_hash = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        cache_dir = cache.cache_root / build_hash
        cache_dir.mkdir(parents=True)

        # Don't create deployment.zip - cache is corrupted

        # Add metadata entry
        metadata = cache._load_metadata()
        metadata[build_hash] = {
            "content_hash": build_hash,
            "type": "build",
            "timestamp": "2024-01-01T00:00:00",
        }
        cache._save_metadata(metadata)

        # Lookup should detect corruption and return None
        result = cache.lookup(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        assert result is None
        # Corrupted cache should be cleaned up
        assert not cache_dir.exists()

    def test_hash_consistency(self, temp_workspace, temp_project):
        """Test that hash calculation is consistent."""
        cache = BuildCache(workspace=temp_workspace)

        hash1 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        hash2 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        assert hash1 == hash2

    def test_hash_changes_with_code(self, temp_workspace, temp_project):
        """Test that hash changes when code changes."""
        cache = BuildCache(workspace=temp_workspace)

        hash1 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        # Modify code
        (temp_project / "app.py").write_text("print('hello world')")

        hash2 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        assert hash1 != hash2

    def test_hash_changes_with_requirements(
        self,
        temp_workspace,
        temp_project,
    ):
        """Test that hash changes when requirements change."""
        cache = BuildCache(workspace=temp_workspace)

        hash1 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        hash2 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.32.0"],  # Different version
            use_local_runtime=False,
        )

        assert hash1 != hash2

    def test_hash_changes_with_entrypoint(self, temp_workspace, temp_project):
        """Test that hash changes when entrypoint changes."""
        cache = BuildCache(workspace=temp_workspace)

        # Create another file
        (temp_project / "main.py").write_text("print('main')")

        hash1 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        hash2 = cache._calculate_build_hash(
            str(temp_project),
            "main.py",  # Different entrypoint
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        assert hash1 != hash2

    def test_ignore_patterns(self, temp_workspace, temp_project):
        """Test that ignore patterns work correctly."""
        cache = BuildCache(workspace=temp_workspace)

        # Calculate initial hash
        hash1 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        # Add files that should be ignored
        (temp_project / "__pycache__").mkdir()
        (temp_project / "__pycache__" / "app.pyc").write_text("compiled")
        (temp_project / "test.pyc").write_text("compiled")
        (temp_project / ".git").mkdir()
        (temp_project / ".git" / "config").write_text("git config")

        # Hash should be the same
        hash2 = cache._calculate_build_hash(
            str(temp_project),
            "app.py",
            ["requests==2.31.0"],
            use_local_runtime=False,
        )

        assert hash1 == hash2

    def test_store_cache(self, temp_workspace, temp_project):
        """Test storing a build in cache."""
        cache = BuildCache(workspace=temp_workspace)

        # Create a fake build directory
        with tempfile.TemporaryDirectory() as build_dir:
            build_path = Path(build_dir)
            (build_path / "deployment.zip").write_text("fake zip content")
            (build_path / "requirements.txt").write_text("requests==2.31.0")

            # Store in cache
            build_hash = cache.store(
                str(temp_project),
                "app.py",
                ["requests==2.31.0"],
                build_path,
                use_local_runtime=False,
            )

            # Verify cache exists
            cache_dir = cache.cache_root / build_hash
            assert cache_dir.exists()
            assert (cache_dir / "deployment.zip").exists()
            assert (cache_dir / "requirements.txt").exists()

    def test_invalidate_all(self, temp_workspace):
        """Test invalidating all caches."""
        cache = BuildCache(workspace=temp_workspace)

        # Create some fake caches
        (cache.cache_root / "hash1").mkdir(parents=True)
        (cache.cache_root / "hash1" / "deployment.zip").write_text("fake")
        (cache.cache_root / "hash2").mkdir(parents=True)
        (cache.cache_root / "hash2" / "deployment.zip").write_text("fake")

        # Invalidate all
        cache.invalidate_all()

        # Verify all caches removed
        assert cache.cache_root.exists()  # Root should still exist
        assert len(list(cache.cache_root.iterdir())) == 0

    def test_directory_hashing(self, temp_workspace):
        """Test directory hashing functionality."""
        cache = BuildCache(workspace=temp_workspace)

        # Create a test directory
        test_dir = temp_workspace / "test_dir"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")

        hash1 = cache._hash_directory(test_dir, [])

        # Hash should be consistent
        hash2 = cache._hash_directory(test_dir, [])
        assert hash1 == hash2

        # Modify content
        (test_dir / "file1.txt").write_text("modified")
        hash3 = cache._hash_directory(test_dir, [])
        assert hash1 != hash3

    def test_should_ignore(self, temp_workspace):
        """Test ignore pattern matching."""
        cache = BuildCache(workspace=temp_workspace)

        patterns = cache._get_ignore_patterns()

        # Test specific patterns
        assert cache._should_ignore("__pycache__/file.pyc", patterns)
        assert cache._should_ignore("test.pyc", patterns)
        assert cache._should_ignore(".git/config", patterns)
        assert cache._should_ignore("venv/lib/python", patterns)

        # Test non-ignored files
        assert not cache._should_ignore("app.py", patterns)
        assert not cache._should_ignore("requirements.txt", patterns)

    def test_cache_validation(self, temp_workspace):
        """Test cache validation logic."""
        cache = BuildCache(workspace=temp_workspace)

        # Create valid cache
        cache_dir = temp_workspace / "valid_cache"
        cache_dir.mkdir()
        (cache_dir / "deployment.zip").write_text("content")

        assert cache._validate_cache(cache_dir)

        # Create invalid cache (empty file)
        invalid_cache_dir = temp_workspace / "invalid_cache"
        invalid_cache_dir.mkdir()
        (invalid_cache_dir / "deployment.zip").write_text("")

        assert not cache._validate_cache(invalid_cache_dir)

        # Create invalid cache (missing file)
        missing_cache_dir = temp_workspace / "missing_cache"
        missing_cache_dir.mkdir()

        assert not cache._validate_cache(missing_cache_dir)
