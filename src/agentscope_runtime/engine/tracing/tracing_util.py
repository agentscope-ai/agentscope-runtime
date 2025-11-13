# -*- coding: utf-8 -*-
import contextvars
import os
from opentelemetry import baggage
from opentelemetry.context import attach

_user_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_user_request_id",
    default="",
)

_user_trace_header: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "_user_trace_header",
    default={},
)

_user_common_attributes: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "_user_common_attributes",
    default={},
)


class TracingUtil:
    @staticmethod
    def set_request_id(value: str = "") -> None:
        """Set request id"""
        _user_request_id.set(value)
        if value:
            ctx = baggage.set_baggage(
                "agentscope-runtime_request_id",
                value,
            )
            attach(ctx)

            TracingUtil.clear_common_attributes()
            TracingUtil.set_common_attributes(
                {
                    "request_id": value,
                    "bailian.request_id": value,
                    "gen_ai.response.id": value,
                    **_global_attributes,
                },
            )

    @staticmethod
    def get_request_id(default_value: str = "") -> str:
        """Get request id"""
        # Try to get from context variable first
        request_id = _user_request_id.get("")
        if request_id:
            return request_id

        # Fallback to baggage for cross-thread scenarios
        request_id = baggage.get_baggage(
            "agentscope-runtime_request_id",
        )
        if request_id:
            return request_id

        return default_value

    @staticmethod
    def set_trace_header(trace_headers: dict) -> None:
        """Set trace headers

        Args:
            trace_headers: trace headers to set
        """
        _user_trace_header.set(trace_headers)

    @staticmethod
    def get_trace_header() -> dict:
        """Get trace headers

        Returns:
            trace headers in dict
        """
        return _user_trace_header.get({})

    @staticmethod
    def set_common_attributes(attributes: dict) -> None:
        """Set common attributes by merging with existing ones

        Args:
            attributes: common attributes to merge
        """
        current_attributes = _user_common_attributes.get({})
        current_attributes.update(attributes)
        _user_common_attributes.set(current_attributes)

    @staticmethod
    def get_common_attributes() -> dict:
        """Get common attributes

        Returns:
            common attributes in dict
        """
        return _user_common_attributes.get({})

    @staticmethod
    def clear_common_attributes() -> None:
        """Clear common attributes"""
        _user_common_attributes.set({})


def get_global_attributes() -> dict:
    """Set global common attributes for tracing."""
    attributes = {"gen_ai.framework": "Alibaba Cloud Model Studio"}

    if app_env := (os.getenv("APPLICATION_ENV") or os.getenv("DS_ENV")):
        attributes["bailian.app.env"] = app_env

    if app_id := os.getenv("APPLICATION_ID"):
        attributes["bailian.app.id"] = app_id

    if app_name := os.getenv("APPLICATION_NAME"):
        attributes["bailian.app.name"] = app_name

    if app_inter_source := os.getenv("APPLICATION_INTER_SOURCE"):
        attributes["bailian.app.inter.source"] = app_inter_source

    if user_id := os.getenv("ALIYUN_UID"):
        attributes["bailian.app.owner_id"] = user_id
        attributes["gen_ai.user.id"] = user_id

    if app_tracing := os.getenv("APPLICATION_TRACING"):
        attributes["bailian.app.tracing"] = app_tracing

    if workspace_id := os.getenv("WORKSPACE_ID"):
        attributes["bailian.app.workspace"] = workspace_id

    return attributes


_global_attributes = get_global_attributes()
