# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import functools
import threading
from dataclasses import dataclass
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=object)


def _toplevel_pkg() -> str:
    pkg = __package__ or __name__
    return pkg.split(".", 1)[0]


@dataclass(frozen=True)
class DeprecationInfo:
    reason: str = ""
    since: str | None = None
    removed_in: str | None = None
    alternative: str | None = None
    issue: str | int | None = None  # e.g. "GH-123" or 123


def format_deprecation_message(subject: str, info: DeprecationInfo) -> str:
    parts: list[str] = [f"{subject} is deprecated."]
    if info.since:
        parts.append(f"Since {info.since}.")
    if info.removed_in:
        parts.append(f"Will be removed in {info.removed_in}.")
    if info.alternative:
        parts.append(f"Use {info.alternative} instead.")
    if info.issue is not None:
        parts.append(f"See {info.issue}.")
    if info.reason:
        parts.append(info.reason.rstrip(".") + ".")
    return " ".join(parts)


_LOGGED_ONCE_MESSAGES: set[str] = set()
_LOGGED_ONCE_LOCK = threading.Lock()


def warn_deprecated(
    subject: str,
    info: DeprecationInfo,
    *,
    stacklevel: int = 2,
    once: bool = False,
) -> None:
    message = format_deprecation_message(subject, info)

    if once:
        with _LOGGED_ONCE_LOCK:
            if message in _LOGGED_ONCE_MESSAGES:
                return
            _LOGGED_ONCE_MESSAGES.add(message)

    logger.warning(message, stacklevel=stacklevel)


def deprecated(
    reason: str | DeprecationInfo = "",
    *,
    since: str | None = None,
    removed_in: str | None = None,
    alternative: str | None = None,
    issue: str | int | None = None,
    stacklevel: int = 2,
    once: bool = False,
) -> Callable[[T], T]:
    """
    Unified decorator:
      - function/method: warn on each call
      - class: warn on each instantiation (__init__)
    """
    info = (
        reason
        if isinstance(reason, DeprecationInfo)
        else DeprecationInfo(
            reason=str(reason),
            since=since,
            removed_in=removed_in,
            alternative=alternative,
            issue=issue,
        )
    )

    def decorator(obj):
        subject = getattr(
            obj,
            "__qualname__",
            getattr(obj, "__name__", repr(obj)),
        )

        if isinstance(obj, type):
            orig_init = obj.__init__

            @functools.wraps(orig_init)
            def __init__(self, *args, **kwargs):
                warn_deprecated(
                    subject,
                    info,
                    stacklevel=stacklevel,
                    once=once,
                )
                orig_init(self, *args, **kwargs)

            obj.__init__ = __init__
            return obj

        @functools.wraps(obj)
        def wrapper(*args, **kwargs):
            warn_deprecated(
                subject,
                info,
                stacklevel=stacklevel,
                once=once,
            )
            return obj(*args, **kwargs)

        return wrapper

    return decorator


def deprecated_module(
    reason: str | DeprecationInfo = "",
    *,
    module_name: str,
    since: str | None = None,
    removed_in: str | None = None,
    alternative: str | None = None,
    issue: str | int | None = None,
    stacklevel: int = 2,
    once: bool = True,
) -> None:
    """
    Use inside a module/package (typically __init__.py) to warn on import.
    """
    info = (
        reason
        if isinstance(reason, DeprecationInfo)
        else DeprecationInfo(
            reason=str(reason),
            since=since,
            removed_in=removed_in,
            alternative=alternative,
            issue=issue,
        )
    )
    warn_deprecated(
        f"Module `{module_name}`",
        info,
        stacklevel=stacklevel,
        once=once,
    )
