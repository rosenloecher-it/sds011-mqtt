import logging
import threading
from queue import Queue, Empty

import paho.mqtt.client as mqtt

from src.config import ConfMainKey, Config
from src.constant import Constant

_logger = logging.getLogger(__name__)


class MqttConnector:

    def __init__(self):
        self._mqtt = None
        self._open = False

        self._channel = None
        self._last_will = None
        self._qos = None
        self._retain = None

        self._message_queue = Queue()  # synchronized
        self._lock = threading.Lock()

    def is_open(self):
        with self._lock:
            return self._mqtt and self._open

    def open(self, config):
        self._channel = Config.get_str(config, ConfMainKey.MQTT_CHANNEL)
        self._last_will = Config.get_str(config, ConfMainKey.MQTT_LAST_WILL)
        self._qos = Config.get_int(config, ConfMainKey.MQTT_QUALITY, Constant.DEFAULT_MQTT_QUALITY)
        self._retain = Config.get_bool(config, ConfMainKey.MQTT_RETAIN, False)

        host = Config.get_str(config, ConfMainKey.MQTT_HOST)
        port = Config.get_int(config, ConfMainKey.MQTT_PORT)
        protocol = Config.get_int(config, ConfMainKey.MQTT_PROTOCOL, Constant.DEFAULT_MQTT_PROTOCOL)
        keepalive = Config.get_int(config, ConfMainKey.MQTT_KEEPALIVE, Constant.DEFAULT_MQTT_KEEPALIVE)
        client_id = Config.get_str(config, ConfMainKey.MQTT_CLIENT_ID)
        ssl_ca_certs = Config.get_str(config, ConfMainKey.MQTT_SSL_CA_CERTS)
        ssl_certfile = Config.get_str(config, ConfMainKey.MQTT_SSL_CERTFILE)
        ssl_keyfile = Config.get_str(config, ConfMainKey.MQTT_SSL_KEYFILE)
        ssl_insecure = Config.get_bool(config, ConfMainKey.MQTT_SSL_INSECURE, False)
        is_ssl = ssl_ca_certs or ssl_certfile or ssl_keyfile
        user_name = Config.get_str(config, ConfMainKey.MQTT_USER_NAME)
        user_pwd = Config.get_str(config, ConfMainKey.MQTT_USER_PWD)

        if not port:
            port = Constant.DEFAULT_MQTT_PORT_SSL if is_ssl else Constant.DEFAULT_MQTT_PORT

        if not host or not client_id:
            raise RuntimeError("mandatory mqtt configuration not found ({}, {})'!".format(
                ConfMainKey.MQTT_HOST.value, ConfMainKey.MQTT_CLIENT_ID.value
            ))

        self._mqtt = mqtt.Client(client_id=client_id, protocol=protocol)

        if is_ssl:
            self._mqtt.tls_set(ca_certs=ssl_ca_certs, certfile=ssl_certfile, keyfile=ssl_keyfile)
            if ssl_insecure:
                _logger.info("disabling SSL certificate verification")
                self._mqtt.tls_insecure_set(True)

        self._mqtt.on_connect = self._on_connect
        self._mqtt.on_disconnect = self._on_disconnect
        self._mqtt.on_message = self._on_message
        self._mqtt.on_publish = self._on_publish

        self.set_last_will()

        if user_name or user_pwd:
            self._mqtt.username_pw_set(user_name, user_pwd)
        self._mqtt.connect_async(host, port=port, keepalive=keepalive)
        self._mqtt.loop_start()

    def close(self):
        if self._mqtt is not None:
            self.publish_last_will()

            self._mqtt.loop_stop()
            self._mqtt.disconnect()
            self._mqtt.loop_forever()  # will block until disconnect complete
            self._mqtt = None
            _logger.debug("mqtt closed.")

    def publish_last_will(self):
        if self._last_will:
            if not self.is_open():
                _logger.error("cannot sent last will (not open)!")
            else:
                self.publish(self._last_will)

    def get_messages(self):
        messages = []

        while True:
            try:
                message = self._message_queue.get(block=False)
                messages.append(message)
            except Empty:
                break

        return messages

    def publish(self, message: str):
        if not self.is_open:
            raise RuntimeError("mqtt is not connected!")

        self._mqtt.publish(
            topic=self._channel,
            payload=message,
            qos=self._qos,
            retain=self._retain
        )
        _logger.info("publish: %s", message)

    def set_last_will(self):
        if self._last_will:
            self._mqtt.will_set(
                topic=self._channel,
                payload=self._last_will,
                qos=self._qos,
                retain=self._retain
            )

    def _on_connect(self, _mqtt_client, _userdata, flags, rc):
        """MQTT callback is called when client connects to MQTT server."""
        with self._lock:
            if rc == 0:
                self._open = True
                _logger.info("successfully connected to MQTT: flags=%s, rc=%s", flags, rc)
            else:
                self._open = False
                _logger.error("connect to MQTT failed: flags=%s, rc=%s", flags, rc)

    def _on_disconnect(self, _mqtt_client, _userdata, rc):
        """MQTT callback for when the client disconnects from the MQTT server."""
        with self._lock:
            self._open = False
            if rc == 0:
                _logger.info("disconnected from MQTT: rc=%s", rc)
            else:
                _logger.error("Unexpectedly disconnected from MQTT broker: rc=%s", rc)

    def _on_message(self, mqtt_client, userdata, message):
        """MQTT callback when a message is received from MQTT server"""
        try:
            _logger.debug('_on_message: topic="%s" payload="%s"', message.topic, message.payload)
            if message is not None:
                self._message_queue.put(message)
        except Exception as ex:
            _logger.exception(ex)

    @classmethod
    def _on_publish(cls, _mqtt_client, _userdata, mid):
        """MQTT callback is invoked when message was successfully sent to the MQTT server."""
        _logger.debug("published message %s", str(mid))
