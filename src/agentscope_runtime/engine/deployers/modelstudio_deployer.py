# -*- coding: utf-8 -*-
# pylint:disable=too-many-nested-blocks, too-many-return-statements,
# pylint:disable=too-many-branches, too-many-statements, try-except-raise
# pylint:disable=ungrouped-imports, arguments-renamed, protected-access
#
# flake8: noqa: E501
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, List, Union, Tuple

import requests
from pydantic import BaseModel, Field

from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .local_deployer import LocalDeployManager
from .utils.detached_app import get_bundle_entry_script
from .utils.wheel_packager import (
    generate_wrapper_project,
    build_wheel,
    default_deploy_name,
)

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
        raw_ws = os.environ.get("MODELSTUDIO_WORKSPACE_ID")
        ws = raw_ws.strip() if isinstance(raw_ws, str) else ""
        resolved_ws = ws if ws else "default"
        return cls(
            endpoint=os.environ.get(
                "MODELSTUDIO_ENDPOINT",
                "bailian.cn-beijing.aliyuncs.com",
            ),
            workspace_id=resolved_ws,
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
        try:
            put_bucket_result = client.put_bucket(req)
            logger.info(
                f"put bucket status code: {put_bucket_result.status_code},"
                f" request id: {put_bucket_result.request_id}",
            )
        except oss.exceptions.OperationError as e:
            logger.error(
                "OSS PutBucket failed: Http Status: %s, ErrorCode: %s, RequestId: %s, Message: %s",
                getattr(e, "http_code", None),
                getattr(e, "error_code", None),
                getattr(e, "request_id", None),
                getattr(e, "message", str(e)),
            )
            raise
        except Exception as e:
            logger.error("Unexpected put bucket failure: %s", e, exc_info=True)
            raise
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


def _upload_to_oss_with_credentials(
    api_response,
    file_path,
) -> str:
    response_data = (
        json.loads(api_response)
        if isinstance(api_response, str)
        else api_response
    )

    try:
        body = response_data["body"]
        data = body.get("Data")
        if data is None:
            messages = [
                "\n❌ Configuration Error: "
                "The current RAM user is not assigned to target workspace.",
                "Bailian requires RAM users to be associated with "
                "at least one workspace to use temporary storage.",
                "\n🔧 How to resolve:",
                "1. Ask the primary account to log in to the "
                "Bailian Console: https://bailian.console.aliyun.com",
                "2. Go to [Permission Management]",
                "3. Go to [Add User]",
                "4. Assign the user to a workspace",
                "\n💡 Note: If you are not the primary account holder,"
                " please contact your administrator to complete this step.",
                "=" * 80,
            ]

            for msg in messages:
                logger.error(msg)

            raise ValueError(
                "RAM user is not assigned to any workspace in Bailian",
            )
        param = data["Param"]
        signed_url = param["Url"]
        headers = param["Headers"]
    except KeyError as e:
        raise ValueError(f"Missing expected field in API response: {e}") from e
    try:
        with open(file_path, "rb") as file:
            response = requests.put(signed_url, data=file, headers=headers)
        logger.info("OSS upload status code: %d", response.status_code)
        response.raise_for_status()  # Raises for 4xx/5xx
        logger.info("File uploaded successfully using requests")
        return data["TempStorageLeaseId"]
    except Exception as e:
        logger.error("Failed to upload file to OSS: %s", e)
        raise


def _get_presign_url_and_upload_to_oss(
    cfg: ModelstudioConfig,
    wheel_path: Path,
) -> str:
    """
    Request a temporary storage lease, obtain a pre-signed OSS URL, and upload the file.

    Args:
        cfg: ModelStudio configuration with credentials and endpoint.
        wheel_path: Path to the wheel file to upload.

    Returns:
        The TempStorageLeaseId returned by the service.

    Raises:
        Exception: Any error from the SDK or upload process (not swallowed).
    """
    try:
        config = open_api_models.Config(
            access_key_id=cfg.access_key_id,
            access_key_secret=cfg.access_key_secret,
        )
        config.endpoint = cfg.endpoint
        client_modelstudio = ModelstudioClient(config)

        filename = wheel_path.name
        size = wheel_path.stat().st_size

        apply_temp_storage_lease_request = (
            ModelstudioTypes.ApplyTempStorageLeaseRequest(
                file_name=filename,
                size_in_bytes=size,
            )
        )
        runtime = util_models.RuntimeOptions()
        headers = {}
        workspace_id = getattr(cfg, "workspace_id", "default")
        try:
            response = (
                client_modelstudio.apply_temp_storage_lease_with_options(
                    workspace_id,
                    apply_temp_storage_lease_request,
                    headers,
                    runtime,
                )
            )
        except Exception as error:
            logger.error(
                "Error during temporary storage lease or upload: %s",
                error,
            )
            error_code = None
            recommend_url = None
            if hasattr(error, "code"):
                error_code = error.code
            if hasattr(error, "data") and isinstance(error.data, dict):
                recommend_url = error.data.get("Recommend")

            if error_code == "NoPermission":
                messages = [
                    "\n❌ Permission Denied (NoPermission)",
                    "The current account does not have permission to apply "
                    "for temporary storage (ApplyTempStorageLease).",
                    "\n🔧 How to resolve:",
                    "1. Ask the primary account holder (or an administrator)"
                    " to grant your RAM user the following permission:",
                    "   - Action: `AliyunBailianDataFullAccess`",
                    "\n2. Steps to grant permission:",
                    "   - Go to Alibaba Cloud RAM Console: https://ram.console.aliyun.com/users",
                    "   - Locate your RAM user",
                    "   - Click 'Add Permissions' and attach a policy that includes "
                    "`AliyunBailianDataFullAccess`",
                    "\n3. For further diagnostics:",
                ]
                official_doc_link = "https://help.aliyun.com/zh/ram/"
                if recommend_url:
                    messages.append(
                        f"   - Official troubleshooting link: {recommend_url}",
                    )
                else:
                    messages.append(
                        "   - Visit the Alibaba Cloud API troubleshooting page",
                    )
                messages.append(
                    f"   - Official document link: {official_doc_link or 'N/A'}",
                )
                messages.append(
                    "\n💡 Note: If you are not an administrator, please "
                    "contact your cloud account administrator for assistance.",
                )
                messages.append("=" * 80)

                # 一次性记录多行日志（每行单独一条日志，便于解析）
                for msg in messages:
                    logger.error(msg)

            logger.error("Original error details: %s", error)
            raise

        temp_storage_lease_id = _upload_to_oss_with_credentials(
            response.to_map(),
            wheel_path,
        )
        return temp_storage_lease_id

    except Exception as error:
        # Log detailed error information
        logger.error(
            "Error during temporary storage upload: %s",
            error,
        )
        if hasattr(error, "message"):
            logger.error("Error message: %s", error.message)
        if hasattr(error, "data") and isinstance(error.data, dict):
            recommend = error.data.get("Recommend")
            if recommend:
                logger.error("Diagnostic recommendation: %s", recommend)
        # Re-raise the exception to avoid silent failures
        raise


async def _modelstudio_deploy(
    cfg: ModelstudioConfig,
    file_url: str,
    filename: str,
    deploy_name: str,
    agent_id: Optional[str] = None,
    agent_desc: Optional[str] = None,
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
        agent_desc=agent_desc,
        agent_id=agent_id,
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

    # logger.info(json.dumps(resp.to_map(), indent=2, ensure_ascii=False))
    request_id = resp.to_map()["headers"].get("x-acs-request-id")
    logger.info("deploy request id: %s", request_id)

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
        wrapper_project_dir, _ = generate_wrapper_project(
            build_root=build_dir,
            user_project_dir=project_dir,
            start_cmd=cmd,
            deploy_name=name,
            telemetry_enabled=telemetry_enabled,
        )

        logger.info("Building wheel under %s", wrapper_project_dir)
        wheel_path = build_wheel(wrapper_project_dir)
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
        agent_id: Optional[str] = None,
        agent_desc: Optional[str] = None,
        telemetry_enabled: bool = True,
    ) -> Tuple[str, str]:
        logger.info("Uploading wheel to OSS")
        temp_storage_lease_id = _get_presign_url_and_upload_to_oss(
            self.modelstudio_config,
            wheel_path,
        )
        logger.info("Triggering Modelstudio Full-Code deploy for %s", name)
        deploy_identifier = await _modelstudio_deploy(
            agent_desc=agent_desc,
            agent_id=agent_id,
            cfg=self.modelstudio_config,
            file_url=temp_storage_lease_id,
            filename=wheel_path.name,
            deploy_name=name,
            telemetry_enabled=telemetry_enabled,
        )

        def _build_console_url(endpoint: str) -> str:
            # Map API endpoint to console domain (no fragment in base)
            base = (
                "https://pre-bailian.console.aliyun.com/?tab=app#"
                if ("bailian-pre" in endpoint or "pre" in endpoint)
                else "https://bailian.console.aliyun.com/?tab=app#"
            )
            # Optional query can be appended if needed; keep path clean
            return f"{base}/app-center"

        console_url = (
            _build_console_url(
                self.modelstudio_config.endpoint,
            )
            if deploy_identifier
            else ""
        )
        return console_url, deploy_identifier

    async def deploy(
        self,
        app=None,
        runner=None,
        endpoint_path: str = "/process",
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
        agent_id: Optional[str] = None,
        agent_desc: Optional[str] = None,
        custom_endpoints: Optional[
            List[Dict]
        ] = None,  # New parameter for custom endpoints
        **kwargs,
    ) -> Dict[str, str]:
        """
        Package the project, upload to OSS and trigger ModelStudio deploy.

        Returns a dict containing deploy_id, wheel_path, url (if uploaded),
        resource_name (deploy_name), and workspace_id.
        """
        if not agent_id:
            if not runner and not project_dir and not external_whl_path:
                raise ValueError(
                    "Either runner, project_dir, "
                    "or external_whl_path must be provided.",
                )

        try:
            if runner:
                if "agent" in kwargs:
                    kwargs.pop("agent")

                # Create package project for detached deployment
                project_dir = await LocalDeployManager.create_detached_project(
                    app=app,
                    endpoint_path=endpoint_path,
                    protocol_adapters=protocol_adapters,
                    custom_endpoints=custom_endpoints,
                    requirements=requirements,
                    extra_packages=extra_packages,
                    port=8080,
                    **kwargs,
                )
                if project_dir:
                    self._generate_env_file(project_dir, environment)
                entry_script = get_bundle_entry_script(project_dir)
                cmd = f"python {entry_script}"
                deploy_name = deploy_name or default_deploy_name()

            if agent_id:
                if not external_whl_path:
                    raise FileNotFoundError(
                        "wheel file not found. "
                        "Please specify your .whl file path by "
                        "'--whl-path <whlpath>' in command line.",
                    )
            # if whl exists then skip the project package method
            if external_whl_path:
                wheel_path = Path(external_whl_path).resolve()
                if not wheel_path.is_file():
                    raise FileNotFoundError(
                        f"External wheel file not found: {wheel_path}",
                    )
                name = deploy_name or default_deploy_name()
                # Don't change name if agent was not updated and
                # deploye_name was missing
                if agent_id and (deploy_name is None):
                    name = None
                logger.info(
                    "Using external wheel file: %s",
                    wheel_path,
                )

            else:
                logger.info("Building wheel package from project")
                (
                    wheel_path,
                    name,
                ) = await self._generate_wrapper_and_build_wheel(
                    project_dir=project_dir,
                    cmd=cmd,
                    deploy_name=deploy_name,
                    telemetry_enabled=telemetry_enabled,
                )

            console_url = ""
            deploy_identifier = ""
            if not skip_upload:
                # Only require cloud SDKs and credentials when performing
                # upload/deploy
                _assert_cloud_sdks_available()
                self.oss_config.ensure_valid()
                self.modelstudio_config.ensure_valid()
                (
                    console_url,
                    deploy_identifier,
                ) = await self._upload_and_deploy(
                    wheel_path,
                    name,
                    agent_id,
                    agent_desc,
                    telemetry_enabled,
                )

            result: Dict[str, str] = {
                "wheel_path": str(wheel_path),
                "resource_name": name,
                "url": console_url,
            }
            env_ws = os.environ.get("MODELSTUDIO_WORKSPACE_ID")
            if env_ws and env_ws.strip():
                result["workspace_id"] = env_ws.strip()
            if deploy_identifier:
                result["deploy_id"] = deploy_identifier

            return result
        except Exception as e:
            # Print richer error message to improve UX
            err_text = str(e)
            logger.error(
                "Failed to deploy to modelstudio: %s",
                err_text,
            )
            raise

    async def stop(self) -> None:  # pragma: no cover - not supported yet
        pass

    def get_status(self) -> str:  # pragma: no cover - not supported yet
        return "unknown"
