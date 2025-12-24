# -*- coding: utf-8 -*-
# pylint:disable=unused-variable, redefined-outer-name, protected-access
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Try to import the FC deployer, skip all tests if not available
try:
    from agentscope_runtime.engine.deployers.fc_deployer import (
        FCDeployManager,
        FCConfig,
        OSSConfig,
        LogConfig,
        VPCConfig,
        CodeConfig,
    )

    FC_AVAILABLE = True
except ImportError:
    FC_AVAILABLE = False
    # Create dummy classes for type hints
    FCDeployManager = None  # type: ignore
    FCConfig = None  # type: ignore
    OSSConfig = None  # type: ignore
    LogConfig = None  # type: ignore
    VPCConfig = None  # type: ignore
    CodeConfig = None  # type: ignore

pytestmark = pytest.mark.skipif(
    not FC_AVAILABLE,
    reason="alibabacloud_fc20230330 SDK not installed",
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
def mock_fc_config():
    """Provide a valid FCConfig for testing."""
    return FCConfig(
        access_key_id="test_ak_id",
        access_key_secret="test_ak_secret",
        account_id="test_account_id",
        region_id="cn-hangzhou",
        cpu=2.0,
        memory=2048,
        disk=512,
    )


@pytest.fixture
def mock_oss_config():
    """Provide a valid OSSConfig for testing."""
    return OSSConfig(
        region="cn-hangzhou",
        access_key_id="test_oss_ak_id",
        access_key_secret="test_oss_ak_secret",
        bucket_name="test-bucket",
    )


@pytest.mark.asyncio
async def test_deploy_build_only_generates_wheel_without_upload(
    tmp_path: Path,
    mock_fc_config: FCConfig,
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
        "agentscope_runtime.engine.deployers.fc_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.fc_deployer.build_wheel",
        return_value=fake_wheel,
    ) as build_mock, patch.object(
        FCDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ) as docker_mock, patch.object(
        FCDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={"bucket_name": "test-bucket", "object_key": "test.zip"},
    ) as upload_mock:
        deployer = FCDeployManager(
            oss_config=mock_oss_config,
            fc_config=mock_fc_config,
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
    mock_fc_config: FCConfig,
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
    mock_function_name = "test-function"
    mock_endpoint_url = "http://test-endpoint.example.com"

    with patch(
        "agentscope_runtime.engine.deployers.fc_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.fc_deployer.build_wheel",
        return_value=fake_wheel,
    ) as build_mock, patch.object(
        FCDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ) as docker_mock, patch.object(
        FCDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={
            "bucket_name": "test-bucket",
            "object_key": "test-path.zip",
            "presigned_url": "http://presigned.url",
        },
    ) as upload_mock, patch.object(
        FCDeployManager,
        "deploy_to_fc",
        new_callable=AsyncMock,
        return_value={
            "success": True,
            "function_name": mock_function_name,
            "endpoint_internet_url": mock_endpoint_url,
            "endpoint_intranet_url": "http://intranet.example.com",
        },
    ) as deploy_mock:
        deployer = FCDeployManager(
            oss_config=mock_oss_config,
            fc_config=mock_fc_config,
            build_root=tmp_path / ".b2",
        )
        # Mock state_manager to avoid file system operations
        deployer.state_manager.save = MagicMock()

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
    assert result["message"] == "Agent deployed successfully to FC"
    assert result["function_name"] == mock_function_name
    assert result["endpoint_url"] == mock_endpoint_url


@pytest.mark.asyncio
async def test_deploy_with_external_wheel(
    tmp_path: Path,
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test deploy with external_whl_path skips building wheel."""
    project_dir = _make_temp_project(tmp_path)
    external_wheel = tmp_path / "external.whl"
    external_wheel.write_bytes(b"external-wheel")

    fake_zip = tmp_path / "external-deploy.zip"
    fake_zip.write_bytes(b"zip-bytes")

    with patch(
        "agentscope_runtime.engine.deployers.fc_deployer"
        ".generate_wrapper_project",
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.fc_deployer.build_wheel",
    ) as build_mock, patch.object(
        FCDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ) as docker_mock, patch.object(
        FCDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={"bucket_name": "test-bucket", "object_key": "test.zip"},
    ) as upload_mock:
        deployer = FCDeployManager(
            oss_config=mock_oss_config,
            fc_config=mock_fc_config,
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
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test that invalid inputs raise appropriate errors."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b4",
    )

    # Missing runner, project_dir, and external_whl_path
    with pytest.raises(
        ValueError,
        match="Must provide either app, runner, project_dir, "
        "or external_whl_path",
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


@pytest.mark.asyncio
async def test_deploy_with_function_name_updates_existing(
    tmp_path: Path,
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test deploy with function_name and external
    wheel updates existing function."""
    external_wheel = tmp_path / "update.whl"
    external_wheel.write_bytes(b"update-wheel")

    fake_zip = tmp_path / "update.zip"
    fake_zip.write_bytes(b"zip-bytes")

    mock_function_name = "existing-function"

    with patch.object(
        FCDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ) as docker_mock, patch.object(
        FCDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={
            "bucket_name": "test-bucket",
            "object_key": "test-path.zip",
            "presigned_url": "http://presigned.url",
        },
    ) as upload_mock, patch.object(
        FCDeployManager,
        "deploy_to_fc",
        new_callable=AsyncMock,
        return_value={
            "success": True,
            "function_name": mock_function_name,
            "endpoint_internet_url": "http://test.example.com",
            "endpoint_intranet_url": "http://intranet.example.com",
        },
    ) as deploy_mock:
        deployer = FCDeployManager(
            oss_config=mock_oss_config,
            fc_config=mock_fc_config,
            build_root=tmp_path / ".b5",
        )
        # Mock state_manager to avoid file system operations
        deployer.state_manager.save = MagicMock()

        result = await deployer.deploy(
            function_name=mock_function_name,
            external_whl_path=str(external_wheel),
            skip_upload=False,
        )

    # Should create zip, upload and deploy
    docker_mock.assert_called_once()
    upload_mock.assert_called_once()
    deploy_mock.assert_called_once()

    # Check that function_name was passed
    call_kwargs = deploy_mock.call_args[1]
    assert call_kwargs.get("function_name") == mock_function_name

    assert result["message"] == "Agent deployed successfully to FC"
    assert result["function_name"] == mock_function_name


@pytest.mark.asyncio
async def test_deploy_to_fc_create_new_function(
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test creating a new FC function."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b6",
    )

    # Mock the client methods
    mock_response = MagicMock()
    mock_response.body = MagicMock()
    mock_response.body.function_name = "new-function"
    mock_response.body.runtime = "custom.debian11"
    mock_response.body.created_time = "2025-01-01T00:00:00Z"

    deployer.client.create_function_with_options = MagicMock(
        return_value=mock_response,
    )

    # Mock trigger creation
    mock_trigger_response = MagicMock()
    mock_trigger_response.body = MagicMock()
    mock_trigger_response.body.http_trigger = MagicMock()
    mock_trigger_response.body.http_trigger.url_internet = (
        "http://internet.example.com"
    )
    mock_trigger_response.body.http_trigger.url_intranet = (
        "http://intranet.example.com"
    )
    mock_trigger_response.body.trigger_id = "trigger-123"

    deployer.client.create_trigger_with_options = MagicMock(
        return_value=mock_trigger_response,
    )

    result = await deployer.deploy_to_fc(
        agent_runtime_name="new-function",
        oss_bucket_name="test-bucket",
        oss_object_name="test-object.zip",
    )

    assert result["success"] is True
    assert result["function_name"] == "new-function"
    deployer.client.create_function_with_options.assert_called_once()
    deployer.client.create_trigger_with_options.assert_called_once()


@pytest.mark.asyncio
async def test_deploy_to_fc_update_existing_function(
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test updating an existing FC function."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b7",
    )

    # Mock the client methods
    mock_response = MagicMock()
    mock_response.body = MagicMock()
    mock_response.body.function_name = "existing-function"
    mock_response.body.runtime = "custom.debian11"
    mock_response.body.created_time = "2025-01-01T00:00:00Z"

    deployer.client.update_function_with_options = MagicMock(
        return_value=mock_response,
    )

    # Mock trigger retrieval
    mock_trigger_response = MagicMock()
    mock_trigger_response.body = MagicMock()
    mock_trigger_response.body.http_trigger = MagicMock()
    mock_trigger_response.body.http_trigger.url_internet = (
        "http://internet.example.com"
    )
    mock_trigger_response.body.http_trigger.url_intranet = (
        "http://intranet.example.com"
    )
    mock_trigger_response.body.trigger_id = "trigger-123"

    deployer.client.get_trigger_with_options = MagicMock(
        return_value=mock_trigger_response,
    )

    result = await deployer.deploy_to_fc(
        agent_runtime_name="updated-function",
        oss_bucket_name="test-bucket",
        oss_object_name="test-object.zip",
        function_name="existing-function",
    )

    assert result["success"] is True
    assert result["function_name"] == "existing-function"
    deployer.client.update_function_with_options.assert_called_once()


@pytest.mark.asyncio
async def test_delete_function(
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test deleting an FC function."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b8",
    )

    # Mock the client delete methods
    deployer.client.delete_trigger_with_options = MagicMock()
    deployer.client.delete_function_with_options = MagicMock()

    result = await deployer.delete(function_name="function-to-delete")

    assert result["success"] is True
    assert result["function_name"] == "function-to-delete"
    deployer.client.delete_trigger_with_options.assert_called_once()
    deployer.client.delete_function_with_options.assert_called_once()


@pytest.mark.asyncio
async def test_delete_function_handles_error(
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test delete handles errors gracefully."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b9",
    )

    # Mock the client to raise an exception
    deployer.client.delete_trigger_with_options = MagicMock()
    deployer.client.delete_function_with_options = MagicMock(
        side_effect=Exception("Function not found"),
    )

    result = await deployer.delete(function_name="non-existent-function")

    assert result["success"] is False
    assert "Function not found" in result["message"]


def test_fc_config_from_env(monkeypatch: pytest.MonkeyPatch):
    """Test loading FCConfig from environment variables."""
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "test_ak")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "test_sk")
    monkeypatch.setenv("FC_ACCOUNT_ID", "test_account")
    monkeypatch.setenv("FC_REGION_ID", "cn-beijing")
    monkeypatch.setenv("FC_CPU", "4.0")
    monkeypatch.setenv("FC_MEMORY", "4096")
    monkeypatch.setenv("FC_DISK", "1024")

    config = FCConfig.from_env()

    assert config.access_key_id == "test_ak"
    assert config.access_key_secret == "test_sk"
    assert config.account_id == "test_account"
    assert config.region_id == "cn-beijing"
    assert config.cpu == 4.0
    assert config.memory == 4096
    assert config.disk == 1024


def test_fc_config_from_env_with_log_config(monkeypatch: pytest.MonkeyPatch):
    """Test loading FCConfig with log config from environment."""
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "test_ak")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "test_sk")
    monkeypatch.setenv("FC_ACCOUNT_ID", "test_account")
    monkeypatch.setenv("FC_LOG_STORE", "test-logstore")
    monkeypatch.setenv("FC_LOG_PROJECT", "test-project")

    config = FCConfig.from_env()

    assert config.log_config is not None
    assert config.log_config.logstore == "test-logstore"
    assert config.log_config.project == "test-project"


