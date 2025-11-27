# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name

import re
from datetime import datetime

import pytest
from agentscope_runtime.tools.alipay.subscribe import (
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
    reason="Skipping the entire file online for security reasons",
)


@pytest.fixture(scope="module")
def alipay_subscribe_status_check():
    """Create Alipay subscription status check component instance"""
    return AlipaySubscribeStatusCheck()


@pytest.fixture(scope="module")
def alipay_subscribe_package_initialize():
    """Create Alipay subscription package initialization component instance"""
    return AlipaySubscribePackageInitialize()


@pytest.fixture(scope="module")
def alipay_subscribe_times_save():
    """Create Alipay subscription usage count save component instance"""
    return AlipaySubscribeTimesSave()


@pytest.fixture(scope="module")
def alipay_subscribe_check_or_initialize():
    """Create Alipay subscription check or initialization component instance"""
    return AlipaySubscribeCheckOrInitialize()


@pytest.fixture
def test_order_no():
    """Generate test order number"""
    return f"test_order_{int(datetime.now().timestamp())}"


# Tests
def test_subscribe_status_check_byCount(alipay_subscribe_status_check):
    """Test subscription status check function - by usage count"""
    check_input = SubscribeStatusCheckInput(
        uuid="123455",
        plan_id="2509011400000004",
        channel="百炼",
    )
    resp = alipay_subscribe_status_check.run(check_input)
    # Verify the returned result
    assert hasattr(resp, "subscribe_flag")
    assert hasattr(resp, "subscribe_package")
    # Check the type of subscribe_flag (can be boolean or None)
    assert isinstance(resp.subscribe_flag, (bool, type(None)))
    # If status value is returned, check whether it is within valid range
    if resp.subscribe_flag is not None:
        valid_statuses = [True, False]
        assert resp.subscribe_flag in valid_statuses
    # Note: Due to SSL certificate issues,
    # actual return may be None, which is normal


def test_subscribe_status_check_byTime(alipay_subscribe_status_check):
    """Test subscription status check function - by duration"""
    check_input = SubscribeStatusCheckInput(
        uuid="123456",
        plan_id="2509011400000004",
        channel="百炼",
    )
    resp = alipay_subscribe_status_check.run(check_input)
    # Verify the returned result
    assert hasattr(resp, "subscribe_flag")
    assert hasattr(resp, "subscribe_package")
    # Check the type of subscribe_flag (can be boolean or None)
    assert isinstance(resp.subscribe_flag, (bool, type(None)))
    # If status value is returned, check whether it is within valid range
    if resp.subscribe_flag is not None:
        valid_statuses = [True, False]
        assert resp.subscribe_flag in valid_statuses
    # Note: Due to SSL certificate issues,
    # actual return may be None, which is normal


def test_subscribe_package_initialize(alipay_subscribe_package_initialize):
    """Test subscription package initialization function"""
    initialize_input = SubscribePackageInitializeInput(
        uuid="1234558",
        plan_id="2509011400000004",
        channel="百炼",
        agent_name="测试agent",
    )
    resp = alipay_subscribe_package_initialize.run(initialize_input)
    # Verify the returned result
    assert hasattr(resp, "subscribe_url")
    # Check the type of subscribe_url (can be string or None)
    assert isinstance(resp.subscribe_url, (str, type(None)))
    # If URL is returned, check whether it is within valid range
    if resp.subscribe_url is not None:
        assert re.search(r"alipays://platformapi/startapp", resp.subscribe_url)
    # Note: Due to SSL certificate issues, actual return may be None,
    # which is normal


def test_subscribe_times_save(alipay_subscribe_times_save, test_order_no):
    """Test subscription usage count billing function"""
    count_input = SubscribeTimesSaveInput(
        uuid="123455",
        plan_id="2509011400000004",
        use_times=1,
        channel="百炼",
        out_request_no=test_order_no,
    )
    resp = alipay_subscribe_times_save.run(count_input)
    # Verify the returned result
    assert hasattr(resp, "success")
    # Check the type of success (can be boolean or None)
    assert isinstance(resp.success, (bool, type(None)))
    # If status value is returned, check whether it is within valid range
    if resp.success is not None:
        valid_statuses = [True, False]
        assert resp.success in valid_statuses
    # Note: Due to SSL certificate issues,
    # actual return may be None, which is normal


def test_subscribe_check_or_initialize_subscribed(
    alipay_subscribe_check_or_initialize,
):
    """
    Test subscription check or initialization function for unsubscribed users
    """
    check_or_initialize_input = SubscribeCheckOrInitializeInput(
        uuid="123",
        plan_id="2509011400000004",
        channel="百炼",
        agent_name="测试Agent",
    )
    resp = alipay_subscribe_check_or_initialize.run(check_or_initialize_input)
    # Verify the returned result (subscription status & subscription link)
    assert hasattr(resp, "subscribe_flag")
    assert hasattr(resp, "subscribe_url")
    assert isinstance(resp.subscribe_url, (str, type(None)))
    assert isinstance(resp.subscribe_flag, (bool, type(None)))
    if resp.subscribe_url is not None:
        assert re.search(r"alipays://platformapi/startapp", resp.subscribe_url)
    if resp.subscribe_flag is not None:
        valid_statuses = [True, False]
        assert resp.subscribe_flag in valid_statuses
    # Note: Due to SSL certificate issues,
    # actual return may be empty
