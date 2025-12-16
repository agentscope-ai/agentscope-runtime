# -*- coding: utf-8 -*-
import ipaddress
import os
import socket
from typing import Optional

import psutil


def get_first_non_loopback_ip() -> Optional[str]:
    """Get the first non-loopback IP address from network interfaces.

    - Selects the interface with the lowest index
    - Only considers interfaces that are up
    - Supports IPv4/IPv6 based on environment variable
    - Falls back to socket.gethostbyname() if no address found

    Returns:
        str | None: The first non-loopback IP address, or None if not found
    """
    result = None
    lowest_index = float("inf")

    use_ipv6 = os.environ.get("USE_IPV6", "false").lower() == "true"
    target_family = socket.AF_INET6 if use_ipv6 else socket.AF_INET

    net_if_stats = psutil.net_if_stats()

    for index, (interface, addrs) in enumerate(
        psutil.net_if_addrs().items(),
    ):
        stats = net_if_stats.get(interface)
        if stats is None or not stats.isup:
            continue

        if index < lowest_index or result is None:
            lowest_index = index
        else:
            continue

        for addr in addrs:
            if addr.family != target_family:
                continue

            try:
                ip_obj = ipaddress.ip_address(
                    addr.address.split("%")[0],
                )
                if ip_obj.is_loopback:
                    continue
                result = addr.address
            except ValueError:
                continue

    if result is not None:
        return result

    try:
        hostname = socket.gethostname()
        fallback_ip = socket.gethostbyname(hostname)
        return fallback_ip
    except socket.error:
        pass

    return None