def test_fc_config_from_env_with_vpc_config(monkeypatch: pytest.MonkeyPatch):
    """Test loading FCConfig with VPC config from environment."""
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "test_ak")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "test_sk")
    monkeypatch.setenv("FC_ACCOUNT_ID", "test_account")
    monkeypatch.setenv("FC_VPC_ID", "vpc-123")
    monkeypatch.setenv("FC_SECURITY_GROUP_ID", "sg-456")
    monkeypatch.setenv("FC_VSWITCH_IDS", '["vsw-1", "vsw-2"]')

    config = FCConfig.from_env()

    assert config.vpc_config is not None
    assert config.vpc_config.vpc_id == "vpc-123"
    assert config.vpc_config.security_group_id == "sg-456"
    assert config.vpc_config.vswitch_ids == ["vsw-1", "vsw-2"]


def test_fc_config_ensure_valid():
    """Test FCConfig validation."""
    # Valid config
    config = FCConfig(
        access_key_id="test_ak",
        access_key_secret="test_sk",
        account_id="test_account",
    )
    config.ensure_valid()  # Should not raise

    # Missing access_key_id
    config = FCConfig(
        access_key_secret="test_sk",
        account_id="test_account",
    )
    with pytest.raises(ValueError, match="ALIBABA_CLOUD_ACCESS_KEY_ID"):
        config.ensure_valid()

    # Missing access_key_secret
    config = FCConfig(
        access_key_id="test_ak",
        account_id="test_account",
    )
    with pytest.raises(ValueError, match="ALIBABA_CLOUD_ACCESS_KEY_SECRET"):
        config.ensure_valid()

    # Missing account_id
    config = FCConfig(
        access_key_id="test_ak",
        access_key_secret="test_sk",
    )
    with pytest.raises(ValueError, match="FC_ACCOUNT_ID"):
        config.ensure_valid()


