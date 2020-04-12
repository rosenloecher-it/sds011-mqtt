#!/usr/bin/env python3

import logging.handlers
import sys

from src.config import Config
from src.logging_helper import LoggingHelper
from src.process import Process

_logger = logging.getLogger("main")


def main():
    process = None

    try:
        config = {}
        Config.load(config)

        LoggingHelper.init(config)

        process = Process()
        process.open(config)
        process.run()

        return 0

    except KeyboardInterrupt:
        return 0

    except Exception as ex:
        _logger.exception(ex)
        return 1

    finally:
        if process is not None:
            process.close()


if __name__ == '__main__':
    sys.exit(main())
