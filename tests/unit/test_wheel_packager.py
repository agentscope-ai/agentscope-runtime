# -*- coding: utf-8 -*-
# pylint: disable=unused-variable,f-string-without-interpolation
# pylint: disable=line-too-long, too-many-branches
from pathlib import Path

from agentscope_runtime.engine.deployers.utils.wheel_packager import (
    generate_wrapper_project,
)


def _make_user_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (proj / "pyproject.toml").write_text(
        """
[project]
name = "dummy"
version = "0.0.1"
dependencies = ["requests>=2.0.0"]
""",
        encoding="utf-8",
    )
    return proj


def test_generate_wrapper_project_writes_config_and_manifest(tmp_path: Path):
    user_proj = _make_user_project(tmp_path)

    wrapper_dir, dist_dir = generate_wrapper_project(
        build_root=tmp_path / "wrap",
        user_project_dir=user_proj,
        start_cmd="python app.py",
        deploy_name="demo",
        telemetry_enabled=False,
    )

    # Files exist
    cfg = wrapper_dir / "deploy_starter" / "config.yml"
    assert cfg.is_file()
    content = cfg.read_text(encoding="utf-8")
    assert 'APP_NAME: "demo"' in content
    assert 'CMD: "python app.py"' in content
    assert 'APP_SUBDIR_NAME: "proj"' in content
    assert "TELEMETRY_ENABLE: false" in content

    assert (wrapper_dir / "setup.py").is_file()
    assert (wrapper_dir / "MANIFEST.in").is_file()
    assert (wrapper_dir / "deploy_starter" / "main.py").is_file()
    assert (
        wrapper_dir / "deploy_starter" / "user_bundle" / "proj" / "app.py"
    ).is_file()


def test_generate_wrapper_project_telemetry_true(tmp_path: Path):
    user_proj = _make_user_project(tmp_path)
    wrapper_dir, _ = generate_wrapper_project(
        build_root=tmp_path / "wrap2",
        user_project_dir=user_proj,
        start_cmd="python app.py",
        deploy_name="demo2",
        telemetry_enabled=True,
    )
    cfg = wrapper_dir / "deploy_starter" / "config.yml"
    assert "TELEMETRY_ENABLE: true" in cfg.read_text(encoding="utf-8")
