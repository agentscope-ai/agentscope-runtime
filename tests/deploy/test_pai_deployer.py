# -*- coding: utf-8 -*-
# pylint:disable=unused-variable,protected-access
"""
E2E tests for PAIDeployManager.
"""
from datetime import datetime
import logging
import os
from pathlib import Path

import logging
from typing import Dict
from urllib.parse import urljoin
import pytest

from agentscope_runtime.engine.deployers.pai_deployer import (
    PAIDeployManager,
)
from agentscope_runtime.engine.helpers.agent_api_client import (
    HTTPAgentAPIClient,
    create_simple_text_request,
)

logger = logging.getLogger(__name__)


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
    else:
        return api_key


@pytest.fixture
def vpc_config() -> Dict[str, str]:
    """ """
    vpc_id = os.getenv("VPC_ID", "")
    security_group_id = os.getenv("SECURITY_GROUP_ID", "")
    vswitch_id = os.getenv("VSWITCH_ID", "")
    if not vpc_id or not security_group_id or not vswitch_id:
        pytest.skip("VPC_ID, SECURITY_GROUP_ID, VSWITCH_ID are not set")
    else:
        return {
            "vpc_id": vpc_id,
            "security_group_id": security_group_id,
            "vswitch_id": vswitch_id,
        }


@pytest.fixture
async def service_name(deploy_manager: PAIDeployManager) -> str:
    service_name = (
        f"test_agentscope_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    # ensure the given service_name/project is not exists
    try:
        await deploy_manager.delete_service(service_name)
    except Exception as e:
        logging.info("Error deleting service: %s", e)
    try:
        await deploy_manager.delete_project(service_name)
    except Exception as e:
        logger.info("Error deleting project: %s", e)

    yield service_name

    # cleanup
    try:
        await deploy_manager.delete_service(service_name)
    except Exception as e:
        logger.warning("Error deleting service: %s", e)

    try:
        await deploy_manager.delete_project(service_name)
    except Exception as e:
        logger.warning("Error deleting project: %s", e)


@pytest.fixture
def deploy_manager():
    """Create a PAIDeployManager instance for testing."""
    return PAIDeployManager(
        workspace_id="285773",
        region_id="cn-hangzhou",
        oss_path="oss://langstudio-hangzhou-pre/test-path/",
    )


@pytest.mark.asyncio
async def test_deploy_with_nonexistent_project(deploy_manager):
    """Test deploy with non-existent project directory."""
    with pytest.raises(FileNotFoundError, match="Project directory not found"):
        await deploy_manager.deploy(
            service_name="test-service",
            project_dir="/nonexistent/path",
        )


@pytest.mark.asyncio
async def test_deploy_with_project_dir(
    agentscope_proj_dir: Path,
    deploy_manager: PAIDeployManager,
    service_name: str,
    dashscope_api_key: str,
    vpc_config: Dict[str, str],
):
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
        create_simple_text_request(query="北京今天的天气如何?")
    ):
        events.append(event)

    assert len(events) > 2

    result_2 = await deploy_manager.deploy(
        project_dir=agentscope_proj_dir,
        service_name=service_name,
        wait=True,
        auto_approve=False,
        environment={
            "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY", ""),
        },
    )

    assert result_2["status"] == "pending"
    assert result_2.get("deploy_id") is not None


async def test_list_workspace_configs(deploy_manager: PAIDeployManager):
    from alibabacloud_aiworkspace20210204.models import ListConfigsRequest

    DEFAULT_OSS_STORAGE_URI = "modelExportPath"

    resp = await deploy_manager.get_workspace_client().list_configs_async(
        workspace_id=deploy_manager.workspace_id,
        request=ListConfigsRequest(config_keys=DEFAULT_OSS_STORAGE_URI),
    )
    default_oss_storage_uri = next(
        (
            c
            for c in resp.body.configs
            if c.config_key == DEFAULT_OSS_STORAGE_URI
        ),
        None,
    )

    assert default_oss_storage_uri is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
