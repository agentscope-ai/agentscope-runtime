# -*- coding: utf-8 -*-
# mypy: disable-error-code="no-redef"

import logging
from datetime import datetime
from typing import Any, Optional, Type

from pydantic import BaseModel, Field

from .base import (
    AP_RETURN_URL,
    AP_NOTIFY_URL,
    X_AGENT_CHANNEL,
    _create_alipay_client,
    AgentExtendParams,
)
from ..base import Tool

try:
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
    from alipay.aop.api.response.AlipayTradeQueryResponse import (
        AlipayTradeQueryResponse,
    )
    from alipay.aop.api.response.AlipayTradeRefundResponse import (
        AlipayTradeRefundResponse,
    )
    from alipay.aop.api.response.AlipayTradeFastpayRefundQueryResponse import (
        AlipayTradeFastpayRefundQueryResponse,
    )

    ALIPAY_SDK_AVAILABLE = True
except ImportError:
    ALIPAY_SDK_AVAILABLE = False
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


logger = logging.getLogger(__name__)


class MobilePaymentInput(BaseModel):
    """Mobile Alipay payment input schema."""

    out_trade_no: str = Field(
        ...,
        description="创建订单参数-商户订单号",
    )
    order_title: str = Field(
        ...,
        description="该订单的订单标题",
    )
    total_amount: float = Field(
        ...,
        gt=0,
        description="该订单的支付金额，以元为单位",
    )


class WebPagePaymentInput(BaseModel):
    """Web page Alipay payment input schema."""

    out_trade_no: str = Field(
        ...,
        description="创建订单参数-商户订单号",
    )
    order_title: str = Field(
        ...,
        description="该订单的订单标题",
    )
    total_amount: float = Field(
        ...,
        gt=0,
        description="该订单的支付金额，以元为单位",
    )


class PaymentQueryInput(BaseModel):
    """Payment query input schema."""

    out_trade_no: str = Field(
        ...,
        description="商户订单号",
    )


class PaymentRefundInput(BaseModel):
    """Payment refund input schema."""

    out_trade_no: str = Field(
        ...,
        description="商户订单号",
    )
    refund_amount: float = Field(
        ...,
        gt=0,
        description="退款金额",
    )
    refund_reason: Optional[str] = Field(
        default=None,
        description="退款原因",
    )
    out_request_no: Optional[str] = Field(
        default=None,
        description="退款请求号",
    )


class RefundQueryInput(BaseModel):
    """Refund query input schema."""

    out_trade_no: str = Field(
        ...,
        description="商户订单号",
    )
    out_request_no: str = Field(
        ...,
        description="退款请求号",
    )


class PaymentOutput(BaseModel):
    """Payment operation output schema."""

    result: str = Field(
        ...,
        description="包含链接的 markdown 文本，" "你要将文本插入对话内容中。",
    )


