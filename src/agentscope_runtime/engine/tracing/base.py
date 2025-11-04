# -*- coding: utf-8 -*-
import time
import traceback
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, List

from opentelemetry.propagate import inject, extract
from opentelemetry.context.context import Context


# Handler Interface
class TracerHandler(ABC):
    """Abstract base class for tracer handlers."""

    @abstractmethod
    def on_start(
        self,
        event_name: str,
        payload: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Handle the start of a trace event.

        Args:
            event_name (str): The name of event being traced.
            payload (Dict[str, Any]): The payload data for the event.
            **kwargs (Any): Additional keyword arguments.
        """
        raise NotImplementedError("Subclasses must implement on_start method")

    @abstractmethod
    def on_end(
        self,
        event_name: str,
        start_payload: Dict[str, Any],
        end_payload: Dict[str, Any],
        start_time: float,
        **kwargs: Any,
    ) -> None:
        """Handle the end of a trace event.

        Args:
            event_name (str): The name of event being traced.
            start_payload (Dict[str, Any]): The payload data from event start.
            end_payload (Dict[str, Any]): The payload data from event end.
            start_time (float): The timestamp when the event started.
            **kwargs (Any): Additional keyword arguments.
        """
        raise NotImplementedError("Subclasses must implement on_end method")

    @abstractmethod
    def on_log(self, message: str, **kwargs: Any) -> None:
        """Handle a log message during tracing.

        Args:
            message (str): The log message.
            **kwargs (Any): Additional keyword arguments.
        """
        raise NotImplementedError("Subclasses must implement on_log method")

    @abstractmethod
    def on_error(
        self,
        event_name: str,
        start_payload: Dict[str, Any],
        error: Exception,
        start_time: float,
        traceback_info: str,
        **kwargs: Any,
    ) -> None:
        """Handle an error during tracing.

        Args:
            event_name (str): The type of event being traced.
            start_payload (Dict[str, Any]): The payload data from event start.
            error (Exception): The exception that occurred.
            start_time (float): The timestamp when the event started.
            traceback_info (str): The traceback information.
            **kwargs (Any): Additional keyword arguments.
        """
        raise NotImplementedError("Subclasses must implement on_error method")


# 新增基础的LogHandler类
class BaseLogHandler(TracerHandler):
    """Basic log handler implementation using Python's logging module."""

    import logging

    logger = logging.getLogger(__name__)

    def on_start(
        self,
        event_name: str,
        payload: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Log the start of a trace event.

        Args:
            event_name (str): The name of event being traced.
            payload (Dict[str, Any]): The payload data for the event.
            **kwargs (Any): Additional keyword arguments.
        """
        self.logger.info(f"Event {event_name} started with payload: {payload}")

    def on_end(
        self,
        event_name: str,
        start_payload: Dict[str, Any],
        end_payload: Dict[str, Any],
        start_time: float,
        **kwargs: Any,
    ) -> None:
        """Log the end of a trace event.

        Args:
            event_name (str): The name of event being traced.
            start_payload (Dict[str, Any]): The payload data from event start.
            end_payload (Dict[str, Any]): The payload data from event end.
            start_time (float): The timestamp when the event started.
            **kwargs (Any): Additional keyword arguments.
        """
        self.logger.info(
            f"Event {event_name} ended with start payload: {start_payload}, "
            f"end payload: {end_payload}, duration: "
            f"{time.time() - start_time} seconds, kwargs: {kwargs}",
        )

    def on_log(self, message: str, **kwargs: Any) -> None:
        """Log a message during tracing.

        Args:
            message (str): The log message.
            **kwargs (Any): Additional keyword arguments.
        """
        self.logger.info(f"Log: {message}")

    def on_error(
        self,
        event_name: str,
        start_payload: Dict[str, Any],
        error: Exception,
        start_time: float,
        traceback_info: str,
        **kwargs: Any,
    ) -> None:
        """Log an error during tracing.

        Args:
            event_name (str): The name of event being traced.
            start_payload (Dict[str, Any]): The payload data from event start.
            error (Exception): The exception that occurred.
            start_time (float): The timestamp when the event started.
            traceback_info (str): The traceback information.
            **kwargs (Any): Additional keyword arguments.
        """
        self.logger.error(
            f"Error in event {event_name} with payload: {start_payload}, "
            f"error: {error}, "
            f"traceback: {traceback_info}, duration: "
            f"{time.time() - start_time} seconds, kwargs: {kwargs}",
        )


class Tracer:
    """
    Tracer class for logging events
    usage:
    with tracer.event(TraceType.LLM, payload) as event:
        event.log("message")
        ""...logic here...""
        end_payload = {xxx}
        # optional on_end call for additional payload and kwargs
        event.on_end(end_payload, if_success=True)
    """

    def __init__(self, handlers: List[TracerHandler]):
        """Initialize the tracer with a list of handlers.

        Args:
            handlers (List[TracerHandler]): List of handlers to process trace
            events.
        """
        self.handlers = handlers

    @contextmanager
    def event(
        self,
        span: Any,
        event_name: str,
        payload: Dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """Create a context manager for tracing an event.

        Args:
            span(Any): span of event
            event_name (str): The name of event being traced.
            payload (Dict[str, Any]): The payload data for the event.
            **kwargs (Any): Additional keyword arguments.

        Yields:
            EventContext: The event context for logging and managing the trace.
        """
        start_time = time.time()

        for handle in self.handlers:
            handle.on_start(
                event_name,
                payload,
                **kwargs,
            )

        event_context = EventContext(
            span,
            self.handlers,
            event_name,
            start_time,
            payload,
        )

        try:
            yield event_context
        except Exception as e:
            traceback_info = traceback.format_exc()
            for handle in self.handlers:
                handle.on_error(
                    event_name,
                    payload,
                    e,
                    start_time,
                    traceback_info=traceback_info,
                )
            raise

        event_context.finalize(payload)

    def log(self, message: str, **kwargs: Any) -> None:
        """Log a message using all registered handlers.

        Args:
            message (str): The log message.
            **kwargs (Any): Additional keyword arguments.
        """
        for handle in self.handlers:
            handle.on_log(message, **kwargs)


class EventContext:
    """Context manager for individual trace events."""

    def __init__(
        self,
        span: Any,
        handlers: List[TracerHandler],
        event_name: str,
        start_time: float,
        start_payload: Dict[str, Any],
    ) -> None:
        """Initialize the event context.

        Args:
            handlers (List[TracerHandler]): List of handlers to process
            trace  events.
            event_name (str): The name of event being traced.
            start_time (float): The timestamp when the event started.
            start_payload (Dict[str, Any]): The payload data from event start.
        """
        self.span = span
        self.handlers = handlers
        self.event_name = event_name
        self.start_time = start_time
        self.start_payload = start_payload
        self.end_payload = {}
        self.kwargs = {}

    def on_end(self, payload: Dict[str, Any], **kwargs: Any) -> None:
        """Set the end payload and additional kwargs for the event.

        Args:
            payload (Dict[str, Any]): The payload data for event end.
            **kwargs (Any): Additional keyword arguments.
        """
        self.end_payload = payload
        self.kwargs = kwargs

    def on_log(self, message: str, **kwargs: Any) -> None:
        """Log a message within this event context.

        Args:
            message (str): The log message.
            **kwargs (Any): Additional keyword arguments.
        """
        kwargs["event_name"] = self.event_name
        kwargs["start_time"] = self.start_time
        kwargs["start_payload"] = self.start_payload
        for handle in self.handlers:
            handle.on_log(message, **kwargs)

    def finalize(self, start_payload: Dict[str, Any] = None) -> None:
        """Public method to finalize the event.

        Args:
            start_payload (Dict[str, Any], optional): The payload data from
            event start.
        """
        self._end(start_payload)

    def _end(self, start_payload: Dict[str, Any] = None) -> None:
        """Finalize the event by calling on_end for all handlers.

        Args:
            start_payload (Dict[str, Any], optional): The payload data from
            event start.
        """
        for handle in self.handlers:
            handle.on_end(
                self.event_name,
                start_payload,
                self.end_payload,
                self.start_time,
                **self.kwargs,
            )

    def set_attribute(self, key: str, value: Any) -> None:
        """Set attribute for the current span.

        Args:
            key (str): key of attribute
            value(str): value of attribute
        """

        self.span.set_attribute(key, value)

    def get_trace_context(self) -> Context:
        carrier = {}
        inject(carrier)
        context = extract(carrier)
        return context
