import logging
import sys
from logging.handlers import RotatingFileHandler

from src.config import ConfMainKey, Config


class LoggingHelper:

    DEFAULT_LOGLEVEL = logging.INFO
    DEFAULT_LOG_MAX_BYTES = 1048576
    DEFAULT_LOG_MAX_COUNT = 10

    @classmethod
    def init(cls, config):
        handlers = []

        format_with_ts = '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
        format_no_ts = '[%(levelname)8s] %(name)s: %(message)s'

        log_file = Config.get_str(config, ConfMainKey.LOG_FILE)
        log_level = Config.get_loglevel(config, ConfMainKey.LOG_LEVEL, cls.DEFAULT_LOGLEVEL)
        print_console = Config.get_bool(config, ConfMainKey.LOG_PRINT, False)
        runs_as_systemd = Config.get_bool(config, ConfMainKey.SYSTEMD, False)

        if log_file:
            max_bytes = Config.get_int(config, ConfMainKey.LOG_MAX_BYTES, cls.DEFAULT_LOG_MAX_BYTES)
            max_count = Config.get_int(config, ConfMainKey.LOG_MAX_COUNT, cls.DEFAULT_LOG_MAX_COUNT)
            handler = RotatingFileHandler(
                log_file,
                maxBytes=int(max_bytes),
                backupCount=int(max_count)
            )
            formatter = logging.Formatter(format_with_ts)
            handler.setFormatter(formatter)
            handlers.append(handler)

        if runs_as_systemd:
            log_format = format_no_ts
        else:
            log_format = format_with_ts

        if print_console or runs_as_systemd:
            handlers.append(logging.StreamHandler(sys.stdout))

        logging.basicConfig(
            format=log_format,
            level=log_level,
            handlers=handlers
        )
