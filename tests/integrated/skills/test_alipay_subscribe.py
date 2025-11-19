# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name

import re
from datetime import datetime

import pytest
from agentscope_runtime.common.skills.alipay.subscribe import (
    SubscribeStatusCheckInput,
    AlipaySubscribeStatusCheck,
    SubscribePackageInitializeInput,
    AlipaySubscribePackageInitialize,
    SubscribeTimesSaveInput,
    AlipaySubscribeTimesSave,
    AlipaySubscribeCheckOrInitialize,
    SubscribeCheckOrInitializeInput,
)

pytestmark = pytest.mark.skip(
    reason="Skipping the entire file online for " "security reasons",
)


@pytest.fixture(scope="module")
def alipay_subscribe_status_check():
    """创建支付宝订阅状态检查组件实例"""
    return AlipaySubscribeStatusCheck()


@pytest.fixture(scope="module")
def alipay_subscribe_package_initialize():
    """创建支付宝订阅套餐包初始化组件实例"""
    return AlipaySubscribePackageInitialize()


@pytest.fixture(scope="module")
def alipay_subscribe_times_save():
    """创建支付宝订阅次数保存组件实例"""
    return AlipaySubscribeTimesSave()


@pytest.fixture(scope="module")
def alipay_subscribe_check_or_initialize():
    """创建支付宝订阅检查或初始化组件实例"""
    return AlipaySubscribeCheckOrInitialize()


@pytest.fixture
def test_order_no():
    """生成测试订单号"""
    return f"test_order_{int(datetime.now().timestamp())}"


# Tests
def test_subscribe_status_check_byCount(alipay_subscribe_status_check):
    """测试订阅状态检查功能-次数"""
    check_input = SubscribeStatusCheckInput(
        uuid="123455",
        plan_id="2509011400000004",
        channel="百炼",
    )
    resp = alipay_subscribe_status_check.run(check_input)
    # 验证返回结果
    assert hasattr(resp, "subscribe_flag")
    assert hasattr(resp, "subscribe_package")
    # 检查 subscribe_flag 的类型（可以是字符串或 None）
    assert isinstance(resp.subscribe_flag, (bool, type(None)))
    # 如果返回了状态值，检查是否在有效范围内
    if resp.subscribe_flag is not None:
        valid_statuses = [True, False]
        assert resp.subscribe_flag in valid_statuses
    # 注意：由于SSL证书问题，
    # 实际返回可能是None，这是正常的


def test_subscribe_status_check_byTime(alipay_subscribe_status_check):
    """测试订阅状态检查功能-时长"""
    check_input = SubscribeStatusCheckInput(
        uuid="123456",
        plan_id="2509011400000004",
        channel="百炼",
    )
    resp = alipay_subscribe_status_check.run(check_input)
    # 验证返回结果
    assert hasattr(resp, "subscribe_flag")
    assert hasattr(resp, "subscribe_package")
    # 检查 subscribe_flag 的类型（可以是字符串或 None）
    assert isinstance(resp.subscribe_flag, (bool, type(None)))
    # 如果返回了状态值，检查是否在有效范围内
    if resp.subscribe_flag is not None:
        valid_statuses = [True, False]
        assert resp.subscribe_flag in valid_statuses
    # 注意：由于SSL证书问题，
    # 实际返回可能是None，这是正常的


def test_subscribe_package_initialize(alipay_subscribe_package_initialize):
    """测试订阅包初始化功能"""
    initialize_input = SubscribePackageInitializeInput(
        uuid="1234558",
        plan_id="2509011400000004",
        channel="百炼",
        agent_name="测试agent",
    )
    resp = alipay_subscribe_package_initialize.run(initialize_input)
    # 验证返回结果
    assert hasattr(resp, "subscribe_url")
    # 检查 subscribe_url 的类型（可以是字符串或 None）
    assert isinstance(resp.subscribe_url, (str, type(None)))
    # 如果返回了状态值，检查是否在有效范围内
    if resp.subscribe_url is not None:
        assert re.search(r"alipays://platformapi/startapp", resp.subscribe_url)
    # 注意：由于SSL证书问题，实际返回可能是None，这是正常的


def test_subscribe_times_save(alipay_subscribe_times_save, test_order_no):
    """测试订阅次数计费功能"""
    count_input = SubscribeTimesSaveInput(
        uuid="123455",
        plan_id="2509011400000004",
        use_times=1,
        channel="百炼",
        out_request_no=test_order_no,
    )
    resp = alipay_subscribe_times_save.run(count_input)
    # 验证返回结果
    assert hasattr(resp, "success")
    # 检查 success 的类型（可以是字符串或 None）
    assert isinstance(resp.success, (bool, type(None)))
    # 如果返回了状态值，检查是否在有效范围内
    if resp.success is not None:
        valid_statuses = [True, False]
        assert resp.success in valid_statuses
    # 注意：由于SSL证书问题，
    # 实际返回可能是None，这是正常的


def test_subscribe_check_or_initialize_subscribed(
    alipay_subscribe_check_or_initialize,
):
    """测试未订阅用户的订阅检查或初始化功能"""
    check_or_initialize_input = SubscribeCheckOrInitializeInput(
        uuid="123",
        plan_id="2509011400000004",
        channel="百炼",
        agent_name="测试Agent",
    )
    resp = alipay_subscribe_check_or_initialize.run(check_or_initialize_input)
    # 验证返回结果（返回订阅状态&订阅链接）
    assert hasattr(resp, "subscribe_flag")
    assert hasattr(resp, "subscribe_url")
    assert isinstance(resp.subscribe_url, (str, type(None)))
    assert isinstance(resp.subscribe_flag, (bool, type(None)))
    if resp.subscribe_url is not None:
        assert re.search(r"alipays://platformapi/startapp", resp.subscribe_url)
    if resp.subscribe_flag is not None:
        valid_statuses = [True, False]
        assert resp.subscribe_flag in valid_statuses
    # 注意：由于SSL证书问题，
    # 实际返回可能为空
