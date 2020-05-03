import json
import unittest

from src.config_key import ConfigKey
from src.subscription import RangeSubscription, OnHoldSubscription


class TestRangeSubscription(unittest.TestCase):

    TEST_CHANNEL = "test_channel"
    TEST_ATTR1 = "attr1"
    TEST_ATTR2 = "attr2"

    EXTRACT_MIN = -20
    EXTRACT_MAX = 60

    def prepare_extract(self, channel_config):
        s = RangeSubscription(ConfigKey.MQTT_CHANNEL_HUMI)

        s.config(channel_config)
        s.set_range((self.EXTRACT_MIN, self.EXTRACT_MAX))

        self.assertEqual(s.matches_topic(self.TEST_CHANNEL), True)
        self.assertEqual(s.matches_topic("??"), False)

        return s

    def test_extract_scalar(self):
        s = self.prepare_extract(self.TEST_CHANNEL)

        s.value = None  # without extract
        self.assertEqual(s.verify(), False)

        s.extract("")
        self.assertEqual(s.verify(), False)

        s.extract("xcayc")  # no number
        self.assertEqual(s.verify(), False)

        s.extract(str(self.EXTRACT_MIN + 1))
        self.assertEqual(s.verify(), True)

        s.extract(str(self.EXTRACT_MIN - 1))
        self.assertEqual(s.verify(), False)

        s.extract(str(self.EXTRACT_MAX + 1))
        self.assertEqual(s.verify(), False)

    def test_extract_dict_level1(self):
        s = self.prepare_extract((self.TEST_CHANNEL, self.TEST_ATTR1))

        def check(value, result):
            payload = json.dumps({self.TEST_ATTR1: value})
            s.extract(payload)
            self.assertEqual(s.verify(), result)
            payload = json.dumps({self.TEST_ATTR1: str(value)})
            s.extract(payload)
            self.assertEqual(s.verify(), result)

        check(self.EXTRACT_MIN + 1, True)
        check(self.EXTRACT_MIN - 1, False)
        check(self.EXTRACT_MAX + 1, False)

    def test_invalid_json(self):
        s = self.prepare_extract((self.TEST_CHANNEL, self.TEST_ATTR1))

        # missing "
        payload = '{0}"{1}: 0{2})'.format("{", self.TEST_ATTR1, "}")
        s.extract(payload)
        self.assertEqual(s.verify(), False)

        # missing attribute
        payload = '{"asdfsdaf": 0}'
        s.extract(payload)
        self.assertEqual(s.verify(), False)


class TestOnHoldSubscription(unittest.TestCase):

    TEST_CHANNEL = "test_channel"
    TEST_ATTR1 = "attr1"
    TEST_ATTR2 = "attr2"

    def prepare_extract(self, channel_config):
        s = OnHoldSubscription(ConfigKey.MQTT_CHANNEL_HOLD)

        s.config(channel_config)

        self.assertEqual(s.matches_topic(self.TEST_CHANNEL), True)
        self.assertEqual(s.matches_topic("??"), False)

        return s

    def test_extract_scalar(self):
        s = self.prepare_extract(self.TEST_CHANNEL)

        s.value = None  # without extract
        self.assertEqual(s.verify(), True)

        s.extract("")
        self.assertEqual(s.verify(), True)

        s.extract(" hoLd ")
        self.assertEqual(s.verify(), False)

        s.extract(" onhoLd ")
        self.assertEqual(s.verify(), False)

        s.extract(" on_hoLd ")
        self.assertEqual(s.verify(), False)

        s.extract(" true ")
        self.assertEqual(s.verify(), False)
