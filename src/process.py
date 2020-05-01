import logging
import signal
import time
from enum import IntEnum

from src.config import ConfMainKey
from src.mqtt_connector import MqttConnector
from src.sensor import Sensor

_logger = logging.getLogger("process")


class SensorState(IntEnum):
    START = 0
    WARMING_UP = 1
    MEASURING = 2
    COOLING_DOWN = 3
    WAITING_FOR_RESET = 4


class Process:

    TIME_STEP = 0.05

    DEFAULT_TIME_INTERVAL = 145
    DEFAULT_TIME_WARM_UP = 30
    DEFAULT_TIME_COOL_DOWN = 5
    DEFAULT_COUNT_MEASUREMENTS = 1
    DEFAULT_TIME_BETWEEN_MEASUREMENT = 5

    def __init__(self):
        self._sensor = None
        self._mqtt = None
        self._shutdown = False

        self._time_counter = 0
        self._time_wait = self.DEFAULT_TIME_INTERVAL
        self._time_warm_up = self.DEFAULT_TIME_WARM_UP
        self._time_cool_down = self.DEFAULT_TIME_COOL_DOWN

        self._on_hold = False

        signal.signal(signal.SIGINT, self._shutdown_gracefully)
        signal.signal(signal.SIGTERM, self._shutdown_gracefully)

    def __del__(self):
        self.close()

    def _shutdown_gracefully(self, sig, _frame):
        _logger.debug("shutdown signaled (%s)", sig)
        self._shutdown = True

    def open(self, config):
        _logger.debug("open(%s)", config)

        if self._mqtt is not None or self._sensor is not None:
            raise RuntimeError("initialisation alread done!")

        def get_config_float(key, default_value):
            value = config.get(key.value)
            return float(value) if value is not None else default_value

        self._time_wait = get_config_float(ConfMainKey.SENSOR_WAIT, self._time_wait)
        self._time_warm_up = get_config_float(ConfMainKey.SENSOR_WARM_UP_TIME, self._time_warm_up)
        self._time_cool_down = get_config_float(ConfMainKey.SENSOR_COOL_DOWN_TIME, self._time_cool_down)

        self._mqtt = MqttConnector()
        self._mqtt.open(config)

        self._sensor = Sensor(config)
        self._sensor.set_mqtt(self._mqtt)

    def close(self):
        if self._mqtt is not None:
            self._mqtt.close()
            self._mqtt = None

        if self._sensor:
            self._sensor.close()
            self._sensor = None

    def _wait(self, seconds: float):
        """time.sleep but overwriteable for tests"""
        time.sleep(seconds)
        self._time_counter += seconds

    def _reset_timer(self):
        """reset time counter - overwriteable for tests"""
        self._time_counter = 0

    def run(self):
        state = SensorState.START

        try:
            self._wait_for_mqtt_connection()

            self._reset_timer()  # better testing
            while not self._shutdown:
                self._process_mqtt_messages()  # changes: self._on_hold

                # may be changed dynamically
                time_cool_down = self._time_warm_up + self._time_cool_down
                time_reset = self._time_warm_up + self._time_cool_down + self._time_wait

                if self._on_hold:
                    if state == SensorState.START:
                        self._sensor.open(warm_up=False)
                        self._mqtt.publish_last_will()
                        state = SensorState.COOLING_DOWN
                else:
                    if state == SensorState.START:
                        self._sensor.open(warm_up=True)
                        state = SensorState.WARMING_UP

                    if state == SensorState.WARMING_UP and self._time_counter >= self._time_warm_up:
                        self._sensor.measure()
                        self._sensor.publish()
                        state = SensorState.COOLING_DOWN

                if state == SensorState.COOLING_DOWN and self._time_counter >= time_cool_down:
                    self._sensor.close()  # includes sleep
                    state = SensorState.WAITING_FOR_RESET

                if self._time_counter >= time_reset:  # any state
                    self._reset_timer()
                    state = SensorState.START

                self._wait(self.TIME_STEP)

        finally:
            self.close()

    def _wait_for_mqtt_connection(self):
        """wait for getting mqtt connect callback called"""
        self._reset_timer()

        while not self._shutdown:
            # make sure mqtt was connected - notified via callback
            if self._time_counter > 15:
                raise RuntimeError("Couldn't connect to MQTT, callback was not called!?")

            self._wait(self.TIME_STEP)
            if self._mqtt.is_open():
                # self._reset_timer()
                break

    def _process_mqtt_messages(self):
        messages = self._mqtt.get_messages()
        for message in messages:
            pass

        # TODO
        # check (notfied) temperatur + humitidy with configured limits
        # check: on hold
        # output => self._on_hold
