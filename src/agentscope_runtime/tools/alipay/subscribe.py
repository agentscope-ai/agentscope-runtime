# -*- coding: utf-8 -*-
# pylint:disable=protected-access, line-too-long
# mypy: disable-error-code="no-redef"

import logging
import os
from typing import Any, Optional, Type

from pydantic import BaseModel, Field

from .base import (
    X_AGENT_CHANNEL,
    _create_alipay_client,
)
from ..base import Tool


try:
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
    AlipayAipaySubscribeStatusCheckRequest: Optional[Type[Any]] = None
    AlipayAipaySubscribePackageInitializeRequest: Optional[Type[Any]] = None
    AlipayAipaySubscribeTimesSaveRequest: Optional[Type[Any]] = None
    AlipayAipaySubscribeStatusCheckResponse: Optional[Type[Any]] = None
    AlipayAipaySubscribePackageInitializeResponse: Optional[Type[Any]] = None
    AlipayAipaySubscribeTimesSaveResponse: Optional[Type[Any]] = None


logger = logging.getLogger(__name__)

# Subscription plan ID - Set by developer in Alipay subscription management
SUBSCRIBE_PLAN_ID = os.getenv("SUBSCRIBE_PLAN_ID", "")
# AI agent name - Used to identify the AI agent
X_AGENT_NAME = os.getenv("X_AGENT_NAME", "")
# Subscription usage count - Number of uses deducted after service, default
# is 1 if not set
USE_TIMES = int(os.getenv("USE_TIMES", "1"))


class SubscribeStatusCheckInput(BaseModel):
    """subscribe status check input schema."""

    uuid: str = Field(
        ...,
        description="账户ID",
    )


class SubscribeStatusOutput(BaseModel):
    """subscribe status check output schema."""

    subscribe_flag: bool = Field(
        ...,
        description="是否订阅,已订阅为true,否则为false",
    )
    subscribe_package: Optional[str] = Field(
        None,
        description="订阅剩余套餐描述",
    )


class SubscribePackageInitializeInput(BaseModel):
    """subscribe package initialize input schema."""

    uuid: str = Field(
        ...,
        description="账户ID",
    )


class SubscribePackageInitializeOutput(BaseModel):
    """subscribe package initialize output schema."""

    subscribe_url: Optional[str] = Field(
        None,
        description="订阅链接",
    )


class SubscribeTimesSaveInput(BaseModel):
    """subscribe times save input schema."""

    uuid: str = Field(
        ...,
        description="账户ID",
    )
    out_request_no: str = Field(
        ...,
        description="外部订单号，用来计次幂等,防止重复扣减订阅次数",
    )


class SubscribeTimesSaveOutput(BaseModel):
    """subscribe times save output schema."""

    success: bool = Field(
        ...,
        description="计次服务调用是否成功",
    )


class SubscribeCheckOrInitializeInput(BaseModel):
    """subscribe check or initialize input schema."""

    uuid: str = Field(
        ...,
        description="账户ID",
    )


class SubscribeCheckOrInitializeOutput(BaseModel):
    """subscribe check or initialize output schema."""

    subscribe_flag: bool = Field(
        ...,
        description="是否订阅,已订阅为true,否则为false",
    )
    subscribe_url: Optional[str] = Field(
        None,
        description="订阅链接，如果未订阅则返回链接",
    )


class AlipaySubscribeStatusCheck(
    Tool[SubscribeStatusCheckInput, SubscribeStatusOutput],
):
    """
    Alipay Subscription Status Check Component

    This component checks whether the user is an active subscriber and returns
    subscription details if valid. Information such as validity period,
    remaining times, etc.

    Features:
    - Query subscription status of an AI agent
    - Returns detailed membership package info

    Input type: SubscribeStatusCheckInput
    Output type: SubscribeStatusOutput

    Usage scenarios:
    - AI Agent subscription payment scenario

    ---
    支付宝订阅状态检查组件

    功能：
    - 判断用户是否为有效会员
    - 返回有效会员的版本信息
    - 包括有效期、剩余次数等

    主要特点：
    - 智能体订阅状态查询

    输入参数类型: SubscribeStatusCheckInput
    输出参数类型: SubscribeStatusOutput

    使用场景：
    智能体订阅付费场景

    """

    name: str = "query-alipay-subscription-status"
    description: str = "查询用户订阅状态及套餐详情"

    async def _arun(
        self,
        args: SubscribeStatusCheckInput,
        **kwargs: Any,
    ) -> SubscribeStatusOutput:
        """Check subscription status."""
        try:
            if not SUBSCRIBE_PLAN_ID:
                raise ValueError(
                    "Subscription configuration error: Please set the "
                    "SUBSCRIBE_PLAN_ID environment variable",
                )
            # Create Alipay client instance
            alipay_client = _create_alipay_client()

            # Create subscription status check request
            request = AlipayAipaySubscribeStatusCheckRequest()
            biz_content = {
                "uuid": args.uuid,
                "plan_id": SUBSCRIBE_PLAN_ID,
                "channel": X_AGENT_CHANNEL,
            }
            request.biz_content = biz_content
            response_content = alipay_client.execute(request)
            response = AlipayAipaySubscribeStatusCheckResponse()
            response.parse_response_content(response_content)
            if response.is_success:
                is_subscribed = response.data.member_status == "VALID"
                subscribe_package_desc = None

                if is_subscribed and hasattr(
                    response.data,
                    "subscribe_member_info_d_t_o",
                ):
                    info = response.data.subscribe_member_info_d_t_o
                    package_type = info.subscribe_package_type

                    if package_type == "byCount":
                        # Count-based subscription: subscribed X times,
                        # Y times remaining
                        total_times = info.subscribe_times
                        left_times = info.left_times
                        subscribe_package_desc = (
                            f"订阅{total_times}次，还剩{left_times}次"
                        )
                    elif package_type == "byTime":
                        # Time-based subscription: expires after expiration
                        # date
                        expired_date = info.expired_date
                        subscribe_package_desc = f"{expired_date}后过期"
                return SubscribeStatusOutput(
                    subscribe_flag=is_subscribed,
                    subscribe_package=subscribe_package_desc,
                )
            else:
                error_msg = (
                    f"Subscription check API returned an error: "
                    f"{response.sub_code or response.code} - "
                    f"{response.sub_msg or response.msg}"
                )
                logger.error(error_msg)
                return SubscribeStatusOutput(
                    subscribe_flag=False,
                    subscribe_package=None,
                )

        except ImportError:
            logger.error(
                "Please install the official Alipay SDK: pip install "
                "alipay-sdk-python",
            )
            return SubscribeStatusOutput(
                subscribe_flag=False,
                subscribe_package=None,
            )
        except Exception as e:
            logger.error(f"Failed to check subscription status: {str(e)}")
            return SubscribeStatusOutput(
                subscribe_flag=False,
                subscribe_package=None,
            )


