import datetime
import logging
import signal
import time
from enum import IntEnum, Enum

from tzlocal import get_localzone

from src.config import Config
from src.config_key import ConfigKey
from src.result import Result, ResultState
from src.mqtt_connector import MqttConnector
from src.sensor import Sensor, MockSensor
from src.subscription import OnHoldSubscription, RangeSubscription

_logger = logging.getLogger(__name__)


class SensorState(IntEnum):
    START = 0

    SWITCHING_ON = 1
    CONNECTING = 2

    WARMING_UP = 3
    MEASURING = 4
    COOLING_DOWN = 5
    WAITING_FOR_RESET = 6
    SWITCHED_OFF = 7


class SwitchSensor(Enum):
    OFF = "OFF"
    ON = "ON"


class Process:

    TIME_STEP = 0.05

    DEFAULT_TIME_WARM_UP = 30
    DEFAULT_TIME_COOL_DOWN = 2
    DEFAULT_TIME_INTERVAL = 180
    DEFAULT_COUNT_MEASUREMENTS = 1
    DEFAULT_TIME_BETWEEN_MEASUREMENT = 5

    DEFAULT_TIME_SWITCHING_ON = 7

    DEFAULT_SENSOR_TEMP_RANGE = (-20, 60)
    DEFAULT_SENSOR_HUMI_RANGE = (0, 70)

    NO_SENSOR_CLOSE_BELOW = 15

    def __init__(self):
        self._sensor = None
        self._mqtt = None
        self._shutdown = False

        self._time_step = self.TIME_STEP
        self._time_counter = 0
        self._time_interval = self.DEFAULT_TIME_INTERVAL
        self._time_warm_up = self.DEFAULT_TIME_WARM_UP
        self._time_cool_down = self.DEFAULT_TIME_COOL_DOWN
        self._time_switching_on = self.DEFAULT_TIME_SWITCHING_ON

        self._humi_range = None
        self._temp_range = None

        self._mqtt_channel_sensor_switch = None

        self._subs_cmd = OnHoldSubscription(ConfigKey.MQTT_CHANNEL_CMD_HOLD)
        self._subs_humi = RangeSubscription(ConfigKey.MQTT_CHANNEL_CMD_HUMI)
        self._subs_temp = RangeSubscription(ConfigKey.MQTT_CHANNEL_CMD_TEMP)
        self._subscriptions = [self._subs_cmd, self._subs_humi, self._subs_temp]

        self._on_hold = False
        self._last_measurement = None

        signal.signal(signal.SIGINT, self._shutdown_gracefully)
        signal.signal(signal.SIGTERM, self._shutdown_gracefully)

    def _shutdown_gracefully(self, sig, _frame):
        _logger.debug("shutdown signaled (%s)", sig)
        self._shutdown = True

    def open(self, config):
        _logger.debug("open(%s)", config)

        if self._mqtt is not None or self._sensor is not None:
            raise RuntimeError("Initialisation alread done!")

        self._time_interval = Config.get_float(config, ConfigKey.SENSOR_WAIT, self._time_interval)
        self._time_warm_up = Config.get_float(config, ConfigKey.SENSOR_WARM_UP_TIME, self._time_warm_up)
        self._time_cool_down = Config.get_float(config, ConfigKey.SENSOR_COOL_DOWN_TIME, self._time_cool_down)
        self._time_switching_on = Config.get_float(config, ConfigKey.TIME_SWITCHING_ON, self._time_switching_on)

        self._subs_cmd.config(config.get(ConfigKey.MQTT_CHANNEL_CMD_HOLD.value))

        self._subs_humi.config(config.get(ConfigKey.MQTT_CHANNEL_CMD_HUMI.value))
        self._subs_humi.set_range(config.get(ConfigKey.SENSOR_HUMI_RANGE.value) or self.DEFAULT_SENSOR_HUMI_RANGE)

        self._subs_temp.config(config.get(ConfigKey.MQTT_CHANNEL_CMD_TEMP.value))
        self._subs_temp.set_range(config.get(ConfigKey.SENSOR_TEMP_RANGE.value) or self.DEFAULT_SENSOR_TEMP_RANGE)

        self._mqtt_channel_sensor_switch = config.get(ConfigKey.MQTT_CHANNEL_SWITCH.value)

        self._mqtt = self._create_mqtt_connector(config)
        self._mqtt.open(config)

        self._sensor = self._create_sensor(config)

    @classmethod
    def _create_mqtt_connector(cls, _config):
        return MqttConnector()

    @classmethod
    def _create_sensor(cls, config):
        mocked = Config.get_bool(config, ConfigKey.MOCK_SENSOR, False)
        sensor_class = MockSensor if mocked else Sensor
        return sensor_class(config)

    def close(self):
        if self._sensor:
            self._sensor.close()
            self._sensor = None

        self._switch_sensor(SwitchSensor.OFF)

        if self._mqtt is not None:
            self._mqtt.close()
            self._mqtt = None

    def _wait(self, seconds: float):
        """time.sleep but overwriteable for tests"""
        time.sleep(seconds)
        self._time_counter += seconds

    def _reset_timer(self):
        """reset time counter - overwriteable for tests"""
        self._time_counter = 0

    def run(self):
        state = SensorState.START

        is_switch_sensor = bool(self._mqtt_channel_sensor_switch)

        try:
            self._wait_for_mqtt_connection()

            self._reset_timer()  # better testing
            while not self._shutdown:
                if state == SensorState.START:
                    self._process_mqtt_messages()  # changes: self._on_hold

                # may be changed dynamically
                time_switching_on = self._time_switching_on if is_switch_sensor else 0
                time_warming_up = self._time_warm_up + time_switching_on
                time_cool_down = time_warming_up + self._time_cool_down

                diff_reset = self._time_interval - self._time_warm_up + self._time_cool_down - time_switching_on
                if diff_reset <= 0:
                    raise ValueError("interval time must be larger then sum up other times!")
                no_sensor_close = diff_reset < self.NO_SENSOR_CLOSE_BELOW

                if self._on_hold:
                    if state == SensorState.START:
                        if is_switch_sensor:
                            self._switch_sensor(SwitchSensor.OFF)
                            state = SensorState.SWITCHED_OFF
                        else:
                            self._sensor.open(warm_up=False)  # prepare for sending to sleep!
                            state = SensorState.COOLING_DOWN

                        self._publish_measurement(Result(ResultState.DEACTIVATED))
                else:
                    if state == SensorState.START:
                        if is_switch_sensor:
                            self._switch_sensor(SwitchSensor.ON)
                            state = SensorState.SWITCHING_ON
                        else:
                            state = SensorState.CONNECTING

                    if state == SensorState.SWITCHING_ON and self._time_counter >= time_switching_on:
                        state = SensorState.CONNECTING

                    if state == SensorState.CONNECTING:
                        self._sensor.open(warm_up=True)
                        state = SensorState.WARMING_UP

                    if state == SensorState.WARMING_UP and self._time_counter >= time_warming_up:
                        self._last_measurement = None
                        measurement = self._sensor.measure()
                        self._publish_measurement(measurement)
                        state = SensorState.COOLING_DOWN

                if state == SensorState.COOLING_DOWN and self._time_counter >= time_cool_down and not no_sensor_close:
                    self._sensor.close()  # includes sleep
                    state = SensorState.WAITING_FOR_RESET

                if self._time_counter >= self._time_interval:  # any state
                    self._reset_timer()
                    state = SensorState.START

                self._wait(self._time_step)

        finally:
            self.close()

    def _publish_measurement(self, measurement):
        measurement.timestamp = self._now()
        if measurement.state == ResultState.OK:
            self._last_measurement = measurement  # store for adaptive intervals

        message = measurement.create_message()
        self._mqtt.publish(message)

    def _wait_for_mqtt_connection(self):
        """wait for getting mqtt connect callback called"""
        self._reset_timer()

        while not self._shutdown:
            # make sure mqtt was connected - notified via callback
            if self._time_counter > 15:
                raise RuntimeError("Couldn't connect to MQTT, callback was not called!?")

            self._wait(self._time_step)
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

    def _switch_sensor(self, switch_state: SwitchSensor):
        if self._mqtt_channel_sensor_switch:
            self._mqtt.publish(switch_state.value, self._mqtt_channel_sensor_switch, True)

    def _now(self):
        """overwrite in test to simulate different times"""
        return datetime.datetime.now(tz=get_localzone())
