# -*- coding: utf-8 -*-
# flake8: noqa: E501
# flake8: noqa: E541
# -*- coding: utf-8 -*-
# pylint: disable=unused-variable, f-string-without-interpolation
# pylint: disable=line-too-long, too-many-branches
"""
Utilities for packaging a local Python project into a distributable wheel
that can be uploaded and deployed by various deployers.

This module extracts and generalizes logic from the legacy test script
`tests/integrated/test_bailian_fc_deploy/deploy_builder.py` so that
production deployers can reuse the behaviour in a structured way.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import List, Tuple

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - fallback on older Pythons
    tomllib = None  # type: ignore


def _read_text_file_lines(file_path: Path) -> List[str]:
    if not file_path.is_file():
        return []
    return [
        line.strip()
        for line in file_path.read_text(encoding="utf-8").splitlines()
    ]


def _parse_requirements_txt(req_path: Path) -> Tuple[List[str], List[str]]:
    """
    Parse requirements.txt, separating standard requirements from local wheel paths.

    Returns:
        Tuple of (standard_requirements, local_wheel_paths)
    """
    standard_requirements: List[str] = []
    local_wheel_paths: List[str] = []

    for line in _read_text_file_lines(req_path):
        if not line or line.startswith("#"):
            continue

        # Check if this is a local wheel file path
        if line.endswith(".whl") and (
            "/" in line or "\\" in line or line.startswith(".")
        ):
            local_wheel_paths.append(line)
        else:
            standard_requirements.append(line)

    return standard_requirements, local_wheel_paths


def _parse_pyproject_toml(pyproject_path: Path) -> List[str]:
    deps: List[str] = []
    if not pyproject_path.is_file():
        return deps
    text = pyproject_path.read_text(encoding="utf-8")

    try:
        # Prefer stdlib tomllib (Python 3.11+)
        if tomllib is None:
            raise RuntimeError("tomllib not available")
        data = tomllib.loads(text)
        # PEP 621
        proj = data.get("project") or {}
        deps.extend(proj.get("dependencies") or [])
        # Poetry fallback
        poetry = (data.get("tool") or {}).get("poetry") or {}
        poetry_deps = poetry.get("dependencies") or {}
        for name, spec in poetry_deps.items():
            if name.lower() == "python":
                continue
            if isinstance(spec, str):
                deps.append(f"{name}{spec if spec.strip() else ''}")
            elif isinstance(spec, dict):
                version = spec.get("version")
                if version:
                    deps.append(f"{name}{version}")
                else:
                    deps.append(name)
    except Exception:
        # Minimal non-toml parser fallback: try to extract a dependencies = [ ... ] list
        block_match = re.search(
            r"dependencies\s*=\s*\[(.*?)\]",
            text,
            re.S | re.I,
        )
        if block_match:
            block = block_match.group(1)
            for m in re.finditer(r"['\"]([^'\"]+)['\"]", block):
                deps.append(m.group(1))
        # Poetry fallback: very limited, heuristic
        poetry_block = re.search(
            r"\[tool\.poetry\.dependencies\](.*?)\n\[",
            text,
            re.S,
        )
        if poetry_block:
            for line in poetry_block.group(1).splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    # name = "^1.2.3"
                    m = re.match(
                        r"([A-Za-z0-9_.-]+)\s*=\s*['\"]([^'\"]+)['\"]",
                        line,
                    )
                    if m and m.group(1).lower() != "python":
                        deps.append(f"{m.group(1)}{m.group(2)}")
                else:
                    # name without version
                    name = line.split("#")[0].strip()
                    if name and name.lower() != "python":
                        deps.append(name)
    return deps


def _gather_user_dependencies(
    project_dir: Path,
) -> Tuple[List[str], List[Path]]:
    """
    Gather user dependencies from pyproject.toml and requirements.txt.

    Returns:
        Tuple of (standard_dependencies, local_wheel_files)
        where local_wheel_files are absolute paths to wheel files
    """
    pyproject = project_dir / "pyproject.toml"
    req_txt = project_dir / "requirements.txt"
    deps: List[str] = []
    local_wheels: List[Path] = []

    if pyproject.is_file():
        dep = _parse_pyproject_toml(pyproject)
        deps.extend(dep)

    if req_txt.is_file():
        # Parse requirements.txt to separate standard deps from local wheels
        standard_reqs, local_wheel_paths = _parse_requirements_txt(req_txt)

        # Merge standard requirements, avoiding duplicates
        existing = set(
            d.split("[", 1)[0]
            .split("=", 1)[0]
            .split("<", 1)[0]
            .split(">", 1)[0]
            .strip()
            .lower()
            for d in deps
        )
        for r in standard_reqs:
            name_key = (
                r.split("[", 1)[0]
                .split("=", 1)[0]
                .split("<", 1)[0]
                .split(">", 1)[0]
                .strip()
                .lower()
            )
            if name_key not in existing:
                deps.append(r)

        # Process local wheel paths - convert to absolute paths
        for wheel_path_str in local_wheel_paths:
            # Handle relative paths like ./wheels/xxx.whl or wheels/xxx.whl
            wheel_path = Path(wheel_path_str)
            if not wheel_path.is_absolute():
                wheel_path = (project_dir / wheel_path).resolve()

            if wheel_path.exists() and wheel_path.is_file():
                local_wheels.append(wheel_path)

    return deps, local_wheels


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform.startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _sanitize_name(name: str) -> str:
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_\-]", "", name)
    return name.lower()


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_wrapper_project(
    build_root: Path,
    user_project_dir: Path,
    start_cmd: str,
    deploy_name: str,
    telemetry_enabled: bool = True,
) -> Tuple[Path, Path]:
    """
    Create a wrapper project under build_root, embedding user project under
    user_bundle/<project_basename>. Returns: (wrapper_project_dir, dist_dir)
    """
    wrapper_dir = build_root

    # 1) Copy user project into wrapper under deploy_starter/user_bundle/<project_basename>
    # Put user code inside the deploy_starter package so wheel includes it and preserves project folder name
    project_basename = user_project_dir.name
    bundle_app_dir = (
        wrapper_dir / "deploy_starter" / "user_bundle" / project_basename
    )
    ignore = shutil.ignore_patterns(
        ".git",
        ".venv",
        ".venv_build",
        ".agentdev_builds",
        ".agentscope_runtime_builds",
        "__pycache__",
        "dist",
        "build",
        "*.pyc",
        ".mypy_cache",
        ".pytest_cache",
    )
    shutil.copytree(
        user_project_dir,
        bundle_app_dir,
        dirs_exist_ok=True,
        ignore=ignore,
    )

    # 2) Dependencies
    _, local_wheels = _gather_user_dependencies(user_project_dir)

    # Copy local wheel files to wrapper project
    if local_wheels:
        wheels_dir = wrapper_dir / "deploy_starter" / "wheels"
        wheels_dir.mkdir(parents=True, exist_ok=True)
        for wheel_file in local_wheels:
            dest = wheels_dir / wheel_file.name
            shutil.copy2(wheel_file, dest)

    wrapper_deps = [
        "pyyaml",
        "alibabacloud-oss-v2",
        "alibabacloud-bailian20231229>=2.6.0",
        "alibabacloud-agentrun20250910>=2.0.1",
        "alibabacloud-credentials",
        "alibabacloud-tea-openapi",
        "alibabacloud-tea-util",
        "python-dotenv",
        "jinja2",
        "psutil",
    ]
    # De-duplicate while preserving order
    seen = set()
    standard_reqs, local_wheel_paths = _parse_requirements_txt(
        user_project_dir / "requirements.txt",
    )

    install_requires: List[str] = []
    for pkg in wrapper_deps + standard_reqs:
        key = pkg.strip().lower()
        if key and key not in seen:
            seen.add(key)
            install_requires.append(pkg)

    req_content = "\n".join(install_requires) + "\n"
    req_content += "\n".join(local_wheel_paths) + "\n"

    # 3) Packaging metadata
    unique_suffix = uuid.uuid4().hex[:8]
    package_name = f"agentscope_runtime_{unique_suffix}"
    version = f"0.1.{int(time.time())}"

    # 4) Template package: deploy_starter
    _write_file(wrapper_dir / "deploy_starter" / "__init__.py", "")

    main_py = f"""
