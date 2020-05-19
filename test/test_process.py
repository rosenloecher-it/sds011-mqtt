import datetime
import random
import unittest

from tzlocal import get_localzone

from src.mqtt_connector import MqttConnector
from src.process import Process, SwitchSensor, LoopParams

from unittest.mock import MagicMock

from src.result import ResultState, Result
from src.sensor import MockSensor


class MockProcess(Process):

    def __init__(self):
        super().__init__()

        self.test_sensor = None
        self.test_mqtt = None

        self.time_stop_at = 0
        self.time_stop_counter = 0

        self.mqtt_messages = []

        self.now = datetime.datetime(2020, 1, 1, 2, 2, 3, tzinfo=datetime.timezone.utc)

    def test_open(self, loop_count=1):
        self.set_loop_count(loop_count)
        self.set_mocked_sensor()
        self.set_mocked_mqtt()

    def set_mocked_sensor(self):
        self._sensor = MockSensor({})
        self.test_sensor = self._sensor

        self._sensor.open = MagicMock()
        self._sensor.measure = MagicMock(return_value=MockSensor.dummy_measure())
        self._sensor.close = MagicMock()

    def set_loop_count(self, loop_count=1):
        self._time_step = 40
        self._time_interval_max = 4 * self._time_step
        self._time_warm_up = 2 * self._time_step
        self._time_cool_down = 0
        self.time_stop_at = loop_count * self._time_interval_max + self._time_step

    def create_dummy_loop_params(self):
        lp = LoopParams()
        lp.tlim_interval = self._time_interval_max
        lp.tlim_switching_on = self._time_switching_on if lp.use_switch_actor else 0
        lp.tlim_warming_up = self._time_warm_up + lp.tlim_switching_on
        lp.tlim_cool_down = lp.tlim_warming_up + self._time_cool_down

        return lp

    def set_mocked_mqtt(self):
        self._mqtt = MqttConnector()
        self.test_mqtt = self._mqtt

        self._mqtt.open = MagicMock()
        self._mqtt.is_open = MagicMock(return_value=True)
        self._mqtt.close = MagicMock()

        def publish(message: str, channel: str = None, retain: bool = None):
            self.mqtt_messages.append(message)

        self._mqtt.publish = publish

    def _wait(self, seconds: float):
        # no sleep
        self._time_counter += seconds
        self.time_stop_counter += seconds
        if self.time_stop_counter >= self.time_stop_at:
            self._shutdown = True

    def _now(self):
        return self.now


class TestProcessLoopStandard(unittest.TestCase):

    def check_loop_running(self, loop_count):
        process = MockProcess()
        process.test_open(loop_count=loop_count)
        process.run()

        self.assertEqual(process.test_sensor.open.call_count, loop_count)
        process.test_sensor.open.assert_called_with(warm_up=True)

        self.assertEqual(process.test_sensor.close.call_count, loop_count + 1)

        self.assertEqual(len(process.mqtt_messages), loop_count)

        result = MockSensor.dummy_measure()
        result.timestamp = process._now()
        message = result.create_message()

        for m in process.mqtt_messages:
            self.assertEqual(m, message)

    def test_loop_1(self):
        self.check_loop_running(loop_count=1)

    def test_loop_n(self):
        self.check_loop_running(loop_count=3)

    def test_loop_sensor_on_hold(self):
        loop_count = 3

        process = MockProcess()

        loop_params = process.create_dummy_loop_params()
        loop_params.on_hold = True

        process._determine_loop_params = MagicMock()
        process._determine_loop_params.return_value = loop_params

        process.test_open(loop_count=loop_count)
        process.run()

        self.assertEqual(process.test_sensor.open.call_count, loop_count)
        process.test_sensor.open.assert_called_with(warm_up=False)

        self.assertEqual(process.test_sensor.measure.call_count, 0)
        self.assertEqual(process.test_sensor.close.call_count, loop_count + 1)

    def test_loop_actor_on_hold(self):
        loop_count = 3

        process = MockProcess()

        process._mqtt_out_actor = "_mqtt_channel_sensor_switch"

        loop_params = process.create_dummy_loop_params()
        loop_params.on_hold = True
        loop_params.use_switch_actor = True

        process._determine_loop_params = MagicMock()
        process._determine_loop_params.return_value = loop_params

        process.test_open(loop_count=loop_count)
        process.run()

        self.assertEqual(0, process.test_sensor.open.call_count)
        self.assertEqual(0, process.test_sensor.measure.call_count)
        self.assertEqual(1, process.test_sensor.close.call_count)  # finally

        self.assertEqual(len(process.mqtt_messages), loop_count * 2 + 1)
        message = Result(ResultState.DEACTIVATED, timestamp=process._now()).create_message()
        for m in process.mqtt_messages:
            self.assertTrue(m in [message, SwitchSensor.OFF.value])


class TestProcessCalcIntervalTime(unittest.TestCase):

    def test_no_measurement(self):
        time_interval_max = random.random() * 1000

        process = MockProcess()

        process._time_interval_max = time_interval_max
        process._last_result = None

        compare = process._calc_interval_time()

        self.assertEqual(compare, time_interval_max)

    def test_max_time(self):
        time_interval_max = random.random() * 1000

        process = MockProcess()

        process._time_interval_max = time_interval_max
        process._last_result = Result(ResultState.OK, pm10=1, pm25=1, timestamp=process.now)

        compare = process._calc_interval_time()

        self.assertEqual(compare, time_interval_max)

    def test_min_time(self):
        time_interval_max = 200 + random.random() * 1000
        time_interval_min = time_interval_max / 5

        process = MockProcess()

        process._time_interval_max = time_interval_max
        process._time_interval_min = time_interval_min
        process._last_result = Result(ResultState.OK, pm25=1, timestamp=process.now,
                                      pm10=process.DEFAULT_ADAPTIVE_DUST_UPPER + 1)

        compare = process._calc_interval_time()

        self.assertEqual(compare, time_interval_min)

    def test_middle(self):
        time_max = 300
        time_min = 100

        process = MockProcess()
        process._time_interval_max = time_max
        process._time_interval_min = time_min

        dust = (process.DEFAULT_ADAPTIVE_DUST_UPPER + process.DEFAULT_ADAPTIVE_DUST_LOWER) / 2
        process._last_result = Result(ResultState.OK, pm10=dust, pm25=1, timestamp=process.now)

        compare = process._calc_interval_time()

        self.assertAlmostEqual(compare, (time_max + time_min) / 2)


class TestProcessDeactivationRanges(unittest.TestCase):

    def test_inactive(self):
        process = MockProcess()
        process.now = datetime.datetime(2020, 1, 1, 2, 2, 3, tzinfo=get_localzone())
        process._deactivation_ranges = None

        compare = process._active_deactivation_ranges()
        self.assertEqual(compare, False)

    def test_active(self):
        process = MockProcess()
        process.now = datetime.datetime(2020, 1, 1, 3, 0, 0, tzinfo=get_localzone())

        minute_of_day = process.now.minute + 60 * process.now.hour

        process._deactivation_ranges = ((minute_of_day - 3, minute_of_day + 5), (2 * minute_of_day, 3 * minute_of_day))
        compare = process._active_deactivation_ranges()
        self.assertEqual(compare, True)

        process._deactivation_ranges = ((2 * minute_of_day, 3 * minute_of_day),)
        compare = process._active_deactivation_ranges()
        self.assertEqual(compare, False)

    def test_error(self):
        process = MockProcess()
        process._deactivation_ranges = (("h"))

        compare = process._active_deactivation_ranges()
        self.assertEqual(compare, False)
