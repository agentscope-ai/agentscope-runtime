# -*- coding: utf-8 -*-
# mypy: disable-error-code="no-redef"
# pylint:disable=unused-import, line-too-long

"""
Alipay Payment Base Module

This module provides unified import, configuration checking, and client
creation for the Alipay SDK. All Alipay-related components should use the
foundational functionality provided by this module.

---
支付宝支付基础模块

该模块提供支付宝SDK的统一导入、配置检查和客户端创建功能。
所有支付宝相关的组件都应该使用此模块提供的基础功能。
"""


import os
import logging
from typing import Optional, Any, Type, Dict

from dotenv import load_dotenv
from ..utils.crypto_utils import ensure_pkcs1_format

try:
    from alipay.aop.api.DefaultAlipayClient import (
        DefaultAlipayClient,
    )
    from alipay.aop.api.AlipayClientConfig import (
        AlipayClientConfig,
    )
    from alipay.aop.api.domain.ExtendParams import (
        ExtendParams,
    )

    ALIPAY_SDK_AVAILABLE = True
except ImportError:
    ALIPAY_SDK_AVAILABLE = False
    DefaultAlipayClient: Optional[Type[Any]] = None
    AlipayClientConfig: Optional[Type[Any]] = None
    ExtendParams: Optional[Type[Any]] = None

logger = logging.getLogger(__name__)

load_dotenv()


# Alipay environment configuration - controls whether to use production or
# sandbox environment
AP_CURRENT_ENV = os.getenv("AP_CURRENT_ENV", "production")

# Application ID (APPID) applied by the merchant on the Alipay open platform.
ALIPAY_APP_ID = os.getenv("ALIPAY_APP_ID", "")
# Merchant's private key applied via Alipay open platform.
ALIPAY_PRIVATE_KEY = os.getenv("ALIPAY_PRIVATE_KEY", "")
# Alipay public key used to verify server-side data signatures, obtained
# from the open platform. Required.
ALIPAY_PUBLIC_KEY = os.getenv("ALIPAY_PUBLIC_KEY", "")
# Synchronous return URL - page address to jump to after user completes
# payment. Optional.
AP_RETURN_URL = os.getenv("AP_RETURN_URL", "")
# Asynchronous notification URL - callback address for Alipay to notify
# payment results. Optional.
AP_NOTIFY_URL = os.getenv("AP_NOTIFY_URL", "")
# AI agent channel source - used to identify the source of AI agents
X_AGENT_CHANNEL = "bailian_adk_1.0.0"


# Unified Alipay SDK import and availability check


class AgentExtendParams(
    ExtendParams if ALIPAY_SDK_AVAILABLE else object,  # type: ignore[misc]
):
    """
    AI Agent Extended Parameters Class, inheriting from Alipay SDK's
    ExtendParams. Adds support for request_channel_source parameter to
    identify AI agent source.

    ---
    智能体扩展参数类，继承支付宝SDK的ExtendParams
    添加request_channel_source参数支持，用于标识AI智能体来源
    """

    def __init__(self) -> None:
        if ALIPAY_SDK_AVAILABLE:
            super().__init__()
        self._request_channel_source = None

    @property
    def request_channel_source(self) -> Optional[str]:
        return self._request_channel_source

    @request_channel_source.setter
    def request_channel_source(self, value: Optional[str]) -> None:
        self._request_channel_source = value

    def to_alipay_dict(self) -> Dict[str, Any]:
        """
        Override parent method to add request_channel_source to the
        serialized result.

        ---
        重写父类方法，添加request_channel_source到序列化结果中
        """
        if ALIPAY_SDK_AVAILABLE:
            params = super().to_alipay_dict()
        else:
            params = {}

        if self.request_channel_source:
            params["request_channel_source"] = self.request_channel_source
        return params

    @staticmethod
    def from_alipay_dict(
        d: Optional[Dict[str, Any]],
    ) -> Optional["AgentExtendParams"]:
        """
        Override parent static method to support deserialization of
        request_channel_source.

        ---
        重写父类静态方法，支持request_channel_source的反序列化
        """
        if not d:
            return None

        # Create instance
        agent_params = AgentExtendParams()

        # If SDK is available, let parent handle standard attributes first
        if ALIPAY_SDK_AVAILABLE:
            parent_obj = ExtendParams.from_alipay_dict(d)
            if parent_obj:
                # Copy attributes from parent object
                agent_params.__dict__.update(parent_obj.__dict__)

        # Handle custom attributes
        if "request_channel_source" in d:
            agent_params.request_channel_source = d["request_channel_source"]

        return agent_params


def get_alipay_gateway_url() -> str:
    """
    Get Alipay gateway URL based on environment variables.

    Returns:
        str: Alipay gateway URL for the corresponding environment
            - Sandbox: https://openapi-sandbox.dl.alipaydev.com/gateway.do
            - Production: https://openapi.alipay.com/gateway.do

    ---
    根据环境变量获取支付宝网关地址

    Returns:
        str: 对应环境的支付宝网关地址
            - 沙箱环境: https://openapi-sandbox.dl.alipaydev.com/gateway.do
            - 生产环境: https://openapi.alipay.com/gateway.do
    """
    return (
        "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
        if AP_CURRENT_ENV == "sandbox"
        else "https://openapi.alipay.com/gateway.do"
    )


