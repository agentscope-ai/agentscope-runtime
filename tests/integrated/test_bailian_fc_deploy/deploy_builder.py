import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

# Optional stdlib TOML parser (Python 3.11+)
try:
    import tomllib  # type: ignore
except Exception:
    tomllib = None  # Fallback parsing will be used

try:
    import alibabacloud_oss_v2 as oss
    from alibabacloud_oss_v2.models import PutBucketRequest, PutObjectRequest
    from alibabacloud_bailian20231229.client import Client as bailian20231229Client
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_bailian20231229 import models as bailian_20231229_models
    from alibabacloud_tea_util import models as util_models
except Exception:
    oss = None  # type: ignore
    PutBucketRequest = None  # type: ignore
    PutObjectRequest = None  # type: ignore
    bailian20231229Client = None  # type: ignore
    open_api_models = None  # type: ignore
    bailian_20231229_models = None  # type: ignore
    util_models = None  # type: ignore


def _read_text_file_lines(file_path: Path) -> List[str]:
    if not file_path.is_file():
        return []
    return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines()]


def _parse_requirements_txt(req_path: Path) -> List[str]:
    requirements: List[str] = []
    for line in _read_text_file_lines(req_path):
        if not line or line.startswith("#"):
            continue
        requirements.append(line)
    return requirements


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
        block_match = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.S | re.I)
        if block_match:
            block = block_match.group(1)
            for m in re.finditer(r"['\"]([^'\"]+)['\"]", block):
                deps.append(m.group(1))
        # Poetry fallback: very limited, heuristic
        poetry_block = re.search(r"\[tool\.poetry\.dependencies\](.*?)\n\[", text, re.S)
        if poetry_block:
            for line in poetry_block.group(1).splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    # name = "^1.2.3"
                    m = re.match(r"([A-Za-z0-9_.-]+)\s*=\s*['\"]([^'\"]+)['\"]", line)
                    if m and m.group(1).lower() != "python":
                        deps.append(f"{m.group(1)}{m.group(2)}")
                else:
                    # name without version
                    name = line.split("#")[0].strip()
                    if name and name.lower() != "python":
                        deps.append(name)
    return deps


def _gather_user_dependencies(project_dir: Path) -> List[str]:
    pyproject = project_dir / "pyproject.toml"
    req_txt = project_dir / "requirements.txt"
    deps: List[str] = []
    if pyproject.is_file():
        deps.extend(_parse_pyproject_toml(pyproject))
    if req_txt.is_file():
        # Merge requirements.txt too, avoiding duplicates
        existing = set(d.split("[", 1)[0].split("=", 1)[0].split("<", 1)[0].split(">", 1)[0].strip().lower() for d in deps)
        for r in _parse_requirements_txt(req_txt):
            name_key = r.split("[", 1)[0].split("=", 1)[0].split("<", 1)[0].split(">", 1)[0].strip().lower()
            if name_key not in existing:
                deps.append(r)
    return deps


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


