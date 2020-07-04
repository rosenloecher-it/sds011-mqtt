import abc
import json
import logging
from json import JSONDecodeError

_logger = logging.getLogger(__name__)


class Subscription(abc.ABC):

    def __init__(self, key):
        self.key = key
        self.topic = None
        self.attribute = None
        self.value = None  # type: str
        self.extract_error = None

    def __str__(self):
        return self.__repr__()

    def __repr__(self) -> str:
        return f'(value={self.value}, topic={self.topic})'

    def config(self, data):
        if data is None:
            self.topic = None
        elif isinstance(data, str):
            self.topic = data
        elif isinstance(data, (list, tuple)):
            if len(data) < 2:
                raise ValueError(f"Cannot config mqtt subscription '{self.key.value}' ({data})!")
            self.topic, *self.attribute = data
        else:
            raise ValueError(f"Cannot extract mqtt subscription for '{self.key.value}' ({data})!")

    def is_active(self):
        return bool(self.topic)

    def matches_topic(self, topic: str) -> bool:
        return topic == self.topic

    def missing_value(self) -> bool:
        """signal that waiting for notifications"""
        return self.value is None

    def extract(self, payload: str) -> bool:
        """Extracts message data"""

        if self.attribute is None:
            # means scalar value
            self.value = payload
            self.extract_error = None
        else:
            self.extract_json(payload)

    def extract_json(self, payload: str):
        self.extract_error = None
        self.value = None

        try:
            self.value = json.loads(payload)
            if not isinstance(self.value, dict):
                raise ValueError("Dict expected!")

            for attribute in self.attribute:
                self.value = self.value[attribute]

        except (JSONDecodeError, AttributeError, ValueError, KeyError) as ex:
            _logger.error(f"Cannot extract '{self.key.value}' from '{str(payload)}'!")
            self.value = None
            self.extract_error = str(ex)

    @abc.abstractmethod
    def verify(self) -> bool:
        """verifies that the condition are fulfilled"""
        raise NotImplementedError()


class RangeSubscription(Subscription):

    def __init__(self, key):
        super().__init__(key)

        self.min = None
        self.max = None
        self.value = None

    def set_range(self, data):
        if not self.is_active():
            return

        self.min = float(min(data))
        self.max = float(max(data))

        if self.min >= self.max:
            raise ValueError(f"Invalid range [{self.min}, {self.max}] for '{self.key.value}'!")

    def verify(self) -> bool:
        if not self.is_active():
            return True

        if self.value is None:
            _logger.info(f"No subscription value '{self.key.value}' available!")
            return False

        if self.value == "-":
            _logger.info(f"No value for '{self.key.value}' available!")
            return False

        try:
            float_value = float(self.value)
        except ValueError:
            _logger.info(f"Cannot convert '{self.key.value}'.value ({self.value}) to float!")
            return False

        if self.min > float_value or float_value > self.max:
            _logger.info(f"'{self.key.value}' ({self.value}) outside range [{self.min}, {self.max}].")
            return False

        return True


class OnHoldSubscription(Subscription):

    def verify(self) -> bool:
        if not self.is_active():
            return True

        # if self.value is None: => doesn't matter, all fine!

        comp = str(self.value).upper().replace(" ", "").replace("_", "")
        if comp in ["HOLD", "ONHOLD", "TRUE", "STOP", "1"]:
            _logger.info(f"'ON HOLD' by '{self.key.value}'.")
            return False

        return True
