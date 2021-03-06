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
        _logger.debug("open(warm_up=%s)", warm_up)

        self._sensor = SDS011(self._port, use_query_mode=True)
        self._sensor.open()
        self._warmup = False  # don't know the state!

        if warm_up:
            self.warm_up()

    def close(self, sleep=True):
        _logger.debug("close(sleep=%s)", sleep)
        if self._sensor is not None:
            if sleep:
                try:
                    self._sensor.sleep()
                except Exception as ex:
                    _logger.exception(ex)

            try:
                self._sensor.close()
            except Exception as ex:
                _logger.exception(ex)
            finally:
                self._sensor = None
                self._warmup = False

    def warm_up(self):
        if self._sensor:
            self._sensor.sleep(sleep=False)
            self._warmup = True
            _logger.debug("warming up")

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
            measurement = self._sensor.query()
        except SerialException as ex:
            self._error_ignored += 1
            if self._error_ignored > self._abort_after_n_errors:
                raise SensorError(ex)

            _logger.error("self._sensor.query() failed, but ignore %s of %s!",
                          self._error_ignored, self._abort_after_n_errors)
            _logger.exception(ex)
            return Result(ResultState.ERROR)
        else:
            if measurement is None:
                pm25, pm10 = None, None
            else:
                pm25, pm10 = measurement

            if not self.check_measurement(pm10=pm10, pm25=pm25):
                self._error_ignored += 1
                if self._error_ignored >= self._abort_after_n_errors:
                    raise SensorError(f"{self._error_ignored} wrong measurments!")

                _logger.warning("wrong measurment (ignore %s of %s): pm25=%s; pm10=%s!",
                                self._error_ignored, self._abort_after_n_errors,
                                pm25, pm10)
                return Result(ResultState.ERROR)
            else:
                self._error_ignored = 0
                return Result(ResultState.OK, pm10=pm10, pm25=pm25)

    @classmethod
    def check_measurement(cls, pm25, pm10):
        if pm25 is None or pm10 is None:
            return False
        if not 0 <= pm25 <= 1000 or not 0 <= pm10 <= 1000:
            return False
        # these typical I get over and over again, can't be rigth
        # pm25 == 25.8 and pm10 == 0.1
        if pm10 == 0.1 and 25.0 < pm25 < 27.0:
            return False
        return True


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