import os
import subprocess
import sys
import yaml
from pathlib import Path
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore


def read_config():
    cfg_path = Path(__file__).with_name('config.yml')
    with cfg_path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {{}}


def install_local_wheels():
    \"\"\"Install local wheel files if they exist.\"\"\"
    wheels_dir = Path(__file__).resolve().parent / 'wheels'
    if wheels_dir.exists() and wheels_dir.is_dir():
        wheel_files = list(wheels_dir.glob('*.whl'))
        if wheel_files:
            print(f'[deploy_starter] Installing {{len(wheel_files)}} local wheel(s)...')
            for wheel in wheel_files:
                try:
                    subprocess.run(
                        ['pip', 'install', '--no-deps', str(wheel)],
                        check=True,
                        capture_output=True,
                    )
                    print(f'[deploy_starter] Installed: {{wheel.name}}')
                except subprocess.CalledProcessError as e:
                    print(f'[deploy_starter] Warning: Failed to install {{wheel.name}}: {{e}}', file=sys.stderr)


def main():
    # Install local wheels first
    install_local_wheels()

    cfg = read_config()
    subdir = cfg.get('APP_SUBDIR_NAME')
    if not subdir:
        print('APP_SUBDIR_NAME missing in config.yml', file=sys.stderr)
        sys.exit(1)
    workdir = Path(__file__).resolve().parent / 'user_bundle' / subdir
    cmd = cfg.get('CMD')
    if not cmd:
        print('CMD missing in config.yml', file=sys.stderr)
        sys.exit(1)

    if not workdir.is_dir():
        print(f'Workdir not found: {{workdir}}', file=sys.stderr)
        sys.exit(1)

    cmd_str = str(cmd).strip()
    if cmd_str.startswith('python '):
        cmd_str = f'"{{sys.executable}}" ' + cmd_str[len('python '):]
    elif cmd_str.startswith('python3 '):
        cmd_str = f'"{{sys.executable}}" ' + cmd_str[len('python3 '):]
    elif cmd_str.endswith('.py') and not cmd_str.startswith('"') and ' ' not in cmd_str.split()[0]:
        cmd_str = f'"{{sys.executable}}" ' + cmd_str

    print(f'[deploy_starter] Starting user service: "{{cmd_str}}" in {{workdir}}')

    # Load environment variables from user's bundle if present
    if load_dotenv is not None:
        for fname in ('.env', '.env.local'):
            env_file = workdir / fname
            if env_file.is_file():
                try:
                    load_dotenv(dotenv_path=env_file, override=False)
                except Exception:
                    pass

    env = os.environ.copy()
    process = subprocess.Popen(cmd_str, cwd=str(workdir), shell=True, env=env)

    try:
        return_code = process.wait()
        sys.exit(return_code)
    except KeyboardInterrupt:
        try:
            process.terminate()
        except Exception:
            pass
        try:
            process.wait(timeout=10)
        except Exception:
            process.kill()
        sys.exit(0)


