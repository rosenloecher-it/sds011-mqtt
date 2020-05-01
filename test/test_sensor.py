import unittest

from src.sensor import Sensor


class TestSensor(unittest.TestCase):

    def test_check_value(self):
        self.assertEqual(Sensor.check_value(-1), False)
        self.assertEqual(Sensor.check_value(1001), False)
        self.assertEqual(Sensor.check_value(1), True)
        self.assertEqual(Sensor.check_value(500), True)
