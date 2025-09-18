# -*- coding: utf-8 -*-
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, List, Union, Tuple

from pydantic import BaseModel, Field

from .base import DeployManager
from ..runner import Runner
from .utils.wheel_packager import (
    generate_wrapper_project,
    build_wheel,
    default_deploy_name,
)

logger = logging.getLogger(__name__)


try:  # Lazy optional imports; validated at runtime
    import alibabacloud_oss_v2 as oss  # type: ignore
    from alibabacloud_oss_v2.models import PutBucketRequest, PutObjectRequest  # type: ignore
    from alibabacloud_bailian20231229.client import Client as bailian20231229Client  # type: ignore
    from alibabacloud_tea_openapi import models as open_api_models  # type: ignore
    from alibabacloud_bailian20231229 import models as bailian_20231229_models  # type: ignore
    from alibabacloud_tea_util import models as util_models  # type: ignore
except Exception:  # pragma: no cover - we validate presence explicitly
    oss = None  # type: ignore
    PutBucketRequest = None  # type: ignore
    PutObjectRequest = None  # type: ignore
    bailian20231229Client = None  # type: ignore
    open_api_models = None  # type: ignore
    bailian_20231229_models = None  # type: ignore
    util_models = None  # type: ignore


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
            access_key_id=os.environ.get("OSS_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("OSS_ACCESS_KEY_SECRET"),
        )

    def ensure_valid(self) -> None:
        missing = []
        if not self.access_key_id:
            missing.append("OSS_ACCESS_KEY_ID")
        if not self.access_key_secret:
            missing.append("OSS_ACCESS_KEY_SECRET")
        if missing:
            raise RuntimeError(
                f"Missing required OSS env vars: {', '.join(missing)}",
            )


class BailianConfig(BaseModel):
    endpoint: str = Field(
        "bailian-pre.cn-hangzhou.aliyuncs.com",
        description="Bailian service endpoint",
    )
    workspace_id: Optional[str] = None
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    dashscope_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "BailianConfig":
        return cls(
            endpoint=os.environ.get(
                "BAILIAN_ENDPOINT",
                "bailian-pre.cn-hangzhou.aliyuncs.com",
            ),
            workspace_id=os.environ.get("ALIBABA_CLOUD_WORKSPACE_ID"),
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            dashscope_api_key=os.environ.get('ALIBABA_CLOUD_DASHSCOPE_API_KEY'),
        )

    def ensure_valid(self) -> None:
        missing = []
        if not self.workspace_id:
            missing.append("ALIBABA_CLOUD_WORKSPACE_ID")
        if not self.access_key_id:
            missing.append("ALIBABA_CLOUD_ACCESS_KEY_ID")
        if not self.access_key_secret:
            missing.append("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        if missing:
            raise RuntimeError(
                f"Missing required Bailian env vars: {', '.join(missing)}",
            )


def _assert_cloud_sdks_available():
    if oss is None or bailian20231229Client is None:
        raise RuntimeError(
            "Cloud SDKs not installed. Please install: "
            "alibabacloud-oss-v2 alibabacloud-bailian20231229 "
            "alibabacloud-credentials alibabacloud-tea-openapi alibabacloud-tea-util",
        )


def _oss_get_client(oss_cfg: OSSConfig):
    oss_cfg.ensure_valid()
    credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
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
            acl='private',
            create_bucket_configuration=oss.CreateBucketConfiguration(storage_class='IA'),
        )
        client.put_bucket(req)
        result = client.put_bucket_tags(
            oss.PutBucketTagsRequest(
                bucket=bucket_name,
                tagging=oss.Tagging(
                    tag_set=oss.TagSet(
                        tags=[
                            oss.Tag(
                                key='bailian-high-code-deploy-oss-access',
                                value='ReadAndAdd',
                            )
                        ]
                    ),
                ),
            )
        )
        logger.info(f'put bucket tag status code: {result.status_code}, request id: {result.request_id}')


def _create_bucket_name(prefix: str, base_name: str) -> str:
    import re as _re
    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    base = _re.sub(r"\s+", "-", base_name)
    base = _re.sub(r"[^a-zA-Z0-9-]", "", base).lower().strip("-")
    name = f"{prefix}-{base}-{ts}"
    return name[:63]


async def _oss_put_and_presign(client, bucket_name: str, object_key: str, file_bytes: bytes) -> str:
    import datetime as _dt
    put_req = PutObjectRequest(bucket=bucket_name, key=object_key, body=file_bytes)
    client.put_object(put_req)
    pre = client.presign(
        oss.GetObjectRequest(bucket=bucket_name, key=object_key),
        expires=_dt.timedelta(minutes=180),
    )
    return pre.url


async def _bailian_deploy(
    cfg: BailianConfig,
    file_url: str,
    filename: str,
    deploy_name: str,
    telemetry_enabled: bool = True,
) -> None:
    cfg.ensure_valid()
    config = open_api_models.Config(
        access_key_id=cfg.access_key_id,
        access_key_secret=cfg.access_key_secret,
    )
    config.endpoint = cfg.endpoint
    client_bailian = bailian20231229Client(config)
    req = bailian_20231229_models.HighCodeDeployRequest(
        source_code_name=filename,
        source_code_oss_url=file_url,
        agent_name=deploy_name,
        telemetry_enabled=telemetry_enabled,
    )
    runtime = util_models.RuntimeOptions()
    headers: Dict[str, str] = {}
    client_bailian.high_code_deploy_with_options(cfg.workspace_id, req, headers, runtime)


