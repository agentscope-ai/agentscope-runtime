# Alipay Components

This directory contains various Alipay payment and subscription service components that provide comprehensive payment processing, subscription management, and transaction query functionality.

## 📋 Component List

### 1. Payment Components

#### MobileAlipayPayment - Mobile Alipay Payment

Alipay payment component for mobile browsers. This supports redirecting users to the Alipay mobile app or completing payments directly in a mobile browser, providing flexibility for different payment scenarios.

**Prerequisites:**

- Valid Alipay application configuration
- Alipay merchant account and API keys
- Mobile browser environment

**Input Parameters (MobilePaymentInput):**

- `out_trade_no` (str): Merchant order number
- `order_title` (str): Order title
- `total_amount` (float): Payment amount (in yuan, must be greater than 0)

**Output Parameters (PaymentOutput):**

- `result` (str): Markdown text containing payment link

**Key Features:**

- QUICK_WAP_WAY product code
- Supports app and in-browser payments
- Returns ready-to-use payment links

#### WebPageAlipayPayment - Desktop Web Alipay Payment

This Alipay payment component is designed for desktop browsers. It allows users to pay by scanning a QR code shown on the desktop website with their Alipay app, making it easy for desktop users to complete payments.

**Prerequisites:**

- Valid Alipay application configuration
- Alipay merchant account and API keys
- Desktop browser environment

**Input Parameters (WebPagePaymentInput):**

- `out_trade_no` (str): Merchant order number
- `order_title` (str): Order title
- `total_amount` (float): Payment amount (in yuan, must be greater than 0)

**Output Parameters (PaymentOutput):**

- `result` (str): Markdown text containing payment link

**Key Features:**

- FAST_INSTANT_TRADE_PAY product code
- Supports QR code payment on desktops

### 2. Transaction Management Components

#### AlipayPaymentQuery - Payment Transaction Query

Query the current status and detailed information of created Alipay transaction orders.

**Input Parameters (PaymentQueryInput):**

- `out_trade_no` (str): Merchant order number

**Output Parameters (PaymentOutput):**

- `result` (str): Text containing transaction status, amount, Alipay transaction number, and other information

**Key Functions:**

- Retrieve transaction details
- Support status validation and synchronization

#### AlipayPaymentRefund - Payment Transaction Refund

Initiate refund requests for successfully paid transactions, supporting full and partial refunds.

**Input Parameters (PaymentRefundInput):**

- `out_trade_no` (str): Merchant order number
- `refund_amount` (float): Refund amount (must be greater than 0)
- `refund_reason` (str, optional): Refund reason
- `out_request_no` (str, optional): Identifier for a refund request, must be unique under the transaction number. Required for partial refunds

**Output Parameters (PaymentOutput):**

- `result` (str): Text containing refund result information

**Key Functions:**

- Support full and partial refunds
- Refund idempotency guarantee

#### AlipayRefundQuery - Refund Query

Query the current status and processing results of initiated refund requests.

**Input Parameters (RefundQueryInput):**

- `out_trade_no` (str): Merchant order number
- `out_request_no` (str): Refund request number

**Output Parameters (PaymentOutput):**

- `result` (str): Text containing refund status and amount information

**Key Functions:**

- Query and validate refund status
- Retrieve refund details

### 3. Subscription Service Components

#### AlipaySubscribeStatusCheck - Subscription Status Check

Check the user's agent subscription status and return membership information and package details.

**Input Parameters (SubscribeStatusCheckInput):**

- `uuid` (str): Account ID

**Output Parameters (SubscribeStatusOutput):**

- `subscribe_flag` (bool): Whether subscribed
- `subscribe_package` (str): Subscription package description

**Key Functions:**

- Check membership status
- Return package validity or usage count

#### AlipaySubscribePackageInitialize - Subscription Initialization

Generate subscription package purchase links for users to enable subscription services.

**Input Parameters (SubscribePackageInitializeInput):**

- `uuid` (str): Account ID

**Output Parameters (SubscribePackageInitializeOutput):**

- `subscribe_url` (str): Subscription purchase link (if not subscribed)

**Key Functions:**

- Generate subscription links

- Support time/usage-based models

#### AlipaySubscribeTimesSave - Subscription Usage Tracking

Record the user's usage count of agent services for pay-per-use deduction.

**Input Parameters (SubscribeTimesSaveInput):**

- `uuid` (str): Account ID

- `out_request_no` (str): External request number (for idempotency control)

**Output Parameters (SubscribeTimesSaveOutput):**

- `success` (bool): Whether the usage tracking service call was successful

**Key Functions:**

- Pay-per-use deduction

- Support idempotent operations

#### AlipaySubscribeCheckOrInitialize - Subscription Check or Initialize

One-stop subscription service component that automatically checks a user's subscription status and returns purchase links if they are not subscribed.

**Input Parameters (SubscribeCheckOrInitializeInput):**

- `uuid` (str): Account ID

**Output Parameters (SubscribeCheckOrInitializeOutput):**

- `subscribe_flag` (bool): Whether subscribed

