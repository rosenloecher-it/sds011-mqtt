import logging
import os
from argparse import ArgumentParser

import yaml

from src.config_key import ConfigKey
from src.constant import Constant


class Config:

    CLI_KEYS_ONLY = [ConfigKey.CONF_FILE, ConfigKey.LOG_PRINT, ConfigKey.SYSTEMD]

    def __init__(self, config):
        self._config = config

    @classmethod
    def load(cls, config):
        instance = Config(config)
        instance._parse_cli()
        instance._load_conf_file()

    def _load_conf_file(self):
        conf_file = self._config[ConfigKey.CONF_FILE.value]
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
        for e in ConfigKey:
            if e != self.CLI_KEYS_ONLY:
                update_main(section, e)

    def _parse_cli(self):
        parser = self.create_cli_parser()
        args = parser.parse_args()

        def handle_cli(key_enum, default_value=None):
            key = key_enum.value
            value = getattr(args, key, default_value)
            self._config[key] = value

        handle_cli(ConfigKey.CONF_FILE, Constant.DEFAULT_CONFFILE)
        handle_cli(ConfigKey.SYSTEMD)

        handle_cli(ConfigKey.LOG_LEVEL)
        handle_cli(ConfigKey.LOG_FILE)
        handle_cli(ConfigKey.LOG_MAX_BYTES)
        handle_cli(ConfigKey.LOG_MAX_COUNT)
        handle_cli(ConfigKey.LOG_PRINT)
        handle_cli(ConfigKey.MOCK_SENSOR, False)

        # list_non_recognized_settings


    @classmethod
    def create_cli_parser(cls):
        parser = ArgumentParser(
            description=Constant.APP_DESC,
            add_help=True
        )

        parser.add_argument(
            "-c", "--" + ConfigKey.CONF_FILE.value,
            help="config file path",
            default=Constant.DEFAULT_CONFFILE
        )
        parser.add_argument(
            "-f", "--" + ConfigKey.LOG_FILE.value,
            help="log file (if stated journal logging ist disabled)"
        )
        parser.add_argument(
            "-l", "--" + ConfigKey.LOG_LEVEL.value,
            choices=["debug", "info", "warning", "error"],
            help="set log level"
        )
        parser.add_argument(
            "-m", "--" + ConfigKey.MOCK_SENSOR.value,
            action="store_true",
            default=None,
            help="mocked sensor (debugging purpose)"
        )
        parser.add_argument(
            "-p", "--" + ConfigKey.LOG_PRINT.value,
            action="store_true",
            default=None,
            help="print log output to console too"
        )
        parser.add_argument(
            "-s", "--" + ConfigKey.SYSTEMD.value,
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

        return value

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
