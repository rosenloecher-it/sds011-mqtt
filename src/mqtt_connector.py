import logging

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

    def __del__(self):
        self.close()

    def is_open(self):
        return self._mqtt and self._open

    def open(self, config):

        self._channel = config.get(ConfMainKey.MQTT_CHANNEL.value)
        self._last_will = config.get(ConfMainKey.MQTT_LAST_WILL.value)
        self._qos = Config.post_process_int(config, ConfMainKey.MQTT_QUALITY, Constant.DEFAULT_MQTT_QUALITY)
        self._retain = Config.post_process_bool(config, ConfMainKey.MQTT_RETAIN, False)

        host = config.get(ConfMainKey.MQTT_HOST.value)
        port = config.get(ConfMainKey.MQTT_PORT.value)
        protocol = config.get(ConfMainKey.MQTT_PROTOCOL.value)
        keepalive = config.get(ConfMainKey.MQTT_KEEPALIVE.value)
        client_id = config.get(ConfMainKey.MQTT_CLIENT_ID.value)
        ssl_ca_certs = config.get(ConfMainKey.MQTT_SSL_CA_CERTS.value)
        ssl_certfile = config.get(ConfMainKey.MQTT_SSL_CERTFILE.value)
        ssl_keyfile = config.get(ConfMainKey.MQTT_SSL_KEYFILE.value)
        ssl_insecure = config.get(ConfMainKey.MQTT_SSL_INSECURE.value)
        is_ssl = ssl_ca_certs or ssl_certfile or ssl_keyfile
        user_name = config.get(ConfMainKey.MQTT_USER_NAME.value)
        user_pwd = config.get(ConfMainKey.MQTT_USER_PWD.value)

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

        self._mqtt.on_connect = self._on_mqtt_connect
        self._mqtt.on_disconnect = self._on_mqtt_disconnect
        self._mqtt.on_publish = self._on_mqtt_publish

        self.will_set()

        if user_name or user_pwd:
            self._mqtt.username_pw_set(user_name, user_pwd)
        self._mqtt.connect_async(host, port=port, keepalive=keepalive)
        self._mqtt.loop_start()

    def close(self):
        if self._mqtt is not None:
            if self._last_will:
                if not self._open:
                    _logger.error("cannot sent last will (not open)!")
                else:
                    self.publish(self._last_will)

            self._mqtt.loop_stop()
            self._mqtt.disconnect()
            self._mqtt.loop_forever()  # will block until disconnect complete
            self._mqtt = None
            _logger.debug("mqtt closed.")

    def publish(self, message: str):
        if not self._open:
            raise RuntimeError("mqtt is not connected!")

        self._mqtt.publish(
            topic=self._channel,
            payload=message,
            qos=self._qos,
            retain=self._retain
        )
        _logger.info("publish: %s", message)

    def will_set(self):
        if self._last_will:
            self._mqtt.will_set(
                topic=self._channel,
                payload=self._last_will,
                qos=self._qos,
                retain=self._retain
            )

    def _on_mqtt_connect(self, mqtt_client, userdata, flags, rc):
        """MQTT callback is called when client connects to MQTT server."""
        if rc == 0:
            self._open = True
            _logger.info("successfully connected to MQTT: flags=%s, rc=%s", flags, rc)
        else:
            self._open = False
            _logger.error("connect to MQTT failed: flags=%s, rc=%s", flags, rc)

    def _on_mqtt_disconnect(self, mqtt_client, userdata, rc):
        """MQTT callback for when the client disconnects from the MQTT server."""
        self._open = False
        if rc == 0:
            _logger.info("disconnected from MQTT: rc=%s", rc)
        else:
            _logger.error("Unexpectedly disconnected from MQTT broker: rc=%s", rc)

    @classmethod
    def _on_mqtt_publish(self, mqtt_client, userdata, mid):
        """MQTT callback is invoked when message was successfully sent to the MQTT server."""
        _logger.debug("published message %s", str(mid))
