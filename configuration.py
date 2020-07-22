import configparser

CONFIG_NAME = "config.ini"

def read_config():
    print("reading")
    cfg = configparser.ConfigParser()
    with open(CONFIG_NAME, "r") as f:
        cfg.read_file(f)
    print("read")
    return cfg


def make_default_config():
    cfg = configparser.ConfigParser()

    cfg["default paths"] = {
        "iso": "",
        "mods": ""
    }


    with open(CONFIG_NAME, "w") as f:
        cfg.write(f)

    return cfg


def save_cfg(cfg):
    with open(CONFIG_NAME, "w") as f:
        cfg.write(f)