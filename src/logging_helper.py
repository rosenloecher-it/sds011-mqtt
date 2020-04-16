import logging
import sys
from logging.handlers import RotatingFileHandler

from src.config import ConfMainKey


class LoggingHelper:

    @classmethod
    def init(cls, config):
        handlers = []

        format_with_ts = '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
        format_no_ts = '[%(levelname)8s] %(name)s: %(message)s'

        log_level = config[ConfMainKey.LOG_LEVEL.value]
        log_file = config[ConfMainKey.LOG_FILE.value]
        print_console = config[ConfMainKey.LOG_PRINT.value]
        runs_as_systemd = config[ConfMainKey.SYSTEMD.value]

        if log_file:
            max_bytes = config[ConfMainKey.LOG_MAX_BYTES.value]
            max_count = config[ConfMainKey.LOG_MAX_COUNT.value]
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
