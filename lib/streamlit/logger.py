# Copyright 2018-2022 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Logging module."""

import logging
import sys
from typing import Dict, Union

from streamlit import config

# Loggers for each name are saved here.
LOGGERS: Dict[str, logging.Logger] = {}

# The global log level is set here across all names.
LOG_LEVEL = logging.INFO

DEFAULT_LOG_MESSAGE = "%(asctime)s %(levelname) -7s " "%(name)s: %(message)s"


def set_log_level(level: Union[str, int]) -> None:
    """Set log level."""
    logger = get_logger(__name__)

    if isinstance(level, str):
        level = level.upper()
    if level in ["CRITICAL", logging.CRITICAL]:
        log_level = logging.CRITICAL
    elif level in ["ERROR", logging.ERROR]:
        log_level = logging.ERROR
    elif level in ["WARNING", logging.WARNING]:
        log_level = logging.WARNING
    elif level in ["INFO", logging.INFO]:
        log_level = logging.INFO
    elif level in ["DEBUG", logging.DEBUG]:
        log_level = logging.DEBUG
    else:
        msg = 'undefined log level "%s"' % level
        logger.critical(msg)
        sys.exit(1)

    for log in LOGGERS.values():
        log.setLevel(log_level)

    global LOG_LEVEL
    LOG_LEVEL = log_level


def setup_formatter(logger: logging.Logger) -> None:
    """Set up the console formatter for a given logger."""

    # Deregister any previous console loggers.
    if hasattr(logger, "streamlit_console_handler"):
        logger.removeHandler(logger.streamlit_console_handler)  # type: ignore[attr-defined]

    logger.streamlit_console_handler = logging.StreamHandler()  # type: ignore[attr-defined]

    if config._config_options:
        # logger is required in ConfigOption.set_value
        # Getting the config option before the config file has been parsed
        # can create an infinite loop
        message_format = config.get_option("logger.messageFormat")
    else:
        message_format = DEFAULT_LOG_MESSAGE
    formatter = logging.Formatter(fmt=message_format)
    formatter.default_msec_format = "%s.%03d"
    logger.streamlit_console_handler.setFormatter(formatter)  # type: ignore[attr-defined]

    # Register the new console logger.
    logger.addHandler(logger.streamlit_console_handler)  # type: ignore[attr-defined]


def update_formatter() -> None:
    for log in LOGGERS.values():
        setup_formatter(log)


def init_tornado_logs() -> None:
    """Initialize tornado logs."""
    global LOGGER

    # http://www.tornadoweb.org/en/stable/log.html
    logs = ["access", "application", "general"]
    for log in logs:
        name = "tornado.%s" % log
        get_logger(name)

    logger = get_logger(__name__)
    logger.debug("Initialized tornado logs")


def get_logger(name: str) -> logging.Logger:
    """Return a logger.

    Parameters
    ----------
    name : str
        The name of the logger to use. You should just pass in __name__.

    Returns
    -------
    Logger

    """
    if name in LOGGERS.keys():
        return LOGGERS[name]

    logger = logging.getLogger() if name == "root" else logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False
    setup_formatter(logger)

    LOGGERS[name] = logger

    return logger