if __name__ == '__main__':
    main()
"""
    _write_file(wrapper_dir / "deploy_starter" / "main.py", main_py)

    config_yml = f"""
APP_NAME: "{deploy_name}"
DEBUG: false

HOST: "0.0.0.0"
PORT: 8080
RELOAD: true

LOG_LEVEL: "INFO"

SETUP_PACKAGE_NAME: "{package_name}"
SETUP_MODULE_NAME: "main"
SETUP_FUNCTION_NAME: "main"
SETUP_COMMAND_NAME: "agentdev-starter"
SETUP_NAME: "agentDev-starter"
SETUP_VERSION: "{version}"
SETUP_DESCRIPTION: "agentDev-starter"
SETUP_LONG_DESCRIPTION: "agentDev-starter services, supporting both direct execution and uvicorn deployment"

FC_RUN_CMD: "python3 /code/python/deploy_starter/main.py"

TELEMETRY_ENABLE: {'true' if telemetry_enabled else 'false'}
CMD: "{start_cmd}"
APP_SUBDIR_NAME: "{project_basename}"
"""
    _write_file(wrapper_dir / "deploy_starter" / "config.yml", config_yml)

    setup_py = f"""
from setuptools import setup, find_packages
import os
import subprocess
import sys
from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.install import install

def run():
    # Step 1: Install all .whl files in the ./wheel/ directory (relative to setup.py)
    wheel_dir = Path(__file__).parent / "wheel"
    if wheel_dir.is_dir():
        whl_files = sorted(wheel_dir.glob("*.whl"))
        if whl_files:
            for whl in whl_files:
                # Use the same Python interpreter to avoid env issues
                subprocess.check_call([sys.executable, "-m", "pip", "install", str(whl)])


setup(
    name='{package_name}',
    version='{version}',
    packages=find_packages(),
    include_package_data=True,
    install_requires={install_requires!r},
)
"""
    _write_file(wrapper_dir / "setup.py", setup_py)

    manifest_in = """
recursive-include deploy_starter *.yml
recursive-include deploy_starter/user_bundle *
recursive-include deploy_starter/wheels *.whl
"""
    _write_file(wrapper_dir / "MANIFEST.in", manifest_in)

    return wrapper_dir, wrapper_dir / "dist"


def build_wheel(project_dir: Path) -> Path:
    """
    Build a wheel inside an isolated virtual environment to avoid PEP 668
    issues. Returns the path to the built wheel.
    """
    venv_dir = project_dir / ".venv_build"
    if not venv_dir.exists():
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
        )
    vpy = _venv_python(venv_dir)
    subprocess.run(
        [str(vpy), "-m", "pip", "install", "--upgrade", "pip", "build"],
        check=True,
    )
    subprocess.run([str(vpy), "-m", "build"], cwd=str(project_dir), check=True)
    dist_dir = project_dir / "dist"
    whls = sorted(
        dist_dir.glob("*.whl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not whls:
        raise RuntimeError("Wheel build failed: no .whl produced")
    return whls[0]


def default_deploy_name() -> str:
    ts = time.strftime("%Y%m%d%H%M%S", time.localtime())
    return f"deploy-{ts}-{uuid.uuid4().hex[:6]}"