- `subscribe_url` (str): Subscription link (if not subscribed)

**Key Functions:**

- Automatically check subscription status (checks if the user is already subscribed)

- Auto-generate purchase links if not subscribed (creates a subscription link for non-subscribed users)

- Simplify business logic handling (reduces complexity for businesses managing subscriptions)

## 🔧 Environment Variable Configuration

| Environment Variable | Required | Default Value | Description |

|---------------------|----------|---------------|-------------|

| `ALIPAY_APP_ID` | ✅ | - | Alipay application ID |

| `ALIPAY_PRIVATE_KEY` | ✅ | - | Application private key |

| `ALIPAY_PUBLIC_KEY` | ✅ | - | Alipay public key |

| `ALIPAY_GATEWAY` | ❌ | https://openapi.alipay.com/gateway.do | Alipay gateway address |

| `AP_RETURN_URL` | ❌ | - | Payment completion callback URL |

| `AP_NOTIFY_URL` | ❌ | - | Payment asynchronous notification URL |

| `SUBSCRIBE_PLAN_ID` | ✅ | - | Subscription plan ID |

| `X_AGENT_NAME` | ✅ | - | Agent name |

| `USE_TIMES` | ❌ | 1 | Usage count deducted per use |

## 🚀 Usage Examples

### Basic Payment Example

```python

from agentscope_runtime.tools.alipay.payment import (

    MobileAlipayPayment,

    WebPageAlipayPayment

)

import asyncio

# Mobile payment

mobile_payment = MobileAlipayPayment()

webpage_payment = WebPageAlipayPayment()

async def mobile_payment_example():

    result = await mobile_payment.arun({

        "out_trade_no": "ORDER_20241218_001",

        "order_title": "AI Agent Service",

        "total_amount": 99.99

    })

    print("Mobile payment link:", result.result)

async def webpage_payment_example():

    result = await webpage_payment.arun({

        "out_trade_no": "ORDER_20241218_002",

        "order_title": "AI Agent Premium Service",

        "total_amount": 199.99

    })

    print("Web payment link:", result.result)

asyncio.run(mobile_payment_example())

asyncio.run(webpage_payment_example())

```

### Transaction Management Example

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
    # Query payment status

    query_result = await query_component.arun({

        "out_trade_no": "ORDER_20241218_001"

    })

    print("Transaction status:", query_result.result)

    # Initiate refund

    refund_result = await refund_component.arun({

        "out_trade_no": "ORDER_20241218_001",

        "refund_amount": 50.0,

        "refund_reason": "User requested refund"

    })

    print("Refund result:", refund_result.result)

    # Query refund status

    refund_query_result = await refund_query_component.arun({

        "out_trade_no": "ORDER_20241218_001",

        "out_request_no": "ORDER_20241218_001_refund_1734509344"

    })

    print("Refund status:", refund_query_result.result)


asyncio.chat(transaction_management_example())

```

### Subscription Service Example

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

    # Check subscription status

    status = await status_check.arun({"uuid": user_uuid})

    print(f"Subscription status: {status.subscribe_flag}")

    if status.subscribe_flag:
        print(f"Package info: {status.subscribe_package}")

    # If not subscribed, get subscription link

    if not status.subscribe_flag:

        init_result = await initialize.arun({"uuid": user_uuid})

        if init_result.subscribe_url:
            print(f"Subscription link: {init_result.subscribe_url}")

    # Track usage after service use

    if status.subscribe_flag:
        times_result = await times_save.arun({

            "uuid": user_uuid,

            "out_request_no": "user_12345_20241218_001",

        })

        print(f"Usage tracking result: {times_result.success}")


async def one_step_subscription_example():
    user_uuid = "user_67890"

    # One-step subscription check or initialization

    result = await check_or_init.arun({"uuid": user_uuid})

    if result.subscribe_flag:

        print("User is subscribed, can use service")

    else:

        print(f"User not subscribed, subscription link: {result.subscribe_url}")


asyncio.chat(subscription_example())

asyncio.chat(one_step_subscription_example())

```

## 🏗️ Architecture Features

### Payment Flow

1. **Payment Link Generation**: Choose appropriate payment method based on device type

2. **User Payment**: User completes payment through payment link

3. **Status Query**: Query payment status, confirm transaction results

4. **Post-processing**: Perform refunds and other operations as needed

### Subscription Models

- **Time-based Subscription**: Users purchase service permissions for a specific time period

- **Usage-based Subscription**: Users purchase a specific number of service uses

## 📦 Dependencies

- `alipay-sdk-python`: Official Alipay Python SDK

- `cryptography`: Encryption-related operations

## ⚠️ Usage Notes

### Configuration Security

- Use environment variables to store sensitive configuration information

- Properly safeguard application private keys, do not expose them in code repositories

- Merchants or service providers can integrate this product through various methods based on actual situations. For details, refer to https://opendocs.alipay.com/open/203/107084?pathHash=a33de091

- For subscription-related configuration, refer to https://opendocs.alipay.com/solution/0i40x9?pathHash=29e2835d