class MobileAlipayPayment(Tool[MobilePaymentInput, PaymentOutput]):
    """
    Mobile Alipay Payment Component

    This component is used to create Alipay payment orders suitable for
    mobile clients. The generated payment link can be opened in a mobile
    browser to redirect users to the Alipay application for payment or
    complete payment directly in the browser.

    Key features:
    - Suitable for mobile websites and mobile applications
    - Supports in-app payment and in-browser payment via Alipay
    - Uses the QUICK_WAP_WAY product code
    - Returns a ready-to-use payment link

    Input type: MobilePaymentInput
    Output type: PaymentOutput

    Usage scenarios:
    - Mobile website payment
    - Embedded mobile App payment

    ---
    手机端支付宝支付组件

    该组件用于创建适合手机端的支付宝支付订单。生成的支付链接可以在手机浏览器中打开，
    用户可以跳转到支付宝应用完成支付，或者直接在浏览器中进行支付操作。

    主要特点：
    - 适用于移动网站和移动应用
    - 支持支付宝应用内支付和浏览器内支付
    - 使用QUICK_WAP_WAY产品码
    - 返回可直接使用的支付链接

    输入参数类型：MobilePaymentInput
    输出参数类型：PaymentOutput

    使用场景：
    - 移动端网站支付
    - 手机App内嵌支付
    """

    name: str = "alipay_mobile_payment"
    description: str = (
        "创建一笔支付宝订单，返回带有支付链接的 Markdown 文本，"
        "该链接在手机浏览器中打开后可跳转到支付宝或直接在浏览器中支付。"
        "本工具适用于移动网站或移动 App。"
    )

    async def _arun(
        self,
        args: MobilePaymentInput,
        **kwargs: Any,
    ) -> PaymentOutput:
        """
        Create a mobile Alipay payment order.

        This method is used to create an Alipay payment order suitable for
        mobile browsers. The generated payment link can be opened in a
        mobile browser, and the user can complete the payment either in the
        Alipay app or within the browser.

        Args:
            args (MobilePaymentInput): Object containing payment parameters
                - out_trade_no: Merchant order number
                - order_title: Order title
                - total_amount: Payment amount (in yuan)
            **kwargs: Additional keyword arguments

        Returns:
            PaymentOutput: Markdown text output containing the payment link

        Raises:
            ValueError: If configuration parameters are incorrect
            ImportError: If Alipay SDK is not available
            Exception: For any other error during order creation

        ---
        创建手机支付宝支付订单

        该方法用于创建适用于手机浏览器的支付宝支付订单。生成的支付链接可以在手机浏览器中
        打开，用户可以跳转到支付宝应用或直接在浏览器中完成支付。

        Args:
            args (MobilePaymentInput): 包含支付参数的输入对象
                - out_trade_no: 商户订单号
                - order_title: 订单标题
                - total_amount: 支付金额（元）
            **kwargs: 额外的关键字参数

        Returns:
            PaymentOutput: 包含支付链接的Markdown文本输出

        Raises:
            ValueError: 当配置参数错误时
            ImportError: 当支付宝SDK不可用时
            Exception: 当创建订单过程中发生其他错误时
        """
        try:
            # Create an Alipay client instance
            alipay_client = _create_alipay_client()

            # Create the mobile payment model and set parameters
            model = AlipayTradeWapPayModel()
            model.out_trade_no = args.out_trade_no  # Merchant order number
            model.total_amount = str(args.total_amount)  # Amount as string
            model.subject = args.order_title  # Order title
            model.product_code = "QUICK_WAP_WAY"  # Fixed product code

            # Use custom extend parameters
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # Create the mobile payment request
            request = AlipayTradeWapPayRequest(biz_model=model)

            # Set callback URL if configured
            if AP_RETURN_URL:
                request.return_url = AP_RETURN_URL
            if AP_NOTIFY_URL:
                request.notify_url = AP_NOTIFY_URL

            # Execute the request to get the payment link
            response = alipay_client.page_execute(request, http_method="GET")
            return PaymentOutput(
                result=f"支付链接: [点击完成支付]({response})",
            )

        except (ValueError, ImportError) as e:
            # 配置或SDK错误，直接抛出
            logger.error(f"移动支付配置或SDK错误: {str(e)}")
            raise
        except Exception as e:
            # 其他异常，包装后抛出
            error_msg = f"创建手机支付订单失败: {str(e)}"
            logger.error(f"移动支付执行异常: {error_msg}")
            raise RuntimeError(error_msg) from e


class WebPageAlipayPayment(Tool[WebPagePaymentInput, PaymentOutput]):
    """
    电脑网页端支付宝支付组件

    该组件用于创建适合电脑端浏览器的支付宝支付订单。生成的支付链接在电脑浏览器中
    打开后会展示支付二维码，用户可以使用支付宝App扫码完成支付。

    主要特点：
    - 适用于桌面端网站和电脑客户端
    - 支持二维码扫码支付
    - 使用FAST_INSTANT_TRADE_PAY产品码
    - 返回可直接使用的支付链接

    输入参数类型：WebPagePaymentInput
    输出参数类型：PaymentOutput

    使用场景：
    - 电脑端网站支付
    - 桌面应用内嵌支付
    - 需要二维码支付的场景
    """

    name: str = "alipay_webpage_payment"
    description: str = (
        "创建一笔支付宝订单，返回带有支付链接的 Markdown 文本，"
        "该链接在电脑浏览器中打开后会展示支付二维码，用户可扫码支付。"
        "本工具适用于桌面网站或电脑客户端。"
    )

    async def _arun(
        self,
        args: WebPagePaymentInput,
        **kwargs: Any,
    ) -> PaymentOutput:
        """
        创建网页版支付宝支付订单

        该方法用于创建适用于电脑浏览器的支付宝支付订单。生成的支付链接在电脑浏览器中
        打开后会展示二维码，用户可以使用支付宝扫码完成支付。

        Args:
            args (WebPagePaymentInput): 包含支付参数的输入对象
                - out_trade_no: 商户订单号
                - order_title: 订单标题
                - total_amount: 支付金额（元）
            **kwargs: 额外的关键字参数

        Returns:
            PaymentOutput: 包含支付链接的Markdown文本输出

        Raises:
            ValueError: 当配置参数错误时
            ImportError: 当支付宝SDK不可用时
            Exception: 当创建订单过程中发生其他错误时
        """
        try:
            # 创建支付宝客户端实例
            alipay_client = _create_alipay_client()

            # 创建电脑网站支付模型并设置参数
            model = AlipayTradePagePayModel()
            model.out_trade_no = args.out_trade_no  # 商户订单号
            model.total_amount = str(
                args.total_amount,
            )  # 支付金额（转换为字符串）
            model.subject = args.order_title  # 订单标题
            model.product_code = "FAST_INSTANT_TRADE_PAY"  # 产品码，固定值

            # 使用自定义的扩展参数类
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # 创建电脑网站支付请求
            request = AlipayTradePagePayRequest(biz_model=model)

            # 设置回调地址（如果配置了环境变量）
            if AP_RETURN_URL:
                request.return_url = AP_RETURN_URL
            if AP_NOTIFY_URL:
                request.notify_url = AP_NOTIFY_URL

            # 执行请求获取支付链接
            response = alipay_client.page_execute(request, http_method="GET")
            return PaymentOutput(
                result=f"网页支付链接: [点击完成支付]({response})",
            )

        except (ValueError, ImportError) as e:
            # Configuration or SDK error
            logger.error(
                f"Mobile payment configuration or SDK error: {str(e)}",
            )
            raise
        except Exception as e:
            # Wrap and raise other exceptions
            error_msg = f"Failed to create mobile payment order: {str(e)}"
            logger.error(f"Mobile payment execution exception: {error_msg}")
            raise RuntimeError(error_msg) from e


