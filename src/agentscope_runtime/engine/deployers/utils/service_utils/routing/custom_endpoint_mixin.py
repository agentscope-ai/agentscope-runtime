# -*- coding: utf-8 -*-
import functools
import inspect
import logging
import json
from typing import Callable, List, Any
from dataclasses import asdict, is_dataclass

from pydantic import BaseModel
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class CustomEndpointMixin:
    def register_single_custom_endpoint(
        self,
        path: str,
        handler: Callable,
        methods: List[str],
    ):
        """Register a single custom endpoint with proper async/sync
        handling."""

        tags = ["custom"]

        # Regular endpoint handling with automatic parameter parsing
        # Check in the correct order: async gen > sync gen > async &
        # sync
        if inspect.isasyncgenfunction(
            handler,
        ) or inspect.isgeneratorfunction(handler):
            wrapped_handler = (
                CustomEndpointMixin._create_streaming_parameter_wrapper(
                    handler,
                )
            )
            self.add_api_route(
                path,
                wrapped_handler,
                methods=methods,
                tags=tags,
                response_model=None,
            )
        else:
            # Non-streaming endpoint -> wrapper that preserves
            # handler signature
            wrapped_handler = CustomEndpointMixin._create_handler_wrapper(
                handler,
            )
            self.add_api_route(
                path,
                wrapped_handler,
                methods=methods,
                response_model=None,
                tags=tags,
            )

    @staticmethod
    def _create_handler_wrapper(handler: Callable):
        """Create a wrapper for a handler that preserves function signature.

        This wrapper maintains the handler's signature to enable FastAPI's
        automatic parameter parsing and dependency injection. For async
        handlers, it returns an async wrapper; for sync handlers,
        it returns a sync wrapper.

        Args:
            handler: The handler function to wrap

        Returns:
            A wrapped handler that preserves the original function signature
        """

        is_awaitable = inspect.iscoroutinefunction(handler)
        if is_awaitable:

            @functools.wraps(handler)
            async def wrapped_handler(*args, **kwargs):
                return await handler(*args, **kwargs)

            wrapped_handler.__signature__ = inspect.signature(handler)
            return wrapped_handler
        else:

            @functools.wraps(handler)
            def wrapped_handler(*args, **kwargs):
                return handler(*args, **kwargs)

            wrapped_handler.__signature__ = inspect.signature(handler)
            return wrapped_handler

    @staticmethod
    def _to_sse_event(item: Any) -> str:
        """Normalize streaming items into JSON-serializable structures."""

        def _serialize(value: Any, depth: int = 0):
            # pylint:disable=too-many-return-statements
            if depth > 20:
                return f"<too-deep-level-{depth}-{str(value)}>"

            if isinstance(value, (list, tuple, set)):
                return [_serialize(i, depth=depth + 1) for i in value]
            elif isinstance(value, dict):
                return {
                    k: _serialize(v, depth=depth + 1) for k, v in value.items()
                }
            elif isinstance(value, (str, int, float, bool, type(None))):
                return value
            elif isinstance(value, BaseModel):
                return value.model_dump()
            elif is_dataclass(value):
                return asdict(value)

            for attr in ("to_map", "to_dict"):
                method = getattr(value, attr, None)
                if callable(method):
                    return method()
            return str(value)

        serialized = _serialize(item, depth=0)

        return f"data: {json.dumps(serialized, ensure_ascii=False)}\n\n"

    @staticmethod
    def _create_streaming_parameter_wrapper(
        handler: Callable,
    ):
        """Create a wrapper for streaming handlers that handles parameter
        parsing."""
        is_async_gen = inspect.isasyncgenfunction(handler)

        # NOTE:
        # -----
        # FastAPI >= 0.123.5 uses Dependant.is_coroutine_callable, which in
        # turn unwraps callables via inspect.unwrap() and then inspects the
        # unwrapped target to decide whether it is a coroutine function /
        # generator / async generator.
        #
        # If we decorate an async-generator handler with
        # functools.wraps(handler), FastAPI will unwrap back to the original
        # async-generator function and *misclassify* the endpoint as
        # non-coroutine. It will then call our async wrapper *without awaiting
        # it*, and later try to JSON-encode the resulting coroutine object,
        # causing errors like:
        # TypeError("'coroutine' object is not iterable")
        #
        # To avoid that, we deliberately do NOT use functools.wraps() here.
        # Instead, we manually copy the key metadata (name, qualname, doc,
        # module, and signature) from the original handler, but we do NOT set
        # __wrapped__. This ensures:
        #   * FastAPI sees the wrapper itself as the callable (an async def),
        #     so Dependant.is_coroutine_callable is True, and it is properly
        #     awaited.
        #   * FastAPI still sees the correct signature for parameter parsing.

        if is_async_gen:

            async def wrapped_handler(*args, **kwargs):
                async def generate():
                    try:
                        async for chunk in handler(*args, **kwargs):
                            yield CustomEndpointMixin._to_sse_event(
                                chunk,
                            )
                    except Exception as e:
                        logger.error(
                            f"Error in streaming handler: {e}",
                            exc_info=True,
                        )
                        err_event = {
                            "error": str(e),
                            "error_type": e.__class__.__name__,
                            "message": "Error in streaming generator",
                        }
                        yield CustomEndpointMixin._to_sse_event(err_event)

                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                )

        else:

            def wrapped_handler(*args, **kwargs):
                def generate():
                    try:
                        for chunk in handler(*args, **kwargs):
                            yield CustomEndpointMixin._to_sse_event(chunk)
                    except Exception as e:
                        logger.error(
                            f"Error in streaming handler: {e}",
                            exc_info=True,
                        )
                        err_event = {
                            "error": str(e),
                            "error_type": e.__class__.__name__,
                            "message": "Error in streaming generator",
                        }
                        yield CustomEndpointMixin._to_sse_event(err_event)

                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                )

        # Manually propagate essential metadata without creating a __wrapped__
        # chain that would confuse FastAPI's unwrap logic.
        wrapped_handler.__name__ = getattr(
            handler,
            "__name__",
            wrapped_handler.__name__,
        )
        wrapped_handler.__qualname__ = getattr(
            handler,
            "__qualname__",
            wrapped_handler.__qualname__,
        )
        wrapped_handler.__doc__ = getattr(
            handler,
            "__doc__",
            wrapped_handler.__doc__,
        )
        wrapped_handler.__module__ = getattr(
            handler,
            "__module__",
            wrapped_handler.__module__,
        )
        wrapped_handler.__signature__ = inspect.signature(handler)

        # Make sure FastAPI doesn't see any stale __wrapped__ pointing back to
        # the original async-generator; if present, remove it.

        return wrapped_handler
