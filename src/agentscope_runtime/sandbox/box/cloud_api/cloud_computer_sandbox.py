# -*- coding: utf-8 -*-
import os
import uuid
import logging
import time
from typing import Callable, List, Any, Optional, Dict
from fastapi import HTTPException
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.sandbox.registry import SandboxRegistry
from .client.cloud_computer_wy import ClientPool
from ..cloud.cloud_sandbox import CloudSandbox


logger = logging.getLogger(__name__)


@SandboxRegistry.register(
    "aliyun-cloud-computer",
    sandbox_type=SandboxType.CLOUD_COMPUTER,
    security_level="high",
    timeout=600,
    description="Alibaba Cloud Wuying Cloud Computer Sandbox",
)
class CloudComputerSandbox(CloudSandbox):
    def __init__(
        self,
        *,
        desktop_id: Optional[str] = None,
        timeout: int = 600,
        sandbox_type: SandboxType = SandboxType.CLOUD_COMPUTER,
        auto_wakeup: bool = True,
        screenshot_dir: Optional[str] = None,
        command_timeout: int = 60,
        **kwargs,
    ) -> None:
        resolved_desktop_id = desktop_id or os.environ.get("DESKTOP_ID")

        if not resolved_desktop_id:
            raise ValueError(
                "desktop_id is required. Provide desktop_id, sandbox_id,"
                " or set DESKTOP_ID.",
            )

        self.desktop_id = resolved_desktop_id
        self.auto_wakeup = auto_wakeup
        if screenshot_dir:
            self.screenshot_dir = screenshot_dir
        elif os.environ.get("CLOUD_COMPUTER_SCREENSHOT_DIR"):
            self.screenshot_dir = os.environ.get(
                "CLOUD_COMPUTER_SCREENSHOT_DIR",
            )
        else:
            # 获取当前文件所在目录，并在其下创建 screenshots 子目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.screenshot_dir = os.path.join(
                current_dir,
                "cloud_computer_screenshots",
            )

        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.command_timeout = command_timeout

        kwargs.pop("desktop_id", None)

        super().__init__(
            timeout=timeout,
            sandbox_type=sandbox_type,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # CloudSandbox abstract implementations
    # ------------------------------------------------------------------
    def _initialize_cloud_client(self):  # type: ignore[override]
        self._client_pool = ClientPool()
        instance_manager = self._client_pool.get_instance_manager(
            self.desktop_id,
        )
        if instance_manager is None:
            raise RuntimeError(
                "Failed to acquire EcdInstanceManager for cloud computer",
            )

        self.instance_manager = instance_manager
        self.oss_client = self._client_pool.get_oss_client()
        return instance_manager

    def _create_cloud_sandbox(self) -> Optional[str]:
        try:
            if self.auto_wakeup:
                try:
                    ready_status = self._wait_for_pc_ready(
                        self.desktop_id,
                        stability_check_duration=2,
                    )
                    if not ready_status:
                        logger.warning(
                            "Wakeup desktop returned non-success "
                            "status %s for %s",
                            ready_status,
                            self.desktop_id,
                        )
                except Exception as wake_error:
                    logger.warning(
                        f"Wakeup desktop failed: {wake_error}",
                    )

            self.instance_manager.refresh_aurh_code()
            return self.desktop_id
        except Exception as error:
            logger.error(
                f"Error preparing cloud computer sandbox: {error}",
            )
            return None

    def _delete_cloud_sandbox(self, sandbox_id: str) -> bool:
        try:
            status = self.instance_manager.ecd_client.hibernate_desktops(
                [sandbox_id],
            )
            return status == 200
        except Exception as error:  # pylint: disable=broad-except
            logger.error(
                "Failed to hibernate desktop %s: %s",
                sandbox_id,
                error,
            )
            return False

    def _call_cloud_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        tool_mapping: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "run_shell_command": self._tool_run_shell_command,
            "run_ipython_cell": self._tool_execute_code,
            "screenshot": self._tool_screenshot,
            "write_file": self._tool_write_file,
            "read_file": self._tool_read_file,
            "remove_file": self._tool_remove_file,
            "press_key": self._tool_press_key,
            "click": self._tool_click,
            "right_click": self._tool_right_click,
            "click_and_type": self._tool_click_and_type,
            "append_text": self._tool_append_text,
            "launch_app": self._tool_launch_app,
            "go_home": self._tool_go_home,
            "mouse_move": self._tool_mouse_move,
            "scroll": self._tool_scroll,
            "scroll_pos": self._tool_scroll_pos,
        }

        handler: Callable[[Dict[str, Any]], Dict[str, Any]] = tool_mapping.get(
            tool_name,
        )

        if handler is None:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not supported in "
                f"CloudComputerSandbox",
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
        return "Alibaba Cloud Wuying"

    def _wait_for_pc_ready(
        self,
        desktop_id: str,
        max_wait_time: int = 300,
        stability_check_duration: int = 10,
    ):
        """异步等待PC设备就绪，增加稳定性检查"""
        start_time = time.time()
        stable_start_time = None
        ready_status = False
        while True:
            try:
                # 将同步的状态检查操作放到线程池中执行
                pc_info = self.instance_manager.ecd_client.search_desktop_info(
                    [desktop_id],
                )

                if pc_info and pc_info[0].desktop_status.lower() == "running":
                    # 第一次检测到运行状态，开始稳定性检查
                    if stable_start_time is None:
                        stable_start_time = time.time()
                        print(
                            f"PC {desktop_id} status: running, "
                            "starting stability check...",
                        )

                    # 检查设备是否已稳定运行足够长时间
                    stable_duration = time.time() - stable_start_time
                    if stable_duration >= stability_check_duration:
                        print(
                            f"✓ PC {desktop_id} is stable and ready"
                            f" (stable for {stable_duration:.1f}s)",
                        )
                        ready_status = True
                        break
                    print(
                        f"PC {desktop_id} stability check: "
                        f"{stable_duration:.1f}"
                        f"s/{stability_check_duration}s",
                    )

                else:
                    # 状态不是运行中，重置稳定性检查
                    if stable_start_time is not None:
                        print(
                            f"PC {desktop_id} status changed, "
                            "resetting stability check",
                        )
                        stable_start_time = None
                    current_status = (
                        pc_info[0].desktop_status.lower()
                        if pc_info
                        else "unknown"
                    )
                    print(
                        f"PC {desktop_id} status: "
                        f"{current_status}, waiting...",
                    )
                    if current_status in ("stopped", "unknown"):
                        # 开机
                        print(f"Equipment restart for desktop_id {desktop_id}")
                        logger.info(
                            f"Equipment restart for desktop_id {desktop_id}",
                        )
                        e_client = self.instance_manager.ecd_client
                        method = e_client.start_desktops
                        status = method(
                            [desktop_id],
                        )
                        if status != 200:
                            raise HTTPException(
                                503,
                                "Failed to start computer resource",
                            )
                    elif current_status == "hibernated":
                        # 唤醒
                        print(f"Equipment wakeup for desktop_id {desktop_id}")
                        logger.info(
                            f"Equipment wakeup for desktop_id {desktop_id}",
                        )
                        e_client = self.instance_manager.ecd_client
                        method = e_client.wakeup_desktops
                        status = method(
                            [desktop_id],
                        )
                        if status != 200:
                            raise HTTPException(
                                503,
                                "Failed to start computer resource",
                            )

                # 检查是否超时
                if time.time() - start_time > max_wait_time:
                    raise TimeoutError(
                        f"PC {desktop_id} failed to become ready"
                        f" within {max_wait_time} seconds",
                    )

            except Exception as e:
                print(f"Error checking PC status for {desktop_id}: {e}")
                # 出现异常时重置稳定性检查
                stable_start_time = None

            time.sleep(3)  # 减少检查间隔，更精确的监控

        return ready_status

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------
    def _tool_run_shell_command(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        command = arguments.get("command")
        if not command:
            return {
                "success": False,
                "error": "'command' argument is required",
            }

        slot_time = arguments.get("slot_time")
        timeout = arguments.get("timeout", self.command_timeout)
        status, output = self.instance_manager.run_command_power_shell(
            command,
            slot_time,
            timeout,
        )
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_execute_code(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute Python code ."""
        code = arguments.get("code")
        if not code:
            return {"success": False, "error": "'code' argument is required"}

        slot_time = arguments.get("slot_time")
        timeout = arguments.get("timeout", self.command_timeout)
        status, output = self.instance_manager.run_code(
            code,
            slot_time,
            timeout,
        )
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_press_key(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        key = arguments.get("key")
        if not key:
            return {"success": False, "error": "'key' argument is required"}

        status, output = self.instance_manager.press_key(key)
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_click(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return {
                "success": False,
                "error": "'x' and 'y' arguments are required",
            }
        count = arguments.get("count", 1)

        status, output = self.instance_manager.tap(int(x), int(y), int(count))
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_right_click(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return {
                "success": False,
                "error": "'x' and 'y' arguments are required",
            }
        count = arguments.get("count", 1)

        status, output = self.instance_manager.right_tap(
            int(x),
            int(y),
            int(count),
        )
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_click_and_type(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        x = arguments.get("x")
        y = arguments.get("y")
        text = arguments.get("text", "")
        if x is None or y is None:
            return {
                "success": False,
                "error": "'x' and 'y' arguments are required",
            }

        status, output = self.instance_manager.tap_type_enter(
            int(x),
            int(y),
            str(text),
        )
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_append_text(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        x = arguments.get("x")
        y = arguments.get("y")
        text = arguments.get("text", "")
        if x is None or y is None:
            return {
                "success": False,
                "error": "'x' and 'y' arguments are required",
            }

        status, output = self.instance_manager.append(
            int(x),
            int(y),
            str(text),
        )
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_launch_app(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        app = arguments.get("app") or arguments.get("name")
        if not app:
            return {"success": False, "error": "'app' argument is required"}

        status, output = self.instance_manager.open_app(str(app))
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_go_home(self, _arguments: Dict[str, Any]) -> Dict[str, Any]:
        status, output = self.instance_manager.home()
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_mouse_move(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return {
                "success": False,
                "error": "'x' and 'y' arguments are required",
            }

        status, output = self.instance_manager.mouse_move(int(x), int(y))
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_scroll(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        pixels = int(arguments.get("pixels", 1))
        status, output = self.instance_manager.scroll(pixels)
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_scroll_pos(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        x = arguments.get("x")
        y = arguments.get("y")
        pixels = int(arguments.get("pixels", 1))
        if x is None or y is None:
            return {
                "success": False,
                "error": "'x' and 'y' arguments are required",
            }

        status, output = self.instance_manager.scroll_pos(
            int(x),
            int(y),
            pixels,
        )
        return {
            "success": bool(status),
            "output": output,
        }

    def _tool_screenshot(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        file_name = arguments.get("file_name", uuid.uuid4().hex)
        local_dir = arguments.get("local_dir", self.screenshot_dir)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, f"{file_name}.png")

        result = self.get_screenshot_oss_save_local(file_name, local_path)

        success = bool(result) and result != "Error"
        return {
            "success": success,
            "output": result if success else None,
            "error": result if hasattr(result, "error") else None,
        }

    # 在 tool handlers 部分添加以下新工具方法

    def _tool_write_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        file_path = arguments.get("file_path")
        content = arguments.get("content", "")
        encoding = arguments.get("encoding", "utf-8")

        if not file_path:
            return {
                "success": False,
                "error": "'file_path' argument is required",
            }

        try:
            status, output = self.instance_manager.write_file(
                file_path,
                content,
                encoding,
            )
            return {
                "success": bool(status),
                "output": output,
                "file_path": file_path,
            }
        except Exception as error:
            logger.error("Error writing file %s: %s", file_path, error)
            return {
                "success": False,
                "error": str(error),
                "file_path": file_path,
            }

    def _tool_read_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        file_path = arguments.get("file_path")
        encoding = arguments.get("encoding", "utf-8")

        if not file_path:
            return {
                "success": False,
                "error": "'file_path' argument is required",
            }

        try:
            status, output = self.instance_manager.read_file(
                file_path,
                encoding,
            )
            return {
                "success": bool(status),
                "output": output if status else None,
                "file_path": file_path,
            }
        except Exception as error:
            logger.error("Error reading file %s: %s", file_path, error)
            return {
                "success": False,
                "error": str(error),
                "file_path": file_path,
            }

    def _tool_remove_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
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
                "output": output,
                "file_path": file_path,
            }
        except Exception as error:
            logger.error("Error removing file %s: %s", file_path, error)
            return {
                "success": False,
                "error": str(error),
                "file_path": file_path,
            }

    # ------------------------------------------------------------------
    # Sandbox metadata APIs
    # ------------------------------------------------------------------
    def list_tools(self, tool_type: Optional[str] = None) -> Dict[str, Any]:
        command_tools = [
            "run_shell_command",
            "run_ipython_cell",
            "write_file",
            "read_file",
            "remove_file",
        ]
        input_tools = [
            "press_key",
            "click",
            "right_click",
            "click_and_type",
            "append_text",
            "mouse_move",
            "scroll",
            "scroll_pos",
        ]
        system_tools = [
            "screenshot",
            "go_home",
            "launch_app",
        ]

        tools_by_type = {
            "command": command_tools,
            "input": input_tools,
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

    def get_screenshot_base64_save_local(
        self,
        local_file_name: str,
        local_save_path: str,
        max_retry: int = 5,
    ) -> str:
        try:
            for _ in range(max_retry):
                screen_base64 = self.instance_manager.get_screenshot(
                    local_file_name,
                    local_save_path,
                )
                if screen_base64:
                    return screen_base64
            return "Error"  # 重试次数用完后返回错误
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Failed to screenshot_base64 desktop %s", error)
            return "Error"

    async def get_screenshot_base64_save_local_async(
        self,
        local_file_name: str,
        local_save_path: str,
        max_retry: int = 5,
    ) -> str:
        try:
            for _ in range(max_retry):
                screen_base64 = (
                    await self.instance_manager.get_screenshot_async(
                        local_file_name,
                        local_save_path,
                    )
                )
                if screen_base64:
                    return screen_base64
            return "Error"
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Failed to screenshot_base64 desktop %s", error)
            return "Error"

    def get_screenshot_oss_save_local(
        self,
        local_file_name: str,
        local_save_path: str,
        max_retry: int = 5,
    ) -> str:
        try:
            for _ in range(max_retry):
                screen_oss_url = self.instance_manager.get_screenshot_oss_url(
                    local_file_name,
                    local_save_path,
                )
                if screen_oss_url:
                    return screen_oss_url
            return "Error"
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Failed to screenshot_oss desktop %s", error)
            return "Error"

    async def get_screenshot_oss_save_local_async(
        self,
        local_file_name: str,
        local_save_path: str,
        max_retry: int = 5,
    ) -> str:
        try:
            for _ in range(max_retry):
                screen_oss_url = (
                    await self.instance_manager.get_screenshot_oss_url(
                        local_file_name,
                        local_save_path,
                    )
                )
                if screen_oss_url:
                    return screen_oss_url
            return "Error"
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Failed to screenshot_oss desktop %s", error)
            return "Error"

    def get_instance_manager(self, desktop_id: str) -> Any:
        retry = 3
        while retry > 0:
            try:
                # 使用ClientPool获取实例管理器，避免重复创建客户端连接
                client_pool = getattr(self, "_client_pool", ClientPool())
                manager = client_pool.get_instance_manager(desktop_id)
                manager.refresh_aurh_code()
                return manager
            except Exception as e:
                retry -= 1
                logger.warning(
                    f"get manager error, retrying: remain {retry}, {e}",
                )
                continue
        return None
