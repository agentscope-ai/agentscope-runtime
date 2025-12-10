# -*- coding: utf-8 -*-
"""
Build cache management with content-aware hashing.

This module provides workspace-based build caching to speed up repeated
deployments during local development by detecting unchanged content and
reusing existing build artifacts.
"""

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BuildCache:
    """
    Manages workspace-based build cache with content hashing.

    The cache uses content-aware hashing to automatically detect when project
    code, requirements, or runtime version haven't changed, allowing for
    reuse of existing build artifacts.

    Cache structure:
        <workspace>/.agentscope_runtime/
        └── builds/
            ├── k8s_20251205_1430_a3f9e2/     # platform_timestamp_code
            │   ├── deployment.zip
            │   ├── Dockerfile
            │   └── requirements.txt
            └── modelstudio_20251205_1445_b7c4d1/
                └── *.whl

    Deployment metadata is tracked in deployments.json for cache validation.
    """

    def __init__(self, workspace: Optional[Path] = None):
        """
        Initialize BuildCache.

        Args:
            workspace: Workspace directory (defaults to cwd or
                      AGENTSCOPE_RUNTIME_WORKSPACE env var)
        """
        if workspace is None:
            workspace_str = os.getenv(
                "AGENTSCOPE_RUNTIME_WORKSPACE",
                os.getcwd(),
            )
            workspace = Path(workspace_str)

        self.workspace = Path(workspace).resolve()
        self.cache_root = self.workspace / ".agentscope_runtime" / "builds"
        self.cache_root.mkdir(parents=True, exist_ok=True)

        # Deployment metadata file for tracking cache mappings
        self.metadata_file = (
            self.workspace / ".agentscope_runtime" / "deployments.json"
        )

        logger.debug(f"BuildCache initialized at: {self.cache_root}")

    def _generate_build_name(self, platform: str, content_hash: str) -> str:
        """
        Generate human-readable build directory name.

        Format: {platform}_{YYYYMMDD_HHMM}_{6-char-code}
        Example: k8s_20251205_1430_a3f9e2

        Args:
            platform: Deployment platform (k8s, modelstudio, agentrun, local)
            content_hash: Full content hash for generating 6-char code

        Returns:
            Build directory name
        """
        # Timestamp to minute precision
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        # 6-character code from content hash
        code = content_hash[:6]

        return f"{platform}_{timestamp}_{code}"

    def _load_metadata(self) -> Dict:
        """Load deployment metadata from JSON file."""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load metadata: {e}")
            return {}

    def _save_metadata(self, metadata: Dict) -> None:
        """Save deployment metadata to JSON file."""
        try:
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save metadata: {e}")

    def lookup(
        self,
        project_dir: str,
        entrypoint_file: str,
        requirements: List[str],
        use_local_runtime: bool = False,
        platform: str = "unknown",
    ) -> Optional[Path]:
        """
        Look up cached build by content hash.

        Args:
            project_dir: Absolute path to project directory
            entrypoint_file: Relative path to entrypoint file
            requirements: List of pip requirements
            use_local_runtime: Whether using local runtime (dev mode)
            platform: Deployment platform (k8s, modelstudio, agentrun, local)

        Returns:
            Path to cached build directory if valid cache exists, No otherwise
        """
        # Calculate content hash
        build_hash = self._calculate_build_hash(
            project_dir,
            entrypoint_file,
            requirements,
            use_local_runtime,
        )

        # Load metadata to find build directory
        metadata = self._load_metadata()

        # Look for existing build with matching hash
        for build_name, build_info in metadata.items():
            if build_info.get("content_hash") == build_hash:
                cache_dir = self.cache_root / build_name

                if not cache_dir.exists():
                    logger.warning(
                        f"Cached build referenced in metadata"
                        f" but not found: {build_name}",
                    )
                    continue

                # Validate cache integrity
                if not self._validate_cache(cache_dir):
                    logger.warning(f"Cache corrupted: {build_name}")
                    try:
                        shutil.rmtree(cache_dir)
                    except Exception as e:
                        logger.warning(f"Failed to clean corrupted cache: {e}")
                    continue

                logger.info(f"✓ Cache hit: {build_name}")
                return cache_dir

        logger.info(f"Cache miss: {build_hash[:8]} (platform: {platform})")
        return None

    def store(
        self,
        project_dir: str,
        entrypoint_file: str,
        requirements: List[str],
        build_path: Path,
        use_local_runtime: bool = False,
        platform: str = "unknown",
    ) -> str:
        """
        Store build in cache with platform-aware naming.

        Args:
            project_dir: Absolute path to project directory
            entrypoint_file: Relative path to entrypoint file
            requirements: List of pip requirements
            build_path: Path to build directory to cache
            use_local_runtime: Whether using local runtime (dev mode)
            platform: Deployment platform (k8s, modelstudio, agentrun, local)

        Returns:
            Build directory name
        """
        # Calculate content hash
        build_hash = self._calculate_build_hash(
            project_dir,
            entrypoint_file,
            requirements,
            use_local_runtime,
        )

        # Generate human-readable build name
        build_name = self._generate_build_name(platform, build_hash)
        cache_dir = self.cache_root / build_name

        # Load metadata
        metadata = self._load_metadata()

        # Check if build_path is already the cache_dir (built in place)
        build_path_resolved = Path(build_path).resolve()
        cache_dir_resolved = cache_dir.resolve()

        if build_path_resolved == cache_dir_resolved:
            # Already built in cache directory, just save metadata
            logger.debug(f"Build already in cache location: {build_name}")

            # Update metadata
            metadata[build_name] = {
                "content_hash": build_hash,
                "platform": platform,
                "project_dir": project_dir,
                "entrypoint": entrypoint_file,
                "created_at": datetime.now().isoformat(),
                "requirements": requirements,
            }
            self._save_metadata(metadata)
            return build_name

        # If cache already exists with same hash, no need to store again
        if build_name in metadata and cache_dir.exists():
            logger.info(f"Build already cached: {build_name}")
            return build_name

        # Copy build to cache
        try:
            shutil.copytree(build_path, cache_dir, dirs_exist_ok=False)
            logger.info(f"Build cached: {build_name}")

            # Update metadata
            metadata[build_name] = {
                "content_hash": build_hash,
                "platform": platform,
                "project_dir": project_dir,
                "entrypoint": entrypoint_file,
                "created_at": datetime.now().isoformat(),
                "requirements": requirements,
            }
            self._save_metadata(metadata)

        except Exception as e:
            logger.error(f"Failed to cache build: {e}")
            # Clean up partial cache
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                except Exception:
                    logger.warning(
                        f"Failed to remove cache build, {cache_dir} with error"
                        f" {e}",
                    )
            raise

        return build_name

    def invalidate_all(self) -> None:
        """Remove all cached builds (simple cleanup)."""
        if self.cache_root.exists():
            try:
                shutil.rmtree(self.cache_root)
                logger.info(f"All caches invalidated: {self.cache_root}")
                # Recreate cache root
                self.cache_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to invalidate caches: {e}")
                raise

    def _calculate_build_hash(
        self,
        project_dir: str,
        entrypoint_file: str,
        requirements: List[str],
        use_local_runtime: bool,
    ) -> str:
        """
        Calculate content hash for build cache lookup.

        Hash is based on:
        - User project code (excluding temp files)
        - Requirements list
        - AgentScope-runtime version:
          - Released version: Use version number
          - Dev version: Hash of runtime source code

        Args:
            project_dir: Absolute path to project directory
            entrypoint_file: Relative path to entrypoint file
            requirements: List of pip requirements
            use_local_runtime: Whether using local runtime (dev mode)

        Returns:
            12-character hex string
        """
        from .detached_app import (
            _get_package_version,
            _get_runtime_source_path,
        )

        hash_parts = []

        # 1. User project code (excluding temp files)
        project_hash = self._hash_directory(
            Path(project_dir),
            self._get_ignore_patterns(),
        )
        hash_parts.append(f"project:{project_hash}")

        # 2. Entrypoint file
        hash_parts.append(f"entry:{entrypoint_file}")

        # 3. Requirements
        req_string = "\n".join(sorted(requirements))
        req_hash = hashlib.sha256(req_string.encode()).hexdigest()[:8]
        hash_parts.append(f"req:{req_hash}")

        # 4. AgentScope-runtime version
        if use_local_runtime:
            # Dev mode: hash runtime source code
            runtime_source = _get_runtime_source_path()
            if runtime_source:
                runtime_hash = self._hash_directory(
                    runtime_source / "src",
                    self._get_ignore_patterns(),
                )
                hash_parts.append(f"runtime-dev:{runtime_hash[:8]}")
            else:
                # Fallback if source not found
                hash_parts.append("runtime-dev:unknown")
        else:
            # Released mode: use version number
            version = _get_package_version()
            hash_parts.append(f"runtime:{version}")

        # Combine and hash
        combined = "-".join(hash_parts)
        final_hash = hashlib.sha256(combined.encode()).hexdigest()[:12]

        logger.debug(f"Calculated build hash: {final_hash}")
        logger.debug(f"Hash components: {combined}")

        return final_hash

    def _hash_directory(
        self,
        path: Path,
        ignore_patterns: List[str],
    ) -> str:
        """
        Calculate hash of directory contents.

        Includes:
        - File paths (relative to directory)
        - File contents
        - File mtimes (for quick detection)

        Excludes:
        - Files matching ignore patterns
        - Empty directories

        Args:
            path: Directory path to hash
            ignore_patterns: List of ignore patterns

        Returns:
            16-character hex string
        """
        hasher = hashlib.sha256()

        if not path.exists():
            logger.warning(f"Directory not found for hashing: {path}")
            return "notfound"

        try:
            for root, dirs, files in sorted(os.walk(path)):
                # Filter ignored directories (in-place)
                dirs[:] = [
                    d
                    for d in sorted(dirs)
                    if not self._should_ignore(d, ignore_patterns)
                ]

                for filename in sorted(files):
                    filepath = Path(root) / filename

                    try:
                        rel_path = filepath.relative_to(path)
                    except ValueError:
                        # Skip files outside the base path
                        continue

                    if self._should_ignore(str(rel_path), ignore_patterns):
                        continue

                    # Hash: relative path + mtime + content
                    hasher.update(str(rel_path).encode())

                    try:
                        stat = filepath.stat()
                        hasher.update(str(stat.st_mtime).encode())

                        with open(filepath, "rb") as f:
                            hasher.update(f.read())
                    except (OSError, IOError) as e:
                        # Skip files that can't be read
                        logger.debug(
                            f"Skipping unreadable file {filepath}: {e}",
                        )
                        continue

        except Exception as e:
            logger.error(f"Error hashing directory {path}: {e}")
            return "error"

        return hasher.hexdigest()[:16]

    def _should_ignore(self, path: str, patterns: List[str]) -> bool:
        """
        Check if path should be ignored based on patterns.

        Args:
            path: Path to check (relative)
            patterns: List of ignore patterns

        Returns:
            True if path should be ignored
        """
        path_parts = Path(path).parts

        for pattern in patterns:
            # Check if any part of the path matches the pattern
            if pattern in path_parts:
                return True

            # Check wildcard patterns
            if "*" in pattern:
                import fnmatch

                if fnmatch.fnmatch(path, pattern):
                    return True
                # Also check each part
                for part in path_parts:
                    if fnmatch.fnmatch(part, pattern):
                        return True

        return False

    def _get_ignore_patterns(self) -> List[str]:
        """
        Get ignore patterns for directory hashing.

        Returns:
            List of ignore patterns
        """
        return [
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".git",
            ".gitignore",
            ".pytest_cache",
            ".mypy_cache",
            ".tox",
            "venv",
            "env",
            ".venv",
            ".env",
            "node_modules",
            ".DS_Store",
            "*.egg-info",
            "build",
            "dist",
            ".cache",
            "*.swp",
            "*.swo",
            "*~",
            ".idea",
            ".vscode",
            "*.log",
            "logs",
            ".agentscope_runtime",  # Don't hash cache itself
        ]

    def lookup_wrapper(
        self,
        project_dir: str,
        cmd: str,
        platform: str = "wrapper",
    ) -> Optional[Path]:
        """
        Look up cached wrapper project build by content hash.

        Args:
            project_dir: Absolute path to project directory
            cmd: Start command for the wrapper
            platform: Deployment platform (modelstudio, agentrun)

        Returns:
            Path to cached directory if valid cache exists, No otherwise
        """
        # Calculate content hash for wrapper
        build_hash = self._calculate_wrapper_hash(project_dir, cmd)

        # Load metadata to find wrapper build
        metadata = self._load_metadata()

        # Look for existing wrapper build with matching hash
        for build_name, build_info in metadata.items():
            if (
                build_info.get("content_hash") == build_hash
                and build_info.get("type") == "wrapper"
            ):
                cache_dir = self.cache_root / build_name

                if not cache_dir.exists():
                    logger.warning(
                        f"Cached wrapper referenced in metadata but not "
                        f"found: {build_name}",
                    )
                    continue

                # Validate cache integrity for wrapper (check for wheel file)
                if not self._validate_wrapper_cache(cache_dir):
                    logger.warning(f"Wrapper cache corrupted: {build_name}")
                    try:
                        shutil.rmtree(cache_dir)
                    except Exception as e:
                        logger.warning(
                            f"Failed to clean corrupted wrapper cache: {e}",
                        )
                    continue

                logger.info(f"✓ Wrapper cache hit: {build_name}")
                return cache_dir

        logger.info(
            f"Wrapper cache miss: {build_hash[:8]} (platform: {platform})",
        )
        return None

    def store_wrapper(
        self,
        project_dir: str,
        cmd: str,
        wrapper_dir: Path,
        platform: str = "wrapper",
    ) -> str:
        """
        Store wrapper project build in cache with platform-aware naming.

        Args:
            project_dir: Absolute path to project directory
            cmd: Start command for the wrapper
            wrapper_dir: Path to wrapper build directory to cache
            platform: Deployment platform (modelstudio, agentrun)

        Returns:
            Build directory name
        """
        # Calculate content hash
        build_hash = self._calculate_wrapper_hash(project_dir, cmd)

        # Generate human-readable build name
        build_name = self._generate_build_name(platform, build_hash)
        cache_dir = self.cache_root / build_name

        # Load metadata
        metadata = self._load_metadata()

        # Check if wrapper_dir is already the cache_dir (built in place)
        wrapper_dir_resolved = Path(wrapper_dir).resolve()
        cache_dir_resolved = cache_dir.resolve()

        if wrapper_dir_resolved == cache_dir_resolved:
            # Already built in cache directory, just save metadata
            logger.debug(f"Wrapper already in cache location: {build_name}")

            # Update metadata
            metadata[build_name] = {
                "content_hash": build_hash,
                "type": "wrapper",
                "platform": platform,
                "project_dir": project_dir,
                "cmd": cmd,
                "created_at": datetime.now().isoformat(),
            }
            self._save_metadata(metadata)
            return build_name

        # If cache already exists with same hash, no need to store again
        if build_name in metadata and cache_dir.exists():
            logger.info(f"Wrapper build already cached: {build_name}")
            return build_name

        # Copy wrapper to cache
        try:
            shutil.copytree(wrapper_dir, cache_dir, dirs_exist_ok=False)
            logger.info(f"Wrapper build cached: {build_name}")

            # Update metadata
            metadata[build_name] = {
                "content_hash": build_hash,
                "type": "wrapper",
                "platform": platform,
                "project_dir": project_dir,
                "cmd": cmd,
                "created_at": datetime.now().isoformat(),
            }
            self._save_metadata(metadata)

        except Exception as e:
            logger.error(f"Failed to cache wrapper build: {e}")
            # Clean up partial cache
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                except Exception:
                    logger.warning(
                        f"Failed to remove cache directory "
                        f"{cache_dir} with error: {e}",
                    )

            raise RuntimeError(
                f"Failed to store cache directory {cache_dir}:" f" {e}",
            ) from e

        return build_name

    def _calculate_wrapper_hash(
        self,
        project_dir: str,
        cmd: str,
    ) -> str:
        """
        Calculate content hash for wrapper project cache lookup.

        Hash is based on:
        - User project code (excluding temp files)
        - Start command

        Args:
            project_dir: Absolute path to project directory
            cmd: Start command for the wrapper

        Returns:
            12-character hex string
        """
        hash_parts = []

        # 1. User project code (excluding temp files)
        project_hash = self._hash_directory(
            Path(project_dir),
            self._get_ignore_patterns(),
        )
        hash_parts.append(f"project:{project_hash}")

        # 2. Start command
        cmd_hash = hashlib.sha256(cmd.encode()).hexdigest()[:8]
        hash_parts.append(f"cmd:{cmd_hash}")

        # Combine and hash
        combined = "-".join(hash_parts)
        final_hash = hashlib.sha256(combined.encode()).hexdigest()[:12]

        logger.debug(f"Calculated wrapper hash: {final_hash}")
        logger.debug(f"Hash components: {combined}")

        return final_hash

    def _validate_wrapper_cache(self, cache_dir: Path) -> bool:
        """
        Validate wrapper cache integrity.

        Args:
            cache_dir: Cache directory to validate

        Returns:
            True if cache is valid
        """
        # Check if any wheel file exists
        wheel_files = list(cache_dir.glob("*.whl"))

        if not wheel_files:
            logger.warning(
                "Wrapper cache validation failed: no wheel file found",
            )
            return False

        # Check wheel file is not empty
        for wheel_file in wheel_files:
            if wheel_file.stat().st_size == 0:
                logger.warning(
                    f"Wrapper cache validation failed: {wheel_file.name} is "
                    f"empty",
                )
                return False

        return True

    def _validate_cache(self, cache_dir: Path) -> bool:
        """
        Validate cache integrity.

        Args:
            cache_dir: Cache directory to validate

        Returns:
            True if cache is valid
        """
        # Check required files exist
        required_files = ["deployment.zip"]

        for required_file in required_files:
            file_path = cache_dir / required_file
            if not file_path.exists():
                logger.warning(
                    f"Cache validation failed: missing {required_file}",
                )
                return False

            # Check file is not empty
            if file_path.stat().st_size == 0:
                logger.warning(
                    f"Cache validation failed: {required_file} is empty",
                )
                return False

        return True
