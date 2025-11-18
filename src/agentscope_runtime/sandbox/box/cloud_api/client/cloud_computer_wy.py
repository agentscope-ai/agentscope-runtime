# -*- coding: utf-8 -*-
import os
import time
import asyncio
import threading
from typing import List, Tuple, Any
import logging
from pydantic import BaseModel
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_ecd20200930.client import Client as ecd20200930Client
from alibabacloud_ecd20200930 import models as ecd_20200930_models
from alibabacloud_appstream_center20210218 import (
    models as appstream_center_20210218_models,
)
from alibabacloud_appstream_center20210218.client import (
    Client as appstream_center20210218Client,
)
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from agentscope_runtime.sandbox.box.cloud_api.utils.oss_client import OSSClient
from ..utils.utils import (
    download_oss_image_and_save,
    download_oss_image_and_save_async,
)


logger = logging.getLogger(__name__)

execute_wait_time_: int = 3


class CommandQueryError(Exception):
    """命令查询状态错误异常"""


class InitError(Exception):
    """初始化异常"""


class ClientPool:
    """客户端池管理器 - 单例模式管理共享客户端实例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 使用双重检查锁定模式确保只初始化一次
        if not hasattr(self, "_initialized"):
            with self._lock:
                if not hasattr(self, "_initialized"):
                    self._ecd_client = None
                    self._oss_client = None
                    self._app_stream_client = None
                    self._instance_managers = (
                        {}
                    )  # 按desktop_id缓存EcdInstanceManager
                    # 使用不同的锁来避免死锁
                    self._ecd_lock = threading.Lock()
                    self._oss_lock = threading.Lock()
                    self._app_stream_lock = threading.Lock()
                    self._instance_manager_lock = threading.Lock()
                    self._initialized = True

    def get_ecd_client(self) -> "EcdClient":
        """获取共享的EcdClient实例"""
        if self._ecd_client is None:
            with self._ecd_lock:
                if self._ecd_client is None:
                    self._ecd_client = EcdClient()
        return self._ecd_client

    def get_oss_client(self) -> OSSClient:
        """获取共享的OSSClient实例"""
        if self._oss_client is None:
            with self._oss_lock:
                if self._oss_client is None:
                    bucket_name = os.environ.get("EDS_OSS_BUCKET_NAME")
                    endpoint = os.environ.get("EDS_OSS_ENDPOINT")
                    self._oss_client = OSSClient(bucket_name, endpoint)
        return self._oss_client

    def get_app_stream_client(
        self,
    ) -> "AppStreamClient":
        """获取AppStreamClient实例，每次调用都创建新的实例（非共享模式）"""
        # 每次都创建新的AppStreamClient实例，不使用缓存
        return AppStreamClient()

    def get_instance_manager(self, desktop_id: str) -> "EcdInstanceManager":
        """获取指定desktop_id的EcdInstanceManager实例"""
        # 先检查是否已存在，避免不必要的锁竞争
        if desktop_id in self._instance_managers:
            return self._instance_managers[desktop_id]

        # 在锁外预先获取客户端，避免死锁
        ecd_client = self.get_ecd_client()
        oss_client = self.get_oss_client()
        app_stream_client = self.get_app_stream_client()

        # 使用专门的锁管理实例管理器
        with self._instance_manager_lock:
            # 再次检查，防止在等待锁的过程中已经被其他线程创建
            if desktop_id not in self._instance_managers:
                # 创建新的实例管理器，并传入共享的客户端
                manager = EcdInstanceManager(desktop_id)
                manager.ecd_client = ecd_client
                manager.oss_client = oss_client
                manager.app_stream_client = app_stream_client
                self._instance_managers[desktop_id] = manager
        return self._instance_managers[desktop_id]


class EcdDeviceInfo(BaseModel):
    # 云电脑设备信息查询字段返回类
    connection_status: str = (None,)
    desktop_id: str = (None,)
    desktop_status: str = (None,)
    start_time: str = (None,)


class CommandTimeoutError(Exception):
    """命令执行超时异常"""


class CommandExecutionError(Exception):
    """命令执行错误异常"""


class EcdClient:
    def __init__(self) -> None:
        config = open_api_models.Config(
            access_key_id=os.environ.get("ECD_ALIBABA_CLOUD_ACCESS_KEY_ID"),
            # 您的AccessKey Secret,
            access_key_secret=os.environ.get(
                "ECD_ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ),
        )
        # Endpoint 请参考 https://api.aliyun.com/product/eds-aic
        config.endpoint = os.environ.get("ECD_ALIBABA_CLOUD_ENDPOINT")
        self.__client__ = ecd20200930Client(config)

    def execute_command(
        self,
        desktop_ids: List[str],
        command: str,
        timeout: int = 60,
    ) -> Tuple[str, str]:
        # 执行命令
        run_command_request = ecd_20200930_models.RunCommandRequest(
            desktop_id=desktop_ids,
            command_content=command,
            type="RunPowerShellScript",
            end_user_id=os.environ.get("ECD_USERNAME"),
            content_encoding="PlainText",
            timeout=timeout,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.run_command_with_options(
                run_command_request,
                runtime,
            )

            assert rsp.status_code == 200
            invoke_id = rsp.body.invoke_id
            request_id = rsp.body.request_id
            # logging.info(invoke_id, request_id)
            return invoke_id, request_id
        except Exception as error:
            logger.error(f"{desktop_ids} excute command failed:{error}")
            return "", ""

    def query_execute_state(
        self,
        desktop_ids: List[str],
        message_id: str,
    ) -> Any:
        # 查询命令执行结果
        describe_invocations_request = (
            ecd_20200930_models.DescribeInvocationsRequest(
                desktop_ids=desktop_ids,
                invoke_id=message_id,
                end_user_id=os.environ.get("ECD_USERNAME"),
                command_type="RunPowerShellScript",
                content_encoding="PlainText",
                include_output=True,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.describe_invocations_with_options(
                describe_invocations_request,
                runtime,
            )
            # print(rsp.body)
            return rsp.body
        except Exception as error:
            UtilClient.assert_as_string(error)
            logger.error(f"{desktop_ids} query message failed:{error}")
        return None

    def run_command_with_wait(
        self,
        desktop_id: str,
        command: str,
        slot_time: float = None,
        timeout: int = 60,
    ) -> Tuple[str, str]:
        execute_id, request_id = self.execute_command(
            [desktop_id],
            command,
            timeout=timeout,
        )
        print(f"execute_id:{execute_id}, request_id:{request_id}")
        start_time = time.time()
        if not slot_time:
            if (
                "execute_wait_time_" in globals()
                and execute_wait_time_ is not None
            ):
                slot_time = execute_wait_time_
            else:
                slot_time = 3  # 默认值
        slot_time = max(0.5, slot_time)
        timeout = slot_time + timeout
        if execute_id:
            while timeout > 0:
                logger.info("start wait execution")
                time.sleep(slot_time)
                logger.info("execution end")
                msgs = self.query_execute_state(
                    [desktop_id],
                    execute_id,
                )
                for msg in msgs.invocations:
                    if msg.invocation_status in [
                        "Success",
                        "Failed",
                        "Timeout",
                    ]:
                        logger.info(
                            f"command cost time: {time.time() - start_time}",
                        )
                        return (
                            msg.invocation_status == "Success",
                            msg.invoke_desktops[0].output,
                        )
                timeout -= slot_time
        raise CommandTimeoutError("Command execution timeout")

    async def run_command_with_wait_async(
        self,
        desktop_id: str,
        command: str,
        slot_time: float = None,
        timeout: int = 60,
    ) -> Tuple[bool, str]:
        execute_id, request_id = self.execute_command(
            [desktop_id],
            command,
            timeout=timeout,
        )
        print(f"execute_id:{execute_id}, request_id:{request_id}")
        start_time = time.time()
        if not slot_time:
            if (
                "execute_wait_time_" in globals()
                and execute_wait_time_ is not None
            ):
                slot_time = execute_wait_time_
            else:
                slot_time = 3  # 默认值
        slot_time = max(0.5, slot_time)
        timeout = slot_time + timeout
        if execute_id:
            while timeout > 0:
                logger.info("start wait execution")
                await asyncio.sleep(slot_time)  # 使用 asyncio.sleep
                logger.info("execution end")
                msgs = self.query_execute_state(
                    [desktop_id],
                    execute_id,
                )
                if msgs is None:
                    raise CommandQueryError("query execute state failed")

                for msg in msgs.invocations:
                    if msg.invocation_status in [
                        "Success",
                        "Failed",
                        "Timeout",
                    ]:
                        logger.info(
                            f"command cost time: {time.time() - start_time}",
                        )
                        return (
                            msg.invocation_status == "Success",
                            (
                                msg.invoke_desktops[0].output
                                if msg.invoke_desktops
                                else ""
                            ),
                        )
                timeout -= slot_time
        raise CommandTimeoutError("Command execution timeout")

    def search_desktop_info(
        self,
        desktop_ids: List[str],
    ) -> List[EcdDeviceInfo]:
        describe_desktop_info_request = (
            ecd_20200930_models.DescribeDesktopInfoRequest(
                region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
                desktop_id=desktop_ids,
            )
        )

        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.describe_desktop_info_with_options(
                describe_desktop_info_request,
                runtime,
            )
            devices_info = [
                EcdDeviceInfo(**inst.__dict__) for inst in rsp.body.desktops
            ]
            return devices_info
        except Exception as error:
            logger.error(f"search wuying desktop failed:{error}")
            return []

    def start_desktops(self, desktop_ids: List[str]) -> int:
        start_desktops_request = ecd_20200930_models.StartDesktopsRequest(
            region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
            desktop_id=desktop_ids,
        )

        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            rsp = e_c.start_desktops_with_options(
                start_desktops_request,
                runtime,
            )
            logger.info(
                f"[{desktop_ids}]: start instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"start_desktops failed:{error}")
            return 400

    async def start_desktops_async(self, desktop_ids: List[str]) -> int:
        start_desktops_request = ecd_20200930_models.StartDesktopsRequest(
            region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
            desktop_id=desktop_ids,
        )

        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            method = e_c.start_desktops_with_options_async
            rsp = await method(
                start_desktops_request,
                runtime,
            )
            logger.info(
                f"[{desktop_ids}]: start instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"start_desktops failed:{error}")
            return 400

    def wakeup_desktops(self, desktop_ids: List[str]) -> int:
        wakeup_desktops_request = ecd_20200930_models.WakeupDesktopsRequest(
            region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
            desktop_id=desktop_ids,
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            rsp = e_c.wakeup_desktops_with_options(
                wakeup_desktops_request,
                runtime,
            )
            logger.info(
                f"[{desktop_ids}]: wakeup instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"wakeup_desktops failed:{error}")
            return 400

    def hibernate_desktops(self, desktop_ids: List[str]) -> int:
        hibernate_desktops_request = (
            ecd_20200930_models.HibernateDesktopsRequest(
                region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
                desktop_id=desktop_ids,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            rsp = e_c.hibernate_desktops_with_options(
                hibernate_desktops_request,
                runtime,
            )
            logger.info(
                f"[{desktop_ids}]: hibernate instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"hibernate_desktops failed:{error}")
            return 400

    async def wakeup_desktops_async(self, desktop_ids: List[str]) -> int:
        wakeup_desktops_request = ecd_20200930_models.WakeupDesktopsRequest(
            region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
            desktop_id=desktop_ids,
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            method = e_c.wakeup_desktops_with_options_async
            rsp = await method(
                wakeup_desktops_request,
                runtime,
            )
            logger.info(
                f"[{desktop_ids}]: wakeup instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"wakeup_desktops failed:{error}")
            return 400

    async def hibernate_desktops_async(self, desktop_ids: List[str]) -> int:
        hibernate_desktops_request = (
            ecd_20200930_models.HibernateDesktopsRequest(
                region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
                desktop_id=desktop_ids,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            method = e_c.hibernate_desktops_with_options_async
            rsp = await method(
                hibernate_desktops_request,
                runtime,
            )
            logger.info(
                f"[{desktop_ids}]: wakeup instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"hibernate_desktops failed:{error}")
            return 400

    async def restart_equipment(self, desktop_id: str) -> int:
        reboot_desktops_request = ecd_20200930_models.RebootDesktopsRequest(
            region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
            desktop_id=[desktop_id],
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = await self.__client__.reboot_desktops_with_options_async(
                reboot_desktops_request,
                runtime,
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"restart equipment failed:{error}")
        return 400

    def stop_desktops(self, desktop_ids: List[str]) -> int:
        stop_desktops_request = ecd_20200930_models.StopDesktopsRequest(
            region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
            desktop_id=desktop_ids,
        )

        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.stop_desktops_with_options(
                stop_desktops_request,
                runtime,
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"stop_desktops failed:{error}")
        return 400

    async def stop_desktops_async(self, desktop_ids: List[str]) -> int:
        stop_desktops_request = ecd_20200930_models.StopDesktopsRequest(
            region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
            desktop_id=desktop_ids,
        )

        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            method = e_c.stop_desktops_with_options_async
            rsp = await method(
                stop_desktops_request,
                runtime,
            )
            logger.info(
                f"[{desktop_ids}]: wakeup instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"stop_desktops failed:{error}")
        return 400

    async def rebuild_equipment_image(
        self,
        desktop_id: str,
        image_id: str,
    ) -> int:
        rebuild_request = ecd_20200930_models.RebuildDesktopsRequest(
            region_id=os.environ.get("ECD_ALIBABA_CLOUD_REGION_ID"),
            image_id=image_id,
            desktop_id=[
                desktop_id,
            ],
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = await self.__client__.rebuild_desktops_with_options_async(
                rebuild_request,
                runtime,
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"rebuild equipment failed:{error}")
        return 400


# pylint: disable=too-many-public-methods
class EcdInstanceManager:
    def __init__(self, desktop_id: str = None) -> None:
        self.desktop_id = desktop_id
        self.ctrl_key = "Ctrl"
        self.ratio = 1
        self.oss_sk = None
        self.oss_ak = None
        self.endpoint = None
        self.oss_client = None
        self.ecd_client = None
        self._initialized = False
        self._init_error = None
        self.app_stream_client = None
        self.auth_code = None

    def init_resources(self) -> bool:
        if self._initialized:
            # 获取新的auth_code
            return self.refresh_aurh_code()
        try:
            # 如果没有预设的客户端（通过ClientPool设置），则创建新的
            if self.ecd_client is None:
                self.ecd_client = EcdClient()
            if self.app_stream_client is None:
                # 每次都创建新的AppStreamClient实例（非共享模式）
                self.app_stream_client = AppStreamClient()
            if self.oss_client is None:
                bucket_name = os.environ.get("EDS_OSS_BUCKET_NAME")
                endpoint = os.environ.get("EDS_OSS_ENDPOINT")
                self.oss_client = OSSClient(bucket_name, endpoint)

            # 获取auth_code
            self.auth_code = self.app_stream_client.search_auth_code()

            # 📝 验证 desktop_id 是否有效（可选）
            if self.desktop_id and self.ecd_client:
                # 验证设备是否存在和可用
                desktop_info = self.ecd_client.search_desktop_info(
                    [self.desktop_id],
                )
                if not desktop_info:
                    raise InitError(
                        f"Desktop {self.desktop_id} not found "
                        f"or not accessible",
                    )

            # 设置OSS endpoint
            self.endpoint = os.environ.get("EDS_OSS_ENDPOINT")

            # 🔑 配置参数
            self.oss_ak = os.environ.get("EDS_OSS_ACCESS_KEY_ID")
            self.oss_sk = os.environ.get("EDS_OSS_ACCESS_KEY_SECRET")
            self.ratio = 1
            self.ctrl_key = "Ctrl"

            self._initialized = True
            return True
        except Exception as e:
            self._init_error = e
            logger.error(f"Initialization failed: {e}")
            return False

    def refresh_aurh_code(self) -> bool:
        # 获取新的auth_code
        self.auth_code = self.app_stream_client.search_auth_code()
        # 如果auth_code为空，返回False,否则返回True
        return bool(self.auth_code)

    async def refresh_aurh_code_async(self) -> bool:
        # 获取新的auth_code
        self.auth_code = await self.app_stream_client.search_auth_code_async()
        return bool(self.auth_code)

    async def init_resources_async(self) -> bool:
        if self._initialized:
            # 获取新的auth_code
            self.auth_code = (
                await self.app_stream_client.search_auth_code_async()
            )
            return True
        try:
            # 如果没有预设的客户端（通过ClientPool设置），则创建新的
            if self.ecd_client is None:
                self.ecd_client = EcdClient()
            if self.app_stream_client is None:
                # 每次都创建新的AppStreamClient实例（非共享模式）
                self.app_stream_client = AppStreamClient()
            if self.oss_client is None:
                bucket_name = os.environ.get("EDS_OSS_BUCKET_NAME")
                endpoint = os.environ.get("EDS_OSS_ENDPOINT")
                self.oss_client = OSSClient(bucket_name, endpoint)

            # 获取auth_code
            self.auth_code = (
                await self.app_stream_client.search_auth_code_async()
            )

            # 📝 验证 desktop_id 是否有效（可选）
            if self.desktop_id and self.ecd_client:
                # 验证设备是否存在和可用
                desktop_info = self.ecd_client.search_desktop_info(
                    [self.desktop_id],
                )
                if not desktop_info:
                    raise InitError(
                        f"Desktop {self.desktop_id} not found "
                        f"or not accessible",
                    )

            # 设置OSS endpoint
            self.endpoint = os.environ.get("EDS_OSS_ENDPOINT")

            # 🔑 配置参数
            self.oss_ak = os.environ.get("EDS_OSS_ACCESS_KEY_ID")
            self.oss_sk = os.environ.get("EDS_OSS_ACCESS_KEY_SECRET")
            self.ratio = 1
            self.ctrl_key = "Ctrl"

            self._initialized = True
            return True
        except Exception as e:
            self._init_error = e
            logger.error(f"Initialization failed: {e}")
            return False

    def get_screenshot(
        self,
        local_file_name: str,
        local_save_path: str,
    ) -> str:
        # local_file_name = f"{uuid.uuid4().hex}__screenshot"
        logger.info("开始截图")
        save_path = f"C:/file/{local_file_name}"
        file_save_path = f"{local_file_name}.png"
        file_local_save_path = f"{save_path}.png"
        retry = 2
        while retry > 0:
            try:
                # 截图
                # 获取oss预签名url上传地址
                oss_signed_url = self.oss_client.get_signal_url(
                    f"{file_save_path}",
                )
                status, file_oss = self.get_screenshot_oss(
                    file_local_save_path,
                    oss_signed_url,
                )
                logger.debug(f"文件输出: {file_oss}")
                if "Traceback" in file_oss:
                    return ""
                base64_image = ""
                file_oss_down = self.oss_client.get_download_url(
                    f"{file_save_path}",
                )
                if status and file_oss:
                    base64_image = download_oss_image_and_save(
                        file_oss_down,
                        local_save_path,
                    )
                    if base64_image:
                        logger.info("成功获取Base64图片数据")
                        return base64_image

                return f"data:image/png;base64,{base64_image}"

            except Exception as e:
                retry -= 1
                logger.warning(f"截图失败，重试中... {retry}次剩余，错误: {e}")
                time.sleep(2)

        return ""

    async def get_screenshot_async(
        self,
        local_file_name: str,
        local_save_path: str,
    ) -> str:
        # local_file_name = f"{uuid.uuid4().hex}__screenshot"
        logger.info("开始截图")
        save_path = f"C:/file/{local_file_name}"
        file_save_path = f"{local_file_name}.png"
        file_local_save_path = f"{save_path}.png"
        retry = 2
        while retry > 0:
            try:
                # 截图
                # 获取oss预签名url上传地址
                oss_signed_url = await self.oss_client.get_signal_url_async(
                    f"{file_save_path}",
                )
                status, file_oss = await self.get_screenshot_oss_async(
                    file_local_save_path,
                    oss_signed_url,
                )
                logger.debug(f"文件输出: {file_oss}")
                if "Traceback" in file_oss:
                    return ""
                base64_image = ""
                file_oss_down = await self.oss_client.get_download_url_async(
                    f"{file_save_path}",
                )
                if status and file_oss:
                    base64_image = await download_oss_image_and_save_async(
                        file_oss_down,
                        local_save_path,
                    )
                    if base64_image:
                        logger.info("成功获取Base64图片数据")
                        return base64_image

                return f"data:image/png;base64,{base64_image}"

            except Exception as e:
                retry -= 1
                logger.warning(f"截图失败，重试中... {retry}次剩余，错误: {e}")
                await asyncio.sleep(2)

        return ""

    def get_screenshot_oss_url(
        self,
        local_file_name: str,
        local_save_path: str,
    ) -> str:
        # local_file_name = f"{uuid.uuid4().hex}__screenshot"
        save_dir = "C:/file/"
        save_path = f"{save_dir}{local_file_name}"
        file_save_path = f"{local_file_name}.png"
        file_local_save_path = f"{save_path}.png"
        retry = 3
        while retry > 0:
            try:
                # 截图
                # 获取oss预签名url上传地址
                oss_signed_url = self.oss_client.get_signal_url(
                    f"{file_save_path}",
                )
                status, file_oss = self.get_screenshot_oss(
                    file_local_save_path,
                    oss_signed_url,
                )
                if "Traceback" in file_oss:
                    return ""
                file_oss_down = self.oss_client.get_download_url(
                    f"{file_save_path}",
                )
                if status and file_oss:
                    download_oss_image_and_save(
                        file_oss_down,
                        local_save_path,
                    )
                    if file_oss_down:
                        logger.info("成功获取图片数据")
                        return file_oss_down
            except Exception as e:
                retry -= 1
                logger.warning(f"截图失败，重试中... {retry}次剩余，错误: {e}")
                time.sleep(2)

        return ""

    async def get_screenshot_oss_url_async(
        self,
        local_file_name: str,
        local_save_path: str,
    ) -> str:
        # local_file_name = f"{uuid.uuid4().hex}__screenshot"
        save_path = f"C:/file/{local_file_name}"
        file_save_path = f"{local_file_name}.png"
        file_local_save_path = f"{save_path}.png"
        retry = 3
        while retry > 0:
            try:
                # 截图
                # 获取oss预签名url上传地址
                oss_signed_url = await self.oss_client.get_signal_url_async(
                    f"{file_save_path}",
                )
                status, file_oss = await self.get_screenshot_oss_async(
                    file_local_save_path,
                    oss_signed_url,
                )
                if "Traceback" in file_oss:
                    return ""
                file_oss_down = await self.oss_client.get_download_url_async(
                    f"{file_save_path}",
                )
                if status and file_oss:
                    await download_oss_image_and_save_async(
                        file_oss_down,
                        local_save_path,
                    )
                    if file_oss_down:
                        logger.info("成功获取图片数据")
                        return file_oss_down
            except Exception as e:
                retry -= 1
                logger.warning(f"截图失败，重试中... {retry}次剩余，错误: {e}")
                await asyncio.sleep(2)

        return ""

    def get_screenshot_oss_down(self, local_file_name: str) -> str:
        # local_file_name = f"{uuid.uuid4().hex}__screenshot"
        save_path = f"C:/file/{local_file_name}"
        file_save_path = f"{local_file_name}.png"
        file_local_save_path = f"{save_path}.png"
        retry = 3
        while retry > 0:
            try:
                # 截图
                # 获取oss预签名url上传地址
                oss_signed_url = self.oss_client.get_signal_url(
                    f"{file_save_path}",
                )
                self.get_screenshot_oss(
                    file_local_save_path,
                    oss_signed_url,
                )
                file_oss_down = self.oss_client.get_download_url(
                    f"{file_save_path}",
                )
                return file_oss_down

            except Exception as e:
                retry -= 1
                logger.warning(f"截图失败，重试中... {retry}次剩余，错误: {e}")
                time.sleep(2)

        return ""

    async def get_screenshot_oss_down_async(self, local_file_name: str) -> str:
        # local_file_name = f"{uuid.uuid4().hex}__screenshot"
        save_path = f"C:/file/{local_file_name}"
        file_save_path = f"{local_file_name}.png"
        file_local_save_path = f"{save_path}.png"
        retry = 3
        while retry > 0:
            try:
                # 截图
                # 获取oss预签名url上传地址
                oss_signed_url = await self.oss_client.get_signal_url_async(
                    f"{file_save_path}",
                )
                await self.get_screenshot_oss_async(
                    file_local_save_path,
                    oss_signed_url,
                )
                file_oss_down = await self.oss_client.get_download_url_async(
                    f"{file_save_path}",
                )
                return file_oss_down

            except Exception as e:
                retry -= 1
                logger.warning(f"截图失败，重试中... {retry}次剩余，错误: {e}")
                await asyncio.sleep(2)

        return ""

    async def run_command_power_shell_async(
        self,
        command: str,
        slot_time: float = None,
        timeout: int = 30,
    ) -> Tuple[str, str]:
        return await self.ecd_client.run_command_with_wait_async(
            self.desktop_id,
            command,
            slot_time,
            timeout,
        )

    def run_command_power_shell(
        self,
        command: str,
        slot_time: float = None,
        timeout: int = 30,
    ) -> Tuple[str, str]:
        return self.ecd_client.run_command_with_wait(
            self.desktop_id,
            command,
            slot_time,
            timeout,
        )

    def run_code(
        self,
        code: str,
        slot_time: float = None,
        timeout: int = 30,
    ) -> Tuple[str, str]:
        # 构建 Python 命令并进行 Base64 编码（使用 utf-16le）
        full_python_command = f'\npython -c "{code}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command, slot_time, timeout)

    async def run_code_async(
        self,
        code: str,
        slot_time: float = None,
        timeout: int = 30,
    ) -> Tuple[str, str]:
        # 构建 Python 命令并进行 Base64 编码（使用 utf-16le）
        full_python_command = f'\npython -c "{code}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(
            command,
            slot_time,
            timeout,
        )

    def write_file(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> Tuple[str, str]:
        # 使用 repr() 处理内容，确保所有特殊字符都被正确转义
        content_repr = repr(content)

        # 使用三重引号包装print语句避免引号冲突
        script = f"""
