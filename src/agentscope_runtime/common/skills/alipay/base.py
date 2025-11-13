# -*- coding: utf-8 -*-
# mypy: disable-error-code="no-redef"
# pylint:disable=unused-import, line-too-long

"""
支付宝支付基础模块

该模块提供支付宝SDK的统一导入、配置检查和客户端创建功能。
所有支付宝相关的组件都应该使用此模块提供的基础功能。
"""

import os
import logging
from typing import Optional, Any, Type, Dict

from dotenv import load_dotenv
from ..utils.crypto_utils import ensure_pkcs1_format

logger = logging.getLogger(__name__)

load_dotenv()


# 支付宝环境配置 - 控制使用生产环境还是沙箱环境
AP_CURRENT_ENV = os.getenv("AP_CURRENT_ENV", "production")

# 商户在支付宝开放平台申请的应用 ID（APPID）。
ALIPAY_APP_ID = os.getenv("ALIPAY_APP_ID", "")
# 商户在支付宝开放平台申请的密钥，申请链接见
ALIPAY_PRIVATE_KEY = os.getenv("ALIPAY_PRIVATE_KEY", "")
# 用于验证支付宝服务端数据签名的支付宝公钥，在开放平台获取。必需。
ALIPAY_PUBLIC_KEY = os.getenv("ALIPAY_PUBLIC_KEY", "")
# 同步返回地址 - 用户完成支付后跳转的页面地址。可选。
AP_RETURN_URL = os.getenv("AP_RETURN_URL", "")
# 异步通知地址 - 支付宝用来通知支付结果的回调地址。可选。
AP_NOTIFY_URL = os.getenv("AP_NOTIFY_URL", "")
# 智能体渠道来源 - 用于标识AI智能体来源
X_AGENT_CHANNEL = "bailian_adk_1.0.0"


# 统一的支付宝SDK导入和可用性检查
try:
    from alipay.aop.api.DefaultAlipayClient import (
        DefaultAlipayClient,
    )
    from alipay.aop.api.AlipayClientConfig import (
        AlipayClientConfig,
    )
    from alipay.aop.api.request.AlipayTradeWapPayRequest import (
        AlipayTradeWapPayRequest,
    )
    from alipay.aop.api.request.AlipayTradePagePayRequest import (
        AlipayTradePagePayRequest,
    )
    from alipay.aop.api.request.AlipayTradeQueryRequest import (
        AlipayTradeQueryRequest,
    )
    from alipay.aop.api.request.AlipayTradeRefundRequest import (
        AlipayTradeRefundRequest,
    )
    from alipay.aop.api.request.AlipayTradeFastpayRefundQueryRequest import (
        AlipayTradeFastpayRefundQueryRequest,
    )
    from alipay.aop.api.domain.AlipayTradePagePayModel import (
        AlipayTradePagePayModel,
    )
    from alipay.aop.api.domain.AlipayTradeWapPayModel import (
        AlipayTradeWapPayModel,
    )
    from alipay.aop.api.domain.AlipayTradeQueryModel import (
        AlipayTradeQueryModel,
    )
    from alipay.aop.api.domain.AlipayTradeRefundModel import (
        AlipayTradeRefundModel,
    )
    from alipay.aop.api.domain.AlipayTradeFastpayRefundQueryModel import (
        AlipayTradeFastpayRefundQueryModel,
    )
    from alipay.aop.api.domain.ExtendParams import (
        ExtendParams,
    )
    from alipay.aop.api.response.AlipayTradeQueryResponse import (
        AlipayTradeQueryResponse,
    )
    from alipay.aop.api.response.AlipayTradeRefundResponse import (
        AlipayTradeRefundResponse,
    )
    from alipay.aop.api.response.AlipayTradeFastpayRefundQueryResponse import (
        AlipayTradeFastpayRefundQueryResponse,
    )

    # 智能体订阅相关请求和返回
    from alipay.aop.api.request.AlipayAipaySubscribeStatusCheckRequest import (
        AlipayAipaySubscribeStatusCheckRequest,
    )
    from alipay.aop.api.request.AlipayAipaySubscribePackageInitializeRequest import (  # noqa: E501
        AlipayAipaySubscribePackageInitializeRequest,
    )
    from alipay.aop.api.request.AlipayAipaySubscribeTimesSaveRequest import (
        AlipayAipaySubscribeTimesSaveRequest,
    )
    from alipay.aop.api.response.AlipayAipaySubscribeStatusCheckResponse import (  # noqa: E501
        AlipayAipaySubscribeStatusCheckResponse,
    )
    from alipay.aop.api.response.AlipayAipaySubscribePackageInitializeResponse import (  # noqa: E501
        AlipayAipaySubscribePackageInitializeResponse,
    )
    from alipay.aop.api.response.AlipayAipaySubscribeTimesSaveResponse import (
        AlipayAipaySubscribeTimesSaveResponse,
    )

    ALIPAY_SDK_AVAILABLE = True
