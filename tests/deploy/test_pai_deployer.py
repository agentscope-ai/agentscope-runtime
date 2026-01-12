# -*- coding: utf-8 -*-
# pylint:disable=unused-variable,protected-access
# pylint: disable=redefined-outer-name
"""
E2E tests for PAIDeployManager.
"""
from datetime import datetime
import logging
import os
import zipfile
from pathlib import Path
from typing import AsyncIterator, Dict
from urllib.parse import urljoin

import pytest

from agentscope_runtime.engine.deployers.pai_deployer import (
    PAIDeployManager,
    PAIDeployConfig,
    _should_ignore,
    _get_default_ignore_patterns,
)
from agentscope_runtime.engine.helpers.agent_api_client import (
    HTTPAgentAPIClient,
    create_simple_text_request,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def agentscope_proj_dir() -> Path:
    """
    AgentScope Project Directory for testing.
    """
    test_data_dir = (
        Path(__file__).parent.parent / "test_data" / "agentscope_agent"
    )
    return test_data_dir


@pytest.fixture
def dashscope_api_key() -> str:
    """
    Dashscope API Key for testing.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY", "")

    if not api_key:
        pytest.skip("DASHSCOPE_API_KEY is not set")
    return api_key


@pytest.fixture
def vpc_config() -> Dict[str, str]:
    """VPC configuration for testing."""
    vpc_id = os.getenv("VPC_ID", "")
    security_group_id = os.getenv("SECURITY_GROUP_ID", "")
    vswitch_id = os.getenv("VSWITCH_ID", "")
    if not vpc_id or not security_group_id or not vswitch_id:
        pytest.skip("VPC_ID, SECURITY_GROUP_ID, VSWITCH_ID are not set")
    return {
        "vpc_id": vpc_id,
        "security_group_id": security_group_id,
        "vswitch_id": vswitch_id,
    }


@pytest.fixture
def workspace_id() -> str:
    """Workspace ID for testing."""
    workspace_id = os.getenv("PAI_WORKSPACE_ID", "")
    if not workspace_id:
        pytest.skip("PAI_WORKSPACE_ID is not set")
    return workspace_id


@pytest.fixture
async def service_name(deploy_manager: PAIDeployManager) -> AsyncIterator[str]:
    """Generate unique service name and cleanup after test."""
    svc_name = (
        f"test_agentscope_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    # ensure the given service_name/project is not exists
    try:
        await deploy_manager.delete_service(svc_name)
    except Exception as e:
        logging.info("Error deleting service: %s", e)
    try:
        await deploy_manager.delete_project(svc_name)
    except Exception as e:
        logger.info("Error deleting project: %s", e)

    yield svc_name

    # cleanup
    try:
        await deploy_manager.delete_service(svc_name)
    except Exception as e:
        logger.warning("Error deleting service: %s", e)

    try:
        await deploy_manager.delete_project(svc_name)
    except Exception as e:
        logger.warning("Error deleting project: %s", e)


@pytest.fixture
def deploy_manager(workspace_id: str):
    """Create a PAIDeployManager instance for testing."""
    deployer_manager = PAIDeployManager(workspace_id=workspace_id)

    if not deployer_manager.workspace_id or not deployer_manager.region_id:
        pytest.skip("PAI_WORKSPACE_ID or REGION_ID is not set")
    return deployer_manager


# =============================================================================
# Unit Tests (No cloud resources required)
# =============================================================================


class TestPAIDeployConfig:
    """Unit tests for PAIDeployConfig configuration handling."""

    def test_from_yaml_basic(self, tmp_path: Path):
        """Test loading basic configuration from YAML."""
        config_content = """
context:
  workspace_id: "test-workspace"
  region: "cn-hangzhou"
spec:
  name: "test-service"
  code:
    source_dir: "my_agent"
    entrypoint: "agent.py"
  resources:
    type: "public"
    instance_type: "ecs.c6.large"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = PAIDeployConfig.from_yaml(config_file)

        assert config.context.workspace_id == "test-workspace"
        assert config.context.region == "cn-hangzhou"
        assert config.spec.name == "test-service"
        assert config.spec.code.source_dir == "my_agent"
        assert config.spec.resources.type == "public"

    def test_merge_cli_overrides(self):
        """Test CLI parameters override YAML config."""
        config = PAIDeployConfig.from_dict(
            {
                "context": {
                    "workspace_id": "yaml-workspace",
                    "region": "cn-hangzhou",
                },
                "spec": {"name": "yaml-service"},
            },
        )

        merged = config.merge_cli(
            name="cli-service",
            workspace_id="cli-workspace",
            instance_count=3,
        )

        assert merged.spec.name == "cli-service"
        assert merged.context.workspace_id == "cli-workspace"
        assert merged.spec.resources.instance_count == 3
        # Original unchanged
        assert config.spec.name == "yaml-service"

    def test_resolve_resource_type_inference(self):
        """Test resource type auto-inference."""
        # Default to public
        config1 = PAIDeployConfig()
        assert config1.resolve_resource_type() == "public"

        # Infer quota from quota_id
        config2 = PAIDeployConfig.from_dict(
            {
                "spec": {"resources": {"quota_id": "quota-123"}},
            },
        )
        assert config2.resolve_resource_type() == "quota"

        # Infer resource from resource_id
        config3 = PAIDeployConfig.from_dict(
            {
                "spec": {"resources": {"resource_id": "res-123"}},
            },
        )
        assert config3.resolve_resource_type() == "resource"

        # Explicit type takes priority
        config4 = PAIDeployConfig.from_dict(
            {
                "spec": {
                    "resources": {"type": "public", "quota_id": "quota-123"},
                },
            },
        )
        assert config4.resolve_resource_type() == "public"

    def test_validate_for_deploy_missing_name(self, tmp_path: Path):
        """Test validation fails when service name is missing."""
        config = PAIDeployConfig.from_dict(
            {
                "spec": {"code": {"source_dir": str(tmp_path)}},
            },
        )

        with pytest.raises(ValueError, match="Service name is required"):
            config.validate_for_deploy()

    def test_validate_for_deploy_missing_source_dir(self):
        """Test validation fails when source_dir is missing."""
        config = PAIDeployConfig.from_dict(
            {
                "spec": {"name": "test-service"},
            },
        )

        with pytest.raises(ValueError, match="Source directory is required"):
            config.validate_for_deploy()

    def test_validate_for_deploy_source_not_exists(self):
        """Test validation fails when source_dir doesn't exist."""
        config = PAIDeployConfig.from_dict(
            {
                "spec": {
                    "name": "test-service",
                    "code": {"source_dir": "/nonexistent/path"},
                },
            },
        )

        with pytest.raises(ValueError, match="Source directory not found"):
            config.validate_for_deploy()

    def test_validate_resource_mode_requirements(self, tmp_path: Path):
        """Test validation for resource/quota mode requirements."""
        # resource mode without resource_id
        config1 = PAIDeployConfig.from_dict(
            {
                "spec": {
                    "name": "test-service",
                    "code": {"source_dir": str(tmp_path)},
                    "resources": {"type": "resource"},
                },
            },
        )
        with pytest.raises(ValueError, match="resource_id is required"):
            config1.validate_for_deploy()

        # quota mode without quota_id
        config2 = PAIDeployConfig.from_dict(
            {
                "spec": {
                    "name": "test-service",
                    "code": {"source_dir": str(tmp_path)},
                    "resources": {"type": "quota"},
                },
            },
        )
        with pytest.raises(ValueError, match="quota_id is required"):
            config2.validate_for_deploy()

    def test_to_deployer_kwargs(self, tmp_path: Path):
        """Test conversion to deployer kwargs."""
        config = PAIDeployConfig.from_dict(
            {
                "spec": {
                    "name": "test-service",
                    "code": {"source_dir": str(tmp_path)},
                    "resources": {"type": "public", "instance_count": 2},
                    "env": {"KEY1": "value1"},
                },
                "wait": False,
                "timeout": 600,
            },
        )

        kwargs = config.to_deployer_kwargs()

        assert kwargs["service_name"] == "test-service"
        assert kwargs["project_dir"] == str(tmp_path)
        assert kwargs["instance_count"] == 2
        assert kwargs["instance_type"] == "ecs.c6.large"  # default
        assert kwargs["environment"] == {"KEY1": "value1"}
        assert kwargs["wait"] is False
        assert kwargs["timeout"] == 600


class TestProjectArchiveIgnorePatterns:
    """Unit tests for project archive ignore patterns."""

    def test_default_ignore_patterns(self):
        """Test default ignore patterns are correctly defined."""
        patterns = _get_default_ignore_patterns()

        assert "__pycache__" in patterns
        assert ".git" in patterns
        assert ".venv" in patterns
        assert "node_modules" in patterns
        assert "*.pyc" in patterns

    def test_should_ignore_exact_match(self):
        """Test exact directory name matching."""
        patterns = ["__pycache__", ".git", "node_modules"]

        assert _should_ignore("__pycache__/cache.pyc", patterns)
        assert _should_ignore(".git/config", patterns)
        assert _should_ignore("src/__pycache__/module.pyc", patterns)
        assert not _should_ignore("src/main.py", patterns)

    def test_should_ignore_glob_patterns(self):
        """Test glob pattern matching."""
        patterns = ["*.pyc", "*.log", "temp_*"]

        assert _should_ignore("module.pyc", patterns)
        assert _should_ignore("app.log", patterns)
        assert _should_ignore("temp_file.txt", patterns)
        assert not _should_ignore("module.py", patterns)

    def test_should_ignore_path_prefix(self):
        """Test path prefix matching."""
        patterns = ["build", "dist"]

        assert _should_ignore("build/output.js", patterns)
        assert _should_ignore("dist/bundle.js", patterns)
        assert not _should_ignore("src/build.py", patterns)

    def test_create_project_archive_excludes_ignored(self, tmp_path: Path):
        """Test that archive correctly excludes ignored files."""
        # Create test project structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create files
        (project_dir / "main.py").write_text("print('hello')")
        (project_dir / "requirements.txt").write_text("requests==2.28.0")

        # Create ignored directories/files
        pycache = project_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-310.pyc").write_bytes(b"compiled")

        git_dir = project_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        venv_dir = project_dir / ".venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("venv config")

        # Create .gitignore
        (project_dir / ".gitignore").write_text("*.log\nsecrets/")

        secrets_dir = project_dir / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "api_key.txt").write_text("secret-key")

        (project_dir / "app.log").write_text("log content")

        # Create archive using deployer
        deployer = PAIDeployManager.__new__(PAIDeployManager)
        deployer.build_root = None

        archive_path = deployer._create_project_archive(
            "test-service",
            project_dir,
        )

        # Verify archive contents
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = zf.namelist()

        assert "main.py" in names
        assert "requirements.txt" in names

        # Should NOT contain ignored files
        assert not any("__pycache__" in n for n in names)
        assert not any(".git" in n for n in names)
        assert not any(".venv" in n for n in names)
        assert not any("secrets" in n for n in names)
        assert not any(".log" in n for n in names)


