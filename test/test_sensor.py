import datetime
import unittest

from src.result import Result, ResultState
from src.sensor import Sensor


class TestSensor(unittest.TestCase):

    def test_check_measurement(self):
        self.assertEqual(Sensor.check_measurement(pm10=0.1, pm25=25.8), False)

        self.assertEqual(Sensor.check_measurement(10, -1), False)
        self.assertEqual(Sensor.check_measurement(-1, 10), False)

        self.assertEqual(Sensor.check_measurement(10, 1001), False)
        self.assertEqual(Sensor.check_measurement(1001, 10), False)

        self.assertEqual(Sensor.check_measurement(None, None), False)
        self.assertEqual(Sensor.check_measurement(None, 10), False)
        self.assertEqual(Sensor.check_measurement(10, None), False)
