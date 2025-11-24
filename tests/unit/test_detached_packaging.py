# -*- coding: utf-8 -*-
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


def _load_module_from_path(
    module_path: Path,
    module_name: str = "temp_app_module",
):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


@pytest.mark.asyncio
async def test_create_detached_project_from_app(tmp_path):
    app_file = tmp_path / "demo_app.py"
    app_file.write_text(
        """
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager

app = AgentApp()


@app.query()
async def query_func(self, msgs, request, **kwargs):
    return {"content": "ok"}


async def build_project():
    return await LocalDeployManager.create_detached_project(app=app)
        """.strip(),
        encoding="utf-8",
    )

    module = _load_module_from_path(app_file, module_name="demo_app_module")

    project_dir = await module.build_project()

    project_path = Path(project_dir)
    extracted_files = [
        p.relative_to(project_path / "project").name
        for p in (project_path / "project").rglob("*.py")
    ]
    assert app_file.name in extracted_files

    meta = json.loads((project_path / "bundle_meta.json").read_text())
    assert meta["entry_script"] == f"project/{app_file.name}"

    shutil.rmtree(project_path)
    sys.modules.pop("demo_app_module", None)