import os
file_path = r'{file_path}'
content = {content_repr}
encoding = '{encoding}'
# 创建目录（如果不存在）
directory = os.path.dirname(file_path)
if directory and not os.path.exists(directory):
    os.makedirs(directory)
# 写入文件
with open(file_path, 'w', encoding=encoding) as f:
    f.write(content)
print('File written successfully')
"""

        # 使用 @' '@ 语法包装脚本以支持多行内容
        full_python_command = f"\npython -c @'{script}'@"

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def read_file(
        self,
        file_path: str,
        encoding: str = "utf-8",
    ) -> Tuple[str, str]:
        script = f"""
import os
import base64

file_path = r'{file_path}'
encoding = '{encoding}'

if not os.path.exists(file_path):
    print(f'Error: File not found - {{file_path}}')
    exit(1)

try:
    with open(file_path, 'r', encoding=encoding) as f:
        content = f.read()
    print(content)
except Exception as e:
    print(f'Error reading file: {{e}}')
    exit(1)
        """

        full_python_command = f'\npython -c "{script}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def remove_file(self, file_path: str) -> Tuple[str, str]:
        script = f"""
import os
import shutil

file_path = r'{file_path}'

try:
    if os.path.isfile(file_path):
        os.remove(file_path)
        print(f'File {{file_path}} removed successfully')
    elif os.path.isdir(file_path):
        shutil.rmtree(file_path)
        print(f'Directory {{file_path}} removed successfully')
    else:
        print(f'Path {{file_path}} does not exist')
        exit(1)
