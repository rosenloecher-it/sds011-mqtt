import datetime
import json
import logging
from enum import Enum
from serial import SerialException

from tzlocal import get_localzone

from src.config import ConfMainKey, Config
from src.sds011 import SDS011

_logger = logging.getLogger(__name__)


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


class SensorError(RuntimeError):
    pass


class Sensor:

    MAX_ERRORS_TO_IGNORE_DEFAULT = 3

    def __init__(self, config):
        self._sensor = None
        self._mqtt = None
        self._warmup = False
        self._measurment = {}

        self._error_ignored = 0
        self._max_errors_to_ignore = Config.post_process_int(config,
                                                             ConfMainKey.SENSOR_MAX_ERRORS_TO_IGNORE,
                                                             self.MAX_ERRORS_TO_IGNORE_DEFAULT)
        if self._max_errors_to_ignore < 0:
            self._max_errors_to_ignore = 0xffffffff

        self._port = config.get(ConfMainKey.SERIAL_PORT.value)

    def __del__(self):
        self.close()

    def set_mqtt(self, mqtt):
        self._mqtt = mqtt

    def open(self, warmup: bool = False):
        self._sensor = SDS011(self._port, use_query_mode=True)
        self._sensor.open()
        self._warmup = False  # don't know the state!

        _logger.debug("opened")

        if warmup:
            self.warmup()

    def close(self):
        if self._sensor is not None:
            try:
                self._sensor.sleep()
            except Exception as ex:
                _logger.error("self._sensor.sleep() failed")
                _logger.exception(ex)

            try:
                self._sensor.close()
                _logger.debug("closed")
            except Exception as ex:
                _logger.error("self._sensor.close() failed")
                _logger.exception(ex)
            finally:
                self._sensor = None
                self._warmup = False

    def warmup(self):
        if self._sensor:
            self._sensor.sleep(sleep=False)
            self._warmup = True
            _logger.debug("warming up")

    def sleep(self):
        self._warmup = False
        if self._sensor:
            self._sensor.sleep()
            _logger.debug("sent to sleep")

    def _set_measurment(self, state: StateValue, pm10: float, pm25: float):
        now = self._now()

        self._measurment = {
            ExportKey.STATE.value: state.value,
            ExportKey.PM10.value: pm10,
            ExportKey.PM25.value: pm25,
            ExportKey.TIMESTAMP.value: now.isoformat(),
        }
        _logger.info("measurment: %s", self._measurment)

    def measure(self):
        if self._sensor is None:
            raise SensorError("sensor was not opened!")
        if not self._warmup:
            raise SensorError("sensor was not warmed up before measurement!")

        try:
            result = self._sensor.query()
        except SerialException as ex:
            self._error_ignored += 1
            if self._error_ignored > self._max_errors_to_ignore:
                raise SensorError(ex)

            _logger.error("self._sensor.query() failed!")
            _logger.exception(ex)
            self._set_measurment(StateValue.ERROR, None, None)
        else:
            if result is None:
                self._error_ignored += 1
                if self._error_ignored > self._max_errors_to_ignore:
                    raise SensorError("no measurment (None)!")

                _logger.error("no measurment (None)!")
                self._set_measurment(StateValue.ERROR, None, None)
            else:
                self._set_measurment(StateValue.OK, pm10=result[1], pm25=result[0])
            self._error_ignored = 0

    def publish(self, reset_measurment: bool = True):
        if self._mqtt is None:
            raise SensorError("no mqtt set!")
        if self._measurment:
            json_text = json.dumps(self._measurment)
            self._mqtt.publish(json_text)
        if reset_measurment:
            self._measurment = {}

    def _now(self):
        """overwrite in test to simulate different times"""
        return datetime.datetime.now(tz=get_localzone())
