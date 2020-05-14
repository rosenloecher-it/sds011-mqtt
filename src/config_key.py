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

    TIME_INTERVAL_MAX = "time_interval_max"
    TIME_INTERVAL_MIN = "time_interval_min"
    TIME_WARM_UP = "time_warm_up"
    TIME_COOL_DOWN = "time_cool_down"
    TIME_WAIT_FOR_ACTOR = "time_wait_for_actor"

    ABORT_AFTER_N_ERRORS = "abort_after_n_errors"
    TEMPERATURE_RANGE = "temperatur_range"
    HUMIDITY_RANGE = "humidity_range"
    DEACTIVATION_TIME_RANGES = "deactivation_time_ranges"

    MQTT_CHANNEL_OUT_STATE = "mqtt_channel_out_state"
    MQTT_CHANNEL_OUT_ACTOR = "mqtt_channel_out_actor"
    MQTT_CHANNEL_IN_TEMP = "mqtt_channel_in_temp"
    MQTT_CHANNEL_IN_HUMI = "mqtt_channel_in_humi"
    MQTT_CHANNEL_IN_HOLD = "mqtt_channel_in_hold"

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
