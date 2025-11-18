# -*- coding: utf-8 -*-
import os
import threading
import asyncio
import time
import uuid
import logging
from typing import Tuple, Optional, Any, List
from pydantic import BaseModel
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_eds_aic20230930.client import Client as eds_aic20230930Client
from alibabacloud_eds_aic20230930 import models as eds_aic_20230930_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient

from agentscope_runtime.sandbox.box.cloud_api.utils.oss_client import OSSClient

logger = logging.getLogger(__name__)


execute_wait_time_: int = 5


class ScreenshotError(Exception):
    """截图相关操作异常"""


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
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # 使用 hasattr 确保属性存在
        if not getattr(self, "_initialized", False):
            self._eds_client = None
            self._oss_client = None
            self._client_lock = threading.Lock()
            self._instance_managers = {}
            # 使用不同的锁来避免死锁
            self._eds_lock = threading.Lock()
            self._oss_lock = threading.Lock()
            self._instance_manager_lock = threading.Lock()
            self._initialized = True

    def get_eds_client(self) -> "EdsClient":
        """获取共享的EdsClient实例"""
        if self._eds_client is None:
            with self._eds_lock:
                if self._eds_client is None:
                    self._eds_client = EdsClient()
        return self._eds_client

    def get_oss_client(self) -> OSSClient:
        """获取共享的OSSClient实例"""
        if self._oss_client is None:
            with self._oss_lock:
                if self._oss_client is None:
                    bucket_name = os.environ.get("EDS_OSS_BUCKET_NAME")
                    endpoint = os.environ.get("EDS_OSS_ENDPOINT")
                    self._oss_client = OSSClient(bucket_name, endpoint)
        return self._oss_client

    def get_instance_manager(self, instance_id: str) -> "EdsInstanceManager":
        """获取指定desktop_id的EcdInstanceManager实例"""
        # 先检查是否已存在，避免不必要的锁竞争
        if instance_id in self._instance_managers:
            return self._instance_managers[instance_id]

        # 在锁外预先获取客户端，避免死锁
        eds_client = self.get_eds_client()
        oss_client = self.get_oss_client()

        # 使用专门的锁管理实例管理器
        with self._instance_manager_lock:
            # 再次检查，防止在等待锁的过程中已经被其他线程创建
            if instance_id not in self._instance_managers:
                # 创建新的实例管理器，并传入共享的客户端
                manager = EdsInstanceManager(instance_id)
                manager.eds_client = eds_client
                manager.oss_client = oss_client
                self._instance_managers[instance_id] = manager
        return self._instance_managers[instance_id]


class EdsDeviceInfo(BaseModel):
    # 云手机设备信息查询字段返回类
    android_instance_name: str
    android_instance_id: str
    network_interface_ip: str
    android_instance_status: str


class CommandTimeoutError(Exception):
    """命令执行超时时抛出的异常"""


