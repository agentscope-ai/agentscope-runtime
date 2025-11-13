# -*- coding: utf-8 -*-
# type: ignore

import contextvars
import inspect
import json
import os
import re
import time
import uuid
from collections.abc import Callable
from copy import deepcopy
from enum import Enum
from functools import wraps
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Iterable,
    Optional,
    TypeVar,
    Union,
)

from pydantic import BaseModel
from opentelemetry.propagate import extract
from opentelemetry.context import attach
from opentelemetry.trace import StatusCode
from opentelemetry import trace as ot_trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as OTLPSpanGrpcExporter,
)
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

from .asyncio_util import aenumerate
from .message_util import (
    merge_incremental_chunk,
    get_finish_reason,
)

from .base import Tracer, TracerHandler, EventContext
from .tracing_metric import TraceType
from .local_logging_handler import LocalLogHandler
from .tracing_util import TracingUtil

T_co = TypeVar("T_co", covariant=True)


def _str_to_bool(value: str) -> bool:
    """Convert string to boolean value.

    Args:
        value (str): String value to convert.

    Returns:
        bool: Boolean representation of the string.
    """
    return value.lower() in ("true", "1", "yes", "on")


class MineType(str, Enum):
    """MIME type enumeration for content types."""

    TEXT = "text/plain"
    JSON = "application/json"


_parent_span_context: contextvars.ContextVar = contextvars.ContextVar(
    "_parent_span_context",
    default=None,
)

_current_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_request_id",
    default="",
)

_current_trace_header: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "_current_trace_header",
    default={},
)


