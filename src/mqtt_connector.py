import logging
import os
import signal
import threading
from queue import Queue, Empty

import paho.mqtt.client as mqtt

from src.config import Config
from src.config_key import ConfigKey

_logger = logging.getLogger(__name__)


class MqttConnector:

    DEFAULT_MQTT_KEEPALIVE = 60
    DEFAULT_MQTT_PORT = 1883
    DEFAULT_MQTT_PORT_SSL = 8883
    DEFAULT_MQTT_PROTOCOL = 4  # 5==MQTTv5, default: 4==MQTTv311, 3==MQTTv31
    DEFAULT_MQTT_QUALITY = 1

    def __init__(self):
        self._mqtt = None
        self._open = False

        self._channel = None
        self._last_will = None
        self._qos = None
        self._retain = None

        self._message_queue = Queue()  # synchronized
        self._lock = threading.Lock()

        self._stored_thread_rc = 0
        self._disconnect_error_count = 0

    def is_open(self):
        self.check_connection_error()

        with self._lock:
            return self._mqtt and self._open

    def open(self, config):
        self._channel = Config.get_str(config, ConfigKey.MQTT_CHANNEL_OUT_STATE)
        self._last_will = Config.get_str(config, ConfigKey.MQTT_LAST_WILL)
        self._qos = Config.get_int(config, ConfigKey.MQTT_QUALITY, self.DEFAULT_MQTT_QUALITY)
        self._retain = Config.get_bool(config, ConfigKey.MQTT_RETAIN, False)

        host = Config.get_str(config, ConfigKey.MQTT_HOST)
        port = Config.get_int(config, ConfigKey.MQTT_PORT)
        protocol = Config.get_int(config, ConfigKey.MQTT_PROTOCOL, self.DEFAULT_MQTT_PROTOCOL)
        keepalive = Config.get_int(config, ConfigKey.MQTT_KEEPALIVE, self.DEFAULT_MQTT_KEEPALIVE)
        client_id = Config.get_str(config, ConfigKey.MQTT_CLIENT_ID)
        ssl_ca_certs = Config.get_str(config, ConfigKey.MQTT_SSL_CA_CERTS)
        ssl_certfile = Config.get_str(config, ConfigKey.MQTT_SSL_CERTFILE)
        ssl_keyfile = Config.get_str(config, ConfigKey.MQTT_SSL_KEYFILE)
        ssl_insecure = Config.get_bool(config, ConfigKey.MQTT_SSL_INSECURE, False)
        is_ssl = ssl_ca_certs or ssl_certfile or ssl_keyfile
        user_name = Config.get_str(config, ConfigKey.MQTT_USER_NAME)
        user_pwd = Config.get_str(config, ConfigKey.MQTT_USER_PWD)

        if not port:
            port = self.DEFAULT_MQTT_PORT_SSL if is_ssl else self.DEFAULT_MQTT_PORT

        if not host or not client_id:
            raise RuntimeError("mandatory mqtt configuration not found ({}, {})'!".format(
                ConfigKey.MQTT_HOST.value, ConfigKey.MQTT_CLIENT_ID.value
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

    def check_connection_error(self):
        with self._lock:
            stored_thread_rc = self._stored_thread_rc

        if stored_thread_rc != 0:
            raise RuntimeError(f"MQTT connection error rc={stored_thread_rc}!")

    def get_messages(self):
        messages = []

        self.check_connection_error()

        while True:
            try:
                message = self._message_queue.get(block=False)
                messages.append(message)
            except Empty:
                break

        return messages

    def publish(self, message: str, channel: str = None, retain: bool = None):
        if not self.is_open:
            raise RuntimeError("mqtt is not connected!")

        if channel is None:
            channel = self._channel
        if retain is None:
            retain = self._retain

        self._mqtt.publish(
            topic=channel,
            payload=message,
            qos=self._qos,
            retain=retain
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

    def subscribe(self, channels):
        subs_qos = 1  # qos for subscriptions, not used, but neccessary
        subscriptions = [(s, subs_qos) for s in channels]
        if subscriptions:
            result, dummy = self._mqtt.subscribe(subscriptions)
            if result != mqtt.MQTT_ERR_SUCCESS:
                text = "could not subscripte to mqtt #{} ({})".format(result, subscriptions)
                raise RuntimeError(text)

            _logger.info("subscripted to MQTT channels (%s)", channels)

    def _on_connect(self, _mqtt_client, _userdata, flags, rc):
        """MQTT callback is called when client connects to MQTT server."""
        with self._lock:
            if rc == 0:
                self._open = True
                _logger.info("successfully connected to MQTT: flags=%s, rc=%s", flags, rc)
            else:
                self._open = False
                self._stored_thread_rc = rc
                _logger.error("connect to MQTT failed: flags=%s, rc=%s", flags, rc)
                self.check_connection_error()

    def _on_disconnect(self, _mqtt_client, _userdata, rc):
        """MQTT callback for when the client disconnects from the MQTT server."""
        disconnect_error_count = 0
        disconnect_error_kill_at = 10

        with self._lock:
            self._open = False
            if rc == 0:
                _logger.info("disconnected from MQTT: rc=%s", rc)
            else:
                self._disconnect_error_count += 1
                disconnect_error_count = self._disconnect_error_count
                self._stored_thread_rc = rc
                _logger.error("Unexpectedly disconnected from MQTT broker: rc=%s (kill when %s >= %s)",
                              rc, disconnect_error_count, disconnect_error_kill_at)

        # no way to get out of the process if there is another client with same name
        if disconnect_error_count >= disconnect_error_kill_at:
            os.kill(os.getpid(), signal.SIGKILL)

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