class AlipaySubscribePackageInitialize(
    Tool[
        SubscribePackageInitializeInput,
        SubscribePackageInitializeOutput,
    ],
):
    """
    Alipay Subscription Package Initialize Component

    This component returns a purchase link for the subscription package
    along with pricing configuration info.

    Features:
    - AI Agent subscription initialization

    Input type: SubscribePackageInitializeInput
    Output type: SubscribePackageInitializeOutput

    Usage scenarios:
    - AI Agent subscription payment scenario

    ---
    支付宝订阅开通组件

    功能：
    - 返回订阅套餐的购买链接
    - 订阅计划的定价配置信息

    主要特点：
    - 智能体订阅开通

    输入参数类型: SubscribePackageInitializeInput
    输出参数类型: SubscribePackageInitializeOutput

    使用场景：
    智能体订阅付费场景

    """

    name: str = "initialize-alipay-subscription-order"
    description: str = "用户发起订阅付费，返回订阅链接"

    async def _arun(
        self,
        args: SubscribePackageInitializeInput,
        **kwargs: Any,
    ) -> SubscribePackageInitializeOutput:
        """Initialize subscription package."""
        try:
            if not SUBSCRIBE_PLAN_ID or not X_AGENT_NAME:
                raise ValueError(
                    "Subscription config error: set SUBSCRIBE_PLAN_ID and "
                    "X_AGENT_NAME env variables.",
                )
            # Create Alipay client instance
            alipay_client = _create_alipay_client()

            # Create subscription initialize request
            request = AlipayAipaySubscribePackageInitializeRequest()
            biz_content = {
                "uuid": args.uuid,
                "plan_id": SUBSCRIBE_PLAN_ID,
                "channel": X_AGENT_CHANNEL,
                "agent_name": X_AGENT_NAME,
            }
            request.biz_content = biz_content
            response_content = alipay_client.execute(request)
            response = AlipayAipaySubscribePackageInitializeResponse()
            response.parse_response_content(response_content)
            if response.is_success:
                return SubscribePackageInitializeOutput(
                    subscribe_url=response.data.subscribe_url,
                )
            else:
                error_msg = (
                    f"Subscription init API error:: "
                    f"{response.sub_code or response.code} - "
                    f"{response.sub_msg or response.msg}"
                )
                logger.error(error_msg)
                return SubscribePackageInitializeOutput(subscribe_url=None)

        except ImportError:
            logger.error(
                "Alipay SDK not installed: pip install alipay-sdk-python",
            )
            return SubscribePackageInitializeOutput(subscribe_url=None)
        except Exception as e:
            logger.error(f"Subscription init failed: {str(e)}")
            return SubscribePackageInitializeOutput(subscribe_url=None)


