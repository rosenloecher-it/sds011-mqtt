import logging


class Constant:
    APP_NAME = "SDS011 sensor to MQTT Bridge"
    APP_DESC = "Forwards fin dust measurements to MQTT"
    APP_VERSION = "0.0.1"

    DEFAULT_CONFFILE = "/etc/sds011-mqtt.conf"

    DEFAULT_LOGLEVEL = logging.INFO
    DEFAULT_LOG_MAX_BYTES = 1048576
    DEFAULT_LOG_MAX_COUNT = 10
    DEFAULT_LOG_PRINT = False
    DEFAULT_SYSTEMD = False