def test_oss_config_from_env(monkeypatch: pytest.MonkeyPatch):
    """Test loading OSSConfig from environment variables."""
    # Clear any existing OSS env vars first
    monkeypatch.delenv("OSS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("OSS_ACCESS_KEY_SECRET", raising=False)

    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "oss_ak")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "oss_sk")
    monkeypatch.setenv("OSS_REGION", "cn-shanghai")
    monkeypatch.setenv("OSS_BUCKET_NAME", "test-bucket")

    config = OSSConfig.from_env()

    assert config.access_key_id == "oss_ak"
    assert config.access_key_secret == "oss_sk"
    assert config.region == "cn-shanghai"
    assert config.bucket_name == "test-bucket"


def test_oss_config_ensure_valid():
    """Test OSSConfig validation."""
    # Valid config
    config = OSSConfig(
        region="cn-hangzhou",
        access_key_id="test_ak",
        access_key_secret="test_sk",
        bucket_name="test-bucket",
    )
    config.ensure_valid()  # Should not raise

    # Missing access_key_id
    config = OSSConfig(
        region="cn-hangzhou",
        access_key_secret="test_sk",
        bucket_name="test-bucket",
    )
    with pytest.raises(RuntimeError, match="Missing OSS configuration"):
        config.ensure_valid()