class AlipayPaymentQuery(Tool[PaymentQueryInput, PaymentOutput]):
    """
    Alipay Transaction Query Component

    This component is used to query the current status of an existing
    Alipay transaction order. It can obtain the payment status, transaction
    amount, Alipay transaction number, and other details.

    Key features:
    - Supports querying by merchant order number
    - Returns detailed transaction status information
    - Supports real-time queries
    - Includes error handling and logging

    Input type: PaymentQueryInput
    Output type: PaymentOutput

    Usage scenarios:
    - Query payment status of an order
    - Verify payment results
    - Synchronize order status
    - Confirm status after payment failure

    ---
    支付宝交易查询组件

    该组件用于查询已创建的支付宝交易订单的当前状态。可以获取订单的支付状态、
    交易金额、支付宝交易号等详细信息。

    主要特点：
    - 支持通过商户订单号查询
    - 返回详细的交易状态信息
    - 支持实时查询
    - 错误处理和日志记录

    输入参数类型：PaymentQueryInput
    输出参数类型：PaymentOutput

    使用场景：
    - 查询订单支付状态
    - 验证支付结果
    - 订单状态同步
    - 支付失败后的状态确认
    """

    name: str = "alipay_query_payment"
    description: str = "查询一笔支付宝订单，并返回带有订单信息的文本。"

    async def _arun(
        self,
        args: PaymentQueryInput,
        **kwargs: Any,
    ) -> PaymentOutput:
        """
        Query Alipay transaction order status.

        This method queries an existing Alipay order's current status,
        including payment status, amount, and Alipay transaction number.

        Args:
            args (PaymentQueryInput): Object containing query parameters
                - out_trade_no: Merchant order number
            **kwargs: Additional keyword arguments

        Returns:
            PaymentOutput: Text output containing query result information

        Raises:
            ValueError: If configuration parameters are incorrect
            ImportError: If Alipay SDK is unavailable
            Exception: For any other query errors

        ---
        查询支付宝交易订单状态

        该方法用于查询已创建的支付宝交易订单的当前状态，包括交易状态、金额、
        支付宝交易号等信息。

        Args:
            args (PaymentQueryInput): 包含查询参数的输入对象
                - out_trade_no: 商户订单号
            **kwargs: 额外的关键字参数

        Returns:
            PaymentOutput: 包含查询结果信息的文本输出

        Raises:
            ValueError: 当配置参数错误时
            ImportError: 当支付宝SDK不可用时
            Exception: 当查询过程中发生其他错误时
        """
        try:
            # Create an Alipay client instance
            alipay_client = _create_alipay_client()

            # Create transaction query model
            model = AlipayTradeQueryModel()
            model.out_trade_no = args.out_trade_no  # Merchant order number

            # Set custom extended parameters
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # Create transaction query request
            request = AlipayTradeQueryRequest(biz_model=model)

            # Execute query request
            response_content = alipay_client.execute(request)
            response = AlipayTradeQueryResponse()
            response.parse_response_content(response_content)

            # Handle response results
            if response.is_success():  # Query success
                result = (
                    f"交易状态: {response.trade_status}, "
                    f"交易金额: {response.total_amount}, "
                    f"支付宝交易号: {response.trade_no}"
                )
                return PaymentOutput(result=result)
            else:  # Query failed
                return PaymentOutput(
                    result=f"交易查询失败. 错误信息: {response.msg}",
                )

        except (ValueError, ImportError) as e:
            # Configuration or SDK error
            logger.error(f"Order query configuration or SDK error: {str(e)}")
            raise
        except Exception as e:
            # Other exceptions with wrapped error message
            error_msg = f"Order query failed: {str(e)}"
            logger.error(f"Order query execution exception: {error_msg}")
            raise RuntimeError(error_msg) from e