def _check_config_and_sdk() -> None:
    """
    Check whether Alipay configuration and SDK are available.

    This function verifies:
    1. Required environment variables are set (ALIPAY_APP_ID,
        ALIPAY_PRIVATE_KEY, ALIPAY_PUBLIC_KEY)
    2. Alipay SDK is successfully imported

    Raises:
        ValueError: If required environment variables are not set.
        ImportError: If Alipay SDK is not installed or failed to import.

    ---
    检查支付宝配置和SDK是否可用

    该函数会验证以下内容：
    1. 检查必需的环境变量是否设置（ALIPAY_APP_ID、ALIPAY_PRIVATE_KEY、ALIPAY_PUBLIC_KEY）
    2. 检查支付宝SDK是否成功导入

    Raises:
        ValueError: 当必需的环境变量未设置时抛出
        ImportError: 当支付宝SDK未安装或导入失败时抛出
    """
    # Check required environment variables
    if not ALIPAY_APP_ID or not ALIPAY_PRIVATE_KEY or not ALIPAY_PUBLIC_KEY:
        raise ValueError(
            "Payment configuration error: Please set ALIPAY_APP_ID, "
            "ALIPAY_PRIVATE_KEY, and ALIPAY_PUBLIC_KEY environment variables.",
        )

    # Check whether Alipay official SDK is available
    if not ALIPAY_SDK_AVAILABLE:
        raise ImportError(
            "Please install the official Alipay SDK: pip install "
            "alipay-sdk-python",
        )


class AgentAlipayClient(DefaultAlipayClient):
    """
    AI Agent Alipay Client, inheriting from DefaultAlipayClient and
    overriding relevant methods.

    ---
    智能体支付宝客户端，继承DefaultAlipayClient并重写相关方法
    """

    def _DefaultAlipayClient__get_common_params(
        self,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Override the parent private method to add AI agent identifier
        parameter to common_params.

        Args:
            params: Request parameters

        Returns:
            dict: common_params containing AI agent identifier

        ---
        重写父类的私有方法，在common_params中添加AI智能体标识参数

        Args:
            params: 请求参数

        Returns:
            dict: 包含AI智能体标识的common_params
        """
        # Call the parent private method
        common_params = super()._DefaultAlipayClient__get_common_params(params)
        common_params["x_agent_source"] = X_AGENT_CHANNEL
        return common_params

    def _DefaultAlipayClient__remove_common_params(
        self,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Override the parent private method to retain our custom parameters.

        Args:
            params: Request parameter dictionary

        ---
        重写父类的私有方法，保留我们的自定义参数

        Args:
            params: 请求参数字典
        """
        if not params:
            return params

        # Import the COMMON_PARAM_KEYS constant from parent
        from alipay.aop.api.constant.ParamConstants import COMMON_PARAM_KEYS

        # Create a new constant set excluding our custom parameters
        keys_to_remove = COMMON_PARAM_KEYS.copy()
        keys_to_remove.discard("x_agent_source")

        for k in keys_to_remove:
            if k in params:
                params.pop(k)

        return params


def _create_alipay_client() -> Any:
    """
    Create an Alipay client instance.

    This function performs:
    1. Validates configuration and SDK availability
    2. Loads key configuration from environment variables
    3. Creates an Alipay client configuration object
    4. Initializes and returns an Alipay client instance

    Returns:
        Any: Configured Alipay client instance (DefaultAlipayClient)

    Raises:
        ValueError: If environment variable configuration is incorrect
        ImportError: If Alipay SDK is unavailable

    ---
    创建支付宝客户端实例

    该函数会执行以下操作：
    1. 验证配置和SDK可用性
    2. 读取环境变量中的密钥配置
    3. 创建支付宝客户端配置对象
    4. 初始化并返回支付宝客户端实例

    Returns:
        Any: 配置完成的支付宝客户端实例 (DefaultAlipayClient)

    Raises:
        ValueError: 当环境变量配置错误时
        ImportError: 当支付宝SDK不可用时
    """
    logger.info("Creating Alipay client instance...")
    logger.info(f"Current Alipay environment: {AP_CURRENT_ENV}")
    # Validate configuration and SDK availability
    _check_config_and_sdk()

    # Ensure private key is in PKCS#1 format for compatibility with
    # alipay-sdk-python
    private_key = ensure_pkcs1_format(ALIPAY_PRIVATE_KEY)
    public_key = ALIPAY_PUBLIC_KEY

    # Create Alipay client configuration object
    alipay_client_config = AlipayClientConfig()
    gateway_url = get_alipay_gateway_url()
    alipay_client_config.server_url = gateway_url
    alipay_client_config.app_id = ALIPAY_APP_ID  # App ID
    alipay_client_config.app_private_key = private_key  # App private key
    alipay_client_config.alipay_public_key = public_key  # Alipay public key
    alipay_client_config.sign_type = "RSA2"  # Signature algorithm type

    # Create and return Alipay client instance
    return AgentAlipayClient(alipay_client_config=alipay_client_config)
