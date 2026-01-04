# -*- coding: utf-8 -*-
# pylint:disable=unused-variable,protected-access
"""
E2E tests for PAIDeployManager.
"""
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime

import pytest

from agentscope_runtime.engine.deployers.pai_deployer import (
    PAIDeployManager,
    OSSConfig,
    PAIConfig,
)


class TestPAIDeployManager:
    """Test PAIDeployManager functionality."""

    @pytest.fixture
    def oss_config(self):
        """Create test OSS config."""
        return OSSConfig(
            region="cn-hangzhou",
            access_key_id="test_key",
            access_key_secret="test_secret",
            oss_path="oss://langstudio-pre/test-path/",
        )

    @pytest.fixture
    def pai_config(self):
        """Create test PAI config."""
        return PAIConfig(
            endpoint="pailangstudio.cn-hangzhou.aliyuncs.com",
            workspace_id="12345",
            region_id="cn-hangzhou",
            access_key_id="test_key",
            access_key_secret="test_secret",
        )

    @pytest.fixture
    def deploy_manager(self, oss_config, pai_config):
        """Create a PAIDeployManager instance for testing."""
        return PAIDeployManager(
            oss_config=oss_config,
            pai_config=pai_config,
        )



    @pytest.mark.asyncio
    async def test_deploy_with_nonexistent_project(self, deploy_manager):
        """Test deploy with non-existent project directory."""
        with pytest.raises(
            FileNotFoundError, match="Project directory not found"
        ):
            await deploy_manager.deploy(
                service_name="test-service",
                project_dir="/nonexistent/path",
            )

    @pytest.mark.asyncio
    async def test_deploy_success_without_wait(
        self,
        mock_get_client,
        mock_deploy_snapshot,
        mock_create_snapshot,
        mock_get_or_create_proj,
        mock_upload_archive,
        mock_assert_sdks,
        deploy_manager,
        tmp_path,
    ):
        """Test successful deployment without waiting."""
        project_dir = _make_temp_project(tmp_path)

        # Setup mocks
        mock_upload_archive.return_value = "oss://bucket/path/archive.zip"
        mock_get_or_create_proj.return_value = "flow-123"
        mock_create_snapshot.return_value = "snapshot-456"
        mock_deploy_snapshot.return_value = "deployment-789"

        result = await deploy_manager.deploy(
            project_dir=str(project_dir),
            service_name="test-service",
            oss_path="oss://test-bucket/path/",
            wait=False,
        )

        # Assertions
        assert result["service_name"] == "test-service"
        assert result["flow_id"] == "flow-123"
        assert result["snapshot_id"] == "snapshot-456"
        assert result["pai_deployment_id"] == "deployment-789"
        assert result["status"] == "deploying"
        assert "deploy_id" in result

        # Verify mocks were called
        mock_assert_sdks.assert_called_once()
        mock_upload_archive.assert_called_once()
        mock_get_or_create_proj.assert_called_once()
        mock_create_snapshot.assert_called_once()
        mock_deploy_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_success_with_wait(
        self,
        mock_get_client,
        mock_wait_deployment,
        mock_deploy_snapshot,
        mock_create_snapshot,
        mock_get_or_create_proj,
        mock_upload_archive,
        mock_assert_sdks,
        deploy_manager,
        tmp_path,
    ):
        """Test successful deployment with waiting."""
        project_dir = _make_temp_project(tmp_path)

        # Setup mocks
        mock_upload_archive.return_value = "oss://bucket/path/archive.zip"
        mock_get_or_create_proj.return_value = "flow-123"
        mock_create_snapshot.return_value = "snapshot-456"
        mock_deploy_snapshot.return_value = "deployment-789"
        mock_wait_deployment.return_value = {"Status": "Running"}

        result = await deploy_manager.deploy(
            project_dir=str(project_dir),
            service_name="test-service",
            oss_path="oss://test-bucket/path/",
            wait=True,
            auto_approve=True,
        )

        # Assertions
        assert result["status"] == "running"
        mock_wait_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_deployment(
        self, mock_get_client, mock_assert_sdks, deploy_manager
    ):
        """Test stopping a deployment."""
        # Create a mock deployment in state
        from agentscope_runtime.engine.deployers.state import Deployment

        deployment = Deployment(
            id="test-deploy-id",
            platform="pai",
            url="https://console.url",
            status="running",
            created_at=datetime.now().isoformat(),
            config={
                "pai_deployment_id": "pai-deployment-123",
                "flow_id": "flow-123",
            },
        )
        deploy_manager.state_manager.save(deployment)

        # Mock PAI client
        mock_client = MagicMock()
        mock_client.delete_deployment_with_options = MagicMock()
        mock_get_client.return_value = mock_client

        result = await deploy_manager.stop("test-deploy-id")

        assert result["success"] is True
        assert "Deployment" in result["message"]

    def test_get_oss_endpoint(self):
        """Test getting OSS endpoint."""
        endpoint = PAIDeployManager._get_oss_endpoint("cn-hangzhou")
        # Should return either internal or public endpoint
        assert "oss-cn-hangzhou" in endpoint
        assert "aliyuncs.com" in endpoint


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