def trace(  # pylint: disable=too-many-statements
    trace_type: Union[TraceType, str, None] = None,
    *,
    trace_name: Optional[str] = None,
    is_root_span: Optional[bool] = None,
    get_finish_reason_func: Optional[
        Callable[[Any], Optional[str]]
    ] = get_finish_reason,
    merge_output_func: Optional[
        Callable[[Any], Union[BaseModel, dict, str, None]]
    ] = merge_incremental_chunk,
) -> Any:
    """Decorator for tracing function execution.

    Args:
        trace_type (Union[TraceType, str]): The type of trace event.
        trace_name (Optional[str]): The name of trace event.
        is_root_span (Optional[bool]): Specify current span as root span
        get_finish_reason_func(Optional[Callable]): The function to judge
            if stopped
        merge_output_func(Optional[Callable]): The function to merge outputs

    Returns:
        Any: The decorated function with tracing capabilities.
    """

    def wrapper(func: Any) -> Any:
        """Wrapper function that applies tracing to the target function.

        Args:
            func (Any): The function to be traced.

        Returns:
            Any: The wrapped function with appropriate tracing logic.
        """

        @wraps(func)
        async def async_exec(*args: Any, **kwargs: Any) -> Any:
            """Execute async function with tracing.

            Args:
                *args (Any): Positional arguments for the function.
                **kwargs (Any): Keyword arguments for the function.

            Returns:
                Any: The result of the traced function.
            """

            _init_trace_context()

            start_payload = _get_start_payload(args, kwargs, func)

            trace_context = kwargs.get("trace_context") if kwargs else None

            if trace_context:
                attach(trace_context)

            parent_ctx = (
                trace_context
                if trace_context
                else _parent_span_context.get(None)
            )

            (
                final_trace_type,
                final_trace_name,
                final_is_root_span,
            ) = _validate_trace_options(
                trace_type,
                trace_name,
                is_root_span,
                func.__name__,
                parent_ctx,
            )

            # Auto generate request_id for root span if needed
            _set_request_id(parent_ctx)

            common_attrs = TracingUtil.get_common_attributes() or {}

            span_attributes = {
                "gen_ai.span.kind": final_trace_type,
                "gen_ai.user.query_root_flag": 1 if final_is_root_span else 0,
                "input.mine_type": MineType.JSON,
                "input.value": json.dumps(
                    start_payload,
                    ensure_ascii=False,
                ),
                **common_attrs,
            }

            with _ot_tracer.start_as_current_span(
                final_trace_name,
                context=parent_ctx,
                attributes=span_attributes,
            ) as span:
                span.set_status(status=StatusCode.OK)
                with _tracer.event(
                    span,
                    final_trace_name,
                    payload=start_payload,
                ) as event:
                    _parent_span_context.set(
                        ot_trace.set_span_in_context(span),
                    )
                    if _function_accepts_kwargs(func):
                        func_kwargs = kwargs.copy() if kwargs else {}
                        func_kwargs["trace_event"] = event
                    else:
                        func_kwargs = kwargs.copy() if kwargs else {}

                    try:
                        result = await func(*args, **func_kwargs)
                        end_payload = _obj_to_dict(result)
                        (
                            output_mine_type,
                            output_value,
                        ) = _get_ot_type_and_value(end_payload)
                        span.set_attribute(
                            "output.mine_type",
                            output_mine_type,
                        )
                        span.set_attribute(
                            "output.value",
                            output_value,
                        )
                        event.on_end(payload=end_payload)
                        return result
                    except Exception as e:
                        span.set_status(
                            status=StatusCode.ERROR,
                            description=f"exception={e}",
                        )
                        event.on_log(str(e))
                        raise e
                    finally:
                        if not trace_context:
                            _parent_span_context.set(parent_ctx)

        @wraps(func)
        def sync_exec(*args: Any, **kwargs: Any) -> Any:
            """Execute sync function with tracing.

            Args:
                *args (Any): Positional arguments for the function.
                **kwargs (Any): Keyword arguments for the function.

            Returns:
                Any: The result of the traced function.
            """

            _init_trace_context()

            start_payload = _get_start_payload(args, kwargs, func)

            trace_context = kwargs.get("trace_context") if kwargs else None

            if trace_context:
                attach(trace_context)

            parent_ctx = (
                trace_context
                if trace_context
                else _parent_span_context.get(None)
            )

            (
                final_trace_type,
                final_trace_name,
                final_is_root_span,
            ) = _validate_trace_options(
                trace_type,
                trace_name,
                is_root_span,
                func.__name__,
                parent_ctx,
            )

            # Auto generate request_id for root span if needed
            _set_request_id(parent_ctx)

            common_attrs = TracingUtil.get_common_attributes() or {}

            span_attributes = {
                "gen_ai.span.kind": final_trace_type,
                "gen_ai.user.query_root_flag": 1 if final_is_root_span else 0,
                "input.mine_type": MineType.JSON,
                "input.value": json.dumps(
                    start_payload,
                    ensure_ascii=False,
                ),
                **common_attrs,
            }

            with _ot_tracer.start_as_current_span(
                final_trace_name,
                context=parent_ctx,
                attributes=span_attributes,
            ) as span:
                span.set_status(status=StatusCode.OK)
                with _tracer.event(
                    span,
                    final_trace_name,
                    payload=start_payload,
                ) as event:
                    _parent_span_context.set(
                        ot_trace.set_span_in_context(span),
                    )
                    if _function_accepts_kwargs(func):
                        func_kwargs = kwargs.copy() if kwargs else {}
                        func_kwargs["trace_event"] = event
                    else:
                        func_kwargs = kwargs.copy() if kwargs else {}

                    try:
                        result = func(*args, **func_kwargs)
                        end_payload = _obj_to_dict(result)
                        (
                            output_mine_type,
                            output_value,
                        ) = _get_ot_type_and_value(end_payload)
                        span.set_attribute(
                            "output.mine_type",
                            output_mine_type,
                        )
                        span.set_attribute(
                            "output.value",
                            output_value,
                        )
                        event.on_end(payload=end_payload)
                        return result
                    except Exception as e:
                        span.set_status(
                            status=StatusCode.ERROR,
                            description=f"exception={e}",
                        )
                        event.on_log(str(e))
                        raise e
                    finally:
                        if not trace_context:
                            _parent_span_context.set(parent_ctx)

        @wraps(func)
        async def async_iter_task(  # pylint: disable=too-many-statements
            *args: Any,
            **kwargs: Any,
        ) -> AsyncGenerator[T_co, None]:
            """Execute async generator function with tracing.

            Args:
                *args (Any): Positional arguments for the function.
                **kwargs (Any): Keyword arguments for the function.

            Yields:
                T_co: Items from the original generator with tracing.
            """
            _init_trace_context()

            start_payload = _get_start_payload(args, kwargs, func)

            trace_context = kwargs.get("trace_context") if kwargs else None

            if trace_context:
                attach(trace_context)

            parent_ctx = (
                trace_context
                if trace_context
                else _parent_span_context.get(None)
            )

            (
                final_trace_type,
                final_trace_name,
                final_is_root_span,
            ) = _validate_trace_options(
                trace_type,
                trace_name,
                is_root_span,
                func.__name__,
                parent_ctx,
            )

            # Auto generate request_id for root span if needed
            _set_request_id(parent_ctx)

            common_attrs = TracingUtil.get_common_attributes() or {}

            span_attributes = {
                "gen_ai.span.kind": final_trace_type,
                "gen_ai.user.query_root_flag": 1 if final_is_root_span else 0,
                "input.mine_type": MineType.JSON,
                "input.value": json.dumps(
                    start_payload,
                    ensure_ascii=False,
                ),
                **common_attrs,
            }

            with _ot_tracer.start_as_current_span(
                final_trace_name,
                context=parent_ctx,
                attributes=span_attributes,
            ) as span:
                span.set_status(status=StatusCode.OK)
                with _tracer.event(
                    span,
                    final_trace_name,
                    payload=start_payload,
                ) as event:
                    _parent_span_context.set(
                        ot_trace.set_span_in_context(span),
                    )
                    if _function_accepts_kwargs(func):
                        func_kwargs = kwargs.copy() if kwargs else {}
                        func_kwargs["trace_event"] = event
                    else:
                        func_kwargs = kwargs.copy() if kwargs else {}

                    cumulated = []

                    async def iter_entry() -> AsyncGenerator[T_co, None]:
                        """Internal async generator for processing items.

                        Yields:
                            T_co: Items from the original generator with
                                tracing.
                        """
                        try:
                            start_time = int(time.time() * 1000)
                            async for i, resp in aenumerate(
                                func(*args, **func_kwargs),
                            ):  # type: ignore
                                yield resp
                                cumulated.append(resp)

                                if i == 0:
                                    _trace_first_resp(
                                        resp,
                                        event,
                                        span,
                                        start_time,
                                    )

                                if get_finish_reason_func is not None:
                                    _trace_last_resp(
                                        resp,
                                        get_finish_reason_func,
                                        event,
                                        span,
                                    )

                            if cumulated and merge_output_func is not None:
                                _trace_merged_resp(
                                    cumulated,
                                    merge_output_func,
                                    event,
                                    span,
                                )

                        except Exception as e:
                            span.set_status(
                                status=StatusCode.ERROR,
                                description=f"exception={e}",
                            )
                            event.on_log(str(e))
                            raise e
                        finally:
                            if not trace_context:
                                _parent_span_context.set(parent_ctx)

                    try:
                        async for resp in iter_entry():
                            yield resp

                    except Exception as e:
                        raise e

        @wraps(func)
        def iter_task(*args: Any, **kwargs: Any) -> Iterable[T_co]:
            """Execute generator function with tracing.

            Args:
                *args (Any): Positional arguments for the function.
                **kwargs (Any): Keyword arguments for the function.

            Yields:
                T_co: Items from the traced generator.
            """
            _init_trace_context()

            start_payload = _get_start_payload(args, kwargs, func)

            trace_context = kwargs.get("trace_context") if kwargs else None

            if trace_context:
                attach(trace_context)

            parent_ctx = (
                trace_context
                if trace_context
                else _parent_span_context.get(None)
            )

            (
                final_trace_type,
                final_trace_name,
                final_is_root_span,
            ) = _validate_trace_options(
                trace_type,
                trace_name,
                is_root_span,
                func.__name__,
                parent_ctx,
            )

            # Auto generate request_id for root span if needed
            _set_request_id(parent_ctx)

            common_attrs = TracingUtil.get_common_attributes() or {}

            span_attributes = {
                "gen_ai.span.kind": final_trace_type,
                "gen_ai.user.query_root_flag": 1 if final_is_root_span else 0,
                "input.mine_type": MineType.JSON,
                "input.value": json.dumps(
                    start_payload,
                    ensure_ascii=False,
                ),
                **common_attrs,
            }

            with _ot_tracer.start_as_current_span(
                final_trace_name,
                context=parent_ctx,
                attributes=span_attributes,
            ) as span:
                span.set_status(status=StatusCode.OK)
                with _tracer.event(
                    span,
                    final_trace_name,
                    payload=start_payload,
                ) as event:
                    _parent_span_context.set(
                        ot_trace.set_span_in_context(span),
                    )
                    try:
                        if _function_accepts_kwargs(func):
                            func_kwargs = kwargs.copy() if kwargs else {}
                            func_kwargs["trace_event"] = event
                        else:
                            func_kwargs = kwargs.copy() if kwargs else {}

                        cumulated = []
                        start_time = int(time.time() * 1000)
                        for i, resp in enumerate(func(*args, **func_kwargs)):
                            yield resp
                            cumulated.append(resp)

                            if i == 0:
                                _trace_first_resp(
                                    resp,
                                    event,
                                    span,
                                    start_time,
                                )

                            if get_finish_reason_func is not None:
                                _trace_last_resp(
                                    resp,
                                    get_finish_reason_func,
                                    event,
                                    span,
                                )

                        if cumulated and merge_output_func is not None:
                            _trace_merged_resp(
                                cumulated,
                                merge_output_func,
                                event,
                                span,
                            )

                    except Exception as e:
                        span.set_status(
                            status=StatusCode.ERROR,
                            description=f"exception={e}",
                        )
                        event.on_log(str(e))
                        raise e
                    finally:
                        if not trace_context:
                            _parent_span_context.set(parent_ctx)

        # Choose the appropriate wrapper based on function type
        if inspect.isasyncgenfunction(func):
            wrapper_func = async_iter_task
        elif inspect.isgeneratorfunction(func):
            wrapper_func = iter_task
        elif inspect.iscoroutinefunction(func):
            wrapper_func = async_exec
        else:
            wrapper_func = sync_exec

        # Preserve the original function's signature
        try:
            wrapper_func.__signature__ = inspect.signature(func)
        except (ValueError, TypeError):
            pass

        return wrapper_func

    return wrapper