# =============================================================================
# E2E Tests (Require cloud resources)
# =============================================================================


@pytest.mark.asyncio
async def test_deploy_with_project_dir(
    agentscope_proj_dir: Path,
    deploy_manager: PAIDeployManager,
    service_name: str,
    dashscope_api_key: str,
    vpc_config: Dict[str, str],
):
    """E2E test: Deploy agent, invoke it, and stop the service."""
    result_1 = await deploy_manager.deploy(
        project_dir=agentscope_proj_dir,
        service_name=service_name,
        wait=True,
        auto_approve=True,
        environment={
            "DASHSCOPE_API_KEY": dashscope_api_key,
        },
        **vpc_config,
    )
    assert result_1["status"] == "running"
    assert result_1.get("deploy_id") is not None

    deployment = deploy_manager.state_manager.get(result_1["deploy_id"])

    assert deployment.token is not None, "Token is not found"
    assert deployment.url is not None, "URL is not found"

    client = HTTPAgentAPIClient(
        endpoint=urljoin(deployment.url.rstrip("/") + "/", "process"),
        token=deployment.token,
    )

    events = []
    async for event in client.astream(
        create_simple_text_request(query="北京今天的天气如何?"),
    ):
        events.append(event)

    assert len(events) > 2

    await deploy_manager.stop(result_1["deploy_id"])