class AlipayPaymentRefund(Tool[PaymentRefundInput, PaymentOutput]):
    """
    Alipay Transaction Refund Component

    This component initiates a refund request for a successfully paid
    Alipay transaction. It supports full and partial refunds as well as
    custom refund reasons.

    Key features:
    - Supports full and partial refunds
    - Allows specifying refund reasons
    - Idempotent refund requests when repeated

    Input type: PaymentRefundInput
    Output type: PaymentOutput

    Usage scenarios:
    - Customer-initiated refund
    - Order cancellation refund
    - After-sales refund processing
    - System-initiated automatic refund

    ---
    支付宝交易退款组件

    该组件用于对已成功支付的订单发起退款申请。支持全额退款和部分退款，
    可以指定退款原因和退款请求号。

    主要特点：
    - 支持全额和部分退款
    - 支持自定义退款原因

    输入参数类型：PaymentRefundInput
    输出参数类型：PaymentOutput

    使用场景：
    - 用户申请退款
    - 订单取消退款
    - 售后处理
    - 系统自动退款
    """

    name: str = "alipay_refund_payment"
    description: str = "对交易发起退款，并返回退款状态和退款金额"

    async def _arun(
        self,
        args: PaymentRefundInput,
        **kwargs: Any,
    ) -> PaymentOutput:
        """
        Initiate a refund request for an Alipay transaction.

        This method initiates a refund request for an already paid Alipay
        order. It supports both partial and full refunds, allows specifying
        refund reason, and uses an idempotency key.

        Args:
            args (PaymentRefundInput): Object containing refund parameters
                - out_trade_no: Merchant order number
                - refund_amount: Refund amount (yuan)
                - refund_reason: Refund reason (optional)
                - out_request_no: Refund request number (optional;
                    generated if not provided)
            **kwargs: Additional keyword arguments

        Returns:
            PaymentOutput: Text output containing refund result

        Raises:
            ValueError: If configuration parameters are incorrect
            ImportError: If Alipay SDK is unavailable
            Exception: For any other refund errors

        ---
        对支付宝交易订单发起退款

        该方法用于对已成功支付的订单发起退款申请。支持部分退款和全额退款，
        可以指定退款原因和退款请求号。

        Args:
            args (PaymentRefundInput): 包含退款参数的输入对象
                - out_trade_no: 商户订单号
                - refund_amount: 退款金额（元）
                - refund_reason: 退款原因（可选）
                - out_request_no: 退款请求号（可选，不提供则自动生成）
            **kwargs: 额外的关键字参数

        Returns:
            PaymentOutput: 包含退款结果信息的文本输出

        Raises:
            ValueError: 当配置参数错误时
            ImportError: 当支付宝SDK不可用时
            Exception: 当退款过程中发生其他错误时
        """
        out_request_no = args.out_request_no
        if not out_request_no:
            timestamp = int(datetime.now().timestamp())
            out_request_no = f"{args.out_trade_no}_refund_{timestamp}"

        try:
            # Create an Alipay client instance
            alipay_client = _create_alipay_client()

            # Create refund model
            model = AlipayTradeRefundModel()
            model.out_trade_no = args.out_trade_no
            model.refund_amount = str(args.refund_amount)
            model.refund_reason = args.refund_reason
            model.out_request_no = out_request_no

            # Set custom extended parameters
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # Create refund request
            request = AlipayTradeRefundRequest(biz_model=model)

            # Execute refund request
            response_content = alipay_client.execute(request)
            response = AlipayTradeRefundResponse()
            response.parse_response_content(response_content)

            if response.is_success():
                if response.fund_change == "Y":
                    result = f"退款结果: 退款成功, 退款交易: {response.trade_no}"
                else:
                    result = f"退款结果: 重复请求退款幂等成功, " f"退款交易: {response.trade_no}"
                return PaymentOutput(result=result)
            else:
                return PaymentOutput(
                    result=f"退款执行失败. 错误信息: {response.msg}",
                )

        except (ValueError, ImportError) as e:
            # Configuration or SDK error
            logger.error(f"Refund configuration or SDK error: {str(e)}")
            raise
        except Exception as e:
            # Other exceptions with wrapped error message
            error_msg = f"Refund failed: {str(e)}"
            logger.error(f"Refund execution exception: {error_msg}")
            raise RuntimeError(error_msg) from e


