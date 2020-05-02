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
        self._max_errors_to_ignore = Config.get_int(config,
                                                    ConfMainKey.SENSOR_MAX_ERRORS_TO_IGNORE,
                                                    self.MAX_ERRORS_TO_IGNORE_DEFAULT)
        if self._max_errors_to_ignore < 0:
            self._max_errors_to_ignore = 0xffffffff

        self._port = Config.get_str(config, ConfMainKey.SERIAL_PORT)

    def __del__(self):
        self.close()

    def set_mqtt(self, mqtt):
        self._mqtt = mqtt

    def open(self, warm_up: bool = False):
        self._sensor = SDS011(self._port, use_query_mode=True)
        self._sensor.open()
        self._warmup = False  # don't know the state!

        _logger.debug("opened")

        if warm_up:
            self.warm_up()

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

    def warm_up(self):
        if self._sensor:
            self._sensor.sleep(sleep=False)
            self._warmup = True
            _logger.info("warming up")

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
                pm25, pm10 = None, None
            else:
                pm25, pm10 = result

            if not self.check_value(pm25) or not self.check_value(pm10):
                self._error_ignored += 1
                if self._error_ignored > self._max_errors_to_ignore:
                    raise SensorError(f"{self._error_ignored} wrong measurments!")

                _logger.warning("(ignore) wrong measurment: pm25=%s; pm10=%s!", pm25, pm10)
                self._set_measurment(StateValue.ERROR, None, None)
            else:
                self._set_measurment(StateValue.OK, pm10=pm10, pm25=pm25)
                self._error_ignored = 0

    @classmethod
    def check_value(cls, value):
        if value is None:
            return False
        return 0 < value <= 1000

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


class MockSensor(Sensor):

    def __init__(self, config):
        super().__init__(config)

    def open(self, warm_up: bool = False):
        _logger.info(f"mocked opened (warm_up={warm_up})")

        if warm_up:
            self.warm_up()

    def close(self):
        _logger.info("mocked closed")

    def warm_up(self):
        _logger.info("mocked warm_up")

    def sleep(self):
        _logger.info("mocked sleep")

    def measure(self):
        _logger.info("mocked measure")
        self._set_measurment(StateValue.OK, 0, 0)
