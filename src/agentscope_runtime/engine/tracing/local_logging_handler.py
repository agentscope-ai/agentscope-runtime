# -*- coding: utf-8 -*-
import json
import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from . import TracingUtil
from .base import TracerHandler

DEFAULT_LOG_NAME = "agentscope-runtime"

INFO_LOG_FILE_NAME = "info"
ERROR_LOG_FILE_NAME = "error"
LOG_EXTENSION = "log"
DS_SVC_ID = os.getenv("DS_SVC_ID", "test_id")
DS_SVC_NAME = os.getenv("DS_SVC_NAME", "test_name")


class LogContext(BaseModel):
    """Pydantic model for log context data."""

    time: str = ""
    step: str = ""
    model: str = ""
    user_id: str = ""
    task_id: str = ""
    code: str = ""
    message: str = ""
    request_id: str = ""
    context: Dict = {}
    interval: Dict = {}
    service_id: str = ""
    service_name: str = ""
    ds_service_id: str = ""
    ds_service_name: str = ""

    model_config = ConfigDict(extra="allow")


class JsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs in llm chat format.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The formatted log record as a JSON string.
        """
        log_record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "step": getattr(record, "step", None),
            "model": getattr(record, "model", None),
            "user_id": getattr(record, "user_id", None),
            "code": getattr(record, "code", None),
            "message": record.getMessage(),
            "task_id": getattr(record, "task_id", None),
            "request_id": getattr(
                record,
                "request_id",
                TracingUtil.get_request_id(),
            ),
            "context": getattr(record, "context", None),
            "interval": getattr(record, "interval", None),
            "ds_service_id": DS_SVC_ID,
            "ds_service_name": DS_SVC_NAME,
        }
        # Clean up any extra fields that are None (not provided)
        log_record = {k: v for k, v in log_record.items() if v is not None}
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)


class LocalLogHandler(TracerHandler):
    """llm chat log handler for structured JSON logging."""

    def __init__(
        self,
        log_level: int = logging.INFO,
        log_file_name: Optional[str] = None,
        log_dir: str = f"{os.getcwd()}/logs",
        max_bytes: int = 1024 * 1024 * 1024,
        backup_count: int = 7,
        enable_console: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the llm chat log handler.

        Args:
            log_level (int): The logging level. Defaults to logging.INFO.
            log_file_name (Optional[str]): Prefix for log file names.
                            Defaults to None.
            log_dir (str): Directory to save log files. Defaults to "./logs".
            max_bytes (int): Maximum size in bytes for a single log file.
                    Defaults to 1GB.
            backup_count (int): Number of log files to keep. Defaults to 7.
            enable_console (bool): Whether to enable console logging.
                            Defaults to False.
            **kwargs (Any): Additional keyword arguments (unused but kept for
                            compatibility).
        """
        # Store kwargs for potential future use
        self._extra_kwargs = kwargs
        self.logger = logging.getLogger(DEFAULT_LOG_NAME)
        if enable_console:
            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
            self.logger.addHandler(handler)
        os.makedirs(log_dir, exist_ok=True)
        self._set_file_handle(
            log_dir=log_dir,
            log_file_name=log_file_name,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )

        self.logger.setLevel(log_level)

    def _set_file_handle(
        self,
        log_dir: str,
        log_file_name: Optional[str],
        max_bytes: int,
        backup_count: int,
    ) -> None:
        """Set up file handlers for logging.

        Args:
            log_dir (str): Directory to save the log files.
            log_file_name (Optional[str]): Prefix name of log file name.
            max_bytes (int): Maximum size in bytes for a single log file.
            backup_count (int): The number of log files to keep.
        """
        log_file_name_prefix = f"{log_file_name}-" if log_file_name else ""

        # Create file handlers with JsonFormatter
        info_file_path = os.path.join(
            log_dir,
            f"{log_file_name_prefix}{INFO_LOG_FILE_NAME}.{LOG_EXTENSION}."
            f"{os.getpid()}",
        )
        info_file_handler = RotatingFileHandler(
            info_file_path,
            mode="a",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        info_file_handler.setFormatter(JsonFormatter())
        info_file_handler.setLevel(logging.INFO)

        # Create error file handler
        error_file_path = os.path.join(
            log_dir,
            f"{log_file_name_prefix}{ERROR_LOG_FILE_NAME}.{LOG_EXTENSION}."
            f"{os.getpid()}",
        )
        error_file_handler = RotatingFileHandler(
            error_file_path,
            mode="a",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        error_file_handler.setFormatter(JsonFormatter())
        error_file_handler.setLevel(logging.ERROR)

        # Add handlers to the logger
        self.logger.addHandler(info_file_handler)
        self.logger.addHandler(error_file_handler)

    @staticmethod
    def _deep_update(original: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Recursively update a dictionary with another dictionary.

        Args:
            original (Dict[str, Any]): The original dictionary to update.
            update (Dict[str, Any]): The dictionary containing updates.
        """
        if not isinstance(original, dict):
            return

        for key, value in update.items():
            if (
                isinstance(value, dict)
                and key in original
                and isinstance(original[key], dict)
            ):
                LocalLogHandler._deep_update(original[key], value)
            else:
                original[key] = value

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
        step = f"{event_name}_start"
        request_id = TracingUtil.get_request_id()
        context = payload.get("context", payload)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        interval = {"type": step, "cost": 0}
        runtime_context = LogContext(
            time=timestamp,
            step=step,
            interval=interval,
            context=context,
            request_id=request_id,
        )
        try:
            self.logger.info(
                runtime_context.message,
                extra=runtime_context.model_dump(exclude={"message"}),
            )
        except Exception as e:
            import traceback

            print(traceback.format_exc())
            print(e)

    def on_end(
        self,
        event_name: str,
        start_payload: Dict[str, Any],
        end_payload: Any,
        start_time: float,
        **kwargs: Any,
    ) -> None:
        """Handle the end of a trace event.

        Args:
            event_name (str): The name of event being traced.
            start_payload (Dict[str, Any]): The payload data from event start.
            end_payload (Any): The payload data from event end.
            start_time (float): The timestamp when the event started.
            **kwargs (Any): Additional keyword arguments.
        """

        request_id = TracingUtil.get_request_id()

        if isinstance(end_payload, dict):
            context = end_payload
        else:
            context = {}
            if end_payload is not None:
                context["output"] = end_payload

        step = f"{event_name}_end"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        duration = time.time() - start_time
        interval = {"type": step, "cost": f"{duration:.3f}"}
        runtime_context = LogContext(
            time=timestamp,
            step=step,
            interval=interval,
            context=context,
            request_id=request_id,
        )
        self.logger.info(
            runtime_context.message,
            extra=runtime_context.model_dump(exclude={"message"}),
        )

    def on_log(self, message: str, **kwargs: Any) -> None:
        """Handle a log message during tracing.

        Args:
            message (str): The log message.
            **kwargs (Any): Additional keyword arguments including:
                - step_suffix: Optional suffix for step identification
                - event_type: The type of event being traced
                - payload: The payload data
                - start_time: The timestamp when the event started
                - start_payload: The payload data from event start
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        if "step_suffix" in kwargs:
            step_suffix = kwargs["step_suffix"]
            event_name = kwargs["event_name"]
            payload = kwargs["payload"]
            start_time = kwargs["start_time"]
            start_payload = kwargs["start_payload"]

            LocalLogHandler._deep_update(payload, start_payload)

            step = f"{event_name}_{step_suffix}"
            duration = time.time() - start_time
            interval = {"type": step, "cost": f"{duration:.3f}"}
        else:
            step = ""
            interval = {"type": step, "cost": "0"}
            payload = {}

        request_id = TracingUtil.get_request_id()

        if isinstance(payload, dict):
            context = payload
        else:
            context = {"payload": str(payload)}

        runtime_context = LogContext(
            time=timestamp,
            step=step,
            interval=interval,
            context=context,
            message=message,
            request_id=request_id,
        )
        self.logger.info(
            runtime_context.message,
            extra=runtime_context.model_dump(exclude={"message"}),
        )

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
            event_name (str): The name of event being traced.
            start_payload (Dict[str, Any]): The payload data from event start.
            error (Exception): The exception that occurred.
            start_time (float): The timestamp when the event started.
            traceback_info (str): The traceback information.
            **kwargs (Any): Additional keyword arguments.
        """
        step = f"{event_name}_error"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        duration = time.time() - start_time
        interval = {"type": step, "cost": f"{duration:.3f}"}
        if "context" not in start_payload:
            start_payload["context"] = {}
        start_payload["context"].update(
            {"type": error.__class__.__name__, "details": traceback_info},
        )
        runtime_context = LogContext(
            time=timestamp,
            step=step,
            interval=interval,
            code=error.__class__.__name__,
            message=str(error),
            **start_payload,
        )
        self.logger.error(
            runtime_context.message,
            extra=runtime_context.model_dump(exclude={"message"}),
        )