def _generate_wrapper_project(build_root: Path, user_project_dir: Path, start_cmd: str, deploy_name: str) -> Tuple[Path, Path]:
    """
    Create a wrapper project under build_root, embedding user project under user_bundle/app.
    Returns: (wrapper_project_dir, dist_dir)
    """
    wrapper_dir = build_root

    # 1) Copy user project into wrapper under deploy_starter/user_bundle/app
    # Put user code inside the deploy_starter package so wheel includes it
    bundle_app_dir = wrapper_dir / "deploy_starter" / "user_bundle" / "app"
    ignore = shutil.ignore_patterns(".git", ".venv", "__pycache__", "dist", "build", "*.pyc", ".mypy_cache", ".pytest_cache")
    shutil.copytree(user_project_dir, bundle_app_dir, dirs_exist_ok=True, ignore=ignore)

    # 2) Dependencies
    user_deps = _gather_user_dependencies(user_project_dir)
    # Minimal deps required for upload/deploy and config parsing
    wrapper_deps = [
        "pyyaml",
        "alibabacloud-oss-v2",
        "alibabacloud-bailian20231229",
        "alibabacloud-credentials",
        "alibabacloud-tea-openapi",
        "alibabacloud-tea-util",
    ]
    # De-duplicate while preserving order
    seen = set()
    install_requires: List[str] = []
    for pkg in wrapper_deps + user_deps:
        key = pkg.strip().lower()
        if key and key not in seen:
            seen.add(key)
            install_requires.append(pkg)

    # 3) Packaging metadata (computed early so config.yml can reference it)
    unique_suffix = uuid.uuid4().hex[:8]
    package_name = f"agentdev_starter_{unique_suffix}"
    version = f"0.1.{int(time.time())}"

    # 4) Template package: deploy_starter
    _write_file(wrapper_dir / "deploy_starter" / "__init__.py", "")

    main_py = f"""
import os
import subprocess
import sys
import time
import yaml
from pathlib import Path
import shlex


def read_config():
    cfg_path = Path(__file__).with_name('config.yml')
    with cfg_path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {{}}


def main():
    cfg = read_config()
    workdir = Path(__file__).resolve().parent / 'user_bundle' / 'app'
    cmd = cfg.get('CMD')
    if not cmd:
        print('CMD missing in config.yml', file=sys.stderr)
        sys.exit(1)

    # Ensure working directory exists
    if not workdir.is_dir():
        print(f'Workdir not found: {{workdir}}', file=sys.stderr)
        sys.exit(1)

    # Normalize python interpreter usage for cloud environment
    cmd_str = str(cmd).strip()
    if cmd_str.startswith('python '):
        cmd_str = f'"{{sys.executable}}" ' + cmd_str[len('python '):]
    elif cmd_str.startswith('python3 '):
        cmd_str = f'"{{sys.executable}}" ' + cmd_str[len('python3 '):]
    elif cmd_str.endswith('.py') and not cmd_str.startswith('"') and ' ' not in cmd_str.split()[0]:
        # If command is a bare python script path, prefix interpreter
        cmd_str = f'"{{sys.executable}}" ' + cmd_str

    print(f'[deploy_starter] Starting user service: "{{cmd_str}}" in {{workdir}}')
    env = os.environ.copy()
    # Host/port are fixed by platform to 0.0.0.0:8080 per requirements.
    # We do not override user's binding to avoid conflicts.
    process = subprocess.Popen(cmd_str, cwd=str(workdir), shell=True, env=env)

    try:
        # Wait and forward exit code
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

DASHSCOPE_API_KEY: null
DASHSCOPE_MODEL_NAME: "qwen-turbo"

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

TELEMETRY_ENABLE: true
CMD: "{start_cmd}"
"""
    _write_file(wrapper_dir / "deploy_starter" / "config.yml", config_yml)

    setup_py = f"""
from setuptools import setup, find_packages

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
recursive-include deploy_starter/user_bundle/app *
"""
    _write_file(wrapper_dir / "MANIFEST.in", manifest_in)

    return wrapper_dir, wrapper_dir / "dist"


def _build_wheel(project_dir: Path) -> Path:
    # Build inside an isolated virtual environment to avoid PEP 668 issues
    venv_dir = project_dir / ".venv_build"
    if not venv_dir.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    vpy = _venv_python(venv_dir)
    subprocess.run([str(vpy), "-m", "pip", "install", "--upgrade", "pip", "build"], check=True)
    subprocess.run([str(vpy), "-m", "build"], cwd=str(project_dir), check=True)
    dist_dir = project_dir / "dist"
    whls = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not whls:
        raise RuntimeError("Wheel build failed: no .whl produced")
    return whls[0]


def _create_bucket_name(base: str) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    base = _sanitize_name(base)
    name = f"tmpbucket-agentdev-{base}-{ts}"
    # OSS bucket must be lowercase and 3-63 chars, start/end alnum
    name = re.sub(r"[^a-z0-9-]", "", name)
    name = name.strip("-")
    return name[:63] if len(name) > 63 else name


def _assert_cloud_sdks_available():
    if oss is None or bailian20231229Client is None:
        raise RuntimeError("Cloud SDKs not installed. Please ensure alibabacloud-oss-v2 and bailian SDKs are available.")