except Exception as e:
    print(f'Error removing {{file_path}}: {{e}}')
    exit(1)
"""

        full_python_command = f'\npython -c "{script}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def get_screenshot_base64(
        self,
        screenshot_file: str,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import os
import base64
screenshot_file = r'{screenshot_file}'
if os.path.exists(screenshot_file):
    os.remove(screenshot_file)
screenshot = pyautogui.screenshot()
screenshot.save(screenshot_file)
with open(screenshot_file, 'rb') as img_file:
    image_data = img_file.read()
encoded_bytes = base64.b64encode(image_data).decode('utf-8')
print(encoded_bytes)
os.remove(screenshot_file)
        """.format(
            screenshot_file=screenshot_file,
        )

        # 转义双引号
        # escaped_script = script.replace('"', '""')

        # 构建 Python 命令并进行 Base64 编码（使用 utf-16le）
        full_python_command = f'\npython -c "{script}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    async def get_screenshot_base64_async(
        self,
        screenshot_file: str,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import os
import base64
screenshot_file = r'{screenshot_file}'
if os.path.exists(screenshot_file):
    os.remove(screenshot_file)
screenshot = pyautogui.screenshot()
screenshot.save(screenshot_file)
with open(screenshot_file, 'rb') as img_file:
    image_data = img_file.read()
