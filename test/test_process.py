import unittest

from src.mqtt_connector import MqttConnector
from src.process import Process

from unittest.mock import MagicMock

from src.sensor import Sensor


class MockProcess(Process):

    def __init__(self):
        super().__init__()

        self.test_sensor = None
        self.test_mqtt = None

        self.time_stop_at = 0
        self.time_stop_counter = 0

    def test_open(self, loop_count=1):
        self.set_loop_count(loop_count)
        self.set_mocked_sensor()
        self.set_mocked_mqtt()

    def set_mocked_sensor(self):
        self._sensor = Sensor({})
        self.test_sensor = self._sensor

        self._sensor.open = MagicMock()
        self._sensor.close = MagicMock()
        self._sensor.measure = MagicMock()
        self._sensor.publish = MagicMock()

    def set_loop_count(self, loop_count=1):
        self._time_wait = 4 * self.TIME_STEP
        self._time_warm_up = 2 * self.TIME_STEP
        self._time_cool_down = 1 * self.TIME_STEP
        self.time_stop_at = loop_count * (self._time_wait + self._time_warm_up + self._time_cool_down) \
                            + self.TIME_STEP

    def set_mocked_mqtt(self):
        self._mqtt = MqttConnector()
        self.test_mqtt = self._mqtt

        self._mqtt.open = MagicMock()
        self._mqtt.is_open = MagicMock(return_value=True)
        self._mqtt.close = MagicMock()
        # self._mqtt.measure = MagicMock()
        # self._mqtt.publish = MagicMock()

    def _wait(self, seconds: float):
        # no sleep
        self._time_counter += seconds
        self.time_stop_counter += seconds
        if self.time_stop_counter >= self.time_stop_at:
            self._shutdown = True


class TestProcess(unittest.TestCase):

    def check_loop_running(self, loop_count):
        process = MockProcess()
        process.test_open(loop_count=loop_count)
        process.run()

        self.assertEqual(process.test_sensor.open.call_count, loop_count)
        process.test_sensor.open.assert_called_with(warm_up=True)

        self.assertEqual(process.test_sensor.measure.call_count, loop_count)
        self.assertEqual(process.test_sensor.publish.call_count, loop_count)
        self.assertEqual(process.test_sensor.close.call_count, loop_count + 1)

    def test_loop_1(self):
        self.check_loop_running(loop_count=1)

    def test_loop_n(self):
        self.check_loop_running(loop_count=3)

    def check_loop_on_hold(self, loop_count):
        loop_count = 3

        process = MockProcess()
        process._on_hold = True
        process.test_open(loop_count=loop_count)
        process.run()

        self.assertEqual(process.test_sensor.open.call_count, loop_count)
        process.test_sensor.open.assert_called_with(warm_up=False)

        self.assertEqual(process.test_sensor.measure.call_count, 0)
        self.assertEqual(process.test_sensor.publish.call_count, 0)
        self.assertEqual(process.test_sensor.close.call_count, loop_count + 1)