@pytest.mark.asyncio
async def test_deploy_with_manual_approval(
    agentscope_proj_dir: Path,
    deploy_manager: PAIDeployManager,
    service_name: str,
    dashscope_api_key: str,
    vpc_config: Dict[str, str],
):
    """E2E test: Deploy with manual approval workflow."""
    # Step 1: Deploy without auto_approve
    result = await deploy_manager.deploy(
        project_dir=agentscope_proj_dir,
        service_name=service_name,
        wait=False,
        auto_approve=False,
        environment={
            "DASHSCOPE_API_KEY": dashscope_api_key,
        },
        **vpc_config,
    )
    assert result.get("deploy_id") is not None
    assert result["status"] == "pending"
    deployment_id = result["deploy_id"]

    # Step 2: Wait for approval stage
    await deploy_manager.wait_for_approval_stage(
        deployment_id,
        timeout=300,
    )

    # Step 3: Approve the deployment
    approve_result = await deploy_manager.approve_deployment(
        deployment_id,
        wait=True,
        timeout=1800,
    )
    assert approve_result["success"] is True

    # Step 4: Verify service is running
    service = await deploy_manager.get_service(service_name)
    assert service is not None
    assert service.status == "Running"

    # Step 5: Stop the service
    await deploy_manager.stop(deployment_id)


