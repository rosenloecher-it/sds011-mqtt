import datetime
import json
import logging
from enum import Enum

from tzlocal import get_localzone

from src.config import ConfMainKey
from src.sds011 import SDS011

_logger = logging.getLogger("sensor")


class ExportKey(Enum):
    PM25 = "PM25"
    PM10 = "PM10"
    STATE = "STATE"
    TIMESTAMP = "TIMESTAMP"


class StateValue(Enum):
    OK = "OK"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"

    def __str__(self):
        return self.__repr__()

    def __repr__(self) -> str:
        return '{}'.format(self.name)

    @classmethod
    def is_success(cls, state):
        return state in [cls.CLOSED, cls.OPEN, cls.TILTED]


class Sensor:

    def __init__(self):
        self._mqtt = None
        self._sensor = None
        self._active = False
        self._measurment = {}

    def __del__(self):
        self.close()

    def set_mqtt(self, mqtt):
        self._mqtt = mqtt

    def open(self, config):
        port = config.get(ConfMainKey.SERIAL_PORT.value)
        self._sensor = SDS011(port, use_query_mode=True)
        self._active = False  # don't know the state!

    def close(self):
        if self._sensor is not None:
            self.sleep()
            self._sensor = None

    def warmup(self):
        self._sensor.sleep(sleep=False)
        self._active = True
        _logger.debug("warmup")

    def sleep(self):
        self._active = False
        if self._sensor:
            self._sensor.sleep()
            _logger.debug("sleep")

    def measure(self):
        if not self._active:
            raise RuntimeError("warm up sensor before measure!")

        now = self._now()
        m = self._sensor.query()

        self._measurment = {
            ExportKey.PM25.value: m[0],
            ExportKey.PM10.value: m[1],
            ExportKey.STATE.value: StateValue.OK.value,
            ExportKey.TIMESTAMP.value: now.isoformat()
        }
        _logger.info("measurment: %s", self._measurment)

    def publish(self, reset_measurment: bool = True):
        if self._measurment:
            json_text = json.dumps(self._measurment)
            self._mqtt.publish(json_text)

        if reset_measurment:
            self._measurment = {}
        pass

    def _now(self):
        """overwrite in test to simulate different times"""
        return datetime.datetime.now(tz=get_localzone())
