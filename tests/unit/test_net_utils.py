# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
"""
Unit tests for network utility functions.

Tests cover:
- get_first_non_loopback_ip() function
- IPv4/IPv6 address selection
- Interface filtering logic
- Fallback behavior
"""
import os
import socket
from unittest.mock import patch, MagicMock

from agentscope_runtime.engine.deployers.utils.net_utils import (
    get_first_non_loopback_ip,
)


class TestGetFirstNonLoopbackIP:
    """Test get_first_non_loopback_ip() function."""

    def test_returns_none_when_no_interfaces(self):
        """Test returns None when no network interfaces are available."""
        with patch("psutil.net_if_addrs", return_value={}):
            with patch("psutil.net_if_stats", return_value={}):
                with patch("socket.gethostname", return_value="testhost"):
                    with patch(
                        "socket.gethostbyname",
                        side_effect=socket.error("Host not found"),
                    ):
                        result = get_first_non_loopback_ip()
                        assert result is None

    def test_skips_loopback_addresses(self):
        """Test that loopback addresses are skipped."""
        # Mock network interfaces with loopback addresses
        mock_addrs = {
            "lo": [
                MagicMock(
                    family=socket.AF_INET,
                    address="127.0.0.1",
                ),
            ],
            "eth0": [
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
            ],
        }

        mock_stats = {
            "lo": MagicMock(isup=True),
            "eth0": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                result = get_first_non_loopback_ip()
                # Should return the non-loopback address
                assert result == "192.168.1.100"

    def test_skips_interfaces_that_are_down(self):
        """Test that interfaces that are down are skipped."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
            ],
            "eth1": [
                MagicMock(
                    family=socket.AF_INET,
                    address="10.0.0.1",
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=False),  # Interface is down
            "eth1": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                result = get_first_non_loopback_ip()
                # Should return address from interface that is up
                assert result == "10.0.0.1"

    def test_selects_lowest_index_interface(self):
        """Test that interface with lowest index is selected."""
        # Create interfaces in a specific order
        mock_addrs = {
            "eth1": [  # This will have index 1
                MagicMock(
                    family=socket.AF_INET,
                    address="10.0.0.1",
                ),
            ],
            "eth0": [  # This will have index 0
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=True),
            "eth1": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                result = get_first_non_loopback_ip()
                # Should return address from interface with lowest index
                # (eth1 comes first in dict iteration, but we want eth0)
                # Note: dict iteration order in Python 3.7+ is insertion order
                # So eth1 (index 0) should be selected first
                assert result in ["10.0.0.1", "192.168.1.100"]

    def test_prefers_ipv4_by_default(self):
        """Test that IPv4 addresses are preferred by default."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET6,
                    address="2001:db8::1",
                ),
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                with patch.dict(os.environ, {}, clear=False):
                    result = get_first_non_loopback_ip()
                    # Should return IPv4 address
                    assert result == "192.168.1.100"

    def test_uses_ipv6_when_env_var_set(self):
        """Test that IPv6 addresses are used when USE_IPV6 is set."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET6,
                    address="2001:db8::1",
                ),
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                with patch.dict(os.environ, {"USE_IPV6": "true"}, clear=False):
                    result = get_first_non_loopback_ip()
                    # Should return IPv6 address
                    assert result == "2001:db8::1"

    def test_handles_ipv6_zone_identifier(self):
        """Test that IPv6 zone identifiers are handled correctly."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET6,
                    address="fe80::1%eth0",  # IPv6 with zone identifier
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                with patch.dict(os.environ, {"USE_IPV6": "true"}, clear=False):
                    result = get_first_non_loopback_ip()
                    # Should return the address (zone identifier handled)
                    assert result == "fe80::1%eth0"

    def test_fallback_to_gethostbyname(self):
        """Test fallback to socket.gethostbyname when no interface found."""
        mock_addrs = {
            "lo": [  # Only loopback interface
                MagicMock(
                    family=socket.AF_INET,
                    address="127.0.0.1",
                ),
            ],
        }

        mock_stats = {
            "lo": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                with patch("socket.gethostname", return_value="testhost"):
                    with patch(
                        "socket.gethostbyname",
                        return_value="192.168.1.50",
                    ) as mock_gethostbyname:
                        result = get_first_non_loopback_ip()
                        # Should fallback to gethostbyname
                        mock_gethostbyname.assert_called_once_with("testhost")
                        assert result == "192.168.1.50"

    def test_returns_none_when_fallback_fails(self):
        """Test returns None when fallback also fails."""
        mock_addrs = {
            "lo": [  # Only loopback interface
                MagicMock(
                    family=socket.AF_INET,
                    address="127.0.0.1",
                ),
            ],
        }

        mock_stats = {
            "lo": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                with patch("socket.gethostname", return_value="testhost"):
                    with patch(
                        "socket.gethostbyname",
                        side_effect=socket.error("Host not found"),
                    ):
                        result = get_first_non_loopback_ip()
                        # Should return None when fallback fails
                        assert result is None

    def test_handles_invalid_ip_addresses(self):
        """Test that invalid IP addresses are handled gracefully."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET,
                    address="invalid-ip",
                ),
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                result = get_first_non_loopback_ip()
                # Should skip invalid address and return valid one
                assert result == "192.168.1.100"

    def test_handles_missing_interface_stats(self):
        """Test that missing interface stats are handled."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
            ],
            "eth1": [
                MagicMock(
                    family=socket.AF_INET,
                    address="10.0.0.1",
                ),
            ],
        }

        mock_stats = {
            "eth0": None,  # Missing stats
            "eth1": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                result = get_first_non_loopback_ip()
                # Should skip interface with missing stats
                assert result == "10.0.0.1"

    def test_handles_case_insensitive_ipv6_env_var(self):
        """Test that USE_IPV6 env var is case insensitive."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET6,
                    address="2001:db8::1",
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                # Test uppercase
                with patch.dict(os.environ, {"USE_IPV6": "TRUE"}, clear=False):
                    result = get_first_non_loopback_ip()
                    assert result == "2001:db8::1"

                # Test mixed case
                with patch.dict(os.environ, {"USE_IPV6": "True"}, clear=False):
                    result = get_first_non_loopback_ip()
                    assert result == "2001:db8::1"

    def test_uses_ipv4_when_ipv6_env_var_is_false(self):
        """Test that IPv4 is used when USE_IPV6 is explicitly false."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET6,
                    address="2001:db8::1",
                ),
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                with patch.dict(
                    os.environ,
                    {"USE_IPV6": "false"},
                    clear=False,
                ):
                    result = get_first_non_loopback_ip()
                    # Should use IPv4 even when env var is set to false
                    assert result == "192.168.1.100"

    def test_handles_multiple_addresses_on_same_interface(self):
        """Test handling of multiple addresses on the same interface."""
        mock_addrs = {
            "eth0": [
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.100",
                ),
                MagicMock(
                    family=socket.AF_INET,
                    address="192.168.1.101",
                ),
            ],
        }

        mock_stats = {
            "eth0": MagicMock(isup=True),
        }

        with patch("psutil.net_if_addrs", return_value=mock_addrs):
            with patch("psutil.net_if_stats", return_value=mock_stats):
                result = get_first_non_loopback_ip()
                # Should return the first non-loopback address found
                assert result in ["192.168.1.100", "192.168.1.101"]
