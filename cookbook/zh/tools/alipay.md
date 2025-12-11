# 支付宝组件 (Alipay)

本目录包含各种支付宝支付和订阅服务组件，提供完整的支付处理、订阅管理和交易查询功能。

## 📋 组件列表

### 1. 支付组件 (Payment Components)

#### MobileAlipayPayment - 手机端支付宝支付
适用于手机端浏览器的支付宝支付组件，支持手机App跳转和浏览器内支付。

**前置使用条件：**
- 有效的支付宝应用配置
- 支付宝商户账号和API密钥
- 移动端浏览器环境

**输入参数 (MobilePaymentInput)：**
- `out_trade_no` (str): 商户订单号
- `order_title` (str): 订单标题
- `total_amount` (float): 支付金额（元，必须大于0）

**输出参数 (PaymentOutput)：**
- `result` (str): 包含支付链接的Markdown文本

**主要特点：**
- 使用QUICK_WAP_WAY产品码
- 支持支付宝App跳转支付
- 支持浏览器内直接支付
- 返回可直接使用的支付链接

#### WebPageAlipayPayment - 电脑网页端支付宝支付
适用于电脑端浏览器的支付宝支付组件，提供二维码扫码支付功能。

**前置使用条件：**
- 有效的支付宝应用配置
- 支付宝商户账号和API密钥
- 桌面端浏览器环境

**输入参数 (WebPagePaymentInput)：**
- `out_trade_no` (str): 商户订单号
- `order_title` (str): 订单标题
- `total_amount` (float): 支付金额（元，必须大于0）

**输出参数 (PaymentOutput)：**
- `result` (str): 包含支付链接的Markdown文本

**主要特点：**
- 使用FAST_INSTANT_TRADE_PAY产品码
- 支持二维码扫码支付
- 适用于电脑端网站

### 2. 交易管理组件 (Transaction Management)

#### AlipayPaymentQuery - 支付交易查询
查询已创建的支付宝交易订单的当前状态和详细信息。

**输入参数 (PaymentQueryInput)：**
- `out_trade_no` (str): 商户订单号

**输出参数 (PaymentOutput)：**
- `result` (str): 包含交易状态、金额、支付宝交易号等信息的文本

**主要功能：**
- 获取交易详细信息
- 支持状态验证和同步

#### AlipayPaymentRefund - 支付交易退款
对已成功支付的交易发起退款申请，支持全额和部分退款。

**输入参数 (PaymentRefundInput)：**
- `out_trade_no` (str): 商户订单号
- `refund_amount` (float): 退款金额（必须大于0）
- `refund_reason` (str, 可选): 退款原因
- `out_request_no` (str, 可选): 标识一次退款请求，需要保证在交易号下唯一，如需部分退款，则此参数必传

**输出参数 (PaymentOutput)：**
- `result` (str): 包含退款结果信息的文本

**主要功能：**
- 支持全额和部分退款
- 退款幂等性保证

#### AlipayRefundQuery - 退款查询
查询已发起的退款申请的当前状态和处理结果。

**输入参数 (RefundQueryInput)：**
- `out_trade_no` (str): 商户订单号
- `out_request_no` (str): 退款请求号

**输出参数 (PaymentOutput)：**
- `result` (str): 包含退款状态和金额信息的文本

**主要功能：**
- 查询退款处理状态
- 获取退款详细信息
- 支持退款状态验证

### 3. 订阅服务组件 (Subscription Services)

#### AlipaySubscribeStatusCheck - 订阅状态检查
检查用户的智能体订阅状态，返回会员信息和套餐详情。

**输入参数 (SubscribeStatusCheckInput)：**
- `uuid` (str): 账户ID

**输出参数 (SubscribeStatusOutput)：**
- `subscribe_flag` (bool): 是否已订阅
- `subscribe_package` (str): 订阅套餐描述

**主要功能：**
- 检查用户会员状态
- 返回套餐有效期或剩余次数

#### AlipaySubscribePackageInitialize - 订阅开通
为用户生成订阅套餐的购买链接，用于订阅服务的开通。

**输入参数 (SubscribePackageInitializeInput)：**
- `uuid` (str): 账户ID

**输出参数 (SubscribePackageInitializeOutput)：**
- `subscribe_url` (str): 订阅购买链接（如果未订阅）

**主要功能：**
- 生成订阅购买链接
- 支持按时间和按次数两种订阅模式

#### AlipaySubscribeTimesSave - 订阅计次
记录用户使用智能体服务的次数，用于按次计费的扣减。

**输入参数 (SubscribeTimesSaveInput)：**
- `uuid` (str): 账户ID
- `out_request_no` (str): 外部请求号（用于幂等性控制）

**输出参数 (SubscribeTimesSaveOutput)：**
- `success` (bool): 计次服务调用是否成功

**主要功能：**
- 按次计费扣减
- 支持幂等性操作

#### AlipaySubscribeCheckOrInitialize - 订阅检查或初始化
一站式订阅服务组件，自动检查用户订阅状态并在未订阅时返回购买链接。

**输入参数 (SubscribeCheckOrInitializeInput)：**
- `uuid` (str): 账户ID

**输出参数 (SubscribeCheckOrInitializeOutput)：**
- `subscribe_flag` (bool): 是否已订阅
- `subscribe_url` (str): 订阅链接（如果未订阅）

**主要功能：**
- 自动检查订阅状态
- 未订阅时自动生成购买链接
- 简化业务逻辑处理

## 🔧 环境变量配置

