import logging
import os
from argparse import ArgumentParser
from enum import Enum

import yaml

from src.constant import Constant


class ConfMainKey(Enum):
    CONF_FILE = "conf_file"
    LOG_FILE = "log_file"
    LOG_LEVEL = "log_level"
    LOG_MAX_BYTES = "log_max_bytes"
    LOG_MAX_COUNT = "log_max_count"
    LOG_PRINT = "log_print"
    SERIAL_PORT = "serial_port"
    SYSTEMD = "systemd"
    SENSOR_WAIT = "sensor_wait"
    SENSOR_WARM_UP_TIME = "sensor_warm_up_time"
    SENSOR_COOL_DOWN_TIME = "sensor_cool_down_time"
    SENSOR_MAX_ERRORS_TO_IGNORE = "sensor_max_errors_to_ignore"

    MQTT_CHANNEL = "mqtt_channel"
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


class Config:

    CLI_KEYS_ONLY = [ConfMainKey.CONF_FILE, ConfMainKey.LOG_PRINT, ConfMainKey.SYSTEMD]

    def __init__(self, config):
        self._config = config

    @classmethod
    def load(cls, config):
        instance = Config(config)
        instance._parse_cli()
        instance._load_conf_file()

    def _load_conf_file(self):
        conf_file = self._config[ConfMainKey.CONF_FILE.value]
        if not os.path.isfile(conf_file):
            raise FileNotFoundError('config file ({}) does not exist!'.format(conf_file))
        with open(conf_file, 'r') as stream:
            data = yaml.unsafe_load(stream)

        # main section
        def update_main(config, item_enum):
            item_name = item_enum.value
            value_cli = self._config.get(item_name)
            if value_cli is None:
                value_file = config.get(item_name)
                self._config[item_name] = value_file

        section = data  # no section
        if not isinstance(section, dict):
            raise RuntimeError("configuration expected to be a dictionary!")
        for e in ConfMainKey:
            if e != self.CLI_KEYS_ONLY:
                update_main(section, e)

    def _parse_cli(self):
        parser = self.create_cli_parser()
        args = parser.parse_args()

        def handle_cli(key_enum, default_value=None):
            key = key_enum.value
            value = getattr(args, key, default_value)
            self._config[key] = value

        handle_cli(ConfMainKey.CONF_FILE, Constant.DEFAULT_CONFFILE)
        handle_cli(ConfMainKey.SYSTEMD)

        handle_cli(ConfMainKey.LOG_LEVEL)
        handle_cli(ConfMainKey.LOG_FILE)
        handle_cli(ConfMainKey.LOG_MAX_BYTES)
        handle_cli(ConfMainKey.LOG_MAX_COUNT)
        handle_cli(ConfMainKey.LOG_PRINT)

    @classmethod
    def create_cli_parser(cls):
        parser = ArgumentParser(
            description=Constant.APP_DESC,
            add_help=True
        )

        parser.add_argument(
            "-c", "--" + ConfMainKey.CONF_FILE.value,
            help="config file path",
            default=Constant.DEFAULT_CONFFILE
        )
        parser.add_argument(
            "-f", "--" + ConfMainKey.LOG_FILE.value,
            help="log file (if stated journal logging ist disabled)"
        )
        parser.add_argument(
            "-l", "--" + ConfMainKey.LOG_LEVEL.value,
            choices=["debug", "info", "warning", "error"],
            help="set log level"
        )
        parser.add_argument(
            "-p", "--" + ConfMainKey.LOG_PRINT.value,
            action="store_true",
            default=None,
            help="print log output to console too"
        )
        parser.add_argument(
            "-s", "--" + ConfMainKey.SYSTEMD.value,
            action="store_true",
            default=None,
            help="systemd/journald integration (skip timestamp + prints to console)"
        )
        parser.add_argument(
            "-v", "--version",
            action="version",
            version="{} v{}".format(Constant.APP_NAME, Constant.APP_VERSION)
        )

        return parser

    @classmethod
    def get_str(cls, config, key_enum, default=None):
        key = key_enum.value
        value = config.get(key)
        if value is None:  # value could be inserted by CLI as None so dict.default doesn't work
            value = default

        if value != default and not isinstance(value, str):
            raise ValueError(f"expected type 'str' for '{key}'!")

        return value

    @classmethod
    def get_bool(cls, config, key_enum, default=None):
        key = key_enum.value
        value = config.get(key)

        if not isinstance(value, bool):
            if value is None:
                value = default
            else:
                temp = str(value).lower().strip()
                if temp in ["true", "1", "on", "active"]:
                    value = True
                elif temp in ["false", "0", "off", "inactive"]:
                    value = False

        if value != default and not isinstance(value, bool):
            raise ValueError(f"expected type 'bool' for '{key}'!")

        return value

    @classmethod
    def get_float(cls, config, key_enum, default=None):
        key = key_enum.value
        value = config.get(key)

        if not isinstance(value, float):
            if value is None:
                value = default
            else:
                try:
                    value = float(value)
                except ValueError:
                    print("cannot parse {} ({}) as float!".format(key, value))

    @classmethod
    def get_int(cls, config, key_enum, default=None):
        key = key_enum.value
        value = config.get(key)

        if not isinstance(value, int):
            if value is None:
                value = default
            else:
                try:
                    value = int(value, 0)  # auto convert hex
                except ValueError:
                    print("cannot parse {} ({}) as int!".format(key, value))

        if value != default and not isinstance(value, int):
            raise ValueError(f"expected type 'int' for '{key}'!")

        return value

    @classmethod
    def get_loglevel(cls, config, key_enum, default=logging.INFO):
        key = key_enum.value
        value = config.get(key)

        if not isinstance(value, type(logging.INFO)):
            input = str(value).lower().strip() if value is not None else value
            if input == "debug":
                value = logging.DEBUG
            elif input == "info":
                value = logging.INFO
            elif input == "warning":
                value = logging.WARNING
            elif input == "error":
                value = logging.ERROR
            else:
                if input is not None:
                    print("cannot parse {} ({})!".format(key, input))
                value = default

        return value