@pytest.mark.asyncio
async def test_deploy_cancel(
    agentscope_proj_dir: Path,
    deploy_manager: PAIDeployManager,
    service_name: str,
    dashscope_api_key: str,
    vpc_config: Dict[str, str],
):
    """E2E test: Cancel a deployment before approval."""
    # Step 1: Deploy without auto_approve
    result = await deploy_manager.deploy(
        project_dir=agentscope_proj_dir,
        service_name=service_name,
        wait=False,
        auto_approve=False,
        environment={
            "DASHSCOPE_API_KEY": dashscope_api_key,
        },
        **vpc_config,
    )
    assert result.get("deploy_id") is not None
    deployment_id = result["deploy_id"]

    # Step 2: Wait for approval stage
    await deploy_manager.wait_for_approval_stage(
        deployment_id,
        timeout=300,
    )

    # Step 3: Cancel the deployment
    cancel_result = await deploy_manager.cancel_deployment(deployment_id)
    assert cancel_result["success"] is True

    # Step 4: Verify service is not created or stopped
    service = await deploy_manager.get_service(service_name)
    # Service should be None or not in Running state
    assert service is None or service.status != "Running"


@pytest.mark.asyncio
async def test_redeploy_existing_service(
    agentscope_proj_dir: Path,
    deploy_manager: PAIDeployManager,
    service_name: str,
    dashscope_api_key: str,
    vpc_config: Dict[str, str],
):
    """E2E test: Redeploy to update an existing service."""
    # Step 1: First deployment
    result_1 = await deploy_manager.deploy(
        project_dir=agentscope_proj_dir,
        service_name=service_name,
        wait=True,
        auto_approve=True,
        environment={
            "DASHSCOPE_API_KEY": dashscope_api_key,
        },
        **vpc_config,
    )
    assert result_1["status"] == "running"
    flow_id_1 = result_1["flow_id"]

    # Step 2: Redeploy with updated environment
    result_2 = await deploy_manager.deploy(
        project_dir=agentscope_proj_dir,
        service_name=service_name,
        wait=True,
        auto_approve=True,
        environment={
            "DASHSCOPE_API_KEY": dashscope_api_key,
            "NEW_VAR": "new_value",
        },
        **vpc_config,
    )
    assert result_2["status"] == "running"
    flow_id_2 = result_2["flow_id"]

    # Step 3: Verify same flow project is reused
    assert flow_id_1 == flow_id_2, "Should reuse existing flow project"

    # Step 4: Verify service is running
    service = await deploy_manager.get_service(service_name)
    assert service is not None
    assert service.status == "Running"

    # Cleanup
    await deploy_manager.stop(result_2["deploy_id"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
