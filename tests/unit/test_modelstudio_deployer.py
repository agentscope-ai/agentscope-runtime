# -*- coding: utf-8 -*-
# pylint:disable=unused-variable
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from agentscope_runtime.engine.deployers.modelstudio_deployer import (
    ModelstudioDeployManager,
    OSSConfig,
    ModelstudioConfig,
)


def _make_temp_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "user_app"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("print('ok')\n", encoding="utf-8")
    # minimal requirements to exercise dependency merge path harmlessly
    (project_dir / "requirements.txt").write_text("pyyaml\n", encoding="utf-8")
    return project_dir


@pytest.mark.asyncio
async def test_deploy_build_only_generates_wheel_without_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    project_dir = _make_temp_project(tmp_path)

    # Avoid requiring real SDKs
    monkeypatch.setattr(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        "._assert_cloud_sdks_available",
        lambda: None,
    )

    # Provide valid configs to bypass ensure_valid checks
    oss_cfg = OSSConfig(
        region="cn-hangzhou",
        access_key_id="id",
        access_key_secret="secret",
    )
    bailian_cfg = ModelstudioConfig(
        endpoint="bailian-pre.cn-hangzhou.aliyuncs.com",
        workspace_id="ws",
        access_key_id="id",
        access_key_secret="secret",
    )

    # Stub wrapper generation and wheel build
    wrapper_dir = tmp_path / "wrapper"
    wrapper_dir.mkdir()
    fake_wheel = wrapper_dir / "dist" / "pkg-0.0.1-py3-none-any.whl"
    fake_wheel.parent.mkdir(parents=True, exist_ok=True)
    fake_wheel.write_bytes(b"wheel-bytes")

    with patch(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.modelstudio_deployer.build_wheel",
        return_value=fake_wheel,
    ) as build_mock:
        deployer = ModelstudioDeployManager(
            oss_config=oss_cfg,
            modelstudio_config=bailian_cfg,
            build_root=tmp_path / ".b",
        )
        result = await deployer.deploy(
            project_dir=str(project_dir),
            cmd="python app.py",
            deploy_name="my-deploy",
            skip_upload=True,
            telemetry_enabled=False,
        )

    # Assertions
    gen_mock.assert_called_once()
    args, kwargs = gen_mock.call_args
    assert kwargs["deploy_name"] == "my-deploy"
    assert kwargs["start_cmd"] == "python app.py"
    assert kwargs["telemetry_enabled"] is False
    build_mock.assert_called_once_with(wrapper_dir)

    assert result["artifact_url"] == ""
    assert result["resource_name"] == "my-deploy"
    assert result["wheel_path"].endswith(".whl")


@pytest.mark.asyncio
async def test_deploy_with_upload_calls_cloud_and_writes_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    project_dir = _make_temp_project(tmp_path)

    # Avoid requiring real SDKs
    monkeypatch.setattr(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        "._assert_cloud_sdks_available",
        lambda: None,
    )

    oss_cfg = OSSConfig(
        region="cn-hangzhou",
        access_key_id="id",
        access_key_secret="secret",
    )
    bailian_cfg = ModelstudioConfig(
        endpoint="bailian-pre.cn-hangzhou.aliyuncs.com",
        workspace_id="ws",
        access_key_id="id",
        access_key_secret="secret",
    )

    wrapper_dir = tmp_path / "wrapper2"
    wrapper_dir.mkdir()
    fake_wheel = wrapper_dir / "dist" / "pkg-0.0.1-py3-none-any.whl"
    fake_wheel.parent.mkdir(parents=True, exist_ok=True)
    fake_wheel.write_bytes(b"wheel-bytes")

    with patch(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.modelstudio_deployer.build_wheel",
        return_value=fake_wheel,
    ) as build_mock, patch(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        "._oss_get_client",
        return_value=MagicMock(),
    ) as get_client_mock, patch(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        "._oss_create_bucket_if_not_exists",
    ) as ensure_bucket_mock, patch(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        "._oss_put_and_presign",
        return_value="https://oss/presigned",
    ) as presign_mock, patch(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        "._modelstudio_deploy",
    ) as bailian_deploy_mock:
        deployer = ModelstudioDeployManager(
            oss_config=oss_cfg,
            modelstudio_config=bailian_cfg,
            build_root=tmp_path / ".b2",
        )
        result = await deployer.deploy(
            project_dir=str(project_dir),
            cmd="python app.py",
            deploy_name="upload-deploy",
            skip_upload=False,
            telemetry_enabled=True,
        )

    # Build path asserted
    gen_mock.assert_called_once()
    build_mock.assert_called_once_with(wrapper_dir)

    # Cloud interactions asserted
    get_client_mock.assert_called_once()
    ensure_bucket_mock.assert_called_once()
    presign_mock.assert_called_once()
    bailian_deploy_mock.assert_called_once()

    # Bailian deploy call args include telemetry true
    _, kwargs = bailian_deploy_mock.call_args
    assert kwargs["deploy_name"] == "upload-deploy"
    assert kwargs["file_url"] == "https://oss/presigned"
    assert kwargs["telemetry_enabled"] is True

    # Result fields
    assert result["artifact_url"] == "https://oss/presigned"
    assert result["resource_name"] == "upload-deploy"
    assert result["wheel_path"].endswith(".whl")


@pytest.mark.asyncio
async def test_deploy_invalid_inputs_raise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    # Avoid real SDK check to test early validation paths
    monkeypatch.setattr(
        "agentscope_runtime.engine.deployers.modelstudio_deployer"
        "._assert_cloud_sdks_available",
        lambda: None,
    )

    oss_cfg = OSSConfig(
        region="cn-hangzhou",
        access_key_id="id",
        access_key_secret="secret",
    )
    bailian_cfg = ModelstudioConfig(
        endpoint="bailian-pre.cn-hangzhou.aliyuncs.com",
        workspace_id="ws",
        access_key_id="id",
        access_key_secret="secret",
    )
    deployer = ModelstudioDeployManager(
        oss_config=oss_cfg,
        modelstudio_config=bailian_cfg,
        build_root=tmp_path / ".b3",
    )

    with pytest.raises(ValueError):
        await deployer.deploy(
            project_dir=None,
            cmd="python app.py",
        )  # type: ignore

    with pytest.raises(ValueError):
        await deployer.deploy(
            project_dir=str(tmp_path),
            cmd=None,
        )  # type: ignore

    with pytest.raises(FileNotFoundError):
        await deployer.deploy(
            project_dir=str(tmp_path / "missing"),
            cmd="python app.py",
        )