encoded_bytes = base64.b64encode(image_data).decode('utf-8')
print(encoded_bytes)
os.remove(screenshot_file)
        """.format(
            screenshot_file=screenshot_file,
        )

        # 转义双引号
        # escaped_script = script.replace('"', '""')

        # 构建 Python 命令并进行 Base64 编码（使用 utf-16le）
        full_python_command = f'\npython -c "{script}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    def get_screenshot_oss(
        self,
        file_save_path: str,
        oss_signal_url: str,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import os
import base64
import requests
oss_signal_url = r'{oss_signal_url}'
file_save_path = r'{file_save_path}'
def upload_file(signed_url, file_path):
    try:
        with open(file_path, 'rb') as file:
            response = requests.put(signed_url, data=file)
        print(response.status_code)
    except Exception as e:
        print(e)
# 确保目录存在
directory = os.path.dirname(file_save_path)
if directory and not os.path.exists(directory):
    os.makedirs(directory)
if os.path.exists(file_save_path):
    os.remove(file_save_path)
screenshot = pyautogui.screenshot()
screenshot.save(file_save_path)
upload_file(oss_signal_url, file_save_path)
print(oss_signal_url)
os.remove(file_save_path)
    """.format(
            oss_signal_url=oss_signal_url,
            file_save_path=file_save_path,
        )

        # 转义双引号
        # escaped_script = script.replace('"', '""')

        # 构建 Python 命令并进行 Base64 编码（使用 utf-16le）
        full_python_command = f'\npython -c "{script}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    async def get_screenshot_oss_async(
        self,
        file_save_path: str,
        oss_signal_url: str,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import os
