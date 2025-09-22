# -*- coding: utf-8 -*-
# pylint:disable=too-many-nested-blocks, too-many-return-statements,
# pylint:disable=too-many-branches, too-many-statements, try-except-raise
# pylint:disable=ungrouped-imports, arguments-renamed, protected-access
#
# flake8: noqa: E501
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, List, Union, Tuple

from pydantic import BaseModel, Field

from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .local_deployer import LocalDeployManager
from .utils.service_utils import (
    ServicesConfig,
)
from .utils.wheel_packager import (
    generate_wrapper_project,
    build_wheel,
    default_deploy_name,
)
from ..runner import Runner

logger = logging.getLogger(__name__)


try:  # Lazy optional imports; validated at runtime
    import alibabacloud_oss_v2 as oss  # type: ignore
    from alibabacloud_oss_v2.models import PutBucketRequest, PutObjectRequest
    from alibabacloud_bailian20231229.client import Client as ModelstudioClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_bailian20231229 import models as ModelstudioTypes
    from alibabacloud_tea_util import models as util_models
except Exception:
    oss = None
    PutBucketRequest = None
    PutObjectRequest = None
    ModelstudioClient = None
    open_api_models = None
    ModelstudioTypes = None
    util_models = None


class OSSConfig(BaseModel):
    region: str = Field("cn-hangzhou", description="OSS region")
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    bucket_prefix: str = Field(
        "tmpbucket-agentscope-runtime",
        description="Prefix for temporary buckets if creation is needed",
    )

    @classmethod
    def from_env(cls) -> "OSSConfig":
        return cls(
            region=os.environ.get("OSS_REGION", "cn-hangzhou"),
            access_key_id=os.environ.get(
                "OSS_ACCESS_KEY_ID",
                os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            ),
            access_key_secret=os.environ.get(
                "OSS_ACCESS_KEY_SECRET",
                os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            ),
        )

    def ensure_valid(self) -> None:
        # allow fallback to Alibaba Cloud AK/SK via from_env()
        if not self.access_key_id or not self.access_key_secret:
            raise RuntimeError(
                "Missing AccessKey for OSS. Set either OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET "
                "or ALIBABA_CLOUD_ACCESS_KEY_ID/ALIBABA_CLOUD_ACCESS_KEY_SECRET.",
            )


