import logging
import signal
import time
from enum import IntEnum

from src.config import ConfMainKey, Config
from src.mqtt_connector import MqttConnector
from src.sensor import Sensor, MockSensor
from src.subscription import OnHoldSubscription, RangeSubscription

_logger = logging.getLogger(__name__)


class SensorState(IntEnum):
    START = 0
    WARMING_UP = 1
    MEASURING = 2
    COOLING_DOWN = 3
    WAITING_FOR_RESET = 4


class Process:

    TIME_STEP = 0.05

    DEFAULT_TIME_WARM_UP = 30
    DEFAULT_TIME_COOL_DOWN = 2
    DEFAULT_TIME_INTERVAL = 180 - DEFAULT_TIME_WARM_UP - DEFAULT_TIME_COOL_DOWN
    DEFAULT_COUNT_MEASUREMENTS = 1
    DEFAULT_TIME_BETWEEN_MEASUREMENT = 5

    DEFAULT_SENSOR_TEMP_RANGE = (-20, 60)
    DEFAULT_SENSOR_HUMI_RANGE = (0, 70)

    def __init__(self):
        self._sensor = None
        self._mqtt = None
        self._shutdown = False

        self._time_counter = 0
        self._time_wait = self.DEFAULT_TIME_INTERVAL
        self._time_warm_up = self.DEFAULT_TIME_WARM_UP
        self._time_cool_down = self.DEFAULT_TIME_COOL_DOWN

        self._humi_range = None
        self._temp_range = None

        self._subs_cmd = OnHoldSubscription(ConfMainKey.MQTT_CHANNEL_HOLD)
        self._subs_humi = RangeSubscription(ConfMainKey.MQTT_CHANNEL_HUMI)
        self._subs_temp = RangeSubscription(ConfMainKey.MQTT_CHANNEL_TEMP)
        self._subscriptions = [self._subs_cmd, self._subs_humi, self._subs_temp]

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
            raise RuntimeError("Initialisation alread done!")

        self._time_wait = Config.get_float(config, ConfMainKey.SENSOR_WAIT, self._time_wait)
        self._time_warm_up = Config.get_float(config, ConfMainKey.SENSOR_WARM_UP_TIME, self._time_warm_up)
        self._time_cool_down = Config.get_float(config, ConfMainKey.SENSOR_COOL_DOWN_TIME, self._time_cool_down)

        self._subs_cmd.config(config.get(ConfMainKey.MQTT_CHANNEL_HOLD.value))

        self._subs_humi.config(config.get(ConfMainKey.MQTT_CHANNEL_HUMI.value))
        self._subs_humi.set_range(config.get(ConfMainKey.SENSOR_HUMI_RANGE.value) or self.DEFAULT_SENSOR_HUMI_RANGE)

        self._subs_temp.config(config.get(ConfMainKey.MQTT_CHANNEL_TEMP.value))
        self._subs_temp.set_range(config.get(ConfMainKey.SENSOR_TEMP_RANGE.value) or self.DEFAULT_SENSOR_TEMP_RANGE)

        self._mqtt = self._create_mqtt_connector(config)
        self._mqtt.open(config)

        self._sensor = self._create_sensor(config)
        self._sensor.set_mqtt(self._mqtt)

    @classmethod
    def _create_mqtt_connector(cls, _config):
        return MqttConnector()

    @classmethod
    def _create_sensor(cls, config):
        mocked = Config.get_bool(config, ConfMainKey.MOCK_SENSOR, False)
        sensor_class = MockSensor if mocked else Sensor
        return sensor_class(config)

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
                if state == SensorState.START:
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
                topics = [s.topic for s in self._subscriptions if s.topic]
                self._mqtt.subscribe(topics)
                break

    def _process_mqtt_messages(self):
        messages = self._mqtt.get_messages()
        for message in messages:
            payload = message.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            _logger.debug("incoming message %s: %s", message.topic, payload)

            for subscription in self._subscriptions:
                if subscription.matches_topic(message.topic):
                    subscription.extract(payload)

        self._on_hold = False
        for subscription in self._subscriptions:
            if not subscription.verify():
                self._on_hold = True