def _get_start_payload(args: Any, kwargs: Any, func: Any = None) -> Dict:
    """Extract and format the start payload from function arguments.

    Args:
        args (Any): Positional arguments from the function call.
        kwargs (Any): Keyword arguments from the function call.
        func (Any): The function being traced (optional).

    Returns:
        Dict: The formatted start payload for tracing.
    """
    merged = {}

    # 处理位置参数：尝试将位置参数与函数签名中的参数名对应
    if func is not None and isinstance(args, tuple) and len(args) > 0:
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.values())

            # 跳过self参数（如果是实例方法）
            start_idx = 0
            if params and params[0].name == "self":
                start_idx = 1

            # 将位置参数与参数名对应
            for i, arg in enumerate(args[start_idx:], start=start_idx):
                if i < len(params):
                    param = params[i]
                    # 只处理位置参数和位置或关键字参数，跳过*args和**kwargs
                    if param.kind in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    ):
                        merged[param.name] = _obj_to_dict(arg)
        except (ValueError, TypeError, IndexError):
            # 如果无法获取函数签名，回退到原来的逻辑
            pass

    # 如果没有函数信息或无法解析，使用原来的逻辑
    if not merged and isinstance(args, tuple) and len(args) > 0:
        dict_args = _obj_to_dict(args)
        if isinstance(dict_args, list):
            for item in dict_args:
                if isinstance(item, dict):
                    merged.update(item)
        elif isinstance(dict_args, dict):
            merged.update(dict_args)

    # 处理关键字参数
    dict_kwargs = _obj_to_dict(kwargs)
    dict_kwargs = {
        key: value
        for key, value in dict_kwargs.items()
        if not key.startswith("trace_")
    }

    if dict_kwargs:
        merged.update(dict_kwargs)

    return merged