class AlipaySubscribeTimesSave(
    Tool[
        SubscribeTimesSaveInput,
        SubscribeTimesSaveOutput,
    ],
):
    """
    Alipay Subscription Times Save Component

    This component records the usage count for count-based subscription
    billing models.

    Features:
    - AI Agent subscription usage count tracking

    Input type: SubscribeTimesSaveInput
    Output type: SubscribeTimesSaveOutput

    Usage scenarios:
    - Count-based subscription scenario

    ---
    支付宝订阅计次组件

    功能：
    - 针对按次付费的计费模式，记录会员用户消耗的使用次数。

    主要特点：
    - 智能体订阅计次

    输入参数类型: SubscribeTimesSaveInput
    输出参数类型: SubscribeTimesSaveOutput

    使用场景：
    智能体订阅计次场景

    """

    name: str = "times-alipay-subscription-consume"
    description: str = "用户使用服务后，记录用户使用消耗的次数"

    async def _arun(
        self,
        args: SubscribeTimesSaveInput,
        **kwargs: Any,
    ) -> SubscribeTimesSaveOutput:
        """Save subscription usage times."""
        try:
            if not SUBSCRIBE_PLAN_ID:
                raise ValueError(
                    "Subscription configuration error: Please set the "
                    "SUBSCRIBE_PLAN_ID environment variable",
                )
            # Create Alipay client instance
            alipay_client = _create_alipay_client()

            # Create subscription times save request
            request = AlipayAipaySubscribeTimesSaveRequest()
            biz_content = {
                "uuid": args.uuid,
                "plan_id": SUBSCRIBE_PLAN_ID,
                "use_times": USE_TIMES,
                "channel": X_AGENT_CHANNEL,
                "out_request_no": args.out_request_no,
            }
            request.biz_content = biz_content
            response_content = alipay_client.execute(request)
            response = AlipayAipaySubscribeTimesSaveResponse()
            response.parse_response_content(response_content)
            if response.is_success:
                return SubscribeTimesSaveOutput(
                    success=response.data.count_success,
                )
            else:
                error_msg = (
                    f"Times save API error:"
                    f"{response.sub_code or response.code} - "
                    f"{response.sub_msg or response.msg}"
                )
                logger.error(error_msg)
                return SubscribeTimesSaveOutput(success=False)

        except ImportError:
            logger.error(
                "Alipay SDK not installed: pip install alipay-sdk-python",
            )
            return SubscribeTimesSaveOutput(success=False)
        except Exception as e:
            logger.error(f"Subscription times save failed: {str(e)}")
            return SubscribeTimesSaveOutput(success=False)


class AlipaySubscribeCheckOrInitialize(
    Tool[
        SubscribeCheckOrInitializeInput,
        SubscribeCheckOrInitializeOutput,
    ],
):
    """
    Alipay Subscription Check or Initialize Component

    This component checks subscription status for count-based billing mode
    and initializes subscription if not already active.

    Features:
    - Verify user subscription status and return state if active
    - If not active, return subscription link

    Input type: SubscribeCheckOrInitializeInput
    Output type: SubscribeCheckOrInitializeOutput

    Usage scenarios:
    - Count-based subscription validation or initialization

    ---
    支付宝订阅检查或初始化组件

    功能：
    - 针对按次付费的计费模式，进行订阅状态检查或初始化。

    主要特点：
    - 提供校验用户状态能力，如果已订阅直接返回状态，如果未订阅返回相关链接

    输入参数类型: SubscribeCheckOrInitializeInput
    输出参数类型: SubscribeCheckOrInitializeOutput

    使用场景：
    智能体订阅检查或初始化场景

    """

    name: str = "alipay_subscribe_check_or_initialize"
    description: str = "检查用户订阅状态，如果已订阅则返回状态，如果未订阅则返回订阅链接"

    async def _arun(
        self,
        args: SubscribeCheckOrInitializeInput,
        **kwargs: Any,
    ) -> SubscribeCheckOrInitializeOutput:
        """Check subscription status or initialize if not subscribed."""
        try:
            if not SUBSCRIBE_PLAN_ID or not X_AGENT_NAME:
                raise ValueError(
                    "Subscription config error: set SUBSCRIBE_PLAN_ID and "
                    "X_AGENT_NAME env variables.",
                )
            # First, check subscription status
            status_check = AlipaySubscribeStatusCheck()
            status_input = SubscribeStatusCheckInput(
                uuid=args.uuid,
                plan_id=SUBSCRIBE_PLAN_ID,
                channel=X_AGENT_CHANNEL,
            )
            status_output = await status_check._arun(status_input)

            # If subscribed, return status
            if status_output.subscribe_flag:
                return SubscribeCheckOrInitializeOutput(
                    subscribe_flag=True,
                    subscribe_url=None,
                )

            # If not subscribed, initialize
            init_component = AlipaySubscribePackageInitialize()
            init_input = SubscribePackageInitializeInput(
                uuid=args.uuid,
                plan_id=SUBSCRIBE_PLAN_ID,
                channel=X_AGENT_CHANNEL,
                agent_name=X_AGENT_NAME,
            )
            init_result = await init_component._arun(init_input)

            return SubscribeCheckOrInitializeOutput(
                subscribe_flag=False,
                subscribe_url=init_result.subscribe_url,
            )

        except ImportError:
            logger.error(
                "Alipay SDK not installed: pip install alipay-sdk-python",
            )
            return SubscribeCheckOrInitializeOutput(
                subscribe_flag=False,
                subscribe_url=None,
            )
        except Exception as e:
            logger.error(f"Subscription check or init failed: {str(e)}")
            return SubscribeCheckOrInitializeOutput(
                subscribe_flag=False,
                subscribe_url=None,
            )
