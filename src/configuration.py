import logging
import pathlib
import configparser

log = logging.getLogger(__name__)
CONFIG_NAME = str(pathlib.Path(__file__).parent.parent.absolute()) + "/config.ini"


def read_config():
    log.info("Reading configuration...")
    cfg = configparser.ConfigParser()
    with open(CONFIG_NAME, "r") as f:
        cfg.read_file(f)
    log.info("Configuration read")
    return cfg


def make_default_config():
    cfg = configparser.ConfigParser()

    populate_default_config(cfg)

    with open(CONFIG_NAME, "w") as f:
        cfg.write(f)

    return cfg


def update_config(cfg):
    if "options" not in cfg:
        cfg["options"] = {
            "folder_mode": False
        }

        save_cfg(cfg)


def populate_default_config(cfg):
    if 'default paths' not in cfg:
        cfg["default paths"] = {
            "iso": "",
            "mods": "",
        }

    if 'options' not in cfg:
        cfg["options"] = {
            "folder_mode": False,
        }


def save_cfg(cfg):
    with open(CONFIG_NAME, "w") as f:
        cfg.write(f)