class BailianFCDeployer(DeployManager):
    """Deployer for Alibaba Bailian Function Compute based agent deployment.

    This deployer packages the user project into a wheel, uploads it to OSS,
    and triggers a Bailian HighCode deploy.
    """

    def __init__(
        self,
        oss_config: Optional[OSSConfig] = None,
        bailian_config: Optional[BailianConfig] = None,
        build_root: Optional[Union[str, Path]] = None,
    ) -> None:
        super().__init__()
        self.oss_config = oss_config or OSSConfig.from_env()
        self.bailian_config = bailian_config or BailianConfig.from_env()
        # Defer default build_root selection to deploy() to avoid using home by default
        self.build_root = Path(build_root) if build_root else None

    async def _generate_wrapper_and_build_wheel(
            self,
            project_dir: Union[str, Path],
            cmd: str,
            deploy_name: Optional[str] = None,
            telemetry_enabled: bool = True
    ) -> Tuple[Path, str]:
        """
        校验参数、生成 wrapper 项目并构建 wheel。

        返回: (wheel_path, wrapper_project_dir, name)
        """
        if not project_dir or not cmd:
            raise ValueError("project_dir and cmd are required for Bailian deployment")

        project_dir = Path(project_dir).resolve()
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project dir not found: {project_dir}")

        name = deploy_name or default_deploy_name()
        proj_root = project_dir.resolve()
        effective_build_root = (
            self.build_root.resolve() if isinstance(self.build_root, Path) else
            (Path(self.build_root).resolve() if self.build_root else (
                        proj_root.parent / ".agentscope_runtime_builds").resolve())
        )
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

    async def _upload_and_deploy(
        self,
        wheel_path: Path,
        name: str,
        telemetry_enabled: bool = True,
    ) -> str:
        logger.info("Uploading wheel to OSS and generating presigned URL")
        client = _oss_get_client(self.oss_config)
        bucket_name = "tmpbucket-for-full-code-deployment"
        await _oss_create_bucket_if_not_exists(client, bucket_name)
        filename = wheel_path.name
        with wheel_path.open("rb") as f:
            file_bytes = f.read()
        artifact_url = await _oss_put_and_presign(client, bucket_name, filename, file_bytes)

        logger.info("Triggering Bailian HighCode deploy for %s", name)
        await _bailian_deploy(
            cfg=self.bailian_config,
            file_url=artifact_url,
            filename=filename,
            deploy_name=name,
            telemetry_enabled=telemetry_enabled,
        )
        return artifact_url

    async def deploy(
        self,
        runner: Optional[Runner] = None,
        endpoint_path: str = "/process",
        stream: bool = True,
        requirements: Optional[Union[str, List[str]]] = None,  # not used directly
        extra_packages: Optional[List[str]] = None,  # not used directly
        base_image: str = "python:3.9-slim",  # not used, kept for API symmetry
        environment: Optional[Dict[str, str]] = None,  # not used directly
        runtime_config: Optional[Dict] = None,  # not used directly
        # Bailian-specific/packaging args (required)
        project_dir: Optional[Union[str, Path]] = None,
        cmd: Optional[str] = None,
        deploy_name: Optional[str] = None,
        skip_upload: bool = False,
        output_file: Optional[Union[str, Path]] = None,
        telemetry_enabled: bool = True,
        external_whl_path: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """
        Package the project, upload to OSS and trigger Bailian deploy.

        Returns a dict containing deploy_id, wheel_path, artifact_url (if uploaded),
        resource_name (deploy_name), and workspace_id.
        """
        _assert_cloud_sdks_available()
        self.oss_config.ensure_valid()
        self.bailian_config.ensure_valid()

        # 如果传入了外部whl包地址，则跳过打包步骤
        if external_whl_path:
            wheel_path = Path(external_whl_path).resolve()
            if not wheel_path.is_file():
                raise FileNotFoundError(f"External wheel file not found: {wheel_path}")
            name = deploy_name or default_deploy_name()
        else:
            wheel_path, name = await self._generate_wrapper_and_build_wheel(
                project_dir=project_dir,
                cmd=cmd,
                deploy_name=deploy_name,
                telemetry_enabled=telemetry_enabled
            )

        artifact_url = ""
        if not skip_upload:
            artifact_url = await self._upload_and_deploy(wheel_path, name, telemetry_enabled)

        result: Dict[str, str] = {
            "deploy_id": self.deploy_id,
            "wheel_path": str(wheel_path),
            "artifact_url": artifact_url,
            "resource_name": name,
            "workspace_id": self.bailian_config.workspace_id or "",
            "url": "",
        }

        if output_file:
            try:
                Path(output_file).write_text("\n".join([f"{k}={v}" for k, v in result.items()]), encoding="utf-8")
            except Exception as e:  # pragma: no cover
                logger.warning("Failed to write output file %s: %s", output_file, e)

        return result

    async def stop(self) -> bool:  # pragma: no cover - not supported yet
        return False

    def get_status(self) -> str:  # pragma: no cover - not supported yet
        return "unknown"


