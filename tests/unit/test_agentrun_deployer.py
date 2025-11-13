# -*- coding: utf-8 -*-
# pylint:disable=unused-variable, redefined-outer-name, protected-access
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from agentscope_runtime.engine.deployers.agentrun_deployer import (
    AgentRunDeployManager,
    AgentRunConfig,
    OSSConfig,
    LogConfig,
    NetworkConfig,
    CodeConfig,
    EndpointConfig,
)


def _make_temp_project(tmp_path: Path) -> Path:
    """Create a minimal temporary project for testing."""
    project_dir = tmp_path / "user_app"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("print('ok')\n", encoding="utf-8")
    # minimal requirements to exercise dependency merge path harmlessly
    (project_dir / "requirements.txt").write_text("pyyaml\n", encoding="utf-8")
    return project_dir


@pytest.fixture
def mock_agentrun_config():
    """Provide a valid AgentRunConfig for testing."""
    return AgentRunConfig(
        access_key_id="test_ak_id",
        access_key_secret="test_ak_secret",
        region_id="cn-hangzhou",
        endpoint="agentrun.cn-hangzhou.aliyuncs.com",
        cpu=2.0,
        memory=2048,
    )


@pytest.fixture
def mock_oss_config():
    """Provide a valid OSSConfig for testing."""
    return OSSConfig(
        region="cn-hangzhou",
        access_key_id="test_oss_ak_id",
        access_key_secret="test_oss_ak_secret",
    )


@pytest.mark.asyncio
async def test_deploy_build_only_generates_wheel_without_upload(
    tmp_path: Path,
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
):
    """Test deploy with skip_upload=True generates wheel without uploading."""
    project_dir = _make_temp_project(tmp_path)

    # Stub wrapper generation and wheel build
    wrapper_dir = tmp_path / "wrapper"
    wrapper_dir.mkdir()
    fake_wheel = wrapper_dir / "dist" / "pkg-0.0.1-py3-none-any.whl"
    fake_wheel.parent.mkdir(parents=True, exist_ok=True)
    fake_wheel.write_bytes(b"wheel-bytes")

    # Create a fake zip file
    fake_zip = wrapper_dir / "dist" / "my-deploy.zip"
    fake_zip.write_bytes(b"zip-bytes")

    with patch(
        "agentscope_runtime.engine.deployers.agentrun_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.agentrun_deployer.build_wheel",
        return_value=fake_wheel,
    ) as build_mock, patch.object(
        AgentRunDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ) as docker_mock, patch.object(
        AgentRunDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={"bucket_name": "test-bucket", "object_key": "test.zip"},
    ) as upload_mock:
        deployer = AgentRunDeployManager(
            oss_config=mock_oss_config,
            agentrun_config=mock_agentrun_config,
            build_root=tmp_path / ".b",
        )
        result = await deployer.deploy(
            project_dir=str(project_dir),
            cmd="python app.py",
            deploy_name="my-deploy",
            skip_upload=True,
        )

    # Assertions
    gen_mock.assert_called_once()
    args, kwargs = gen_mock.call_args
    assert kwargs["deploy_name"] == "my-deploy"
    assert kwargs["start_cmd"] == "python app.py"
    build_mock.assert_called_once_with(wrapper_dir)
    docker_mock.assert_called_once()
    # When skip_upload=True, should NOT upload to OSS
    upload_mock.assert_not_called()

    assert (
        result["message"]
        == "Agent package built successfully (upload skipped)"
    )
    assert result["deploy_name"] == "my-deploy"