# pylint: disable=too-many-public-methods
class EdsClient:
    def __init__(self) -> None:
        config = open_api_models.Config(
            access_key_id=os.environ.get("EDS_ALIBABA_CLOUD_ACCESS_KEY_ID"),
            # 您的AccessKey Secret,
            access_key_secret=os.environ.get(
                "EDS_ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ),
        )
        # Endpoint 请参考 https://api.aliyun.com/product/eds-aic
        config.endpoint = os.environ.get("EDS_ALIBABA_CLOUD_ENDPOINT")
        config.read_timeout = 6000
        self._client = eds_aic20230930Client(config)

    def client_ticket_create(self, instance_id: str) -> Tuple[str, str, str]:
        logger.info(f"[{instance_id}]: create ticket")
        batch_get_acp_connection_ticket_request = (
            eds_aic_20230930_models.BatchGetAcpConnectionTicketRequest(
                instance_ids=[
                    instance_id,
                ],
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = self._client.batch_get_acp_connection_ticket_with_options(
                batch_get_acp_connection_ticket_request,
                runtime,
            )
            info = rsp.body.instance_connection_models[0]
            logger.info(
                f"[{instance_id}]: create ticket success",
            )
            return (
                info.ticket,
                info.persistent_app_instance_id,
                info.app_instance_id,
            )
        except Exception as error:
            logger.error(
                f"[{instance_id}]: error when create ticket error:{error}",
            )
            return "", "", ""

    async def client_ticket_create_async(
        self,
        instance_id: str,
    ) -> Tuple[str, str, str]:
        logger.info(f"[{instance_id}]: start to create ticket")
        batch_get_acp_connection_ticket_request = (
            eds_aic_20230930_models.BatchGetAcpConnectionTicketRequest(
                instance_ids=[
                    instance_id,
                ],
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            method = (
                self._client.batch_get_acp_connection_ticket_with_options_async
            )
            rsp = await method(
                batch_get_acp_connection_ticket_request,
                runtime,
            )
            info = rsp.body.instance_connection_models[0]
            logger.info(f"[{instance_id}]: create ticket success")
            return (
                info.ticket,
                info.persistent_app_instance_id,
                info.app_instance_id,
            )
        except Exception as error:
            logger.error(
                f"[{instance_id}]: error when create ticket error:{error}",
            )
            return "", "", ""

    def execute_command(
        self,
        instance_ids: List[str],
        command: str,
        timeout: int = 60,
    ) -> tuple[str, str | None]:
        logger.info(f"[{instance_ids}]: start to execute command: {command}")
        # 执行命令
        run_command_request = eds_aic_20230930_models.RunCommandRequest(
            instance_ids=instance_ids,
            command_content=command,
            timeout=timeout,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self._client.run_command_with_options(
                run_command_request,
                runtime,
            )
            assert rsp.status_code == 200
            logger.info(
                f"[{instance_ids}]: execute command success",
            )
            invoke_id = rsp.body.invoke_id
            request_id = rsp.body.request_id
            # logging.info(invoke_id, request_id)
            return invoke_id, request_id
        except Exception as error:
            logger.error(
                f"[{instance_ids}]: error when excute command:"
                f" {command}, error:{error}",
            )
            return "", ""

    async def execute_command_async(
        self,
        instance_ids: List[str],
        command: str,
        timeout: int = 60,
    ) -> tuple[str, str | None]:
        # 执行命令
        run_command_request = eds_aic_20230930_models.RunCommandRequest(
            instance_ids=instance_ids,
            command_content=command,
            timeout=timeout,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = await self._client.run_command_with_options_async(
                run_command_request,
                runtime,
            )

            assert rsp.status_code == 200
            invoke_id = rsp.body.invoke_id
            request_id = rsp.body.request_id
            # logging.info(invoke_id, request_id)
            return invoke_id, request_id
        except Exception as error:
            logger.error(
                f"[{instance_ids}]: error when excute command:"
                f" {command}, error:{error}",
            )
            return "", ""

    def query_execute_state(
        self,
        instance_ids: List[str],
        message_id: str,
    ) -> Any:
        # 查询命令执行结果
        describe_invocations_request = (
            eds_aic_20230930_models.DescribeInvocationsRequest(
                instance_ids=instance_ids,
                invocation_id=message_id,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self._client.describe_invocations_with_options(
                describe_invocations_request,
                runtime,
            )
            # print(rsp.body)
            return rsp.body
        except Exception as error:
            UtilClient.assert_as_string(error)
            logger.error(
                f"[{instance_ids}]: error when query message:"
                f" {message_id}, error:{error}",
            )
            return None

    def run_command_with_wait(
        self,
        instances_id: str,
        command: str,
        slot_time: float = None,
        timeout: int = 60,
    ) -> tuple[bool, str | None]:
        logger.info(f"[{instances_id}]: start to run command async:{command}")
        execute_id, request_id = self.execute_command(
            [instances_id],
            command,
            timeout=timeout,
        )
        logger.info(f"[{request_id}{instances_id}]: start to wait command")
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
                time.sleep(slot_time)
                msgs = self.query_execute_state(
                    [instances_id],
                    execute_id,
                )
                for msg in msgs.data:
                    if msg.invocation_status in [
                        "Success",
                        "Failed",
                        "Timeout",
                    ]:
                        print(
                            f"command cost time: "
                            f"{time.time() - start_time}",
                        )
                        logger.info(
                            f"[{instances_id}]: command status:"
                            f" {msg.invocation_status}",
                        )
                        return (
                            msg.invocation_status == "Success",
                            msg.output,
                        )
                timeout -= slot_time
        logger.error(f"[{instances_id}]: command timeout")
        raise CommandTimeoutError("command timeout")

    async def run_command_with_wait_async(
        self,
        instances_id: str,
        command: str,
        slot_time: float = None,
        timeout: int = 60,
    ) -> tuple[bool, str | None]:
        logger.info(f"[{instances_id}]: start to run command async:{command}")
        execute_id, request_id = await self.execute_command_async(
            [instances_id],
            command,
            timeout=timeout,
        )
        logger.info(f"[{request_id}{instances_id}]: start to wait command")
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
                await asyncio.sleep(slot_time)
                msgs = self.query_execute_state(
                    [instances_id],
                    execute_id,
                )
                for msg in msgs.data:
                    if msg.invocation_status in [
                        "Success",
                        "Failed",
                        "Timeout",
                    ]:
                        print(
                            f"command cost time: "
                            f"{time.time() - start_time}",
                        )
                        logger.info(
                            f"[{instances_id}]: command status:"
                            f" {msg.invocation_status}",
                        )
                        return (
                            msg.invocation_status == "Success",
                            msg.output,
                        )
                timeout -= slot_time
        logger.error(f"[{instances_id}]: command timeout")
        raise CommandTimeoutError("command timeout")

    async def create_screenshot_async(self, instances_id: str) -> str:
        logger.info(f"[{instances_id}]: start to ask api to do screenshot")
        create_screenshot_request = (
            eds_aic_20230930_models.CreateScreenshotRequest(
                android_instance_id_list=[
                    instances_id,
                ],
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = await self._client.create_screenshot_with_options_async(
                create_screenshot_request,
                runtime,
            )
            logger.info(
                f"[{instances_id}]: start to ask api to do screenshot success",
            )
            return rsp.body.tasks[0].task_id
        except Exception as error:
            logger.error(
                f"[{instances_id}]: error when ask api to do screenshot:"
                f" {error}",
            )
        return ""

    def create_screenshot(self, instances_id: str) -> str:
        logger.info(f"[{instances_id}]: start to ask api to do screenshot")
        create_screenshot_request = (
            eds_aic_20230930_models.CreateScreenshotRequest(
                android_instance_id_list=[
                    instances_id,
                ],
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = self._client.create_screenshot_with_options(
                create_screenshot_request,
                runtime,
            )
            logger.info(
                f"[{instances_id}]: start to ask api to do screenshot success",
            )
            return rsp.body.tasks[0].task_id
        except Exception as error:
            logger.error(
                f"[{instances_id}]: error when ask api to do screenshot:"
                f" {error}",
            )
        return ""

    async def describe_tasks_async(self, task_ids: List[str]) -> str:
        logger.info(f"[{task_ids}]: start to wait task")
        describe_tasks_request = eds_aic_20230930_models.DescribeTasksRequest(
            task_ids=task_ids,
        )
        runtime = util_models.RuntimeOptions()
        retry = 3
        while retry > 0:
            try:
                await asyncio.sleep(1)
                # 复制代码运行请自行打印 API 的返回值
                rsp = await self._client.describe_tasks_with_options_async(
                    describe_tasks_request,
                    runtime,
                )
                result = rsp.body.data[0].result
                logger.info(f"[{task_ids}]: task result: {result}")
                if not result:
                    logger.error(
                        f"[{task_ids}]: task result is empty and retry",
                    )
                    retry += 1
                    continue
                return result
            except Exception as error:
                retry -= 1
                logger.error(f"[{task_ids}]: task result error: {error}")
        return ""

    def describe_tasks(self, task_ids: List[str]) -> str:
        logger.info(f"[{task_ids}]: start to wait task")
        describe_tasks_request = eds_aic_20230930_models.DescribeTasksRequest(
            task_ids=task_ids,
        )
        runtime = util_models.RuntimeOptions()
        retry = 3
        while retry > 0:
            try:
                time.sleep(1)
                # 复制代码运行请自行打印 API 的返回值
                rsp = self._client.describe_tasks_with_options(
                    describe_tasks_request,
                    runtime,
                )
                result = rsp.body.data[0].result
                logger.info(f"[{task_ids}]: task result: {result}")
                if not result:
                    logger.error(
                        f"[{task_ids}]: task result is empty and retry",
                    )
                    retry += 1
                    continue
                return result
            except Exception as error:
                retry -= 1
                logger.error(f"[{task_ids}]: task result error: {error}")
        return ""

    def list_instance(
        self,
        page_size: Optional[int] = 10,
        next_token: Optional[int] = None,
        status: Optional[int] = None,
        instance_ids: List[str] = None,
    ) -> Any:
        logger.info(f"start to list instances {instance_ids}")
        describe_android_instances_request = (
            eds_aic_20230930_models.DescribeAndroidInstancesRequest(
                max_results=page_size,
                next_token=next_token,
                status=status,
                android_instance_ids=instance_ids,
            )
        )

        runtime = util_models.RuntimeOptions()
        try:
            rsp = self._client.describe_android_instances_with_options(
                describe_android_instances_request,
                runtime,
            )
            devices_info = [
                EdsDeviceInfo(**inst.__dict__)
                for inst in rsp.body.instance_model
            ]
            logger.info(f"list instances success: {devices_info}")
            return rsp.body.total_count, rsp.body.next_token, devices_info
        except Exception as error:
            logger.error(f"list wuying mobile failed: {error}")
            return 0, None, []

    def list_all_instance(
        self,
        page_size: int = 5,
    ) -> List[EdsDeviceInfo]:
        instances = []
        count, next_token, page_instances = self.list_instance(
            page_size=page_size,
            next_token=None,
        )
        print("count:", count)
        instances += page_instances
        while next_token is not None:
            _, next_token, page_instances = self.list_instance(
                page_size=page_size,
                next_token=next_token,
            )
            instances += page_instances
            # print("------", next_token)
        return instances

    def restart_equipment(self, instance_ids: List[str]) -> None:
        logger.info(f"{instance_ids}: start to restart equipment")
        reboot_android_instances_in_group_request = (
            eds_aic_20230930_models.RebootAndroidInstancesInGroupRequest(
                android_instance_ids=instance_ids,
                force_stop=True,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self._client
            method = e_c.reboot_android_instances_in_group_with_options
            rsp = method(
                reboot_android_instances_in_group_request,
                runtime,
            )
            logger.info(
                "instance_ids: restart equipment ask api success,"
                " and wait finish",
            )
            print(rsp)
        except Exception as error:
            logger.info(
                f"restart equipment failed:{error}",
            )

    async def restart_equipment_async(self, instance_ids: List[str]) -> None:
        logger.info(f"{instance_ids}: start to restart equipment")
        reboot_android_instances_in_group_request = (
            eds_aic_20230930_models.RebootAndroidInstancesInGroupRequest(
                android_instance_ids=instance_ids,
                force_stop=True,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self._client
            method = e_c.reboot_android_instances_in_group_with_options_async
            rsp = await method(
                reboot_android_instances_in_group_request,
                runtime,
            )
            logger.info(
                "instance_ids: restart equipment ask api success,"
                " and wait finish",
            )
            print(rsp)
        except Exception as error:
            logger.info(
                f"restart equipment failed:{error}",
            )

    async def start_equipment_async(self, instance_ids: List[str]) -> int:
        logger.info(f"{instance_ids}: start to start instance")
        start_android_instance_request = (
            eds_aic_20230930_models.StartAndroidInstanceRequest(
                android_instance_ids=instance_ids,
            )
        )

        runtime = util_models.RuntimeOptions()
        try:
            e_c = self._client
            method = e_c.start_android_instance_with_options_async
            rsp = await method(
                start_android_instance_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: start instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"start instance failed:{error}")
        return 400

    def start_equipment(self, instance_ids: List[str]) -> int:
        logger.info(f"{instance_ids}: start to start instance")
        start_android_instance_request = (
            eds_aic_20230930_models.StartAndroidInstanceRequest(
                android_instance_ids=instance_ids,
            )
        )

        runtime = util_models.RuntimeOptions()
        try:
            e_c = self._client
            method = e_c.start_android_instance_with_options
            rsp = method(
                start_android_instance_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: start instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"start instance failed:{error}")
        return 400

    def stop_equipment(self, instance_ids: List[str]) -> int:
        logger.info(f"{instance_ids}: start to stop instance")
        stop_android_instance_request = (
            eds_aic_20230930_models.StopAndroidInstanceRequest(
                android_instance_ids=instance_ids,
            )
        )

        runtime = util_models.RuntimeOptions()
        try:
            rsp = self._client.stop_android_instance_with_options(
                stop_android_instance_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: stop instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"stop_equipment failed:{error}")
        return 400

    async def stop_equipment_async(self, instance_ids: List[str]) -> int:
        logger.info(f"{instance_ids}: start to stop instance")
        stop_android_instance_request = (
            eds_aic_20230930_models.StopAndroidInstanceRequest(
                android_instance_ids=instance_ids,
            )
        )

        runtime = util_models.RuntimeOptions()
        try:
            e_c = self._client
            method = e_c.stop_android_instance_with_options_async
            rsp = await method(
                stop_android_instance_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: stop instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"stop instance failed:{error}")
        return 400

    async def reset_equipment_async(self, instance_ids: List[str]) -> int:
        logger.info(f"{instance_ids}: start to reset equipment")
        reset_android_instances_in_group_request = (
            eds_aic_20230930_models.ResetAndroidInstancesInGroupRequest(
                android_instance_ids=instance_ids,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self._client
            method = e_c.reset_android_instances_in_group_with_options_async
            rsp = await method(
                reset_android_instances_in_group_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: reset equipment ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"reset_equipment failed:{error}")
        return 400

    def reset_equipment(self, instance_ids: List[str]) -> int:
        logger.info(f"{instance_ids}: start to reset equipment")
        reset_android_instances_in_group_request = (
            eds_aic_20230930_models.ResetAndroidInstancesInGroupRequest(
                android_instance_ids=instance_ids,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self._client
            method = e_c.reset_android_instances_in_group_with_options
            rsp = method(
                reset_android_instances_in_group_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: reset equipment ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"reset_equipment failed:{error}")
        return 400

    def rebuild_equipment_image(
        self,
        instance_ids: List[str],
        image_id: str,
    ) -> int:
        logger.info(f"{instance_ids}: start to rebuild equipment image")
        update_instance_image_request = (
            eds_aic_20230930_models.UpdateInstanceImageRequest(
                instance_id_list=instance_ids,
                image_id=image_id,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self._client.update_instance_image_with_options(
                update_instance_image_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: rebuild equipment image ask api "
                f"success, and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"rebuild_equipment_image failed:{error}")
        return 400

    async def rebuild_equipment_image_async(
        self,
        instance_ids: List[str],
        image_id: str,
    ) -> int:
        logger.info(f"{instance_ids}: start to rebuild equipment image")
        update_instance_image_request = (
            eds_aic_20230930_models.UpdateInstanceImageRequest(
                instance_id_list=instance_ids,
                image_id=image_id,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = await self._client.update_instance_image_with_options_async(
                update_instance_image_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: rebuild equipment image ask api "
                f"success, and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"rebuild_equipment_image failed:{error}")
        return 400

    def send_file(
        self,
        instance_ids: List[str],
        source_file_path: str,
        upload_url: str,
    ) -> int:
        logger.info(f"{instance_ids}: start to rebuild equipment image")
        send_file_request = eds_aic_20230930_models.SendFileRequest(
            android_instance_id_list=instance_ids,
            source_file_path=source_file_path,
            upload_type="DOWNLOAD_URL",
            upload_url=upload_url,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self._client.send_file_with_options(
                send_file_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: send file ask api "
                f"success, and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"send file failed:{error}")
        return 400

    async def send_file_async(
        self,
        instance_ids: List[str],
        source_file_path: str,
        upload_url: str,
    ) -> int:
        logger.info(f"{instance_ids}: start to rebuild equipment image")
        send_file_request = eds_aic_20230930_models.SendFileRequest(
            android_instance_id_list=instance_ids,
            source_file_path=source_file_path,
            upload_type="DOWNLOAD_URL",
            upload_url=upload_url,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = await self._client.send_file_with_options_async(
                send_file_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: send file ask api "
                f"success, and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"send file failed:{error}")
        return 400

    def fetch_file(
        self,
        instance_ids: List[str],
        source_file_path: str,
        upload_endpoint: str,
        upload_url: str,
    ) -> int:
        logger.info(f"{instance_ids}: start to rebuild equipment image")
        fetch_file_request = eds_aic_20230930_models.FetchFileRequest(
            android_instance_id_list=instance_ids,
            source_file_path=source_file_path,
            upload_type="OSS",
            upload_endpoint=upload_endpoint,
            upload_url=upload_url,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self._client.fetch_file_with_options(
                fetch_file_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: fetch file ask api "
                f"success, and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"fetch file failed:{error}")
        return 400

    async def fetch_file_async(
        self,
        instance_ids: List[str],
        source_file_path: str,
        upload_endpoint: str,
        upload_url: str,
    ) -> int:
        logger.info(f"{instance_ids}: start to rebuild equipment image")
        fetch_file_request = eds_aic_20230930_models.FetchFileRequest(
            android_instance_id_list=instance_ids,
            source_file_path=source_file_path,
            upload_type="OSS",
            upload_endpoint=upload_endpoint,
            upload_url=upload_url,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = await self._client.fetch_file_with_options_async(
                fetch_file_request,
                runtime,
            )
            logger.info(
                f"{instance_ids}: fetch file ask api "
                f"success, and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"fetch file failed:{error}")
        return 400


# pylint: disable=too-many-public-methods
class EdsInstanceManager:
    def __init__(self, instance_id: str = ""):
        # 📝 直接使用传入的 instance_id，移除本地缓存逻辑
        if not instance_id:
            logger.error(
                "instance_id is required for "
                "EdsInstanceManager initialization",
            )
            raise InitError(
                "instance_id is required for "
                "EdsInstanceManager initialization",
            )

        self.instance_id = instance_id
        self.client_pool = ClientPool()
        self.eds_client = self.client_pool.get_eds_client()
        self.oss_client = self.client_pool.get_oss_client()
        bucket_name = os.environ.get("EDS_OSS_BUCKET_NAME")
        endpoint = os.environ.get("EDS_OSS_ENDPOINT")
        # self.oss_client = OSSClient(bucket_name, endpoint)
        self.endpoint = endpoint
        self.des_oss_dir = f"oss://{bucket_name}/__mPLUG__/{self.instance_id}/"
        self.oss_ak = (os.environ.get("EDS_OSS_ACCESS_KEY_ID"),)
        self.oss_sk = os.environ.get("EDS_OSS_ACCESS_KEY_SECRET")
        self._initialized = False
        self.ticket = None
        self.person_app_id = None
        self.app_instance_id = None

    def refresh_ticket(self):
        logger.info(f"实例{self.instance_id}:refresh_ticket...")
        (
            self.ticket,
            self.person_app_id,
            self.app_instance_id,
        ) = self.eds_client.client_ticket_create(
            self.instance_id,
        )
        self._initialized = True
        logger.info(f"实例{self.instance_id}:refresh_ticket成功")

    async def refresh_ticket_async(self):
        logger.info(f"实例{self.instance_id}:refresh_ticket...")
        (
            self.ticket,
            self.person_app_id,
            self.app_instance_id,
        ) = await self.eds_client.client_ticket_create_async(
            self.instance_id,
        )
        self._initialized = True
        logger.info(f"实例{self.instance_id}:refresh_ticket成功")

    def _ensure_initialized(self):
        if not self._initialized:
            logger.warning(f"实例{self.instance_id}:请先初始化")
            raise InitError(
                "Manager not initialized. Call await initialize() first.",
            )

    # 🚫 run_list_instance 函数已被移除，因为设备分配现在由 backend.py 统一管理

    async def get_screenshot_sdk_async(self) -> str:
        logger.info(f"实例{self.instance_id}:获取截图")
        task_id = await self.eds_client.create_screenshot_async(
            self.instance_id,
        )
        logger.info(
            f"实例{self.instance_id}:截图任务创建成功，task_id:{task_id}",
        )
        result = await self.eds_client.describe_tasks_async([task_id])
        return result

    def get_screenshot_sdk(self) -> str:
        logger.info(f"实例{self.instance_id}:获取截图")
        task_id = self.eds_client.create_screenshot(self.instance_id)
        logger.info(
            f"实例{self.instance_id}:截图任务创建成功，task_id:{task_id}",
        )
        result = self.eds_client.describe_tasks([task_id])
        return result

    # async def in_upload_file_and_sign_async(
    #     self,
    #     filepath: str,
    #     file_name: str,
    # ) -> str:
    #     return await self.oss_client.oss_upload_file_and_sign_async(
    #         filepath,
    #         file_name,
    #     )
    #
    # def in_upload_file_and_sign(
    #     self,
    #     filepath: str,
    #     file_name: str,
    # ) -> str:
    #     return self.oss_client.oss_upload_file_and_sign(
    #         filepath,
    #         file_name,
    #     )

    async def get_screenshot_async(self) -> str:
        local_file_name = f"{uuid.uuid4().hex}__screenshot.png"
        mobile_screen_file_path = f"/sdcard/{local_file_name}"
        des_oss_sub_path = f"__mPLUG__/{self.instance_id}/{local_file_name}"
        print(
            f"mobile path: {mobile_screen_file_path} , "
            f"des_oss_sub_path: {des_oss_sub_path}",
        )
        logger.info(
            f"mobile path: {mobile_screen_file_path}"
            f"des_oss_sub_path: {des_oss_sub_path}",
        )
        retry = 3
        while retry > 0:
            try:
                logger.info(f"实例{self.instance_id}:获取截图")
                (
                    status,
                    output,
                ) = await self.eds_client.run_command_with_wait_async(
                    self.instance_id,
                    f"screencap {mobile_screen_file_path} "
                    f"&& md5sum {mobile_screen_file_path}",
                )
                logger.info(
                    f"实例{self.instance_id}:获取截图{status}{output},开始上传oss",
                )
                await self.eds_client.run_command_with_wait_async(
                    self.instance_id,
                    f"ossutil cp {mobile_screen_file_path} {self.des_oss_dir}"
                    f" -i {self.oss_ak} -k {self.oss_sk} -e {self.endpoint}",
                )

                screen_url = await self.oss_client.get_url_async(
                    des_oss_sub_path,
                )
                logger.info(
                    f"实例{self.instance_id}:获取截图成功{screen_url}" f",开始删除手机文件",
                )
                await self.eds_client.execute_command_async(
                    [self.instance_id],
                    f"rm {mobile_screen_file_path}",
                )
                if screen_url is None:
                    logger.error("screen_shot is None")
                    raise ScreenshotError("screen_shot is None")
                return screen_url
            except Exception as e:
                retry -= 1
                logger.error(
                    f"screen_shot error {e}" f", retrying: remain {retry}",
                )
                continue
        return ""

    def get_screenshot(self) -> str:
        local_file_name = f"{uuid.uuid4().hex}__screenshot.png"
        mobile_screen_file_path = f"/sdcard/{local_file_name}"
        des_oss_sub_path = f"__mPLUG__/{self.instance_id}/{local_file_name}"
        print(
            f"mobile path: {mobile_screen_file_path} , "
            f"des_oss_sub_path: {des_oss_sub_path}",
        )
        logger.info(
            f"mobile path: {mobile_screen_file_path}"
            f"des_oss_sub_path: {des_oss_sub_path}",
        )
        retry = 3
        while retry > 0:
            try:
                logger.info(f"实例{self.instance_id}:获取截图")
                status, output = self.eds_client.run_command_with_wait(
                    self.instance_id,
                    f"screencap {mobile_screen_file_path} "
                    f"&& md5sum {mobile_screen_file_path}",
                )
                logger.info(
                    f"实例{self.instance_id}:获取截图{status}{output},开始上传oss",
                )
                self.eds_client.run_command_with_wait(
                    self.instance_id,
                    f"ossutil cp {mobile_screen_file_path} {self.des_oss_dir}"
                    f" -i {self.oss_ak} -k {self.oss_sk} -e {self.endpoint}",
                )

                screen_url = self.oss_client.get_url(
                    des_oss_sub_path,
                )
                logger.info(
                    f"实例{self.instance_id}:获取截图成功{screen_url}" f",开始删除手机文件",
                )
                self.eds_client.execute_command(
                    [self.instance_id],
                    f"rm {mobile_screen_file_path}",
                )
                if screen_url is None:
                    logger.error("screen_shot is None")
                    raise ScreenshotError("Failed to get screenshot URL")
                return screen_url
            except Exception as e:
                retry -= 1
                logger.error(
                    f"screen_shot error {e}" f", retrying: remain {retry}",
                )
                continue
        return ""

    def tab(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        width: int,
        height: int,
    ) -> tuple[bool, str | None]:
        x, y = int((x1 + x2) / 2), int((y1 + y2) / 2)
        input_x = int(x / 1000 * width)
        input_y = int(y / 1000 * height)
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            f"input tap {input_x} {input_y}",
        )

    def long_press(
        self,
        x: int,
        y: int,
        press_time: str,
    ) -> tuple[bool, str | None]:
        time_ms = int(press_time) * 1000
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            f"input swipe {x} {y} {x} {y} {time_ms}",
        )

    def download_and_install_apk(
        self,
        oss_url: str,
        apk_name: str,
    ) -> tuple[bool, str]:
        """
        从OSS地址下载APK文件并安装

        Args:
            oss_url (str): APK文件的OSS下载地址
            apk_name (str): APK文件名

        Returns:
            tuple: (status, response) 安装状态和响应信息
        """
        # 下载APK文件到云手机
        download_path = f"/data/local/tmp/{apk_name}"
        # download_command = f"curl -o {download_path} {oss_url}"
        # 合并下载和安装命令，使用分号分隔
        combined_command = (
            f"curl -o {download_path} {oss_url} && pm install {download_path}"
        )

        try:
            status, rsp = self.eds_client.run_command_with_wait(
                self.instance_id,
                combined_command,
            )

            if not status:
                return False, f"下载或安装失败: {rsp or '未知错误'}"

            # 判断安装是否成功（检查输出中是否包含Success）
            if rsp and "Success" in rsp:
                return True, rsp
            else:
                return False, f"安装失败: {rsp or '未知错误'}"

        except Exception as e:
            return False, f"下载并安装APK时出错: {str(e)}"

    def check_and_setup_app(
        self,
        internal_oss_url: str,
        app_name: str,
    ) -> tuple[bool, str | None]:
        if internal_oss_url is None or app_name is None:
            return False, "param is empty"

        return self.eds_client.run_command_with_wait(
            internal_oss_url,
            app_name,
        )

    def type(self, text: str) -> str | None:
        time_start = time.time()
        # 转义文本内容
        escaped_text = text.replace('"', '\\"').replace("'", "\\'")

        # 组合完整命令：检查输入法 -> 安装ADBKeyboard(如需要) ->
        # 启用并设置ADBKeyboard -> 发送文本 -> 禁用ADBKeyboard
        # 注意：这里简化处理，假设ADBKeyboard已经安装
        combined_command = (
            f"ime enable com.android.adbkeyboard/.AdbIME && "
            f"ime set com.android.adbkeyboard/.AdbIME && "
            f"sleep 0.3 && "
            f'am broadcast -a ADB_INPUT_TEXT --es msg "{escaped_text}" && '
            f"sleep 0.2 && "
            f"ime disable com.android.adbkeyboard/.AdbIME"
        )

        status, rsp = self.eds_client.run_command_with_wait(
            self.instance_id,
            combined_command,
            slot_time=0.5,
        )
        print(f"{status}{rsp}")
        print(f"输入文字耗时：{time.time() - time_start}")
        return rsp

    def slide(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> tuple[bool, str | None]:
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            f"input swipe {x1} {y1} {x2} {y2} 500",
        )

    def back(self) -> tuple[bool, str | None]:
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            "input keyevent KEYCODE_BACK",
        )

    def home(self) -> tuple[bool, str | None]:
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            "am start -a android.intent.action.MAIN"
            " -c android.intent.category.HOME",
        )

    def menu(self) -> tuple[bool, str | None]:
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            "input keyevent 82",
        )

    def enter(self) -> tuple[bool, str | None]:
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            "input keyevent 66",
        )

    def kill_the_front_app(self) -> tuple[bool, str | None]:
        command = (
            "am force-stop $(dumpsys activity activities | "
            "grep mResumedActivity"
            " | awk '{print $4}' | cut -d "
            "'/' -f 1)"
        )
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            command,
        )

    def run_command(self, command: str) -> tuple[bool, str | None]:
        return self.eds_client.run_command_with_wait(
            self.instance_id,
            command,
        )

    async def tab_async(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        width: int,
        height: int,
    ) -> tuple[bool, str | None]:
        x, y = int((x1 + x2) / 2), int((y1 + y2) / 2)
        input_x = int(x / 1000 * width)
        input_y = int(y / 1000 * height)
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            f"input tap {input_x} {input_y}",
        )

    async def long_press_async(
        self,
        x: int,
        y: int,
        press_time: str,
    ) -> tuple[bool, str | None]:
        time_ms = int(press_time) * 1000
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            f"input swipe {x} {y} {x} {y} {time_ms}",
        )

    async def download_and_install_apk_async(
        self,
        oss_url: str,
        apk_name: str,
    ) -> tuple[bool, str]:
        """
        从OSS地址下载APK文件并安装

        Args:
            oss_url (str): APK文件的OSS下载地址
            apk_name (str): APK文件名

        Returns:
            tuple: (status, response) 安装状态和响应信息
        """
        # 下载APK文件到云手机
        download_path = f"/data/local/tmp/{apk_name}"
        # download_command = f"curl -o {download_path} {oss_url}"
        # 合并下载和安装命令，使用分号分隔
        combined_command = (
            f"curl -o {download_path} {oss_url} && pm install {download_path}"
        )

        try:
            status, rsp = await self.eds_client.run_command_with_wait_async(
                self.instance_id,
                combined_command,
            )

            if not status:
                return False, f"下载或安装失败: {rsp or '未知错误'}"

            # 判断安装是否成功（检查输出中是否包含Success）
            if rsp and "Success" in rsp:
                return True, rsp
            else:
                return False, f"安装失败: {rsp or '未知错误'}"

        except Exception as e:
            return False, f"下载并安装APK时出错: {str(e)}"

    async def check_and_setup_app_async(
        self,
        internal_oss_url: str,
        app_name: str,
    ) -> tuple[bool, str | None]:
        if internal_oss_url is None or app_name is None:
            return False, "param is empty"

        status_in, rsp_in = await self.download_and_install_apk_async(
            internal_oss_url,
            app_name,
        )

        # 返回原来的输入法ID，以便后续恢复
        return status_in, rsp_in

    async def type_async(self, text: str) -> str | None:
        time_start = time.time()
        # 转义文本内容
        escaped_text = text.replace('"', '\\"').replace("'", "\\'")

        # 组合完整命令：检查输入法 -> 安装ADBKeyboard(如需要) ->
        # 启用并设置ADBKeyboard -> 发送文本 -> 禁用ADBKeyboard
        # 注意：这里简化处理，假设ADBKeyboard已经安装
        combined_command = (
            f"ime enable com.android.adbkeyboard/.AdbIME && "
            f"ime set com.android.adbkeyboard/.AdbIME && "
            f"sleep 0.3 && "
            f'am broadcast -a ADB_INPUT_TEXT --es msg "{escaped_text}" && '
            f"sleep 0.2 && "
            f"ime disable com.android.adbkeyboard/.AdbIME"
        )

        status, rsp = await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            combined_command,
            slot_time=0.5,
        )
        print(f"{status}{rsp}")
        print(f"输入文字耗时：{time.time() - time_start}")
        return rsp

    async def slide_async(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            f"input swipe {x1} {y1} {x2} {y2} 500",
        )

    async def back_async(self) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            "input keyevent KEYCODE_BACK",
        )

    async def home_async(self) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            "am start -a android.intent.action.MAIN"
            " -c android.intent.category.HOME",
        )

    async def menu_async(self) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            "input keyevent 82",
        )

    async def enter_async(self) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            "input keyevent 66",
        )

    async def kill_the_front_app_async(self) -> tuple[bool, str | None]:
        command = (
            "am force-stop $(dumpsys activity activities | "
            "grep mResumedActivity"
            " | awk '{print $4}' | cut -d "
            "'/' -f 1)"
        )
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            command,
        )

    async def run_command_async(self, command: str) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            command,
        )

    def send_file(self, source_file_path: str, upload_url: str) -> int:
        return self.eds_client.send_file(
            [self.instance_id],
            source_file_path,
            upload_url,
        )

    async def send_file_async(
        self,
        source_file_path: str,
        upload_url: str,
    ) -> int:
        return await self.eds_client.send_file_async(
            [self.instance_id],
            source_file_path,
            upload_url,
        )

    def fetch_file(
        self,
        source_file_path: str,
        upload_endpoint: str,
        upload_url: str,
    ) -> int:
        return self.eds_client.fetch_file(
            [self.instance_id],
            source_file_path,
            upload_endpoint,
            upload_url,
        )

    async def fetch_file_async(
        self,
        source_file_path: str,
        upload_endpoint: str,
        upload_url: str,
    ) -> int:
        return await self.eds_client.fetch_file_async(
            [self.instance_id],
            source_file_path,
            upload_endpoint,
            upload_url,
        )

    def remove_file(self, file_path: str) -> tuple[bool, str | None]:
        # 使用 rm 命令删除文件，-r 递归删除目录，-f 强制删除
        command = f"rm -rf '{file_path}'"

        return self.eds_client.run_command_with_wait(
            self.instance_id,
            command,
        )

    async def remove_file_async(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        # 使用 rm 命令删除文件，-r 递归删除目录，-f 强制删除
        command = f"rm -rf '{file_path}'"

        return await self.eds_client.run_command_with_wait_async(
            self.instance_id,
            command,
        )
