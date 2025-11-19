# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..base import Skill


from .base import (
    AP_RETURN_URL,
    AP_NOTIFY_URL,
    X_AGENT_CHANNEL,
    _create_alipay_client,
    AlipayTradeWapPayModel,
    AlipayTradeWapPayRequest,
    AlipayTradePagePayModel,
    AlipayTradePagePayRequest,
    AlipayTradeQueryModel,
    AlipayTradeQueryRequest,
    AlipayTradeQueryResponse,
    AlipayTradeRefundModel,
    AlipayTradeRefundRequest,
    AlipayTradeRefundResponse,
    AlipayTradeFastpayRefundQueryModel,
    AlipayTradeFastpayRefundQueryRequest,
    AlipayTradeFastpayRefundQueryResponse,
    AgentExtendParams,
)

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


class MobileAlipayPayment(Skill[MobilePaymentInput, PaymentOutput]):
    """
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
            # 创建支付宝客户端实例
            alipay_client = _create_alipay_client()

            # 创建手机网站支付模型并设置参数
            model = AlipayTradeWapPayModel()
            model.out_trade_no = args.out_trade_no  # 商户订单号
            model.total_amount = str(
                args.total_amount,
            )  # 支付金额（转换为字符串）
            model.subject = args.order_title  # 订单标题
            model.product_code = "QUICK_WAP_WAY"  # 产品码，固定值

            # 使用自定义的扩展参数类
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # 创建手机网站支付请求
            request = AlipayTradeWapPayRequest(biz_model=model)

            # 设置回调地址（如果配置了环境变量）
            if AP_RETURN_URL:
                request.return_url = AP_RETURN_URL
            if AP_NOTIFY_URL:
                request.notify_url = AP_NOTIFY_URL

            # 执行请求获取支付链接
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


class WebPageAlipayPayment(Skill[WebPagePaymentInput, PaymentOutput]):
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
            # 配置或SDK错误，直接抛出
            logger.error(f"网页支付配置或SDK错误: {str(e)}")
            raise
        except Exception as e:
            # 其他异常，包装后抛出
            error_msg = f"创建网页支付订单失败: {str(e)}"
            logger.error(f"网页支付执行异常: {error_msg}")
            raise RuntimeError(error_msg) from e


class AlipayPaymentQuery(Skill[PaymentQueryInput, PaymentOutput]):
    """
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
            # 创建支付宝客户端实例
            alipay_client = _create_alipay_client()

            # 创建交易查询模型并设置参数
            model = AlipayTradeQueryModel()
            model.out_trade_no = args.out_trade_no  # 商户订单号

            # 使用自定义的扩展参数类
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # 创建交易查询请求
            request = AlipayTradeQueryRequest(biz_model=model)

            # 执行查询请求
            response_content = alipay_client.execute(request)
            response = AlipayTradeQueryResponse()
            response.parse_response_content(response_content)

            # 处理响应结果
            if response.is_success():  # 查询成功
                result = (
                    f"交易状态: {response.trade_status}, "
                    f"交易金额: {response.total_amount}, "
                    f"支付宝交易号: {response.trade_no}"
                )
                return PaymentOutput(result=result)
            else:  # 查询失败
                return PaymentOutput(
                    result=f"交易查询失败. 错误信息: {response.msg}",
                )

        except (ValueError, ImportError) as e:
            # 配置或SDK错误，直接抛出
            logger.error(f"订单查询配置或SDK错误: {str(e)}")
            raise
        except Exception as e:
            # 其他异常，包装后抛出
            error_msg = f"查询订单失败: {str(e)}"
            logger.error(f"订单查询执行异常: {error_msg}")
            raise RuntimeError(error_msg) from e


class AlipayPaymentRefund(Skill[PaymentRefundInput, PaymentOutput]):
    """
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
            # 创建支付宝客户端
            alipay_client = _create_alipay_client()

            # 创建退款模型
            model = AlipayTradeRefundModel()
            model.out_trade_no = args.out_trade_no
            model.refund_amount = str(args.refund_amount)
            model.refund_reason = args.refund_reason
            model.out_request_no = out_request_no

            # 使用自定义的扩展参数类
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # 创建退款请求
            request = AlipayTradeRefundRequest(biz_model=model)

            # 执行请求
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
            logger.error(f"退款配置或SDK错误: {str(e)}")
            raise
        except Exception as e:
            error_msg = f"退款失败: {str(e)}"
            logger.error(f"退款执行异常: {error_msg}")
            raise RuntimeError(error_msg) from e


class AlipayRefundQuery(Skill[RefundQueryInput, PaymentOutput]):
    """
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
            # 创建支付宝客户端实例
            alipay_client = _create_alipay_client()

            # 创建快捷支付退款查询模型并设置参数
            model = AlipayTradeFastpayRefundQueryModel()
            model.out_trade_no = args.out_trade_no  # 商户订单号
            model.out_request_no = args.out_request_no  # 退款请求号

            # 使用自定义的扩展参数类
            extend_params = AgentExtendParams()
            extend_params.request_channel_source = X_AGENT_CHANNEL
            model.extend_params = extend_params

            # 创建快捷支付退款查询请求
            request = AlipayTradeFastpayRefundQueryRequest(biz_model=model)

            # 执行退款查询请求
            response_content = alipay_client.execute(request)
            response = AlipayTradeFastpayRefundQueryResponse()
            response.parse_response_content(response_content)

            # 处理响应结果
            if response.is_success():  # 查询成功
                if response.refund_status == "REFUND_SUCCESS":  # 退款成功
                    result = (
                        f"查询到退款成功, 退款交易: {response.trade_no}, "
                        f"退款金额: {response.refund_amount}, "
                        f"退款状态: {response.refund_status}"
                    )
                    return PaymentOutput(result=result)
                else:  # 退款未成功或其他状态
                    return PaymentOutput(
                        result=(
                            f"未查询到退款成功. " f"退款状态: {response.refund_status}"
                        ),
                    )
            else:  # 查询失败
                return PaymentOutput(
                    result=f"退款查询失败. 错误信息: {response.msg}",
                )

        except (ValueError, ImportError) as e:
            # 配置或SDK错误，直接抛出
            logger.error(f"退款查询配置或SDK错误: {str(e)}")
            raise
        except Exception as e:
            # 其他异常，包装后抛出
            error_msg = f"退款查询失败: {str(e)}"
            logger.error(f"退款查询执行异常: {error_msg}")
            raise RuntimeError(error_msg) from e