class ModelstudioConfig(BaseModel):
    endpoint: str = Field(
        "bailian.cn-beijing.aliyuncs.com",
        description="Modelstudio service endpoint",
    )
    workspace_id: Optional[str] = None
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    dashscope_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ModelstudioConfig":
        return cls(
            endpoint=os.environ.get(
                "MODELSTUDIO_ENDPOINT",
                "bailian.cn-beijing.aliyuncs.com",
            ),
            workspace_id=os.environ.get("MODELSTUDIO_WORKSPACE_ID"),
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get(
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ),
            dashscope_api_key=os.environ.get(
                "DASHSCOPE_API_KEY",
            ),
        )

    def ensure_valid(self) -> None:
        missing = []
        if not self.workspace_id:
            missing.append("MODELSTUDIO_WORKSPACE_ID")
        if not self.access_key_id:
            missing.append("ALIBABA_CLOUD_ACCESS_KEY_ID")
        if not self.access_key_secret:
            missing.append("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        if missing:
            raise RuntimeError(
                f"Missing required Modelstudio env vars: {', '.join(missing)}",
            )


def _assert_cloud_sdks_available():
    if oss is None or ModelstudioClient is None:
        raise RuntimeError(
            "Cloud SDKs not installed. Please install: "
            "alibabacloud-oss-v2 alibabacloud-bailian20231229 "
            "alibabacloud-credentials alibabacloud-tea-openapi alibabacloud-tea-util",
        )


def _oss_get_client(oss_cfg: OSSConfig):
    oss_cfg.ensure_valid()
    # Ensure OSS SDK can read credentials from environment variables.
    # If OSS_* are not set, populate them from resolved config (which may
    # already have fallen back to ALIBABA_CLOUD_* as per from_env()).
    if not os.environ.get("OSS_ACCESS_KEY_ID") and oss_cfg.access_key_id:
        os.environ["OSS_ACCESS_KEY_ID"] = str(oss_cfg.access_key_id)
    if (
        not os.environ.get("OSS_ACCESS_KEY_SECRET")
        and oss_cfg.access_key_secret
    ):
        os.environ["OSS_ACCESS_KEY_SECRET"] = str(oss_cfg.access_key_secret)

    credentials_provider = (
        oss.credentials.EnvironmentVariableCredentialsProvider()
    )
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = oss_cfg.region
    return oss.Client(cfg)


async def _oss_create_bucket_if_not_exists(client, bucket_name: str) -> None:
    try:
        exists = client.is_bucket_exist(bucket=bucket_name)
    except Exception:
        exists = False
    if not exists:
        req = PutBucketRequest(
            bucket=bucket_name,
            acl="private",
            create_bucket_configuration=oss.CreateBucketConfiguration(
                storage_class="IA",
            ),
        )
        client.put_bucket(req)
        result = client.put_bucket_tags(
            oss.PutBucketTagsRequest(
                bucket=bucket_name,
                tagging=oss.Tagging(
                    tag_set=oss.TagSet(
                        tags=[
                            oss.Tag(
                                key="bailian-high-code-deploy-oss-access",
                                value="ReadAndAdd",
                            ),
                        ],
                    ),
                ),
            ),
        )
        logger.info(
            f"put bucket tag status code: {result.status_code}, request id: {result.request_id}",
        )


def _create_bucket_name(prefix: str, base_name: str) -> str:
    import re as _re

    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    base = _re.sub(r"\s+", "-", base_name)
    base = _re.sub(r"[^a-zA-Z0-9-]", "", base).lower().strip("-")
    name = f"{prefix}-{base}-{ts}"
    return name[:63]


async def _oss_put_and_presign(
    client,
    bucket_name: str,
    object_key: str,
    file_bytes: bytes,
) -> str:
    import datetime as _dt

    put_req = PutObjectRequest(
        bucket=bucket_name,
        key=object_key,
        body=file_bytes,
    )
    client.put_object(put_req)
    pre = client.presign(
        oss.GetObjectRequest(bucket=bucket_name, key=object_key),
        expires=_dt.timedelta(minutes=180),
    )
    return pre.url


async def _modelstudio_deploy(
    cfg: ModelstudioConfig,
    file_url: str,
    filename: str,
    deploy_name: str,
    telemetry_enabled: bool = True,
) -> str:
    cfg.ensure_valid()
    config = open_api_models.Config(
        access_key_id=cfg.access_key_id,
        access_key_secret=cfg.access_key_secret,
    )
    config.endpoint = cfg.endpoint
    client_modelstudio = ModelstudioClient(config)
    req = ModelstudioTypes.HighCodeDeployRequest(
        source_code_name=filename,
        source_code_oss_url=file_url,
        agent_name=deploy_name,
        telemetry_enabled=telemetry_enabled,
    )
    runtime = util_models.RuntimeOptions()
    headers: Dict[str, str] = {}
    resp = client_modelstudio.high_code_deploy_with_options(
        cfg.workspace_id,
        req,
        headers,
        runtime,
    )

    # Extract deploy identifier string from response
    def _extract_deploy_identifier(response_obj) -> str:
        try:
            if isinstance(response_obj, str):
                return response_obj
            # Tea responses often have a 'body' that can be a dict or model
            body = getattr(response_obj, "body", None)

            # 1) If body is a plain string
            if isinstance(body, str):
                return body
            # 2) If body is a dict, prefer common fields
            if isinstance(body, dict):
                # Explicit error handling: do not build URL on failure
                if isinstance(body.get("success"), bool) and not body.get(
                    "success",
                ):
                    err_code = (
                        body.get("errorCode") or body.get("code") or "unknown"
                    )
                    err_msg = body.get("errorMsg") or body.get("message") or ""
                    raise RuntimeError(
                        f"ModelStudio deploy failed: {err_code} {err_msg}".strip(),
                    )
                for key in ("data", "result", "deployId"):
                    val = body.get(key)
                    if isinstance(val, str) and val:
                        return val
                # Try nested structures
                data_val = body.get("data")
                if isinstance(data_val, dict):
                    for key in ("id", "deployId"):
                        v = data_val.get(key)
                        if isinstance(v, str) and v:
                            return v
            # 3) If body is a Tea model, try to_map()
            if hasattr(body, "to_map") and callable(getattr(body, "to_map")):
                try:
                    m = body.to_map()
                    if isinstance(m, dict):
                        if isinstance(m.get("success"), bool) and not m.get(
                            "success",
                        ):
                            err_code = (
                                m.get("errorCode")
                                or m.get("code")
                                or "unknown"
                            )
                            err_msg = (
                                m.get("errorMsg") or m.get("message") or ""
                            )
                            raise RuntimeError(
                                f"ModelStudio deploy failed: {err_code} {err_msg}".strip(),
                            )
                        for key in ("data", "result", "deployId"):
                            val = m.get(key)
                            if isinstance(val, str) and val:
                                return val
                        d = m.get("data")
                        if isinstance(d, dict):
                            for key in ("id", "deployId"):
                                v = d.get(key)
                                if isinstance(v, str) and v:
                                    return v
                except Exception:
                    raise
            # 4) If response_obj itself is a dict
            if isinstance(response_obj, dict):
                b = response_obj.get("body")
                if isinstance(b, dict):
                    if isinstance(b.get("success"), bool) and not b.get(
                        "success",
                    ):
                        err_code = (
                            b.get("errorCode") or b.get("code") or "unknown"
                        )
                        err_msg = b.get("errorMsg") or b.get("message") or ""
                        raise RuntimeError(
                            f"ModelStudio deploy failed: {err_code} {err_msg}".strip(),
                        )
                    for key in ("data", "result", "deployId"):
                        val = b.get(key)
                        if isinstance(val, str) and val:
                            return val
            # Fallback: return empty to avoid polluting URL with dump
            return ""
        except Exception:  # pragma: no cover - conservative fallback
            # Propagate errors as empty identifier; upper layer logs/raises
            raise

    return _extract_deploy_identifier(resp)


class ModelstudioDeployManager(DeployManager):
    """Deployer for Alibaba Modelstudio Function Compute based agent
    deployment.

    This deployer packages the user project into a wheel, uploads it to OSS,
    and triggers a Modelstudio Full-Code deploy.
    """

    def __init__(
        self,
        oss_config: Optional[OSSConfig] = None,
        modelstudio_config: Optional[ModelstudioConfig] = None,
        build_root: Optional[Union[str, Path]] = None,
    ) -> None:
        super().__init__()
        self.oss_config = oss_config or OSSConfig.from_env()
        self.modelstudio_config = (
            modelstudio_config or ModelstudioConfig.from_env()
        )
        self.build_root = Path(build_root) if build_root else None

    async def _generate_wrapper_and_build_wheel(
        self,
        project_dir: Union[Optional[str], Path],
        cmd: Optional[str] = None,
        deploy_name: Optional[str] = None,
        telemetry_enabled: bool = True,
    ) -> Tuple[Path, str]:
        """
        校验参数、生成 wrapper 项目并构建 wheel。

        返回: (wheel_path, wrapper_project_dir, name)
        """
        if not project_dir or not cmd:
            raise ValueError(
                "project_dir and cmd are required for "
                "Modelstudio deployment",
            )

        project_dir = Path(project_dir).resolve()
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project dir not found: {project_dir}")

        name = deploy_name or default_deploy_name()
        proj_root = project_dir.resolve()
        if isinstance(self.build_root, Path):
            effective_build_root = self.build_root.resolve()
        else:
            if self.build_root:
                effective_build_root = Path(self.build_root).resolve()
            else:
                effective_build_root = (
                    proj_root.parent / ".agentscope_runtime_builds"
                ).resolve()

        build_dir = effective_build_root / f"build-{int(time.time())}"
        build_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Generating wrapper project for %s", name)
        wrapper_project_dir, _ = await generate_wrapper_project(
            build_root=build_dir,
            user_project_dir=project_dir,
            start_cmd=cmd,
            deploy_name=name,
            telemetry_enabled=telemetry_enabled,
        )

        logger.info("Building wheel under %s", wrapper_project_dir)
        wheel_path = await build_wheel(wrapper_project_dir)
        return wheel_path, name

    def _generate_env_file(
        self,
        project_dir: Union[str, Path],
        environment: Optional[Dict[str, str]] = None,
        env_filename: str = ".env",
    ) -> Optional[Path]:
        """
        Generate a .env file from environment variables dictionary.

        Args:
            project_dir: The project directory where the .env file will be
            created  environment: Dictionary of environment variables to
            write to .env file env_filename: Name of the env file (default:
            ".env")

        Returns:
            Path to the created .env file, or None if no environment
            variables provided
        """
        if not environment:
            return None

        project_path = Path(project_dir).resolve()
        if not project_path.exists():
            raise FileNotFoundError(
                f"Project directory not found: " f"{project_path}",
            )

        env_file_path = project_path / env_filename

        try:
            with env_file_path.open("w", encoding="utf-8") as f:
                f.write("# Environment variables used by AgentScope Runtime\n")

                for key, value in environment.items():
                    # Escape special characters and quote values if needed
                    if value is None:
                        continue

                    # Quote values that contain spaces or special characters
                    if " " in str(value) or any(
                        char in str(value)
                        for char in ["$", "`", '"', "'", "\\"]
                    ):
                        # Escape existing quotes and wrap in double quotes
                        escaped_value = (
                            str(value)
                            .replace("\\", "\\\\")
                            .replace('"', '\\"')
                        )
                        f.write(f'{key}="{escaped_value}"\n')
                    else:
                        f.write(f"{key}={value}\n")

            logger.info(f"Generated .env file at: {env_file_path}")
            return env_file_path

        except Exception as e:
            logger.warning(f"Failed to generate .env file: {e}")
            return None

    async def _upload_and_deploy(
        self,
        wheel_path: Path,
        name: str,
        telemetry_enabled: bool = True,
    ) -> Tuple[str, str]:
        logger.info("Uploading wheel to OSS and generating presigned URL")
        client = _oss_get_client(self.oss_config)
        bucket_name = (
            f"tmp-bucket-for-code-deployment-"
            f"{os.getenv('MODELSTUDIO_WORKSPACE_ID', str(uuid.uuid4()))}"
        )
        await _oss_create_bucket_if_not_exists(client, bucket_name)
        filename = wheel_path.name
        with wheel_path.open("rb") as f:
            file_bytes = f.read()
        artifact_url = await _oss_put_and_presign(
            client,
            bucket_name,
            filename,
            file_bytes,
        )

        logger.info("Triggering Modelstudio Full-Code deploy for %s", name)
        deploy_identifier = await _modelstudio_deploy(
            cfg=self.modelstudio_config,
            file_url=artifact_url,
            filename=filename,
            deploy_name=name,
            telemetry_enabled=telemetry_enabled,
        )

        def _build_console_url(endpoint: str, identifier: str) -> str:
            # Map API endpoint to console domain (no fragment in base)
            base = (
                "https://pre-bailian.console.aliyun.com/?tab=app&efm_v=3.4.108#"
                if ("bailian-pre" in endpoint or "pre" in endpoint)
                else "https://bailian.console.aliyun.com/?tab=app"
            )
            # Optional query can be appended if needed; keep path clean
            return f"{base}/app-center/high-code-detail/{identifier}"

        console_url = (
            _build_console_url(
                self.modelstudio_config.endpoint,
                deploy_identifier,
            )
            if deploy_identifier
            else ""
        )
        return artifact_url, console_url

    async def deploy(
        self,
        runner: Optional[Runner] = None,
        endpoint_path: str = "/process",
        services_config: Optional[Union[ServicesConfig, dict]] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        environment: Optional[Dict[str, str]] = None,
        # runtime_config: Optional[Dict] = None,
        # ModelStudio-specific/packaging args (required)
        project_dir: Optional[Union[str, Path]] = None,
        cmd: Optional[str] = None,
        deploy_name: Optional[str] = None,
        skip_upload: bool = False,
        telemetry_enabled: bool = True,
        external_whl_path: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """
        Package the project, upload to OSS and trigger ModelStudio deploy.

        Returns a dict containing deploy_id, wheel_path, artifact_url (if uploaded),
        resource_name (deploy_name), and workspace_id.
        """
        if not runner and not project_dir and not external_whl_path:
            raise ValueError("")

        # convert services_config to Model body
        if services_config and isinstance(services_config, dict):
            services_config = ServicesConfig(**services_config)

        try:
            if runner:
                agent = runner._agent

                # Create package project for detached deployment
                project_dir = await LocalDeployManager.create_detached_project(
                    agent=agent,
                    endpoint_path=endpoint_path,
                    services_config=services_config,  # type: ignore[arg-type]
                    protocol_adapters=protocol_adapters,
                    requirements=requirements,
                    extra_packages=extra_packages,
                    **kwargs,
                )
                self._generate_env_file(project_dir, environment)
                cmd = "python main.py"
                deploy_name = deploy_name or default_deploy_name()

            # if whl exists then skip the project package method
            if external_whl_path:
                wheel_path = Path(external_whl_path).resolve()
                if not wheel_path.is_file():
                    raise FileNotFoundError(
                        f"External wheel file not found: {wheel_path}",
                    )
                name = deploy_name or default_deploy_name()
            else:
                (
                    wheel_path,
                    name,
                ) = await self._generate_wrapper_and_build_wheel(
                    project_dir=project_dir,
                    cmd=cmd,
                    deploy_name=deploy_name,
                    telemetry_enabled=telemetry_enabled,
                )

            artifact_url = ""
            console_url = ""
            if not skip_upload:
                # Only require cloud SDKs and credentials when performing upload/deploy
                _assert_cloud_sdks_available()
                self.oss_config.ensure_valid()
                self.modelstudio_config.ensure_valid()
                artifact_url, console_url = await self._upload_and_deploy(
                    wheel_path,
                    name,
                    telemetry_enabled,
                )

            result: Dict[str, str] = {
                "deploy_id": self.deploy_id,
                "wheel_path": str(wheel_path),
                "artifact_url": artifact_url,
                "resource_name": name,
                "workspace_id": self.modelstudio_config.workspace_id or "",
                "url": console_url,
            }

            return result
        except Exception as e:
            # Print richer error message to improve UX
            err_text = str(e)
            logger.error("Failed to deploy to modelstudio: %s", err_text)
            raise

    async def stop(self) -> None:  # pragma: no cover - not supported yet
        pass

    def get_status(self) -> str:  # pragma: no cover - not supported yet
        return "unknown"