import base64
import requests
oss_signal_url = r'{oss_signal_url}'
file_save_path = r'{file_save_path}'
def upload_file(signed_url, file_path):
    try:
        with open(file_path, 'rb') as file:
            response = requests.put(signed_url, data=file)
        print(response.status_code)
    except Exception as e:
        print(e)
# 确保目录存在
directory = os.path.dirname(file_save_path)
if directory and not os.path.exists(directory):
    os.makedirs(directory)
if os.path.exists(file_save_path):
    os.remove(file_save_path)
screenshot = pyautogui.screenshot()
screenshot.save(file_save_path)
upload_file(oss_signal_url, file_save_path)
print(oss_signal_url)
os.remove(file_save_path)
    """.format(
            oss_signal_url=oss_signal_url,
            file_save_path=file_save_path,
        )

        # 转义双引号
        # escaped_script = script.replace('"', '""')

        # 构建 Python 命令并进行 Base64 编码（使用 utf-16le）
        full_python_command = f'\npython -c "{script}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    def open_app(self, name: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import time
import re
pyautogui.FAILSAFE = False

# 定义快捷键
ctrl_key = '{self.ctrl_key}'

def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

name = '{name}'
if 'Outlook' in name:
    name = name.replace('Outlook', 'Outlook new')

print(f'Action: open {name}')

# 打开 Windows 搜索栏
pyautogui.press('win')  # 按下 Win 键
time.sleep(0.3)
pyperclip.copy(name)
time.sleep(0.3)
pyautogui.keyDown(ctrl_key)
pyautogui.press('v')
pyautogui.keyUp(ctrl_key)
# 回车确认
time.sleep(0.3)
pyautogui.press('enter')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    async def open_app_async(self, name: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import time
import re
pyautogui.FAILSAFE = False

# 定义快捷键
ctrl_key = '{self.ctrl_key}'

def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

name = '{name}'
if 'Outlook' in name:
    name = name.replace('Outlook', 'Outlook new')

print(f'Action: open {name}')

# 打开 Windows 搜索栏
pyautogui.press('win')  # 按下 Win 键
time.sleep(0.3)
pyperclip.copy(name)
time.sleep(0.3)
pyautogui.keyDown(ctrl_key)
pyautogui.press('v')
pyautogui.keyUp(ctrl_key)
# 回车确认
time.sleep(0.3)
pyautogui.press('enter')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    def home(self) -> Tuple[str, str]:
        # 显示桌面
        script = """
