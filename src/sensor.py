import logging
import random

from serial import SerialException

from src.config import Config
from src.config_key import ConfigKey
from src.result import ResultState, Result
from src.sds011 import SDS011

_logger = logging.getLogger(__name__)


class SensorError(RuntimeError):
    pass


class Sensor:

    DEBAULT_ABORT_AFTER_N_ERRORS = 5

    def __init__(self, config):
        self._sensor = None
        self._warmup = False

        self._error_ignored = 0
        self._abort_after_n_errors = Config.get_int(config,
                                                    ConfigKey.ABORT_AFTER_N_ERRORS,
                                                    self.DEBAULT_ABORT_AFTER_N_ERRORS)
        if self._abort_after_n_errors < 0:
            self._abort_after_n_errors = 0xffffffff

        self._port = Config.get_str(config, ConfigKey.SERIAL_PORT)

    def __del__(self):
        self.close()

    def open(self, warm_up: bool = False):
        self._sensor = SDS011(self._port, use_query_mode=True)
        self._sensor.open()
        self._warmup = False  # don't know the state!

        _logger.debug("opened")

        if warm_up:
            self.warm_up()

    def close(self, sleep=True):
        if sleep and self._sensor is not None:
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

    def measure(self):
        if self._sensor is None:
            raise SensorError("sensor was not opened!")
        if not self._warmup:
            raise SensorError("sensor was not warmed up before measurement!")

        try:
            result = self._sensor.query()
        except SerialException as ex:
            self._error_ignored += 1
            if self._error_ignored > self._abort_after_n_errors:
                raise SensorError(ex)

            _logger.error("self._sensor.query() failed!")
            _logger.exception(ex)
            return Result(ResultState.ERROR)
        else:
            if result is None:
                pm25, pm10 = None, None
            else:
                pm25, pm10 = result

            if not self.check_value(pm25) or not self.check_value(pm10):
                self._error_ignored += 1
                if self._error_ignored > self._abort_after_n_errors:
                    raise SensorError(f"{self._error_ignored} wrong measurments!")

                _logger.warning("(ignore) wrong measurment: pm25=%s; pm10=%s!", pm25, pm10)
                return Result(ResultState.ERROR)
            else:
                self._error_ignored = 0
                return Result(ResultState.OK, pm10=pm10, pm25=pm25)

    @classmethod
    def check_value(cls, value):
        if value is None:
            return False
        return 0 < value <= 1000


class MockSensor(Sensor):

    def __init__(self, config):
        super().__init__(config)

    def open(self, warm_up: bool = False):
        _logger.info(f"mocked opened (warm_up={warm_up})")

        if warm_up:
            self.warm_up()

    def close(self, sleep=True):
        _logger.info(f"mocked closed (sleep={sleep})")

    def warm_up(self):
        _logger.info("mocked warm_up")

    def sleep(self):
        _logger.info("mocked sleep")

    @classmethod
    def dummy_measure(self):
        return Result(ResultState.OK, pm10=1, pm25=1)

    def measure(self):
        _logger.info("mocked measure")
        if random.randint(0, 10) > 7:
            return Result(ResultState.ERROR)
        else:
            value = random.randint(1, 300) / 10
            return Result(ResultState.OK, pm10=value, pm25=value)