def _init_trace_context() -> None:
    current_req_id = _current_request_id.get("")
    user_req_id = TracingUtil.get_request_id()
    if user_req_id and user_req_id != current_req_id:
        _parent_span_context.set(None)
        _current_request_id.set(user_req_id)

    current_trace_header = _current_trace_header.get({})
    user_trace_header = TracingUtil.get_trace_header()
    if user_trace_header and user_trace_header != current_trace_header:
        _current_trace_header.set(user_trace_header)
        context = extract(user_trace_header)
        attach(context)


def _set_request_id(parent_ctx: Any) -> None:
    """Auto generate request_id for root span if not already set.

    Args:
        parent_ctx: Parent context. If None, this is a root span.
    """
    # Check if we already have a request_id (from context var or baggage)
    current_request_id = TracingUtil.get_request_id()

    if parent_ctx is None:
        # This is a root span
        if not current_request_id:
            # For root spans without request_id, generate a new one
            current_parent_span = _parent_span_context.get(None)
            if current_parent_span is None:
                # This is a truly new request, generate a new request_id
                new_request_id = str(uuid.uuid4())
                TracingUtil.set_request_id(new_request_id)
    else:
        if current_request_id and not TracingUtil.get_common_attributes().get(
            "request_id",
        ):
            # Set common attributes from baggage request_id
            TracingUtil.set_request_id(current_request_id)