class AlipayRefundQuery(Tool[RefundQueryInput, PaymentOutput]):
    """
    Alipay Refund Query Component

    This component queries the current status of a refund request that has
    been initiated. It can determine if the refund was successful, refund
    amount, and refund status.

    Key features:
    - Supports querying by merchant order number and refund request number
    - Returns detailed refund status information

    Input type: RefundQueryInput
    Output type: PaymentOutput

    Usage scenarios:
    - Query refund processing status
    - Verify refund results
    - Customer support inquiries

    ---
    支付宝退款查询组件

    该组件用于查询已发起的退款申请的当前状态。可以获取退款是否成功、
    退款金额、退款状态等详细信息。

    主要特点：
    - 支持通过商户订单号和退款请求号查询
    - 返回详细的退款状态信息

    输入参数类型：RefundQueryInput
    输出参数类型：PaymentOutput

    使用场景：
    - 查询退款处理状态
    - 验证退款结果
    - 客服查询退款情况
    """

    name: str = "alipay_query_refund"
    description: str = "查询一笔支付宝退款，并返回退款状态和退款金额"

    async def _arun(
        self,
        args: RefundQueryInput,
        **kwargs: Any,
    ) -> PaymentOutput:
        """
        Query Alipay refund status.

        This method queries the current status of a refund request,
        including whether it was successful, the refunded amount,
        and refund status code.

        Args:
            args (RefundQueryInput): Object containing query parameters
                - out_trade_no: Merchant order number
                - out_request_no: Refund request number
            **kwargs: Additional keyword arguments

        Returns:
            PaymentOutput: Text output containing refund status result

        Raises:
            ValueError: If configuration parameters are incorrect
            ImportError: If Alipay SDK is unavailable
            Exception: For any other query errors

        ---
        查询支付宝退款状态

        该方法用于查询已发起的退款申请的当前状态，包括退款是否成功、
        退款金额、退款状态等信息。

        Args:
            args (RefundQueryInput): 包含查询参数的输入对象
                - out_trade_no: 商户订单号
                - out_request_no: 退款请求号
            **kwargs: 额外的关键字参数

        Returns:
            PaymentOutput: 包含退款查询结果信息的文本输出

        Raises:
            ValueError: 当配置参数错误时
            ImportError: 当支付宝SDK不可用时
            Exception: 当查询过程中发生其他错误时
        """
        try:
            # Create an Alipay client instance
            alipay_client = _create_alipay_client()

            # Create fastpay refund query model
            model = AlipayTradeFastpayRefundQueryModel()
            model.out_trade_no = args.out_trade_no  # Merchant order number
            model.out_request_no = args.out_request_no  # Refund request number

            # Set custom extended parameters
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # Create refund query request
            request = AlipayTradeFastpayRefundQueryRequest(biz_model=model)

            # Execute refund query
            response_content = alipay_client.execute(request)
            response = AlipayTradeFastpayRefundQueryResponse()
            response.parse_response_content(response_content)

            # Process response
            if response.is_success():  # Query success
                if response.refund_status == "REFUND_SUCCESS":
                    # Refund succeeded
                    result = (
                        f"查询到退款成功, 退款交易: {response.trade_no}, "
                        f"退款金额: {response.refund_amount}, "
                        f"退款状态: {response.refund_status}"
                    )
                    return PaymentOutput(result=result)
                else:
                    # Refund not successful
                    return PaymentOutput(
                        result=(
                            f"未查询到退款成功. " f"退款状态: {response.refund_status}"
                        ),
                    )
            else:
                # Query failed
                return PaymentOutput(
                    result=f"退款查询失败. 错误信息: {response.msg}",
                )

        except (ValueError, ImportError) as e:
            # Configuration or SDK error
            logger.error(f"Refund query configuration or SDK error: {str(e)}")
            raise
        except Exception as e:
            # Other exceptions with wrapped error message
            error_msg = f"Refund query failed: {str(e)}"
            logger.error(f"Refund query execution exception: {error_msg}")
            raise RuntimeError(error_msg) from e