| 环境变量 | 必需 | 默认值 | 说明 |
|---------|------|--------|------|
| `ALIPAY_APP_ID` | ✅ | - | 支付宝应用ID |
| `ALIPAY_PRIVATE_KEY` | ✅ | - | 应用私钥 |
| `ALIPAY_PUBLIC_KEY` | ✅ | - | 支付宝公钥 |
| `ALIPAY_GATEWAY` | ❌ | https://openapi.alipay.com/gateway.do | 支付宝网关地址 |
| `AP_RETURN_URL` | ❌ | - | 支付完成后回调地址 |
| `AP_NOTIFY_URL` | ❌ | - | 支付异步通知地址 |
| `SUBSCRIBE_PLAN_ID` | ✅ | - | 订阅计划ID |
| `X_AGENT_NAME` | ✅ | - | 智能体名称 |
| `USE_TIMES` | ❌ | 1 | 每次使用扣减的次数 |

## 🚀 使用示例

### 基础支付示例

```python
from agentscope_runtime.tools.alipay.payment import (
    MobileAlipayPayment,
    WebPageAlipayPayment
)
import asyncio

# 手机端支付
mobile_payment = MobileAlipayPayment()
webpage_payment = WebPageAlipayPayment()

async def mobile_payment_example():
    result = await mobile_payment.arun({
        "out_trade_no": "ORDER_20241218_001",
        "order_title": "AI智能体服务",
        "total_amount": 99.99
    })
    print("手机支付链接:", result.result)

async def webpage_payment_example():
    result = await webpage_payment.arun({
        "out_trade_no": "ORDER_20241218_002",
        "order_title": "AI智能体高级服务",
        "total_amount": 199.99
    })
    print("网页支付链接:", result.result)

asyncio.run(mobile_payment_example())
asyncio.run(webpage_payment_example())
```

### 交易管理示例

```python
from agentscope_runtime.tools.alipay.payment import (
    AlipayPaymentQuery,
    AlipayPaymentRefund,
    AlipayRefundQuery
)

query_component = AlipayPaymentQuery()
refund_component = AlipayPaymentRefund()
refund_query_component = AlipayRefundQuery()


async def transaction_management_example():
    # 查询支付状态
    query_result = await query_component.arun({
        "out_trade_no": "ORDER_20241218_001"
    })
    print("交易状态:", query_result.result)

    # 发起退款
    refund_result = await refund_component.arun({
        "out_trade_no": "ORDER_20241218_001",
        "refund_amount": 50.0,
        "refund_reason": "用户申请退款"
    })
    print("退款结果:", refund_result.result)

    # 查询退款状态
    refund_query_result = await refund_query_component.arun({
        "out_trade_no": "ORDER_20241218_001",
        "out_request_no": "ORDER_20241218_001_refund_1734509344"
    })
    print("退款状态:", refund_query_result.result)


asyncio.chat(transaction_management_example())
```

### 订阅服务示例

```python
from agentscope_runtime.tools.alipay.subscribe import (
    AlipaySubscribeStatusCheck,
    AlipaySubscribePackageInitialize,
    AlipaySubscribeTimesSave,
    AlipaySubscribeCheckOrInitialize
)

status_check = AlipaySubscribeStatusCheck()
initialize = AlipaySubscribePackageInitialize()
times_save = AlipaySubscribeTimesSave()
check_or_init = AlipaySubscribeCheckOrInitialize()


async def subscription_example():
    user_uuid = "user_12345"

    # 检查订阅状态
    status = await status_check.arun({"uuid": user_uuid})
    print(f"订阅状态: {status.subscribe_flag}")
    if status.subscribe_flag:
        print(f"套餐信息: {status.subscribe_package}")

    # 如果未订阅，获取订阅链接
    if not status.subscribe_flag:
        init_result = await initialize.arun({"uuid": user_uuid})
        if init_result.subscribe_url:
            print(f"订阅链接: {init_result.subscribe_url}")

    # 使用服务后计次
    if status.subscribe_flag:
        times_result = await times_save.arun({
            "uuid": user_uuid,
            "out_request_no": "user_12345_20241218_001",
        })
        print(f"计次结果: {times_result.success}")


async def one_step_subscription_example():
    user_uuid = "user_67890"

    # 一步完成订阅检查或初始化
    result = await check_or_init.arun({"uuid": user_uuid})

    if result.subscribe_flag:
        print("用户已订阅，可以使用服务")
    else:
        print(f"用户未订阅，订阅链接: {result.subscribe_url}")


asyncio.chat(subscription_example())
asyncio.chat(one_step_subscription_example())
```

## 🏗️ 架构特点

### 支付流程
1. **支付链接生成**: 根据设备类型选择合适的支付方式
2. **用户支付**: 用户通过支付链接完成支付
3. **状态查询**: 查询支付状态，确认交易结果
4. **后续处理**: 根据需要进行退款等操作

### 订阅模式
- **按时间订阅**: 用户购买一定时间段的服务权限
- **按次数订阅**: 用户购买一定次数的服务使用权限


## 📦 依赖包
- `alipay-sdk-python`: 官方支付宝Python SDK
- `cryptography`: 加密相关操作

## ⚠️ 使用注意事项

### 配置安全
- 使用环境变量存储敏感配置信息,妥善保管应用私钥，不要泄露到代码仓库
- 商家或服务商可根据实际情况通过以下方式接入该产品，具体参考https://opendocs.alipay.com/open/203/107084?pathHash=a33de091
- 订阅相关配置参考 https://opendocs.alipay.com/solution/0i40x9?pathHash=29e2835d