def test_log_config():
    """Test LogConfig dataclass."""
    log_config = LogConfig(
        logstore="test-store",
        project="test-project",
    )
    assert log_config.logstore == "test-store"
    assert log_config.project == "test-project"


def test_vpc_config():
    """Test VPCConfig dataclass."""
    vpc_config = VPCConfig(
        vpc_id="vpc-123",
        security_group_id="sg-456",
        vswitch_ids=["vsw-1", "vsw-2"],
    )
    assert vpc_config.vpc_id == "vpc-123"
    assert vpc_config.security_group_id == "sg-456"
    assert vpc_config.vswitch_ids == ["vsw-1", "vsw-2"]


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


@pytest.mark.asyncio
async def test_deploy_with_environment_variables(
    tmp_path: Path,
    mock_fc_config: FCConfig,
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
        "agentscope_runtime.engine.deployers.fc_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ), patch(
        "agentscope_runtime.engine.deployers.fc_deployer.build_wheel",
        return_value=fake_wheel,
    ), patch.object(
        FCDeployManager,
        "_build_and_zip_in_docker",
        new_callable=AsyncMock,
        return_value=fake_zip,
    ), patch.object(
        FCDeployManager,
        "_upload_to_fixed_oss_bucket",
        new_callable=AsyncMock,
        return_value={"bucket_name": "test-bucket", "object_key": "test.zip"},
    ):
        deployer = FCDeployManager(
            oss_config=mock_oss_config,
            fc_config=mock_fc_config,
            build_root=tmp_path / ".b10",
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


def test_merge_environment_variables(
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test _merge_environment_variables method."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b11",
    )

    custom_env = {"MY_VAR": "my_value", "DEBUG": "true"}
    merged = deployer._merge_environment_variables(custom_env)

    # Check that Python 3.12 paths are included
    assert "PATH" in merged
    assert "PYTHONPATH" in merged
    assert "LD_LIBRARY_PATH" in merged
    assert merged["PYTHON_VERSION"] == "3.12"

    # Check that custom variables are included
    assert merged["MY_VAR"] == "my_value"
    assert merged["DEBUG"] == "true"


def test_merge_environment_variables_empty(
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test _merge_environment_variables with no custom variables."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b12",
    )

    merged = deployer._merge_environment_variables(None)

    # Check that Python 3.12 paths are included
    assert "PATH" in merged
    assert "PYTHONPATH" in merged
    assert merged["PYTHON_VERSION"] == "3.12"


@pytest.mark.asyncio
async def test_stop_deployment(
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test stopping an FC deployment."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b13",
    )

    # Mock state manager
    mock_deployment = MagicMock()
    mock_deployment.url = "http://console.example.com"
    mock_deployment.config = {"resource_name": "test-function"}
    deployer.state_manager.get = MagicMock(return_value=mock_deployment)
    deployer.state_manager.update_status = MagicMock()

    # Mock the delete method
    deployer.client.delete_trigger_with_options = MagicMock()
    deployer.client.delete_function_with_options = MagicMock()

    result = await deployer.stop(deploy_id="test-deploy-id")

    assert result["success"] is True
    deployer.state_manager.update_status.assert_called_once_with(
        "test-deploy-id",
        "stopped",
    )


@pytest.mark.asyncio
async def test_generate_wrapper_and_build_wheel(
    tmp_path: Path,
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test _generate_wrapper_and_build_wheel method."""
    project_dir = _make_temp_project(tmp_path)

    wrapper_dir = tmp_path / "wrapper"
    wrapper_dir.mkdir()
    fake_wheel = wrapper_dir / "dist" / "pkg-0.0.1-py3-none-any.whl"
    fake_wheel.parent.mkdir(parents=True, exist_ok=True)
    fake_wheel.write_bytes(b"wheel-bytes")

    with patch(
        "agentscope_runtime.engine.deployers.fc_deployer"
        ".generate_wrapper_project",
        return_value=(wrapper_dir, wrapper_dir / "dist"),
    ) as gen_mock, patch(
        "agentscope_runtime.engine.deployers.fc_deployer.build_wheel",
        return_value=fake_wheel,
    ) as build_mock:
        deployer = FCDeployManager(
            oss_config=mock_oss_config,
            fc_config=mock_fc_config,
            build_root=tmp_path / ".b14",
        )

        wheel_path, name = await deployer._generate_wrapper_and_build_wheel(
            project_dir=str(project_dir),
            cmd="python app.py",
            deploy_name="test-deploy",
        )

    assert wheel_path == fake_wheel
    assert name == "test-deploy"
    gen_mock.assert_called_once()
    build_mock.assert_called_once()


@pytest.mark.asyncio
async def test_generate_wrapper_missing_project_dir(
    tmp_path: Path,
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test _generate_wrapper_and_build_wheel raises error for missing dir."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b15",
    )

    with pytest.raises(ValueError, match="project_dir and cmd are required"):
        await deployer._generate_wrapper_and_build_wheel(
            project_dir=None,
            cmd="python app.py",
        )


@pytest.mark.asyncio
async def test_generate_wrapper_nonexistent_project_dir(
    tmp_path: Path,
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test _generate_wrapper_and_build_wheel
    raises error for nonexistent dir."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b16",
    )

    with pytest.raises(FileNotFoundError, match="Project directory not found"):
        await deployer._generate_wrapper_and_build_wheel(
            project_dir=str(tmp_path / "nonexistent"),
            cmd="python app.py",
        )


def test_generate_env_file(
    tmp_path: Path,
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test _generate_env_file method."""
    project_dir = _make_temp_project(tmp_path)

    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b17",
    )

    environment = {"API_KEY": "secret", "DEBUG": "true"}
    env_file_path = deployer._generate_env_file(project_dir, environment)

    assert env_file_path is not None
    assert env_file_path.exists()

    content = env_file_path.read_text()
    assert "API_KEY=secret" in content
    assert "DEBUG=true" in content


def test_generate_env_file_with_special_chars(
    tmp_path: Path,
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test _generate_env_file handles special characters."""
    project_dir = _make_temp_project(tmp_path)

    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b18",
    )

    environment = {"MESSAGE": "hello world with spaces"}
    env_file_path = deployer._generate_env_file(project_dir, environment)

    assert env_file_path is not None
    content = env_file_path.read_text()
    assert 'MESSAGE="hello world with spaces"' in content


def test_generate_env_file_returns_none_for_empty(
    tmp_path: Path,
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
):
    """Test _generate_env_file returns None for empty environment."""
    project_dir = _make_temp_project(tmp_path)

    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b19",
    )

    result = deployer._generate_env_file(project_dir, None)
    assert result is None

    result = deployer._generate_env_file(project_dir, {})
    assert result is None


def test_fc_config_default_values():
    """Test FCConfig default values."""
    config = FCConfig()

    assert config.region_id == "cn-hangzhou"
    assert config.cpu == 2.0
    assert config.memory == 2048
    assert config.disk == 512
    assert config.session_concurrency_limit == 200
    assert config.session_idle_timeout_seconds == 3600


def test_oss_config_default_values():
    """Test OSSConfig default values."""
    config = OSSConfig(bucket_name="test-bucket")

    assert config.region == "cn-hangzhou"
    assert config.bucket_name == "test-bucket"


@pytest.mark.asyncio
async def test_deploy_to_fc_handles_exception(
    mock_fc_config: FCConfig,
    mock_oss_config: OSSConfig,
    tmp_path: Path,
):
    """Test deploy_to_fc handles exceptions gracefully."""
    deployer = FCDeployManager(
        oss_config=mock_oss_config,
        fc_config=mock_fc_config,
        build_root=tmp_path / ".b20",
    )

    # Mock the client to raise an exception
    deployer.client.create_function_with_options = MagicMock(
        side_effect=Exception("API Error"),
    )

    result = await deployer.deploy_to_fc(
        agent_runtime_name="error-function",
        oss_bucket_name="test-bucket",
        oss_object_name="test-object.zip",
    )

    assert result["success"] is False
    assert "API Error" in result["error"]


def test_http_trigger_name_constant():
    """Test HTTP_TRIGGER_NAME constant."""
    assert FCDeployManager.HTTP_TRIGGER_NAME == "agentscope-runtime-trigger"
