import datetime
import logging
import signal
import time
from enum import IntEnum, Enum

from tzlocal import get_localzone

from src.config import Config
from src.config_key import ConfigKey
from src.mqtt_connector import MqttConnector
from src.result import Result, ResultState
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


class LoopParams:

    def __init__(self):
        self.use_switch_actor = False
        self.on_hold = False

        # time limits
        self.tlim_interval = None
        self.tlim_interval_min = None
        self.tlim_switching_on = None
        self.tlim_warming_up = None
        self.tlim_cool_down = None

        self.sensor_sleep = True


class Process:

    DEFAULT_TIME_COOL_DOWN = 2
    DEFAULT_TIME_INTERVAL_MAX = 180
    DEFAULT_TIME_INTERVAL_MIN = 15
    DEFAULT_TIME_STEP = 0.05
    DEFAULT_TIME_SWITCHING_ON = 7
    DEFAULT_TIME_WARM_UP = 30

    DEFAULT_COUNT_MEASUREMENTS = 1
    DEFAULT_TIME_BETWEEN_MEASUREMENT = 5

    DEFAULT_SENSOR_TEMP_RANGE = (-20, 60)
    DEFAULT_SENSOR_HUMI_RANGE = (0, 70)

    DEFAULT_ADAPTIVE_DUST_UPPER = 80
    DEFAULT_ADAPTIVE_DUST_LOWER = 10  # µg/m³

    NO_SENSOR_CLOSE_BELOW = 15

    def __init__(self):
        self._sensor = None
        self._mqtt = None
        self._shutdown = False

        self._time_step = self.DEFAULT_TIME_STEP
        self._time_counter = 0

        self._time_cool_down = self.DEFAULT_TIME_COOL_DOWN
        self._time_interval_max = self.DEFAULT_TIME_INTERVAL_MAX
        self._time_interval_min = self.DEFAULT_TIME_INTERVAL_MIN
        self._time_switching_on = self.DEFAULT_TIME_SWITCHING_ON
        self._time_warm_up = self.DEFAULT_TIME_WARM_UP

        # µg/m³
        self._adaptive_dust_upper = self.DEFAULT_ADAPTIVE_DUST_UPPER
        self._adaptive_dust_lower = self.DEFAULT_ADAPTIVE_DUST_LOWER

        self._humi_range = None
        self._temp_range = None

        self._mqtt_out_actor = None

        self._mqtt_in_hold = OnHoldSubscription(ConfigKey.MQTT_CHANNEL_IN_HOLD)
        self._mqtt_in_humi = RangeSubscription(ConfigKey.MQTT_CHANNEL_IN_HUMI)
        self._mqtt_in_temp = RangeSubscription(ConfigKey.MQTT_CHANNEL_IN_TEMP)
        self._subscriptions = [self._mqtt_in_hold, self._mqtt_in_humi, self._mqtt_in_temp]

        self._last_result = None  # type: Result

        self._deactivation_ranges = None

        signal.signal(signal.SIGINT, self._shutdown_gracefully)
        signal.signal(signal.SIGTERM, self._shutdown_gracefully)

    def _shutdown_gracefully(self, sig, _frame):
        _logger.debug("shutdown signaled (%s)", sig)
        self._shutdown = True

    def open(self, config):
        _logger.debug("open(%s)", config)

        if self._mqtt is not None or self._sensor is not None:
            raise RuntimeError("Initialisation alread done!")

        self._time_cool_down = Config.get_float(config, ConfigKey.TIME_COOL_DOWN, self._time_cool_down)
        self._time_interval_max = Config.get_float(config, ConfigKey.TIME_INTERVAL_MAX, self._time_interval_max)
        self._time_interval_min = Config.get_float(config, ConfigKey.TIME_INTERVAL_MIN, self._time_interval_min)
        self._time_switching_on = Config.get_float(config, ConfigKey.TIME_WAIT_FOR_ACTOR, self._time_switching_on)
        self._time_warm_up = Config.get_float(config, ConfigKey.TIME_WARM_UP, self._time_warm_up)

        self._adaptive_dust_upper = self.DEFAULT_ADAPTIVE_DUST_UPPER
        self._adaptive_dust_lower = self.DEFAULT_ADAPTIVE_DUST_LOWER
        self._deactivation_ranges = config.get(ConfigKey.DEACTIVATION_TIME_RANGES.value)

        self._mqtt_in_hold.config(config.get(ConfigKey.MQTT_CHANNEL_IN_HOLD.value))
        self._mqtt_in_humi.config(config.get(ConfigKey.MQTT_CHANNEL_IN_HUMI.value))
        self._mqtt_in_humi.set_range(config.get(ConfigKey.HUMIDITY_RANGE.value) or self.DEFAULT_SENSOR_HUMI_RANGE)
        self._mqtt_in_temp.config(config.get(ConfigKey.MQTT_CHANNEL_IN_TEMP.value))
        self._mqtt_in_temp.set_range(config.get(ConfigKey.TEMPERATURE_RANGE.value) or self.DEFAULT_SENSOR_TEMP_RANGE)

        self._mqtt_out_actor = config.get(ConfigKey.MQTT_CHANNEL_OUT_ACTOR.value)

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

        if self._mqtt is not None:
            self._switch_sensor(SwitchSensor.OFF)
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
        loop_params = None

        try:
            self._wait_for_mqtt_connection()

            self._reset_timer()  # better testing
            while not self._shutdown:

                if state == SensorState.START:
                    self._process_mqtt_messages()
                    loop_params = self._determine_loop_params()

                if loop_params.on_hold:
                    if state == SensorState.START:
                        if loop_params.use_switch_actor:
                            self._switch_sensor(SwitchSensor.OFF)
                            state = SensorState.SWITCHED_OFF
                        else:
                            self._sensor.open(warm_up=False)  # prepare for sending to sleep!
                            state = SensorState.COOLING_DOWN

                        self._handle_result(loop_params, Result(ResultState.DEACTIVATED))
                else:
                    if state == SensorState.START:
                        if loop_params.use_switch_actor:
                            self._switch_sensor(SwitchSensor.ON)
                            state = SensorState.SWITCHING_ON
                        else:
                            state = SensorState.CONNECTING

                    if state == SensorState.SWITCHING_ON and self._time_counter >= loop_params.tlim_switching_on:
                        state = SensorState.CONNECTING

                    if state == SensorState.CONNECTING:
                        self._sensor.open(warm_up=True)
                        state = SensorState.WARMING_UP

                    if state == SensorState.WARMING_UP and self._time_counter >= loop_params.tlim_warming_up:
                        result = self._sensor.measure()
                        self._handle_result(loop_params, result)
                        state = SensorState.COOLING_DOWN

                if state == SensorState.COOLING_DOWN and \
                        (self._time_counter >= loop_params.tlim_cool_down or loop_params.on_hold):
                    self._sensor.close(sleep=loop_params.sensor_sleep)
                    state = SensorState.WAITING_FOR_RESET

                if self._time_counter >= loop_params.tlim_interval:  # any state
                    self._reset_timer()
                    state = SensorState.START

                self._wait(self._time_step)

        finally:
            self.close()

    def _determine_loop_params(self):
        lp = LoopParams()

        if self._active_deactivation_ranges():
            lp.on_hold = True

        if not lp.on_hold:
            for subscription in self._subscriptions:
                if not subscription.verify():
                    lp.on_hold = True

        lp.use_switch_actor = bool(self._mqtt_out_actor)

        # may be changed dynamically
        lp.tlim_switching_on = self._time_switching_on if lp.use_switch_actor else 0
        lp.tlim_warming_up = self._time_warm_up + lp.tlim_switching_on
        lp.tlim_cool_down = lp.tlim_warming_up + self._time_cool_down
        lp.tlim_interval_min = self._time_warm_up + self._time_cool_down + lp.tlim_switching_on

        if lp.on_hold:
            lp.tlim_interval = self._time_interval_max
        else:
            lp.tlim_interval = self._calc_interval_time()
            if lp.tlim_interval_min > lp.tlim_interval:
                _logger.debug("adaptive time interval is corrected to %s (%s)",
                              lp.tlim_interval_min, lp.tlim_interval)
                lp.tlim_interval = lp.tlim_interval_min

        if lp.on_hold:
            lp.sensor_sleep = True
        else:
            diff_reset = lp.tlim_interval - lp.tlim_interval_min
            lp.sensor_sleep = diff_reset > self.NO_SENSOR_CLOSE_BELOW

        return lp

    def _calc_interval_time(self):
        time_interval = self._time_interval_max

        if self._last_result is None or self._last_result.state != ResultState.OK:
            return time_interval

        # reset old measurment
        diff = (self._last_result.timestamp - self._now()).total_seconds()
        if diff > 300:
            return time_interval

        max_time = self._time_interval_max
        min_time = self._time_interval_min

        pm_upper = self._adaptive_dust_upper  # µg/m³
        pm_lower = self._adaptive_dust_lower  # µg/m³

        pm_value = max([self._last_result.pm10, self._last_result.pm25])

        if pm_value <= pm_lower:
            time_interval = max_time
        elif pm_value >= pm_upper:
            time_interval = min_time
        else:
            m = (max_time - min_time) / (pm_lower - pm_upper)
            n = max_time - m * pm_lower
            time_interval = m * pm_value + n

        return time_interval

    def _handle_result(self, loop_params, result):
        result.timestamp = self._now()
        self._last_result = result

        if self._last_result and self._last_result.state == ResultState.ERROR:
            # pump potential humidity out of sensor!?
            loop_params.sensor_sleep = False
            # quick retry
            loop_params.tlim_interval = loop_params.tlim_interval_min

        message = result.create_message()
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

        # wait for delivering retained subscribtions
        self._reset_timer()
        while not self._shutdown:
            self._wait(self._time_step)
            if self._time_counter > 1:
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

    def _switch_sensor(self, switch_state: SwitchSensor):
        if self._mqtt_out_actor:
            self._mqtt.publish(switch_state.value, self._mqtt_out_actor, True)

    def _active_deactivation_ranges(self):
        if not self._deactivation_ranges:
            return False

        now = self._now()
        minute_of_day = now.minute + now.hour * 60

        try:
            for range in self._deactivation_ranges:
                lower = min(range)
                upper = max(range)
                if lower <= minute_of_day <= upper:
                    _logger.debug(f"deactivation range active [{lower} <= {minute_of_day} <= {upper}]!")
                    return True

        except (TypeError) as ex:
            _logger.error(f"Iterable[Iterable] expected for '{ConfigKey.DEACTIVATION_TIME_RANGES.value}'!"
                          " E.g.: '((60,300),(660,900),)'")
            _logger.exception(ex)

        return False

    def _now(self):
        """overwrite in test to simulate different times"""
        return datetime.datetime.now(tz=get_localzone())
