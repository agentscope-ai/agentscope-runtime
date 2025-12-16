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
import os
from typing import List, Tuple, Optional, Union
from .detached_app import _parse_pyproject_toml, append_project_requirements


def get_user_bundle_appdir(build_root: Path, user_project_dir: Path) -> Path:
    return (
        build_root / "deploy_starter" / "user_bundle" / user_project_dir.name
    )


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
    requirements: Optional[Union[str, List[str]]] = None,
) -> Tuple[Path, Path]:
    """
    Create a wrapper project under build_root, embedding user project under
    user_bundle/<project_basename>. Returns: (wrapper_project_dir, dist_dir)
    """
    wrapper_dir = build_root

    # 1) Copy user project into wrapper under deploy_starter/user_bundle/<project_basename>
    # Put user code inside the deploy_starter package so wheel includes it and preserves project folder name
    project_basename = user_project_dir.name
    bundle_app_dir = get_user_bundle_appdir(wrapper_dir, user_project_dir)

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

    _, local_wheels = _gather_user_dependencies(user_project_dir)

    # gather
    append_project_requirements(
        build_root,
        additional_requirements=requirements,
        use_local_runtime=os.getenv("USE_LOCAL_RUNTIME", "False") == "True",
    )
    _, project_wheels = _gather_user_dependencies(build_root)

    local_wheels.extend(project_wheels)

    # Copy local wheel files to wrapper project
    if local_wheels:
        wheels_dir = wrapper_dir / "deploy_starter" / "wheels"
        wheels_dir.mkdir(parents=True, exist_ok=True)
        for wheel_file in local_wheels:
            dest = wheels_dir / wheel_file.name
            shutil.copy2(wheel_file, dest)
    else:
        # if not use local wheel, make sure the agentscope-runtime will be installed
        wrapper_deps.append("agentscope_runtime")

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


def main():

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
from setuptools.command.build_py import build_py
import zipfile
import shutil
from pathlib import Path
from email.parser import Parser
import tempfile


class BuildPyWithWheelMerge(build_py):
    \"\"\"Merge bundled wheel packages into the final wheel at build time\"\"\"

    def run(self):
        build_py.run(self)
        self._merge_wheels()

    def _merge_wheels(self):
        \"\"\"Extract and merge all wheel files from the wheels directory\"\"\"
        wheels_dir = Path("deploy_starter/wheels")
        if not wheels_dir.exists():
            return

        whl_files = list(wheels_dir.glob("*.whl"))
        if not whl_files:
            return

        print(f"\\n{{'='*60}}\\nMerging {{len(whl_files)}} wheel(s)...\\n{{'='*60}}\\n")

        for whl_file in whl_files:
            self._extract_wheel(whl_file, Path(self.build_lib))

        print(f"{{'='*60}}\\nMerge completed!\\n{{'='*60}}\\n")

    def _extract_wheel(self, whl_path, build_lib):
        \"\"\"Extract wheel contents to build directory\"\"\"
        with tempfile.TemporaryDirectory() as tmpdir, zipfile.ZipFile(whl_path) as zf:
            zf.extractall(tmpdir)

            for item in Path(tmpdir).iterdir():
                if item.suffix in ['.dist-info', '.egg-info']:
                    continue

                dest = build_lib / item.name
                if dest.exists():
                    shutil.rmtree(dest) if dest.is_dir() else dest.unlink()

                shutil.copytree(item, dest) if item.is_dir() else shutil.copy2(item, dest)
                print(f"  Merged: {{item.name}}")


def extract_wheel_dependencies():
    \"\"\"Extract dependency declarations from wheel files\"\"\"
    deps = []
    wheels_dir = Path("deploy_starter/wheels")

    if not wheels_dir.exists():
        return deps

    for whl in wheels_dir.glob("*.whl"):
        try:
            with zipfile.ZipFile(whl) as zf:
                metadata_file = next((f for f in zf.namelist() if f.endswith('/METADATA')), None)
                if metadata_file:
                    content = zf.read(metadata_file).decode('utf-8')
                    metadata = Parser().parsestr(content)
                    deps.extend([v.split(';')[0].strip() for k, v in metadata.items()
                               if k == 'Requires-Dist' and v.split(';')[0].strip() not in deps])
        except Exception as e:
            print(f"Warning: Failed to extract deps from {{whl.name}}: {{e}}")

    return deps


setup(
    name='{package_name}',
    version='{version}',
    packages=find_packages(),
    include_package_data=True,
    install_requires={install_requires!r} + extract_wheel_dependencies(),
    cmdclass={{
        'build_py': BuildPyWithWheelMerge,
    }},
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
