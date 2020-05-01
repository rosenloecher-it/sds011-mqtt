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
    SENSOR_INTERVAL = "sensor_interval"
    SENSOR_WARMUP_TIME = "sensor_warmup_time"
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
        instance._post_process()

    def _post_process(self):
        self.post_process_loglevel(self._config)

        self.post_process_int(self._config, ConfMainKey.LOG_MAX_BYTES, Constant.DEFAULT_LOG_MAX_BYTES)
        self.post_process_int(self._config, ConfMainKey.LOG_MAX_COUNT, Constant.DEFAULT_LOG_MAX_COUNT)

        self.post_process_float(self._config, ConfMainKey.SENSOR_INTERVAL, Constant.DEFAULT_SENSOR_INTERVAL)
        self.post_process_float(self._config, ConfMainKey.SENSOR_WARMUP_TIME, Constant.DEFAULT_SENSOR_WARMUP_TIME)

        self.post_process_int(self._config, ConfMainKey.MQTT_KEEPALIVE, Constant.DEFAULT_MQTT_KEEPALIVE)
        self.post_process_int(self._config, ConfMainKey.MQTT_PORT, None)
        self.post_process_int(self._config, ConfMainKey.MQTT_PROTOCOL, Constant.DEFAULT_MQTT_PROTOCOL)

        self.post_process_bool(self._config, ConfMainKey.MQTT_SSL_INSECURE, False)

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
    def post_process(cls, config, key_enum, default=None):
        key = key_enum.value
        value_in = config.get(key)

        if type(value_in) != str:
            if value_in is None:
                config[key] = default
            else:
                config[key] = str(value_in)

        return config[key]

    @classmethod
    def post_process_str(cls, config, key_enum, default=None):
        key = key_enum.value
        value_in = config.get(key)

        if type(value_in) != str:
            if value_in is None:
                config[key] = default
            else:
                config[key] = str(value_in)

        return config[key]

    @classmethod
    def post_process_bool(cls, config, key_enum, default):
        key = key_enum.value
        value_in = config.get(key)

        if type(value_in) != bool:
            if value_in is None:
                config[key] = default
            else:
                temp = str(value_in).lower().strip()
                config[key] = temp in ["true", "1", "on", "active"]

        return config[key]

    @classmethod
    def post_process_float(cls, config, key_enum, default):
        key = key_enum.value
        value_in = config.get(key)

        if type(value_in) != float:
            if value_in is None:
                config[key] = default
            else:
                try:
                    config[key] = float(value_in)
                except ValueError:
                    print("cannot parse {} ({}) as float!".format(key, value_in))

    @classmethod
    def post_process_int(cls, config, key_enum, default):
        key = key_enum.value
        value_in = config.get(key)

        if type(value_in) != int:
            if value_in is None:
                config[key] = default
            else:
                try:
                    config[key] = int(value_in, 0)  # auto convert hex
                except ValueError:
                    print("cannot parse {} ({}) as int!".format(key, value_in))

        return config[key]

    @classmethod
    def post_process_loglevel(cls, config):
        key = ConfMainKey.LOG_LEVEL.value
        value_in = config.get(key)

        if not isinstance(value_in, type(logging.INFO)):
            log_level = str(value_in).lower().strip() if value_in is not None else value_in
            if log_level == "debug":
                value_out = logging.DEBUG
            elif log_level == "info":
                value_out = logging.INFO
            elif log_level == "warning":
                value_out = logging.WARNING
            elif log_level == "error":
                value_out = logging.ERROR
            else:
                if log_level is not None:
                    print("cannot parse {} ({})!".format(key, log_level))
                value_out = Constant.DEFAULT_LOGLEVEL

            config[key] = value_out

        return config[key]