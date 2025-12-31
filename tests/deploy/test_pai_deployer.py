# -*- coding: utf-8 -*-
"""
Tests for PAI Deployer

Run with: pytest tests/deploy/test_pai_deployer.py
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from agentscope_runtime.engine.deployers.pai_deployer import (
    PAIDeployManager,
    PAIConfig,
    OSSConfig,
    _assert_cloud_sdks_available,
)


class TestPAIConfig:
    """Test PAIConfig class."""

    def test_from_env_with_workspace_id(self):
        """Test creating PAIConfig from environment variables."""
        with patch.dict(
            os.environ,
            {
                "PAI_WORKSPACE_ID": "285773",
                "PAI_REGION_ID": "cn-beijing",
                "ALIBABA_CLOUD_ACCESS_KEY_ID": "test_ak",
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "test_sk",
            },
        ):
            config = PAIConfig.from_env()
            assert config.workspace_id == "285773"
            assert config.region_id == "cn-beijing"
            assert config.endpoint == "pailangstudio.cn-beijing.aliyuncs.com"
            assert config.access_key_id == "test_ak"
            assert config.access_key_secret == "test_sk"

    def test_from_env_with_parameter(self):
        """Test creating PAIConfig with workspace_id parameter."""
        with patch.dict(
            os.environ,
            {
                "ALIBABA_CLOUD_ACCESS_KEY_ID": "test_ak",
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "test_sk",
            },
        ):
            config = PAIConfig.from_env(workspace_id="custom_ws")
            assert config.workspace_id == "custom_ws"

    def test_ensure_valid_success(self):
        """Test ensure_valid with valid configuration."""
        config = PAIConfig(
            workspace_id="285773",
            access_key_id="test_ak",
            access_key_secret="test_sk",
        )
        config.ensure_valid()  # Should not raise

    def test_ensure_valid_missing_credentials(self):
        """Test ensure_valid with missing credentials."""
        config = PAIConfig(workspace_id="285773")
        with pytest.raises(RuntimeError, match="Missing required PAI configuration"):
            config.ensure_valid()

    def test_ensure_valid_missing_workspace(self):
        """Test ensure_valid with missing workspace_id."""
        config = PAIConfig(
            access_key_id="test_ak",
            access_key_secret="test_sk",
        )
        with pytest.raises(RuntimeError, match="workspace_id"):
            config.ensure_valid()


class TestOSSConfig:
    """Test OSSConfig class."""

    def test_from_env(self):
        """Test creating OSSConfig from environment variables."""
        with patch.dict(
            os.environ,
            {
                "OSS_REGION": "cn-shanghai",
                "OSS_ACCESS_KEY_ID": "oss_ak",
                "OSS_ACCESS_KEY_SECRET": "oss_sk",
                "OSS_PATH": "oss://test-bucket/path/",
            },
        ):
            config = OSSConfig.from_env()
            assert config.region == "cn-shanghai"
            assert config.access_key_id == "oss_ak"
            assert config.access_key_secret == "oss_sk"
            assert config.oss_path == "oss://test-bucket/path/"

    def test_from_env_with_fallback_credentials(self):
        """Test fallback to ALIBABA_CLOUD credentials."""
        with patch.dict(
            os.environ,
            {
                "ALIBABA_CLOUD_ACCESS_KEY_ID": "cloud_ak",
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "cloud_sk",
            },
        ):
            config = OSSConfig.from_env()
            assert config.access_key_id == "cloud_ak"
            assert config.access_key_secret == "cloud_sk"

    def test_ensure_valid_success(self):
        """Test ensure_valid with valid configuration."""
        config = OSSConfig(
            access_key_id="test_ak",
            access_key_secret="test_sk",
            oss_path="oss://bucket/path/",
        )
        config.ensure_valid()  # Should not raise

    def test_ensure_valid_missing_oss_path(self):
        """Test ensure_valid with missing oss_path."""
        config = OSSConfig(
            access_key_id="test_ak",
            access_key_secret="test_sk",
        )
        with pytest.raises(RuntimeError, match="oss_path"):
            config.ensure_valid()


class TestPAIDeployManager:
    """Test PAIDeployManager class."""

    def test_init_default(self):
        """Test initialization with default configs."""
        with patch.dict(os.environ, {}, clear=True):
            deployer = PAIDeployManager()
            assert deployer.oss_config is not None
            assert deployer.pai_config is not None
            assert deployer.build_root is None

    def test_init_with_configs(self):
        """Test initialization with provided configs."""
        oss_config = OSSConfig(
            access_key_id="ak",
            access_key_secret="sk",
            oss_path="oss://bucket/",
        )
        pai_config = PAIConfig(
            workspace_id="ws",
            access_key_id="ak",
            access_key_secret="sk",
        )
        deployer = PAIDeployManager(
            oss_config=oss_config,
            pai_config=pai_config,
            build_root="/tmp/build",
        )
        assert deployer.oss_config == oss_config
        assert deployer.pai_config == pai_config
        assert deployer.build_root == Path("/tmp/build")

    def test_parse_oss_path_standard(self):
        """Test parsing standard OSS path."""
        deployer = PAIDeployManager()
        bucket, prefix = deployer._parse_oss_path("oss://my-bucket/path/to/dir/")
        assert bucket == "my-bucket"
        assert prefix == "path/to/dir/"

    def test_parse_oss_path_with_internal_suffix(self):
        """Test parsing OSS path with internal suffix."""
        deployer = PAIDeployManager()
        bucket, prefix = deployer._parse_oss_path(
            "oss://my-bucket-internal.aliyuncs.com/path/",
        )
        assert bucket == "my-bucket"
        assert prefix == "path/"

    def test_parse_oss_path_no_prefix(self):
        """Test parsing OSS path without prefix."""
        deployer = PAIDeployManager()
        bucket, prefix = deployer._parse_oss_path("oss://my-bucket")
        assert bucket == "my-bucket"
        assert prefix == ""

    def test_parse_oss_path_invalid(self):
        """Test parsing invalid OSS path."""
        deployer = PAIDeployManager()
        with pytest.raises(ValueError, match="Invalid OSS path format"):
            deployer._parse_oss_path("invalid://bucket/path")

    def test_build_deployment_config_public(self):
        """Test building deployment config for public resource."""
        deployer = PAIDeployManager()
        deployer.pai_config.workspace_id = "285773"

        config_str = deployer._build_deployment_config(
            resource_type="public",
            instance_count=2,
            instance_type=["ecs.g7.xlarge", "ecs.g6.xlarge"],
        )

        import json

        config = json.loads(config_str)
        assert config["metadata"]["instance"] == 2
        assert config["metadata"]["workspace_id"] == "285773"
        assert "computing" in config["cloud"]
        assert len(config["cloud"]["computing"]["instances"]) == 2

    def test_build_deployment_config_eas_group(self):
        """Test building deployment config for EAS resource group."""
        deployer = PAIDeployManager()
        deployer.pai_config.workspace_id = "285773"

        config_str = deployer._build_deployment_config(
            resource_type="eas_group",
            instance_count=3,
            resource_id="eas-r-test123",
            cpu=4,
            memory=8000,
        )

        import json

        config = json.loads(config_str)
        assert config["metadata"]["instance"] == 3
        assert config["metadata"]["resource"] == "eas-r-test123"
        assert config["metadata"]["cpu"] == 4
        assert config["metadata"]["memory"] == 8000

    def test_build_deployment_config_quota(self):
        """Test building deployment config for quota."""
        deployer = PAIDeployManager()
        deployer.pai_config.workspace_id = "285773"

        config_str = deployer._build_deployment_config(
            resource_type="quota",
            instance_count=1,
            quota_id="quota-test",
            cpu=8,
            memory=16000,
        )

        import json

        config = json.loads(config_str)
        assert config["metadata"]["quota_id"] == "quota-test"
        assert config["metadata"]["cpu"] == 8
        assert config["metadata"]["memory"] == 16000
        assert config["options"]["priority"] == 9

    def test_build_deployment_config_with_vpc(self):
        """Test building deployment config with VPC settings."""
        deployer = PAIDeployManager()
        deployer.pai_config.workspace_id = "285773"

        config_str = deployer._build_deployment_config(
            resource_type="public",
            instance_count=1,
            instance_type=["ecs.g7.xlarge"],
            vpc_id="vpc-test",
            vswitch_id="vsw-test",
            security_group_id="sg-test",
        )

        import json

        config = json.loads(config_str)
        assert config["cloud"]["networking"]["vpc_id"] == "vpc-test"
        assert config["cloud"]["networking"]["vswitch_id"] == "vsw-test"
        assert config["cloud"]["networking"]["security_group_id"] == "sg-test"

    def test_build_deployment_config_missing_resource_id(self):
        """Test building config for eas_group without resource_id."""
        deployer = PAIDeployManager()
        deployer.pai_config.workspace_id = "285773"

        with pytest.raises(ValueError, match="resource_id required"):
            deployer._build_deployment_config(
                resource_type="eas_group",
                instance_count=1,
            )

    def test_build_deployment_config_missing_quota_id(self):
        """Test building config for quota without quota_id."""
        deployer = PAIDeployManager()
        deployer.pai_config.workspace_id = "285773"

        with pytest.raises(ValueError, match="quota_id required"):
            deployer._build_deployment_config(
                resource_type="quota",
                instance_count=1,
            )

    def test_build_credential_config_default(self):
        """Test building credential config with default mode."""
        deployer = PAIDeployManager()
        config = deployer._build_credential_config(ram_role_mode="default")

        assert config["EnableCredentialInject"] is True
        assert config["AliyunEnvRoleKey"] == "0"
        assert len(config["CredentialConfigItems"]) == 1
        assert config["CredentialConfigItems"][0]["Type"] == "Role"

    def test_build_credential_config_custom(self):
        """Test building credential config with custom mode."""
        deployer = PAIDeployManager()
        config = deployer._build_credential_config(
            ram_role_mode="custom",
            ram_role_arn="acs:ram::123456:role/TestRole",
        )

        assert config["EnableCredentialInject"] is True
        assert config["CredentialConfigItems"][0]["Roles"] == [
            "acs:ram::123456:role/TestRole",
        ]

    def test_build_credential_config_none(self):
        """Test building credential config with none mode."""
        deployer = PAIDeployManager()
        config = deployer._build_credential_config(ram_role_mode="none")

        assert config["EnableCredentialInject"] is False

    def test_build_credential_config_custom_missing_arn(self):
        """Test building custom credential config without ARN."""
        deployer = PAIDeployManager()

        with pytest.raises(ValueError, match="ram_role_arn required"):
            deployer._build_credential_config(ram_role_mode="custom")

    @pytest.mark.asyncio
    async def test_deploy_missing_service_name(self):
        """Test deploy with missing service_name."""
        deployer = PAIDeployManager()

        with pytest.raises(ValueError, match="service_name is required"):
            await deployer.deploy(
                app=Mock(),
                oss_path="oss://bucket/path/",
            )

    @pytest.mark.asyncio
    async def test_deploy_missing_project_and_app(self):
        """Test deploy with missing project_dir and app."""
        deployer = PAIDeployManager()
        deployer.oss_config.oss_path = "oss://bucket/path/"
        deployer.pai_config.workspace_id = "285773"

        with patch("agentscope_runtime.engine.deployers.pai_deployer._assert_cloud_sdks_available"):
            with pytest.raises(
                ValueError,
                match="Either project_dir or app/runner must be provided",
            ):
                await deployer.deploy(
                    service_name="test-service",
                )


class TestAssertCloudSDKs:
    """Test cloud SDK assertion."""

    @patch("agentscope_runtime.engine.deployers.pai_deployer.oss", None)
    def test_assert_sdks_missing_oss(self):
        """Test assertion when OSS SDK is missing."""
        with pytest.raises(RuntimeError, match="PAI SDKs not installed"):
            _assert_cloud_sdks_available()

    @patch("agentscope_runtime.engine.deployers.pai_deployer.PAIClient", None)
    def test_assert_sdks_missing_pai(self):
        """Test assertion when PAI SDK is missing."""
        with pytest.raises(RuntimeError, match="PAI SDKs not installed"):
            _assert_cloud_sdks_available()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

