import datetime
import json
import logging
from enum import Enum

from tzlocal import get_localzone


_logger = logging.getLogger(__name__)


class ResultKey(Enum):
    PM25 = "PM25"
    PM10 = "PM10"
    STATE = "STATE"
    TIMESTAMP = "TIMESTAMP"


class ResultState(Enum):
    OK = "OK"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"
    DEACTIVATED = "DEACTIVATED"

    def __str__(self):
        return self.__repr__()

    def __repr__(self) -> str:
        return '{}'.format(self.name)


class Result:

    def __init__(self, state, pm10=None, pm25=None, timestamp=None):
        self.state = state if state else ResultState.ERROR
        self.pm10 = pm10
        self.pm25 = pm25
        self.timestamp = timestamp if timestamp else self._now()

    def create_message(self):
        payload = {
            ResultKey.PM10.value: self.pm10,
            ResultKey.PM25.value: self.pm25,
            ResultKey.STATE.value: self.state.value,
            ResultKey.TIMESTAMP.value: self.timestamp.isoformat(),
        }

        message = json.dumps(payload)
        return message

    @classmethod
    def _now(self):
        """overwrite in test to simulate different times"""
        return datetime.datetime.now(tz=get_localzone())