@pytest.mark.asyncio
async def test_deploy_with_upload_calls_cloud_methods(
    tmp_path: Path,
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
):
    """Test deploy without skip_upload calls cloud deployment methods."""
    project_dir = _make_temp_project(tmp_path)

    wrapper_dir = tmp_path / "wrapper2"
    wrapper_dir.mkdir()
    fake_wheel = wrapper_dir / "dist" / "pkg-0.0.1-py3-none-any.whl"
    fake_wheel.parent.mkdir(parents=True, exist_ok=True)
    fake_wheel.write_bytes(b"wheel-bytes")

    fake_zip = wrapper_dir / "dist" / "upload-deploy.zip"
    fake_zip.write_bytes(b"zip-bytes")

    # Mock the deployment methods
    mock_runtime_id = "test-runtime-id"
    mock_endpoint_url = "http://test-endpoint.example.com"

    with patch(
        "agentscope_runtime.engine.deployers.agentrun_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.agentrun_deployer.build_wheel",
        return_value=fake_wheel,
    ) as build_mock, patch.object(
        AgentRunDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ) as docker_mock, patch.object(
        AgentRunDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={
            "bucket_name": "test-bucket",
            "object_key": "test-path.zip",
            "presigned_url": "http://presigned.url",
        },
    ) as upload_mock, patch.object(
        AgentRunDeployManager,
        "deploy_to_agentrun",
        new_callable=AsyncMock,
        return_value={
            "agent_runtime_id": mock_runtime_id,
            "agent_runtime_public_endpoint_url": mock_endpoint_url,
            "url": "http://console.example.com",
        },
    ) as deploy_mock:
        deployer = AgentRunDeployManager(
            oss_config=mock_oss_config,
            agentrun_config=mock_agentrun_config,
            build_root=tmp_path / ".b2",
        )
        result = await deployer.deploy(
            project_dir=str(project_dir),
            cmd="python app.py",
            deploy_name="upload-deploy",
            skip_upload=False,
        )

    # Build path asserted
    gen_mock.assert_called_once()
    build_mock.assert_called_once_with(wrapper_dir)
    docker_mock.assert_called_once()

    # Cloud interactions asserted
    upload_mock.assert_called_once()
    deploy_mock.assert_called_once()

    # Result fields
    assert result["message"] == "Agent deployed successfully to AgentRun"
    assert result["agentrun_id"] == mock_runtime_id
    assert result["agentrun_endpoint_url"] == mock_endpoint_url


@pytest.mark.asyncio
async def test_deploy_with_external_wheel(
    tmp_path: Path,
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
):
    """Test deploy with external_whl_path skips building wheel."""
    project_dir = _make_temp_project(tmp_path)
    external_wheel = tmp_path / "external.whl"
    external_wheel.write_bytes(b"external-wheel")

    fake_zip = tmp_path / "external-deploy.zip"
    fake_zip.write_bytes(b"zip-bytes")

    with patch(
        "agentscope_runtime.engine.deployers.agentrun_deployer"
        ".generate_wrapper_project",
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.agentrun_deployer.build_wheel",
    ) as build_mock, patch.object(
        AgentRunDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ) as docker_mock, patch.object(
        AgentRunDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={"bucket_name": "test-bucket", "object_key": "test.zip"},
    ) as upload_mock:
        deployer = AgentRunDeployManager(
            oss_config=mock_oss_config,
            agentrun_config=mock_agentrun_config,
            build_root=tmp_path / ".b3",
        )
        result = await deployer.deploy(
            project_dir=str(project_dir),
            cmd="python app.py",
            deploy_name="external-deploy",
            skip_upload=True,
            external_whl_path=str(external_wheel),
        )

    # Should not generate wrapper or build when external wheel is provided
    gen_mock.assert_not_called()
    build_mock.assert_not_called()
    # But should still create zip in docker
    docker_mock.assert_called_once()
    # When skip_upload=True, should NOT upload to OSS
    upload_mock.assert_not_called()

    assert (
        result["message"]
        == "Agent package built successfully (upload skipped)"
    )
    assert result["deploy_name"] == "external-deploy"