import pyautogui
pyautogui.FAILSAFE = False
key1 = 'win'
key2 = 'd'
pyautogui.keyDown(key1)
pyautogui.keyDown(key2)
pyautogui.keyUp(key2)
pyautogui.keyUp(key1)
        """
        full_python_command = f'\npython -c "{script}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def tap(self, x: int, y: int, count: int = 1) -> Tuple[str, str]:
        script = f"""
import pyautogui
from pynput.mouse import Button, Controller
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x = {x}
y = {y}
count = {count}
x, y = x//ratio, y//ratio
print('Action: click (%d, %d) %d times' % (x, y, count))
mouse = Controller()
pyautogui.moveTo(x,y)
mouse.click(Button.left, count=count)
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def right_tap(
        self,
        x: int,
        y: int,
        count: int = 1,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
from pynput.mouse import Button, Controller
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x = {x}
y = {y}
count = {count}
x, y = x//ratio, y//ratio
print('Action: right click (%d, %d) %d times' % (x, y, count))
pyautogui.rightClick(x, y)
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def shortcut(self, key1: str, key2: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
key1 = '{key1}'
key2 = '{key2}'
ctrl_key = '{self.ctrl_key}'
if key1 == 'command' or key1 == 'ctrl':
    key1 = ctrl_key
print('Action: shortcut %s + %s' % (key1, key2))
pyautogui.keyDown(key1)
pyautogui.keyDown(key2)
pyautogui.keyUp(key2)
pyautogui.keyUp(key1)
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def hotkey(self, key_list: List[str]) -> Tuple[str, str]:
        """
        远程执行组合键操作（例如 ['ctrl', 'c']、['alt', 'f4'] 等）
        :param key_list: 组合键列表，如 ['ctrl', 'a'], ['alt', 'f4']
        """
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
pyautogui.hotkey('{key_list[0]}', '{key_list[1]}')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def press_key(self, key: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
pyautogui.press('{key}')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def tap_type_enter(
        self,
        x: int,
        y: int,
        text: str,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import time
pyautogui.FAILSAFE = False
ratio = {self.ratio}
ctrl_key = '{self.ctrl_key}'
x = {x}
y = {y}
text = '{text}'
x, y = x//ratio, y//ratio
print('Action: click (%d, %d), enter %s and press Enter' % (x, y, text))
pyautogui.click(x=x, y=y)
time.sleep(0.5)
pyperclip.copy(text)
pyautogui.keyDown(ctrl_key)
pyautogui.keyDown('v')
pyautogui.keyUp('v')
pyautogui.keyUp(ctrl_key)
time.sleep(0.5)
pyautogui.press('enter')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x1 = {x1}
y1 = {y1}
x2 = {x2}
y2 = {y2}
x1, y1 = x1//ratio, y1//ratio
x2, y2 = x2//ratio, y2//ratio
pyautogui.moveTo(x1,y1)
pyautogui.mouseDown()
pyautogui.moveTo(x2,y2,duration=0.5)
pyautogui.mouseUp()
print('Action: drag from (%d, %d) to (%d, %d)' % (x1, y1, x2, y2))
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def replace(self, x: int, y: int, text: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
from pynput.mouse import Button, Controller
import re
pyautogui.FAILSAFE = False
ratio = {self.ratio}
ctrl_key = '{self.ctrl_key}'
x = {x}
y = {y}
text = '{text}'
x, y = x//ratio, y//ratio
print('Action: replace the content at (%d, %d) '
      'with %s and press Enter' % (x, y, text))
mouse = Controller()
pyautogui.moveTo(x,y)
mouse.click(Button.left, count=2)
shortcut('command', 'a')
pyperclip.copy(text)
pyautogui.keyDown(ctrl_key)
pyautogui.keyDown('v')
pyautogui.keyUp('v')
pyautogui.keyUp(ctrl_key)
time.sleep(0.5)
pyautogui.press('enter')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def append(self, x: int, y: int, text: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import re
from pynput.mouse import Button, Controller
pyautogui.FAILSAFE = False
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))
def shortcut(key1, key2):
    # if key1 == 'command' and args.pc_type != "mac":
    # key1 = 'ctrl'
    if key1 == 'command' or key1 == 'ctrl':
        key1 = ctrl_key
    print('Action: shortcut %s + %s' % (key1, key2))
    pyautogui.keyDown(key1)
    pyautogui.keyDown(key2)
    pyautogui.keyUp(key2)
    pyautogui.keyUp(key1)
    return
x = {x}
y = {y}
text = '{text}'
ctrl_key = '{self.ctrl_key}'
ratio = {self.ratio}
x, y = x//ratio, y//ratio
print('Action: append the content at (%d, %d) '
      'with %s and press Enter' % (x, y, text))
mouse = Controller()
pyautogui.moveTo(x,y)
mouse.click(Button.left, count=1)
shortcut('command', 'a')
pyautogui.press('down')
if contains_chinese(text):
    pyperclip.copy(text)
    pyautogui.keyDown(ctrl_key)
    pyautogui.keyDown('v')
    pyautogui.keyUp('v')
    pyautogui.keyUp(ctrl_key)
else:
    pyautogui.typewrite(text)
time.sleep(1)
pyautogui.press('enter')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def mouse_move(self, x: int, y: int) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x = {x}
y = {y}
x, y = x//ratio, y//ratio
pyautogui.moveTo(x,y)
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def middle_click(self, x: int, y: int) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x = {x}
y = {y}
pyautogui.middleClick(x, y)
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def type_with_clear_enter(
        self,
        text: str,
        clear: int,
        enter: int,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import time
ratio = {self.ratio}
ctrl_key = '{self.ctrl_key}'
text = '{text}'
clear = {clear}
enter = {enter}
if clear == 1:
    pyautogui.keyDown(ctrl_key)
    pyautogui.keyDown('a')
    pyautogui.keyUp('a')
    pyautogui.keyUp(ctrl_key)
    pyautogui.press('backspace')
    time.sleep(0.5)
pyperclip.copy(text)
pyautogui.keyDown(ctrl_key)
pyautogui.keyDown('v')
pyautogui.keyUp('v')
pyautogui.keyUp(ctrl_key)
time.sleep(0.5)
if enter == 1:
    pyautogui.press('enter')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def type_with_clear_enter_pos(
        self,
        text: str,
        x: int,
        y: int,
        clear: int,
        enter: int,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import time
ratio = {self.ratio}
ctrl_key = '{self.ctrl_key}'
text = '{text}'
x = {x}
y = {y}
clear = {clear}
enter = {enter}
x, y = x/ratio, y/ratio
pyautogui.click(x=x, y=y)
time.sleep(0.5)
if clear == 1:
    pyautogui.keyDown(ctrl_key)
    pyautogui.keyDown('a')
    pyautogui.keyUp('a')
    pyautogui.keyUp(ctrl_key)
    pyautogui.press('backspace')
    time.sleep(0.5)

pyperclip.copy(text)
pyautogui.keyDown(ctrl_key)
pyautogui.keyDown('v')
pyautogui.keyUp('v')
pyautogui.keyUp(ctrl_key)
time.sleep(0.5)
if enter == 1:
    pyautogui.press('enter')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def scroll_pos(self, x: int, y: int, pixels: int) -> Tuple[str, str]:
        script = f"""
import pyautogui
import time
ratio = {self.ratio}
x = {x}
y = {y}
pixels = {pixels}*150
x, y = x//ratio, y//ratio
pyautogui.moveTo(x, y)
time.sleep(0.5)
pyautogui.scroll(pixels)
print('scroll_pos')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    def scroll(self, pixels: int) -> Tuple[str, str]:
        script = f"""
import pyautogui
pixels = {pixels}*150
pyautogui.scroll(pixels)
print('scroll')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return self.run_command_power_shell(command)

    async def home_async(self) -> Tuple[str, str]:
        # 显示桌面
        script = """
import pyautogui
pyautogui.FAILSAFE = False
key1 = 'win'
key2 = 'd'
pyautogui.keyDown(key1)
pyautogui.keyDown(key2)
pyautogui.keyUp(key2)
pyautogui.keyUp(key1)
        """
        full_python_command = f'\npython -c "{script}"'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def tap_async(
        self,
        x: int,
        y: int,
        count: int = 1,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
from pynput.mouse import Button, Controller
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x = {x}
y = {y}
count = {count}
x, y = x//ratio, y//ratio
print('Action: click (%d, %d) %d times' % (x, y, count))
mouse = Controller()
pyautogui.moveTo(x,y)
mouse.click(Button.left, count=count)
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def right_tap_async(
        self,
        x: int,
        y: int,
        count: int = 1,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
from pynput.mouse import Button, Controller
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x = {x}
y = {y}
count = {count}
x, y = x//ratio, y//ratio
print('Action: right click (%d, %d) %d times' % (x, y, count))
pyautogui.rightClick(x, y)
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def shortcut_async(self, key1: str, key2: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
key1 = '{key1}'
key2 = '{key2}'
ctrl_key = '{self.ctrl_key}'
if key1 == 'command' or key1 == 'ctrl':
    key1 = ctrl_key
print('Action: shortcut %s + %s' % (key1, key2))
pyautogui.keyDown(key1)
pyautogui.keyDown(key2)
pyautogui.keyUp(key2)
pyautogui.keyUp(key1)
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def hotkey_async(self, key_list: List[str]) -> Tuple[str, str]:
        """
        远程执行组合键操作（例如 ['ctrl', 'c']、['alt', 'f4'] 等）
        :param key_list: 组合键列表，如 ['ctrl', 'a'], ['alt', 'f4']
        """
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
pyautogui.hotkey('{key_list[0]}', '{key_list[1]}')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def press_key_async(self, key: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
pyautogui.press('{key}')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def tap_type_enter_async(
        self,
        x: int,
        y: int,
        text: str,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import time
pyautogui.FAILSAFE = False
ratio = {self.ratio}
ctrl_key = '{self.ctrl_key}'
x = {x}
y = {y}
text = '{text}'
x, y = x//ratio, y//ratio
print('Action: click (%d, %d), enter %s and press Enter' % (x, y, text))
pyautogui.click(x=x, y=y)
time.sleep(0.5)
pyperclip.copy(text)
pyautogui.keyDown(ctrl_key)
pyautogui.keyDown('v')
pyautogui.keyUp('v')
pyautogui.keyUp(ctrl_key)
time.sleep(0.5)
pyautogui.press('enter')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def drag_async(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x1 = {x1}
y1 = {y1}
x2 = {x2}
y2 = {y2}
x1, y1 = x1//ratio, y1//ratio
x2, y2 = x2//ratio, y2//ratio
pyautogui.moveTo(x1,y1)
pyautogui.mouseDown()
pyautogui.moveTo(x2,y2,duration=0.5)
pyautogui.mouseUp()
print('Action: drag from (%d, %d) to (%d, %d)' % (x1, y1, x2, y2))
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def replace_async(
        self,
        x: int,
        y: int,
        text: str,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
from pynput.mouse import Button, Controller
import re
pyautogui.FAILSAFE = False
ratio = {self.ratio}
ctrl_key = '{self.ctrl_key}'
x = {x}
y = {y}
text = '{text}'
x, y = x//ratio, y//ratio
print('Action: replace the content at (%d, %d) '
      'with %s and press Enter' % (x, y, text))
mouse = Controller()
pyautogui.moveTo(x,y)
mouse.click(Button.left, count=2)
shortcut('command', 'a')
pyperclip.copy(text)
pyautogui.keyDown(ctrl_key)
pyautogui.keyDown('v')
pyautogui.keyUp('v')
pyautogui.keyUp(ctrl_key)
time.sleep(0.5)
pyautogui.press('enter')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def append_async(self, x: int, y: int, text: str) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import re
from pynput.mouse import Button, Controller
pyautogui.FAILSAFE = False
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))
def shortcut(key1, key2):
    # if key1 == 'command' and args.pc_type != "mac":
    # key1 = 'ctrl'
    if key1 == 'command' or key1 == 'ctrl':
        key1 = ctrl_key
    print('Action: shortcut %s + %s' % (key1, key2))
    pyautogui.keyDown(key1)
    pyautogui.keyDown(key2)
    pyautogui.keyUp(key2)
    pyautogui.keyUp(key1)
    return
x = {x}
y = {y}
text = '{text}'
ctrl_key = '{self.ctrl_key}'
ratio = {self.ratio}
x, y = x//ratio, y//ratio
print('Action: append the content at (%d, %d) '
      'with %s and press Enter' % (x, y, text))
mouse = Controller()
pyautogui.moveTo(x,y)
mouse.click(Button.left, count=1)
shortcut('command', 'a')
pyautogui.press('down')
if contains_chinese(text):
    pyperclip.copy(text)
    pyautogui.keyDown(ctrl_key)
    pyautogui.keyDown('v')
    pyautogui.keyUp('v')
    pyautogui.keyUp(ctrl_key)
else:
    pyautogui.typewrite(text)
time.sleep(1)
pyautogui.press('enter')
"""

        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def mouse_move_async(self, x: int, y: int) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x = {x}
y = {y}
x, y = x//ratio, y//ratio
pyautogui.moveTo(x,y)
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def middle_click_async(self, x: int, y: int) -> Tuple[str, str]:
        script = f"""
import pyautogui
pyautogui.FAILSAFE = False
ratio = {self.ratio}
x = {x}
y = {y}
pyautogui.middleClick(x, y)
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def type_with_clear_enter_async(
        self,
        text: str,
        clear: int,
        enter: int,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import time
ratio = {self.ratio}
ctrl_key = '{self.ctrl_key}'
text = '{text}'
clear = {clear}
enter = {enter}
if clear == 1:
    pyautogui.keyDown(ctrl_key)
    pyautogui.keyDown('a')
    pyautogui.keyUp('a')
    pyautogui.keyUp(ctrl_key)
    pyautogui.press('backspace')
    time.sleep(0.5)
pyperclip.copy(text)
pyautogui.keyDown(ctrl_key)
pyautogui.keyDown('v')
pyautogui.keyUp('v')
pyautogui.keyUp(ctrl_key)
time.sleep(0.5)
if enter == 1:
    pyautogui.press('enter')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def type_with_clear_enter_pos_async(
        self,
        text: str,
        x: int,
        y: int,
        clear: int,
        enter: int,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import pyperclip
import time
ratio = {self.ratio}
ctrl_key = '{self.ctrl_key}'
text = '{text}'
x = {x}
y = {y}
clear = {clear}
enter = {enter}
x, y = x/ratio, y/ratio
pyautogui.click(x=x, y=y)
time.sleep(0.5)
if clear == 1:
    pyautogui.keyDown(ctrl_key)
    pyautogui.keyDown('a')
    pyautogui.keyUp('a')
    pyautogui.keyUp(ctrl_key)
    pyautogui.press('backspace')
    time.sleep(0.5)

pyperclip.copy(text)
pyautogui.keyDown(ctrl_key)
pyautogui.keyDown('v')
pyautogui.keyUp('v')
pyautogui.keyUp(ctrl_key)
time.sleep(0.5)
if enter == 1:
    pyautogui.press('enter')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def scroll_pos_async(
        self,
        x: int,
        y: int,
        pixels: int,
    ) -> Tuple[str, str]:
        script = f"""
import pyautogui
import time
ratio = {self.ratio}
x = {x}
y = {y}
pixels = {pixels}*150
x, y = x//ratio, y//ratio
pyautogui.moveTo(x, y)
time.sleep(0.5)
pyautogui.scroll(pixels)
print('scroll_pos')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)

    async def scroll_async(self, pixels: int) -> Tuple[str, str]:
        script = f"""
import pyautogui
pixels = {pixels}*150
pyautogui.scroll(pixels)
print('scroll')
"""
        full_python_command = f'\npython -c @"{script}"@'

        # 构造 PowerShell 命令
        command = (
            r'$env:Path += ";C:\Program Files\Python310"'
            f"{full_python_command}"
        )

        return await self.run_command_power_shell_async(command)


class AppStreamClient:
    def __init__(self) -> None:
        config = open_api_models.Config(
            access_key_id=os.environ.get("ECD_ALIBABA_CLOUD_ACCESS_KEY_ID"),
            # 您的AccessKey Secret,
            access_key_secret=os.environ.get(
                "ECD_ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ),
        )
        # Endpoint 请参考 https://api.aliyun.com/product/eds-aic
        config.endpoint = (
            f"appstream-center."
            f'{os.environ.get("ECD_APP_STREAM_REGION_ID")}.aliyuncs.com'
        )
        self.__client__ = appstream_center20210218Client(config)

    async def search_auth_code_async(self) -> str:
        """获取新的auth_code，每次调用都会生成新的认证码"""
        get_auth_code_request = (
            appstream_center_20210218_models.GetAuthCodeRequest(
                end_user_id=os.environ.get("ECD_USERNAME"),
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rep = await self.__client__.get_auth_code_with_options_async(
                get_auth_code_request,
                runtime,
            )
            auth_code = rep.body.auth_model.auth_code
            logger.info(f"成功获取新的auth_code: {auth_code[:20]}...")
            return auth_code
        except Exception as error:
            logger.error(f"search authcode failed:{error}")
            return ""

    def search_auth_code(self) -> str:
        """获取新的auth_code，每次调用都会生成新的认证码"""
        get_auth_code_request = (
            appstream_center_20210218_models.GetAuthCodeRequest(
                end_user_id=os.environ.get("ECD_USERNAME"),
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rep = self.__client__.get_auth_code_with_options(
                get_auth_code_request,
                runtime,
            )
            auth_code = rep.body.auth_model.auth_code
            logger.info(f"成功获取新的auth_code: {auth_code[:20]}...")
            return auth_code
        except Exception as error:
            logger.error(f"search authcode failed:{error}")
            return ""
