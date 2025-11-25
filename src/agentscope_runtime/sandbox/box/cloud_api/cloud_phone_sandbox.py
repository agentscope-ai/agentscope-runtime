# -*- coding: utf-8 -*-
import os
import asyncio
import logging
import time
from typing import Optional, Any, List, Dict
from typing import Callable
from fastapi import HTTPException
from agentscope_runtime.sandbox.registry import SandboxRegistry
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.sandbox.box.cloud.cloud_sandbox import CloudSandbox
from .client.cloud_phone_wy import ClientPool, EdsInstanceManager

logger = logging.getLogger(__name__)


@SandboxRegistry.register(
    "aliyun-cloud-phone",
    sandbox_type=SandboxType.CLOUD_PHONE,
    security_level="high",
    timeout=600,
    description="Alibaba Cloud EDS Cloud Phone Sandbox Environment",
)
class CloudPhoneSandbox(CloudSandbox):
    def __init__(
        self,
        *,
        instance_id: Optional[str] = None,
        timeout: int = 600,
        sandbox_type: SandboxType = SandboxType.CLOUD_PHONE,
        auto_start: bool = True,
        **kwargs,
    ) -> None:
        """
        Initialize the CloudPhone sandbox.

        Args:
            instance_id: Cloud phone instance ID (from environment
             or parameter)
            timeout: Timeout for operations in seconds
            sandbox_type: Type of sandbox (default: CLOUD_PHONE)
            auto_start: Whether to auto-start the instance if stopped
            **kwargs: Additional configuration
        """
        resolved_instance_id = instance_id or os.environ.get(
            "PHONE_INSTANCE_ID",
        )
        if not resolved_instance_id:
            raise ValueError(
                "instance_id is required. Provide instance_id.",
            )

        self.instance_id = resolved_instance_id
        self.auto_start = auto_start

        kwargs.pop("instance_id", None)

        super().__init__(
            timeout=timeout,
            sandbox_type=sandbox_type,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # CloudSandbox abstract implementations
    # ------------------------------------------------------------------
    def _initialize_cloud_client(self):  # type: ignore[override]
        """Initialize EDS client via shared client pool."""
        self._client_pool = ClientPool()
        instance_manager = self._client_pool.get_instance_manager(
            self.instance_id,
        )
        if instance_manager is None:
            raise RuntimeError(
                "Failed to acquire EdsInstanceManager for cloud phone",
            )

        self.instance_manager = instance_manager
        self.eds_client = self._client_pool.get_eds_client()
        self.oss_client = self._client_pool.get_oss_client()
        return self.eds_client

    def _create_cloud_sandbox(self) -> Optional[str]:
        """Ensure cloud phone instance is ready."""
        try:
            # Auto-start instance if needed
            if self.auto_start:
                try:
                    ready_status = self._wait_for_phone_ready(
                        self.instance_id,
                        stability_check_duration=2,
                    )
                    if not ready_status:
                        logger.warning(
                            "Wakeup desktop returned non-success"
                            " status %s for %s",
                            ready_status,
                            self.instance_id,
                        )
                except Exception as start_error:
                    logger.warning(
                        f"Start instance failed: {start_error}",
                    )
            self.instance_manager.refresh_ticket()
            return self.instance_id
        except Exception as error:
            logger.error(
                f"Error preparing cloud phone sandbox: {error}",
            )
            return None

    def _delete_cloud_sandbox(self, sandbox_id: str) -> bool:
        """Stop cloud phone instance (optional cleanup)."""
        try:
            # Note: We don't delete the instance, just stop it
            # The instance can be reused later
            status = self.eds_client.stop_equipment([sandbox_id])
            return status == 200
        except Exception as error:  # pylint: disable=broad-except
            logger.error(
                f"Failed to stop instance {sandbox_id}: {error}",
            )
            return False

    def _call_cloud_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """
        Call a tool in the cloud phone environment.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool

        Returns:
            Tool execution result
        """
        tool_mapping: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "run_shell_command": self._tool_run_shell_command,
            "screenshot": self._tool_screenshot,
            "send_file": self._tool_send_file,
            "remove_file": self._tool_remove_file,
            "click": self._tool_click,
            "type_text": self._tool_type_text,
            "slide": self._tool_slide,
            "go_home": self._tool_go_home,
            "back": self._tool_back,
            "menu": self._tool_menu,
            "enter": self._tool_enter,
            "kill_front_app": self._tool_kill_front_app,
        }

        handler: Callable[
            [Dict[str, Any]],
            Dict[str, Any],
        ] = tool_mapping.get(tool_name)

        if handler is None:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not supported in"
                f" CloudPhoneSandbox",
                "tool_name": tool_name,
            }

        try:
            return handler(arguments or {})
        except Exception as error:  # pylint: disable=broad-except
            logger.error(
                "Error executing tool %s: %s",
                tool_name,
                error,
            )
            return {
                "success": False,
                "error": str(error),
                "tool_name": tool_name,
                "arguments": arguments,
            }

    def _get_cloud_provider_name(self) -> str:  # type: ignore[override]
        """Get the name of the cloud provider."""
        return "Alibaba Cloud EDS"

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------
    def _tool_run_shell_command(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute ADB shell command in the cloud phone."""
        command = arguments.get("command")
        if not command:
            return {
                "success": False,
                "error": "'command' argument is required",
            }

        status, output = self.instance_manager.run_command(str(command))
        return {
            "success": bool(status),
            "output": output or "",
        }

    def _tool_click(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Click at coordinates in the cloud phone."""
        x1 = arguments.get("x1", 0)
        y1 = arguments.get("y1", 0)
        x2 = arguments.get("x2", 0)
        y2 = arguments.get("y2", 0)
        width = arguments.get("width", 0)
        height = arguments.get("height", 0)

        status, output = self.instance_manager.tab(
            int(x1),
            int(y1),
            int(x2),
            int(y2),
            int(width),
            int(height),
        )
        return {
            "success": bool(status),
            "output": output or "",
        }

    def _tool_type_text(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Type text in the cloud phone. need install ADBKeyboard"""
        text = arguments.get("text", "")
        if not text:
            return {"success": False, "error": "'text' argument is required"}

        output = self.instance_manager.type(str(text))
        return {
            "success": True,
            "output": output or "",
        }

    def _tool_slide(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Slide from one point to another."""
        x1 = arguments.get("x1")
        y1 = arguments.get("y1")
        x2 = arguments.get("x2")
        y2 = arguments.get("y2")
        if x1 is None or y1 is None or x2 is None or y2 is None:
            return {
                "success": False,
                "error": "'x1', 'y1', 'x2', 'y2' arguments are required",
            }

        status, output = self.instance_manager.slide(
            int(x1),
            int(y1),
            int(x2),
            int(y2),
        )
        return {
            "success": bool(status),
            "output": output or "",
        }

    def _tool_go_home(self, _arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Go to home screen."""
        status, output = self.instance_manager.home()
        return {
            "success": bool(status),
            "output": output or "",
        }

    def _tool_back(self, _arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Press back button."""
        status, output = self.instance_manager.back()
        return {
            "success": bool(status),
            "output": output or "",
        }

    def _tool_menu(self, _arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Press menu button."""
        status, output = self.instance_manager.menu()
        return {
            "success": bool(status),
            "output": output or "",
        }

    def _tool_enter(self, _arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Press enter button."""
        status, output = self.instance_manager.enter()
        return {
            "success": bool(status),
            "output": output or "",
        }

    def _tool_kill_front_app(
        self,
        _arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Kill the front app."""
        status, output = self.instance_manager.kill_the_front_app()
        return {
            "success": bool(status),
            "output": output or "",
        }

    def _tool_screenshot(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Take a screenshot."""
        max_retry = arguments.get("max_retry", 5)

        result = self.get_screenshot_oss_phone(max_retry)

        success = bool(result) and result != "Error"
        return {
            "success": success,
            "output": result if success else None,
            "error": result if hasattr(result, "error") else None,
        }

    def _tool_send_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Send file to the cloud phone."""
        # 云手机上的文件路径包括文件名
        source_file_path = arguments.get("source_file_path")
        # 文件公网下载地址
        upload_url = arguments.get("upload_url")

        if not source_file_path or not upload_url:
            return {
                "success": False,
                "error": "'source_file_path' and 'upload_url' "
                "arguments are required",
            }

        try:
            status_code = self.instance_manager.send_file(
                source_file_path,
                upload_url,
            )
            return {
                "success": status_code == 200,
                "status_code": status_code,
                "output": upload_url,
            }
        except Exception as error:
            logger.error("Error sending file: %s", error)
            return {
                "success": False,
                "error": str(error),
                "source_file_path": source_file_path,
                "upload_url": upload_url,
            }

    def _tool_remove_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Remove file from the cloud phone."""
        file_path = arguments.get("file_path")

        if not file_path:
            return {
                "success": False,
                "error": "'file_path' argument is required",
            }

        try:
            status, output = self.instance_manager.remove_file(file_path)
            return {
                "success": bool(status),
                "output": output or "",
            }
        except Exception as error:
            logger.error("Error removing file: %s", error)
            return {
                "success": False,
                "error": str(error),
                "file_path": file_path,
            }

    # ------------------------------------------------------------------
    # Sandbox metadata APIs
    # ------------------------------------------------------------------
    def list_tools(self, tool_type: Optional[str] = None) -> Dict[str, Any]:
        """
        List available tools in the cloud phone sandbox.

        Args:
            tool_type: Optional filter for tool type
            (e.g., "input", "navigation", "command", "system")

        Returns:
            Dictionary containing available tools organized by type
        """
        input_tools = [
            "click",
            "type_text",
            "slide",
        ]
        navigation_tools = [
            "go_home",
            "back",
            "menu",
            "enter",
        ]
        command_tools = [
            "run_shell_command",
            "kill_front_app",
        ]
        system_tools = [
            "screenshot",
            "send_file",
            "remove_file",
        ]

        tools_by_type = {
            "input": input_tools,
            "navigation": navigation_tools,
            "command": command_tools,
            "system": system_tools,
        }

        if tool_type:
            tools = tools_by_type.get(tool_type, [])
            return {
                "tools": tools,
                "tool_type": tool_type,
                "sandbox_id": self._sandbox_id,
                "total_count": len(tools),
            }

        all_tools: List[str] = []
        for group in tools_by_type.values():
            all_tools.extend(group)

        return {
            "tools": all_tools,
            "tools_by_type": tools_by_type,
            "tool_type": tool_type,
            "sandbox_id": self._sandbox_id,
            "total_count": len(all_tools),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _get_instance_manager_async(self, instance_id: str) -> Any:
        """Get or create instance manager for the cloud phone."""
        retry = 3
        while retry > 0:
            try:
                logger.info("开始初始化云手机实例，尝试调用次数%s", retry)
                manager = await asyncio.to_thread(
                    EdsInstanceManager,
                    instance_id,
                )
                return manager
            except Exception as e:  # pylint: disable=broad-except
                retry -= 1
                logger.error(
                    "get manager error, retrying: remain %s, %s",
                    retry,
                    e,
                )
                await asyncio.sleep(5)
                continue
        return None

    def _ensure_initialized(self) -> None:
        """Helper method to check if async initialization was called."""
        if (
            not hasattr(self, "instance_manager")
            or self.instance_manager is None
        ):
            raise RuntimeError(
                "CloudPhone not initialized. Call 'await cloud_phone."
                "initialize()' first.",
            )

    def _wait_for_phone_ready(
        self,
        instance_id: str,
        max_wait_time: int = 300,
        stability_check_duration: int = 4,
    ):
        """异步等待手机设备就绪"""
        start_time = time.time()
        stable_start_time = None
        while True:
            try:
                # 将同步的状态检查操作放到线程池中执行
                method = self.instance_manager.eds_client.list_instance
                total_count, next_token, devices_info = method(
                    instance_ids=[instance_id],
                )
                print(f"{total_count}{next_token}")
                if (
                    devices_info
                    and devices_info[0].android_instance_status.lower()
                    == "running"
                ):
                    # 第一次检测到运行状态，开始稳定性检查
                    if stable_start_time is None:
                        stable_start_time = time.time()
                        print(
                            f"Phone {instance_id} status: running, "
                            "starting stability check...",
                        )

                    # 检查设备是否已稳定运行足够长时间
                    stable_duration = time.time() - stable_start_time
                    if stable_duration >= stability_check_duration:
                        print(
                            f"✓ Phone {instance_id} is stable and ready"
                            f" (stable for {stable_duration:.1f}s)",
                        )
                        ready_status = True
                        break
                    print(
                        f"Phone {instance_id} stability check: "
                        f"{stable_duration:.1f}"
                        f"s/{stability_check_duration}s",
                    )

                else:
                    # 状态不是运行中，重置稳定性检查
                    if stable_start_time is not None:
                        print(
                            f"PHONE {instance_id} status changed, "
                            "resetting stability check",
                        )
                        stable_start_time = None
                    current_status = (
                        devices_info[0].android_instance_status.lower()
                        if devices_info
                        else "unknown"
                    )
                    print(
                        f"PHONE {instance_id} status: "
                        f"{current_status}, waiting...",
                    )
                    if current_status == "stopped":
                        # 开机
                        print(
                            f"Equipment restart for instance_id {instance_id}",
                        )
                        logger.info(
                            f"Equipment restart for instance_id {instance_id}",
                        )
                        e_client = self.instance_manager.eds_client
                        method = e_client.start_equipment
                        status = method(
                            [instance_id],
                        )
                        if status != 200:
                            raise HTTPException(
                                503,
                                "Failed to start computer resource",
                            )
                    else:
                        # 没查到设备状态，等待一会，重新查询
                        print(
                            f"Equipment for instance_id {instance_id} unknown,"
                            " and wait",
                        )
                        logger.info(
                            f"Equipment for instance_id {instance_id} unknown,"
                            " and wait",
                        )
                        time.sleep(2)

                # 检查是否超时
                if time.time() - start_time > max_wait_time:
                    raise TimeoutError(
                        f"Phone {instance_id} failed to become ready "
                        f"within {max_wait_time} seconds",
                    )

            except Exception as e:
                print(f"Error checking phone status for {instance_id}: {e}")

            time.sleep(5)
        return ready_status

    async def get_screenshot_oss_phone_async(
        self,
        max_retry: int = 5,
    ) -> str:
        self._ensure_initialized()
        for _ in range(max_retry):
            screen_url = await self.instance_manager.get_screenshot_sdk_async()
            return screen_url
        return "Error"

    def get_screenshot_oss_phone(
        self,
        max_retry: int = 5,
    ) -> str:
        self._ensure_initialized()
        for _ in range(max_retry):
            screen_url = self.instance_manager.get_screenshot_sdk()
            return screen_url
        return "Error"

    def get_instance_manager(self, instance_id: str) -> Any:
        """Get or create instance manager for the cloud phone."""
        retry = 3
        while retry > 0:
            try:
                # 使用ClientPool获取实例管理器，避免重复创建客户端连接
                client_pool = getattr(self, "_client_pool", ClientPool())
                manager = client_pool.get_instance_manager(instance_id)
                manager.refresh_ticket()
                return manager
            except Exception as e:  # pylint: disable=broad-except
                retry -= 1
                logger.warning(
                    f"get manager error, retrying: remain {retry}, {e}",
                )
                continue
        return None