def _trace_first_resp(
    resp: Any,
    event: EventContext,
    span: Any,
    start_time: int,
) -> None:
    payload = _obj_to_dict(resp)
    event.on_log(
        "",
        **{
            "step_suffix": "first_resp",
            "payload": payload,
        },
    )
    span.set_attribute(
        "gen_ai.response.first_delay",
        int(time.time() * 1000) - start_time,
    )
    _, output_value = _get_ot_type_and_value(payload)
    span.set_attribute(
        "gen_ai.response.first_pkg",
        output_value,
    )


def _trace_last_resp(
    resp: Any,
    func: Callable,
    event: EventContext,
    span: Any,
) -> None:
    resp_copy = deepcopy(resp)

    finish_reason = func(resp_copy)
    if finish_reason:
        step_suffix = "last_resp" if finish_reason == "stop" else finish_reason
        payload = _obj_to_dict(resp_copy)
        event.on_log(
            "",
            **{
                "step_suffix": step_suffix,
                "payload": payload,
            },
        )
        _, output_value = _get_ot_type_and_value(payload)
        span.set_attribute(
            "gen_ai.response.pkg_" + finish_reason,
            output_value,
        )


def _trace_merged_resp(
    cumulated: Any,
    func: Callable,
    event: EventContext,
    span: Any,
) -> None:
    cumulated_copy = deepcopy(cumulated)

    merged_output = func(cumulated_copy)
    end_payload = _obj_to_dict(merged_output)
    output_mine_type, output_value = _get_ot_type_and_value(end_payload)
    span.set_attribute(
        "output.mine_type",
        output_mine_type,
    )
    span.set_attribute(
        "output.value",
        output_value,
    )
    event.on_end(
        payload=end_payload,
    )


def _get_ot_type_and_value(payload: Any) -> tuple[MineType, Any]:
    if isinstance(payload, dict):
        mine_type = MineType.JSON
        value = json.dumps(payload, ensure_ascii=False)
    else:
        mine_type = MineType.TEXT
        if isinstance(payload, (str, int, float, bool)):
            value = payload
        else:
            value = str(payload)
    return mine_type, value


