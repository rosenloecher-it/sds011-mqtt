from enum import Enum


class ConfigKey(Enum):
    CONF_FILE = "conf_file"
    LOG_FILE = "log_file"
    LOG_LEVEL = "log_level"
    LOG_MAX_BYTES = "log_max_bytes"
    LOG_MAX_COUNT = "log_max_count"
    LOG_PRINT = "log_print"
    MOCK_SENSOR = "mock_sensor"
    SERIAL_PORT = "serial_port"
    SYSTEMD = "systemd"
    SENSOR_WAIT = "sensor_wait"
    SENSOR_WARM_UP_TIME = "sensor_warm_up_time"
    SENSOR_COOL_DOWN_TIME = "sensor_cool_down_time"
    SENSOR_IGNORE_N_ERRORS = "sensor_ignore_n_errors"
    SENSOR_TEMP_RANGE = "sensor_temperatur_range"
    SENSOR_HUMI_RANGE = "sensor_humidity_range"

    TIME_SWITCHING_ON = "time_switching_on"

    MQTT_CHANNEL_STATE = "mqtt_channel_state"
    MQTT_CHANNEL_SWITCH = "mqtt_channel_switch"
    MQTT_CHANNEL_CMD_TEMP = "mqtt_channel_cmd_temp"
    MQTT_CHANNEL_CMD_HUMI = "mqtt_channel_cmd_humi"
    MQTT_CHANNEL_CMD_HOLD = "mqtt_channel_cmd_hold"

    MQTT_LAST_WILL = "mqtt_last_will"
    MQTT_QUALITY = "mqtt_quality"
    MQTT_RETAIN = "mqtt_retain"

    MQTT_HOST = "mqtt_host"
    MQTT_PORT = "mqtt_port"
    MQTT_PROTOCOL = "mqtt_protocol"
    MQTT_CLIENT_ID = "mqtt_client_id"
    MQTT_KEEPALIVE = "mqtt_keepalive"
    MQTT_SSL_CA_CERTS = "mqtt_ssl_ca_certs"
    MQTT_SSL_CERTFILE = "mqtt_ssl_certfile"
    MQTT_SSL_INSECURE = "mqtt_ssl_insecure"
    MQTT_SSL_KEYFILE = "mqtt_ssl_keyfile"
    MQTT_USER_NAME = "mqtt_user_name"
    MQTT_USER_PWD = "mqtt_user_pwd"

    def __str__(self):
        return self.__repr__()

    def __repr__(self) -> str:
        return '{}'.format(self.name)
