# -*- coding: utf-8 -*-
import logging
import os


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[34m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[41m\033[97m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        level = f"{color}{record.levelname}{self.RESET}"

        full_path = record.pathname
        cwd = os.getcwd()
        if full_path.startswith(cwd):
            full_path = full_path[len(cwd) + 1 :]

        prefix = f"{level} {full_path}:{record.lineno}"
        original_msg = super().format(record)

        return f"{prefix} | {original_msg}"


def setup_logger(level=logging.INFO):
    log_format = "%(asctime)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    formatter = ColorFormatter(log_format, datefmt)
    logger = logging.getLogger()
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
