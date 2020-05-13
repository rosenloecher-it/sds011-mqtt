import datetime
import unittest

from src.result import Result, ResultState


class TestMeasurement(unittest.TestCase):

    def test_create_message(self):

        now = datetime.datetime(2020, 1, 1, 2, 2, 3, tzinfo=datetime.timezone.utc)

        r = Result(ResultState.ERROR, timestamp=now)
        m = r.create_message()
        self.assertEqual(m, '{"PM10": null, "PM25": null, "STATE": "ERROR", "TIMESTAMP": "2020-01-01T02:02:03+00:00"}')

        r = Result(ResultState.OK, pm10=0.1, pm25=0.2, timestamp=now)
        m = r.create_message()
        self.assertEqual(m, '{"PM10": 0.1, "PM25": 0.2, "STATE": "OK", "TIMESTAMP": "2020-01-01T02:02:03+00:00"}')