def _oss_get_client():
    # Env credentials
    access_key_id = os.environ.get('OSS_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
    if not access_key_id or not access_key_secret:
        raise RuntimeError("OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET must be set in environment")

    region = os.environ.get("OSS_REGION", "cn-hangzhou")
    credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = region
    return oss.Client(cfg)


def _oss_create_bucket_if_not_exists(client, bucket_name: str) -> None:
    try:
        exists = client.is_bucket_exist(bucket=bucket_name)
    except Exception:
        exists = False
    if not exists:
        req = PutBucketRequest(
            bucket=bucket_name,
            acl='private',
            create_bucket_configuration=oss.CreateBucketConfiguration(storage_class='IA'),
        )
        client.put_bucket(req)


def _oss_upload_and_presign(client, bucket_name: str, object_key: str, file_bytes: bytes, expires_minutes: int = 180) -> str:
    put_req = PutObjectRequest(bucket=bucket_name, key=object_key, body=file_bytes)
    client.put_object(put_req)
    pre = client.presign(oss.GetObjectRequest(bucket=bucket_name, key=object_key), expires=time.timedelta(minutes=expires_minutes))
    return pre.url


def _bailian_deploy(file_url: str, filename: str, deploy_name: str, telemetry_enabled: bool) -> None:
    config = open_api_models.Config(
        access_key_id=os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'],
        access_key_secret=os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET'],
    )
    config.endpoint = 'bailian-pre.cn-hangzhou.aliyuncs.com'
    client_bailian = bailian20231229Client(config)
    req = bailian_20231229_models.HighCodeDeployRequest(
        source_code_name=filename,
        source_code_oss_url=file_url,
        agent_name=deploy_name,
        telemetry_enabled=telemetry_enabled,
    )
    runtime = util_models.RuntimeOptions()
    headers = {}
    workspace_id = os.environ['ALIBABA_CLOUD_WORKSPACE_ID']
    client_bailian.high_code_deploy_with_options(workspace_id, req, headers, runtime)


def _upload_and_deploy(whl_path: Path, deploy_name: str, telemetry_enabled: bool = True) -> Tuple[str, str]:
    _assert_cloud_sdks_available()

    client = _oss_get_client()
    bucket_name = _create_bucket_name(deploy_name)
    _oss_create_bucket_if_not_exists(client, bucket_name)

    filename = whl_path.name
    with whl_path.open("rb") as f:
        file_bytes = f.read()
    # Presigned URL
    # Workaround: oss SDK presign uses datetime.timedelta
    import datetime as _dt
    put_req = PutObjectRequest(bucket=bucket_name, key=filename, body=file_bytes)
    client.put_object(put_req)
    pre = client.presign(oss.GetObjectRequest(bucket=bucket_name, key=filename), expires=_dt.timedelta(minutes=180))
    file_url = pre.url

    try:
        Path("oss_url.txt").write_text(file_url, encoding="utf-8")
    except Exception:
        pass

    _bailian_deploy(file_url, filename, deploy_name, telemetry_enabled)
    return file_url, bucket_name


def _default_deploy_name() -> str:
    ts = time.strftime("%Y%m%d%H%M%S", time.localtime())
    return f"deploy-{ts}-{uuid.uuid4().hex[:6]}"


def run(dir_path: str, cmd: str, deploy_name: Optional[str] = None, skip_upload: bool = False) -> Path:
    project_dir = Path(dir_path).resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project dir not found: {project_dir}")

    deploy_name = deploy_name or _default_deploy_name()
    builds_root = Path.cwd() / ".agentdev_builds" / f"build-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    builds_root.mkdir(parents=True, exist_ok=True)

    wrapper_project_dir, _ = _generate_wrapper_project(builds_root, project_dir, cmd, deploy_name)

    wheel_path = _build_wheel(wrapper_project_dir)

    if not skip_upload:
        _upload_and_deploy(wheel_path, deploy_name, telemetry_enabled=True)

    return wheel_path


def main_cli():
    parser = argparse.ArgumentParser(description="Package and deploy a Python project into AgentDev starter template")
    parser.add_argument("--dir", required=True, help="Path to user project directory")
    parser.add_argument("--cmd", required=True, help="Command to start the user project (e.g., 'python app.py')")
    parser.add_argument("--deploy-name", dest="deploy_name", default=None, help="Deploy name (agent_name). Random if omitted")
    parser.add_argument("--skip-upload", action="store_true", help="Only build wheel, do not upload/deploy")

    args = parser.parse_args()
    wheel_path = run(args.dir, args.cmd, deploy_name=args.deploy_name, skip_upload=args.skip_upload)
    print(f"Built wheel at: {wheel_path}")


if __name__ == "__main__":
    main_cli()