@pytest.mark.asyncio
async def test_deploy_invalid_inputs_raise(
    tmp_path: Path,
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
):
    """Test that invalid inputs raise appropriate errors."""
    deployer = AgentRunDeployManager(
        oss_config=mock_oss_config,
        agentrun_config=mock_agentrun_config,
        build_root=tmp_path / ".b4",
    )

    # Missing runner, project_dir, and external_whl_path
    with pytest.raises(
        ValueError,
        match="Must provide either runner, project_dir, or external_whl_path",
    ):
        await deployer.deploy(
            project_dir=None,
            cmd=None,
        )

    # Non-existent project directory
    with pytest.raises(FileNotFoundError):
        await deployer.deploy(
            project_dir=str(tmp_path / "missing"),
            cmd="python app.py",
        )

    # Update with agentrun_id but no wheel
    with pytest.raises(
        FileNotFoundError,
        match="Wheel file required for agent update",
    ):
        await deployer.deploy(
            agentrun_id="existing-runtime-id",
        )


@pytest.mark.asyncio
async def test_deploy_with_agentrun_id_updates_existing(
    tmp_path: Path,
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
):
    """Test deploy with agentrun_id and external
    wheel updates existing runtime."""
    external_wheel = tmp_path / "update.whl"
    external_wheel.write_bytes(b"update-wheel")

    fake_zip = tmp_path / "update.zip"
    fake_zip.write_bytes(b"zip-bytes")

    mock_runtime_id = "existing-runtime-id"

    with patch.object(
        AgentRunDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ) as docker_mock, patch.object(
        AgentRunDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={
            "bucket_name": "test-bucket",
            "object_key": "test-path.zip",
            "presigned_url": "http://presigned.url",
        },
    ) as upload_mock, patch.object(
        AgentRunDeployManager,
        "deploy_to_agentrun",
        new_callable=AsyncMock,
        return_value={
            "agent_runtime_id": mock_runtime_id,
            "agent_runtime_public_endpoint_url": "http://test.example.com",
            "url": "http://console.example.com",
        },
    ) as deploy_mock:
        deployer = AgentRunDeployManager(
            oss_config=mock_oss_config,
            agentrun_config=mock_agentrun_config,
            build_root=tmp_path / ".b5",
        )
        result = await deployer.deploy(
            agentrun_id=mock_runtime_id,
            external_whl_path=str(external_wheel),
            skip_upload=False,
        )

    # Should create zip, upload and deploy
    docker_mock.assert_called_once()
    upload_mock.assert_called_once()
    deploy_mock.assert_called_once()

    # Check that agentrun_id was passed
    call_kwargs = deploy_mock.call_args[1]
    assert call_kwargs.get("agentrun_id") == mock_runtime_id

    assert result["message"] == "Agent deployed successfully to AgentRun"
    assert result["agentrun_id"] == mock_runtime_id


