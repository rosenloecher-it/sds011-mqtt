import datetime
import unittest

from src.mqtt_connector import MqttConnector
from src.process import Process, SwitchSensor

from unittest.mock import MagicMock

from src.result import ResultState, Result
from src.sensor import Sensor, MockSensor


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
        self._time_interval = 4 * self._time_step
        self._time_warm_up = 2 * self._time_step
        self._time_cool_down = 0
        self.time_stop_at = loop_count * self._time_interval + self._time_step

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
            self.assertEqual(m , message)

    def test_loop_1(self):
        self.check_loop_running(loop_count=1)

    def test_loop_n(self):
        self.check_loop_running(loop_count=3)

    def test_loop_sensor_on_hold(self):
        loop_count = 3

        process = MockProcess()
        process._process_mqtt_messages = lambda *args: None
        process._on_hold = True
        process.test_open(loop_count=loop_count)
        process.run()

        self.assertEqual(process.test_sensor.open.call_count, loop_count)
        process.test_sensor.open.assert_called_with(warm_up=False)

        self.assertEqual(process.test_sensor.measure.call_count, 0)
        self.assertEqual(process.test_sensor.close.call_count, loop_count + 1)

    def test_loop_switch_on_hold(self):
        loop_count = 3

        process = MockProcess()
        process._process_mqtt_messages = lambda *args: None
        process._on_hold = True
        process._mqtt_channel_sensor_switch = "mqtt_channel_sensor_switch"

        process.test_open(loop_count=loop_count)
        process.run()

        self.assertEqual(0, process.test_sensor.open.call_count)
        self.assertEqual(0, process.test_sensor.measure.call_count)
        self.assertEqual(1, process.test_sensor.close.call_count)  # finally

        self.assertEqual(len(process.mqtt_messages), loop_count * 2 + 1)
        message = Result(ResultState.DEACTIVATED, timestamp=process._now()).create_message()
        for m in process.mqtt_messages:
            self.assertTrue(m in [message, SwitchSensor.OFF.value])