def _validate_trace_options(
    trace_type: Union[TraceType, str, None] = None,
    trace_name: Optional[str] = None,
    is_root_span: Optional[bool] = None,
    function_name: Optional[str] = None,
    parent_ctx: Optional[Any] = None,
) -> tuple[str, str | None, bool | None]:
    out_is_root_span = (
        is_root_span
        and parent_ctx is None
        and not _parent_span_context.get(None)
    )

    if out_is_root_span:
        out_trace_type = TraceType.CHAIN
        out_trace_name = "FullCodeApp"
    else:
        if trace_type:
            if isinstance(trace_type, str):
                out_trace_type = TraceType(trace_type)
            else:
                out_trace_type = trace_type
        else:
            out_trace_type = TraceType.OTHER

        if trace_name:
            out_trace_name = trace_name
        else:
            if function_name:
                out_trace_name = function_name
            else:
                out_trace_name = str(out_trace_type).lower()

    return out_trace_type, out_trace_name, out_is_root_span


def _obj_to_dict(obj: Any) -> Any:
    """Convert an object to a dictionary representation for tracing.

    Args:
        obj (Any): The object to convert.

    Returns:
        Any: The dictionary representation of the object, or the object
            itself if it's a primitive type.
    """
    if obj is None:
        return {}
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, dict):
        return {k: _obj_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, set, tuple)):
        return [_obj_to_dict(item) for item in obj]
    elif isinstance(obj, BaseModel):
        return obj.model_dump()
    else:
        result = None
        try:
            result = str(obj)
        except Exception as e:
            print(f"{obj} str method failed with error: {e}")
        return result


def _function_accepts_kwargs(func: Any) -> bool:
    """Check if a function accepts **kwargs parameter.

    Args:
        func (Any): The function to check.

    Returns:
        bool: True if the function accepts **kwargs, False otherwise.
    """
    try:
        sig = inspect.signature(func)
        return any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )
    except (ValueError, TypeError):
        return False


def _get_service_name() -> str:
    """Get service name
    Returns:
        str: The extracted service name, or the original name if extraction
        fails.
    """

    service_name = os.getenv("SERVICE_NAME") or os.getenv("DS_SVC_NAME")
    if not service_name:
        service_name = "agentscope_runtime-service"

    pattern = r"deployment\.([^-]+(?:-[^-]+)*?)(?=-[^-]+-[^-]+$)"
    match = re.search(pattern, service_name)
    if match:
        return match.group(1)
    else:
        return service_name


def _get_tracer() -> Tracer:
    handlers: list[TracerHandler] = []
    if _str_to_bool(os.getenv("TRACE_ENABLE_LOG", "true")):
        handlers.append(LocalLogHandler(enable_console=True))

    tracer = Tracer(handlers=handlers)
    return tracer


# TODO: support more tracing protocols and platforms
def _get_ot_tracer() -> ot_trace.Tracer:
    """Get the OpenTelemetry tracer.

    Returns:
        ot_trace.Tracer: The OpenTelemetry tracer instance.
    """

    resource = Resource(
        attributes={
            SERVICE_NAME: _get_service_name(),
            SERVICE_VERSION: os.getenv("SERVICE_VERSION", "1.0.0"),
            "source": "agentscope_runtime-source",
        },
    )
    provider = TracerProvider(resource=resource)
    if _str_to_bool(os.getenv("TRACE_ENABLE_REPORT", "false")):
        span_exporter = BatchSpanProcessor(
            OTLPSpanGrpcExporter(
                endpoint=os.getenv("TRACE_ENDPOINT", ""),
                headers=f"Authentication="
                f"{os.getenv('TRACE_AUTHENTICATION', '')}",
            ),
        )
        provider.add_span_processor(span_exporter)

    if _str_to_bool(os.getenv("TRACE_ENABLE_DEBUG", "false")):
        span_logger = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(span_logger)

    tracer = ot_trace.get_tracer(
        "agentscope_runtime",
        tracer_provider=provider,
    )
    return tracer


_ot_tracer = _get_ot_tracer()

_tracer = _get_tracer()
