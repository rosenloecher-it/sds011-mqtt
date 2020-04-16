import logging
import signal
import time

from src.config import ConfMainKey
from src.mqtt_connector import MqttConnector
from src.sensor import Sensor

_logger = logging.getLogger("process")


class Process:

    def __init__(self):
        self._config = {}

        self._sensor = None
        self._mqtt = None
        self._shutdown = False

        signal.signal(signal.SIGINT, self._shutdown_gracefully)
        signal.signal(signal.SIGTERM, self._shutdown_gracefully)

        _logger.debug("config: %s", self._config)

    def __del__(self):
        self.close()

    def _shutdown_gracefully(self, sig, _frame):
        _logger.debug("shutdown signaled (%s)", sig)
        self._shutdown = True

    def open(self, config):
        if self._mqtt is not None or self._sensor is not None:
            raise RuntimeError("initialisation failed!")

        self._config = config
        self._mqtt = MqttConnector()
        self._mqtt.open(self._config)

        self._sensor = Sensor(self._config)
        self._sensor.set_mqtt(self._mqtt)

    def close(self):
        if self._mqtt is not None:
            # device.sent_last_will_disconnect()
            self._mqtt.close()
            self._mqtt = None

        if self._sensor:
            self._sensor.close()
            self._sensor = None

    def run(self):
        interval = self._config.get(ConfMainKey.SENSOR_INTERVAL.value)
        warmup = self._config.get(ConfMainKey.SENSOR_WARMUP_TIME.value)
        time_warmup = interval
        time_measure = interval + warmup

        time_step = 0.05
        counter = time_warmup  # start with measurement
        warming_up = False

        while not self._shutdown:
            # make sure mqtt was connected - notified via callback
            time.sleep(time_step)
            counter += time_step
            if self._mqtt.is_open():
                break

        try:
            while not self._shutdown:
                if not warming_up and time_warmup <= counter < time_measure:
                    self._sensor_prepare()
                    warming_up = True
                elif counter > time_measure:
                    warming_up = False
                    self._sensor_measure_and_sleep()
                    counter = 0

                time.sleep(time_step)
                counter += time_step

        except KeyboardInterrupt:
            # gets called without signal-handler
            _logger.debug("finishing...")
        finally:
            self.close()

    def _sensor_prepare(self):
        """Sensor prepare """
        self._sensor.open(warmup=True)
        pass

    def _sensor_measure_and_sleep(self):
        try:
            self._sensor.measure()
            self._sensor.publish()
        finally:
            self._sensor.close()  # includes sleep