@pytest.mark.asyncio
async def test_create_agent_runtime(
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test creating a new agent runtime."""
    deployer = AgentRunDeployManager(
        oss_config=mock_oss_config,
        agentrun_config=mock_agentrun_config,
        build_root=tmp_path / ".b6",
    )

    # Mock the client methods
    mock_response = MagicMock()
    mock_response.body.code = "SUCCESS"
    mock_response.body.request_id = "test-request-id"
    mock_response.body.data = MagicMock()
    mock_response.body.data.agent_runtime_id = "new-runtime-id"

    deployer.client.create_agent_runtime_async = AsyncMock(
        return_value=mock_response,
    )
    deployer._poll_agent_runtime_status = AsyncMock(
        return_value={"status": "READY", "status_reason": "OK"},
    )

    result = await deployer.create_agent_runtime(
        agent_runtime_name="test-runtime",
        artifact_type="oss",
        cpu=2.0,
        memory=2048,
        port=8080,
    )

    assert result["success"] is True
    assert result["agent_runtime_id"] == "new-runtime-id"
    assert result["status"] == "READY"
    deployer.client.create_agent_runtime_async.assert_called_once()


@pytest.mark.asyncio
async def test_update_agent_runtime(
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test updating an existing agent runtime."""
    deployer = AgentRunDeployManager(
        oss_config=mock_oss_config,
        agentrun_config=mock_agentrun_config,
        build_root=tmp_path / ".b7",
    )

    # Mock the client methods
    mock_response = MagicMock()
    mock_response.body.code = "SUCCESS"
    mock_response.body.request_id = "test-request-id"
    mock_response.body.data = MagicMock()
    mock_response.body.data.agent_runtime_id = "existing-runtime-id"

    deployer.client.update_agent_runtime_async = AsyncMock(
        return_value=mock_response,
    )
    deployer._poll_agent_runtime_status = AsyncMock(
        return_value={"status": "READY", "status_reason": "Updated"},
    )

    result = await deployer.update_agent_runtime(
        agent_runtime_id="existing-runtime-id",
        agent_runtime_name="updated-runtime",
    )

    assert result["success"] is True
    assert result["agent_runtime_id"] == "existing-runtime-id"
    assert result["status"] == "READY"
    deployer.client.update_agent_runtime_async.assert_called_once()


@pytest.mark.asyncio
async def test_create_agent_runtime_endpoint(
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test creating an agent runtime endpoint."""
    deployer = AgentRunDeployManager(
        oss_config=mock_oss_config,
        agentrun_config=mock_agentrun_config,
        build_root=tmp_path / ".b8",
    )

    # Mock the client methods
    mock_response = MagicMock()
    mock_response.body.code = "SUCCESS"
    mock_response.body.request_id = "test-request-id"
    mock_response.body.data = MagicMock()
    mock_response.body.data.agent_runtime_endpoint_id = "endpoint-id"

    mock_response.body.data.agent_runtime_endpoint_name = "test-endpoint"
    mock_response.body.data.endpoint_public_url = "http://endpoint.example.com"

    deployer.client.create_agent_runtime_endpoint_async = AsyncMock(
        return_value=mock_response,
    )
    deployer._poll_agent_runtime_endpoint_status = AsyncMock(
        return_value={
            "status": "ENABLED",
            "status_reason": "OK",
            "endpoint_public_url": "http://endpoint.example.com",
        },
    )

    endpoint_config = EndpointConfig(
        agent_runtime_endpoint_name="test-endpoint",
        description="Test endpoint",
    )
    result = await deployer.create_agent_runtime_endpoint(
        agent_runtime_id="runtime-id",
        endpoint_config=endpoint_config,
    )

    assert result["success"] is True
    assert result["agent_runtime_endpoint_id"] == "endpoint-id"
    assert (
        result["agent_runtime_public_endpoint_url"]
        == "http://endpoint.example.com"
    )
    assert result["status"] == "ENABLED"
    deployer.client.create_agent_runtime_endpoint_async.assert_called_once()


@pytest.mark.asyncio
async def test_delete_agent_runtime(
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test deleting an agent runtime."""
    deployer = AgentRunDeployManager(
        oss_config=mock_oss_config,
        agentrun_config=mock_agentrun_config,
        build_root=tmp_path / ".b9",
    )

    # Mock the client delete method
    mock_response = MagicMock()
    mock_response.body.code = "SUCCESS"
    mock_response.body.request_id = "test-request-id"
    deployer.client.delete_agent_runtime_async = AsyncMock(
        return_value=mock_response,
    )

    # Test delete
    result = await deployer.delete(agent_runtime_id="runtime-to-delete")

    # Verify client method was called
    deployer.client.delete_agent_runtime_async.assert_called_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_agent_runtime(
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test getting agent runtime details."""
    deployer = AgentRunDeployManager(
        oss_config=mock_oss_config,
        agentrun_config=mock_agentrun_config,
        build_root=tmp_path / ".b10",
    )

    # Mock the client get method
    mock_response = MagicMock()
    mock_response.body.code = "SUCCESS"
    mock_response.body.request_id = "test-request-id"
    mock_response.body.data = MagicMock()
    mock_response.body.data.to_map = MagicMock(
        return_value={
            "agent_runtime_id": "runtime-id",
            "agent_runtime_name": "test-runtime",
            "status": "READY",
        },
    )

    deployer.client.get_agent_runtime_async = AsyncMock(
        return_value=mock_response,
    )

    result = await deployer.get_agent_runtime(agent_runtime_id="runtime-id")

    assert result["success"] is True
    assert result["data"]["agent_runtime_id"] == "runtime-id"
    assert result["data"]["agent_runtime_name"] == "test-runtime"
    assert result["data"]["status"] == "READY"
    deployer.client.get_agent_runtime_async.assert_called_once()


def test_agentrun_config_from_env(monkeypatch: pytest.MonkeyPatch):
    """Test loading AgentRunConfig from environment variables."""
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "test_ak")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "test_sk")
    monkeypatch.setenv("AGENT_RUN_REGION_ID", "cn-beijing")
    monkeypatch.setenv("AGENT_RUN_CPU", "4.0")
    monkeypatch.setenv("AGENT_RUN_MEMORY", "4096")

    config = AgentRunConfig.from_env()

    assert config.access_key_id == "test_ak"
    assert config.access_key_secret == "test_sk"
    assert config.region_id == "cn-beijing"
    assert config.cpu == 4.0
    assert config.memory == 4096


def test_agentrun_config_ensure_valid():
    """Test AgentRunConfig validation."""
    # Valid config
    config = AgentRunConfig(
        access_key_id="test_ak",
        access_key_secret="test_sk",
    )
    config.ensure_valid()  # Should not raise

    # Missing access_key_id
    config = AgentRunConfig(access_key_secret="test_sk")
    with pytest.raises(ValueError, match="ALIBABA_CLOUD_ACCESS_KEY_ID"):
        config.ensure_valid()

    # Missing access_key_secret
    config = AgentRunConfig(access_key_id="test_ak")
    with pytest.raises(ValueError, match="ALIBABA_CLOUD_ACCESS_KEY_SECRET"):
        config.ensure_valid()


def test_oss_config_from_env(monkeypatch: pytest.MonkeyPatch):
    """Test loading OSSConfig from environment variables."""
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "oss_ak")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "oss_sk")
    monkeypatch.setenv("OSS_REGION", "cn-shanghai")

    config = OSSConfig.from_env()

    assert config.access_key_id == "oss_ak"
    assert config.access_key_secret == "oss_sk"
    assert config.region == "cn-shanghai"


def test_oss_config_ensure_valid():
    """Test OSSConfig validation."""
    # Valid config
    config = OSSConfig(
        region="cn-hangzhou",
        access_key_id="test_ak",
        access_key_secret="test_sk",
    )
    config.ensure_valid()  # Should not raise

    # Missing access_key_id
    config = OSSConfig(
        region="cn-hangzhou",
        access_key_secret="test_sk",
    )
    with pytest.raises(RuntimeError, match="Missing AccessKey for OSS"):
        config.ensure_valid()

    # Missing access_key_secret
    config = OSSConfig(
        region="cn-hangzhou",
        access_key_id="test_ak",
    )
    with pytest.raises(RuntimeError, match="Missing AccessKey for OSS"):
        config.ensure_valid()


def test_log_config():
    """Test LogConfig dataclass."""
    log_config = LogConfig(
        logstore="test-store",
        project="test-project",
    )
    assert log_config.logstore == "test-store"
    assert log_config.project == "test-project"


def test_network_config():
    """Test NetworkConfig dataclass."""
    network_config = NetworkConfig(
        network_mode="VPC",
        security_group_id="sg-123",
        vpc_id="vpc-456",
        vswitch_ids=["vsw-1", "vsw-2"],
    )
    assert network_config.network_mode == "VPC"
    assert network_config.security_group_id == "sg-123"
    assert network_config.vpc_id == "vpc-456"
    assert network_config.vswitch_ids == ["vsw-1", "vsw-2"]


def test_code_config():
    """Test CodeConfig dataclass."""
    code_config = CodeConfig(
        command=["python", "app.py"],
        oss_bucket_name="test-bucket",
        oss_object_name="test-object",
    )
    assert code_config.command == ["python", "app.py"]
    assert code_config.oss_bucket_name == "test-bucket"
    assert code_config.oss_object_name == "test-object"


def test_endpoint_config():
    """Test EndpointConfig dataclass."""
    endpoint_config = EndpointConfig(
        agent_runtime_endpoint_name="test-endpoint",
        description="Test endpoint",
        tags=["tag1", "tag2"],
        target_version="v1.0",
    )
    assert endpoint_config.agent_runtime_endpoint_name == "test-endpoint"
    assert endpoint_config.description == "Test endpoint"
    assert endpoint_config.tags == ["tag1", "tag2"]
    assert endpoint_config.target_version == "v1.0"


@pytest.mark.asyncio
async def test_deploy_with_environment_variables(
    tmp_path: Path,
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
):
    """Test deploy with custom environment variables."""
    project_dir = _make_temp_project(tmp_path)

    wrapper_dir = tmp_path / "wrapper"
    wrapper_dir.mkdir()
    fake_wheel = wrapper_dir / "dist" / "pkg-0.0.1-py3-none-any.whl"
    fake_wheel.parent.mkdir(parents=True, exist_ok=True)
    fake_wheel.write_bytes(b"wheel-bytes")

    fake_zip = wrapper_dir / "dist" / "env-deploy.zip"
    fake_zip.write_bytes(b"zip-bytes")

    custom_env = {
        "API_KEY": "test-key",
        "DEBUG": "true",
    }

    with patch(
        "agentscope_runtime.engine.deployers.agentrun_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ), patch(
        "agentscope_runtime.engine.deployers.agentrun_deployer.build_wheel",
        return_value=fake_wheel,
    ), patch.object(
        AgentRunDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ), patch.object(
        AgentRunDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={"bucket_name": "test-bucket", "object_key": "test.zip"},
    ):
        deployer = AgentRunDeployManager(
            oss_config=mock_oss_config,
            agentrun_config=mock_agentrun_config,
            build_root=tmp_path / ".b11",
        )
        result = await deployer.deploy(
            project_dir=str(project_dir),
            cmd="python app.py",
            deploy_name="env-deploy",
            skip_upload=True,
            environment=custom_env,
        )

    # Verify deployment was successful
    assert (
        result["message"]
        == "Agent package built successfully (upload skipped)"
    )
    assert result["deploy_name"] == "env-deploy"


@pytest.mark.asyncio
async def test_publish_agent_runtime_version(
    mock_agentrun_config: AgentRunConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test publishing an agent runtime version."""
    deployer = AgentRunDeployManager(
        oss_config=mock_oss_config,
        agentrun_config=mock_agentrun_config,
        build_root=tmp_path / ".b12",
    )

    # Mock the client publish method
    mock_response = MagicMock()
    mock_response.body.code = "SUCCESS"
    mock_response.body.request_id = "test-request-id"
    mock_response.body.data = MagicMock()
    mock_response.body.data.agent_runtime_id = "runtime-id"
    mock_response.body.data.agent_runtime_version = "v1.0"
    mock_response.body.data.description = "Version 1.0"

    deployer.client.publish_runtime_version_async = AsyncMock(
        return_value=mock_response,
    )

    result = await deployer.publish_agent_runtime_version(
        agent_runtime_id="runtime-id",
        description="Version 1.0",
    )

    assert result["success"] is True
    assert result["agent_runtime_version"] == "v1.0"
    assert result["agent_runtime_id"] == "runtime-id"
    deployer.client.publish_runtime_version_async.assert_called_once()