except ImportError:
    ALIPAY_SDK_AVAILABLE = False
    # 类型安全的占位符
    DefaultAlipayClient: Optional[Type[Any]] = None
    AlipayClientConfig: Optional[Type[Any]] = None
    AlipayTradeWapPayRequest: Optional[Type[Any]] = None
    AlipayTradePagePayRequest: Optional[Type[Any]] = None
    AlipayTradeQueryRequest: Optional[Type[Any]] = None
    AlipayTradeRefundRequest: Optional[Type[Any]] = None
    AlipayTradeFastpayRefundQueryRequest: Optional[Type[Any]] = None
    AlipayTradePagePayModel: Optional[Type[Any]] = None
    AlipayTradeWapPayModel: Optional[Type[Any]] = None
    AlipayTradeQueryModel: Optional[Type[Any]] = None
    AlipayTradeRefundModel: Optional[Type[Any]] = None
    AlipayTradeFastpayRefundQueryModel: Optional[Type[Any]] = None
    AlipayTradeQueryResponse: Optional[Type[Any]] = None
    AlipayTradeRefundResponse: Optional[Type[Any]] = None
    AlipayTradeFastpayRefundQueryResponse: Optional[Type[Any]] = None
    ExtendParams: Optional[Type[Any]] = None
    # 智能体订阅相关类型安全占位符
    AlipayAipaySubscribeStatusCheckRequest: Optional[Type[Any]] = None
    AlipayAipaySubscribePackageInitializeRequest: Optional[Type[Any]] = None
    AlipayAipaySubscribeTimesSaveRequest: Optional[Type[Any]] = None
    AlipayAipaySubscribeStatusCheckResponse: Optional[Type[Any]] = None
    AlipayAipaySubscribePackageInitializeResponse: Optional[Type[Any]] = None
    AlipayAipaySubscribeTimesSaveResponse: Optional[Type[Any]] = None


class AgentExtendParams(
    ExtendParams if ALIPAY_SDK_AVAILABLE else object,  # type: ignore[misc]
):
    """
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
        重写父类静态方法，支持request_channel_source的反序列化
        """
        if not d:
            return None

        # 创建我们的对象实例
        agent_params = AgentExtendParams()

        # 如果SDK可用，先用父类方法处理标准属性
        if ALIPAY_SDK_AVAILABLE:
            parent_obj = ExtendParams.from_alipay_dict(d)
            if parent_obj:
                # 动态复制父类的所有属性
                agent_params.__dict__.update(parent_obj.__dict__)

        # 处理我们的自定义属性
        if "request_channel_source" in d:
            agent_params.request_channel_source = d["request_channel_source"]

        return agent_params


def get_alipay_gateway_url() -> str:
    """
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
    检查支付宝配置和SDK是否可用

    该函数会验证以下内容：
    1. 检查必需的环境变量是否设置（ALIPAY_APP_ID、ALIPAY_PRIVATE_KEY、ALIPAY_PUBLIC_KEY）
    2. 检查支付宝SDK是否成功导入

    Raises:
        ValueError: 当必需的环境变量未设置时抛出
        ImportError: 当支付宝SDK未安装或导入失败时抛出
    """
    # 检查必需的环境变量配置
    if not ALIPAY_APP_ID or not ALIPAY_PRIVATE_KEY or not ALIPAY_PUBLIC_KEY:
        raise ValueError(
            "支付配置错误：请设置ALIPAY_APP_ID、ALIPAY_PRIVATE_KEY和ALIPAY_PUBLIC_KEY环境变量",
        )

    # 检查支付宝官方SDK是否可用
    if not ALIPAY_SDK_AVAILABLE:
        raise ImportError("请安装官方支付宝SDK: pip install alipay-sdk-python")


class AgentAlipayClient(DefaultAlipayClient):
    """
    智能体支付宝客户端，继承DefaultAlipayClient并重写相关方法
    """

    def _DefaultAlipayClient__get_common_params(
        self,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        重写父类的私有方法，在common_params中添加AI智能体标识参数

        Args:
            params: 请求参数

        Returns:
            dict: 包含AI智能体标识的common_params
        """
        # 调用父类的私有方法
        common_params = super()._DefaultAlipayClient__get_common_params(params)
        common_params["x_agent_source"] = X_AGENT_CHANNEL
        return common_params

    def _DefaultAlipayClient__remove_common_params(
        self,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        重写父类的私有方法，保留我们的自定义参数

        Args:
            params: 请求参数字典
        """
        if not params:
            return params

        # 导入父类的COMMON_PARAM_KEYS常量
        from alipay.aop.api.constant.ParamConstants import COMMON_PARAM_KEYS

        # 创建一个新的常量集合，排除我们的自定义参数
        keys_to_remove = COMMON_PARAM_KEYS.copy()
        keys_to_remove.discard("x_agent_source")

        for k in keys_to_remove:
            if k in params:
                params.pop(k)

        return params


def _create_alipay_client() -> Any:
    """
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
    logger.info("正在创建支付宝客户端")
    logger.info(f"当前支付宝环境: {AP_CURRENT_ENV}")
    # 验证配置和SDK可用性
    _check_config_and_sdk()

    # 确保私钥为 PKCS#1 格式以兼容 alipay-sdk-python
    private_key = ensure_pkcs1_format(ALIPAY_PRIVATE_KEY)
    public_key = ALIPAY_PUBLIC_KEY

    # 创建支付宝客户端配置对象
    alipay_client_config = AlipayClientConfig()
    gateway_url = get_alipay_gateway_url()
    alipay_client_config.server_url = gateway_url
    alipay_client_config.app_id = ALIPAY_APP_ID  # 应用ID
    alipay_client_config.app_private_key = private_key  # 应用私钥
    alipay_client_config.alipay_public_key = public_key  # 支付宝公钥
    alipay_client_config.sign_type = "RSA2"  # 签名算法类型

    # 创建并返回支付宝客户端实例
    return AgentAlipayClient(alipay_client_config=alipay_client_config)
