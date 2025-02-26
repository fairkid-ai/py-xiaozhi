import os
import yaml
import psutil
import uuid
from log import logger


API_OTA_URL = "https://api.tenclass.net/xiaozhi/ota/"
WEBSOCKET_URL = "wss://api.tenclass.net/xiaozhi/v1/"
SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_DURATION = 60
MAC_ADDR = None
DEVICE_ID = None
CLIENT_ID = None


def load_mac_addr():
    interfaces = psutil.net_if_addrs()
    for if_name, if_addrs in interfaces.items():
        for addr in if_addrs:
            if addr.family == psutil.AF_LINK:  # AF_LINK is the family for MAC addresses
                return addr.address.replace("-", ":")

    raise ValueError("MAC address not found")


def save_default_config(config_path="config.yml"):
    mac_addr = load_mac_addr()
    device_id = mac_addr
    client_id = str(uuid.uuid4())

    config = {
        "api_ota_url": API_OTA_URL,
        "websocket_url": WEBSOCKET_URL,
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "frame_duration": FRAME_DURATION,
        "mac_addr": mac_addr,
        "device_id": device_id,
        "client_id": client_id,
    }
    with open(config_path, "w") as fp:
        yaml.dump(config, fp)


def load_config(config_path="config.yml"):
    global API_OTA_URL, WEBSOCKET_URL
    global SAMPLE_RATE, CHANNELS, FRAME_DURATION
    global MAC_ADDR, DEVICE_ID, CLIENT_ID

    if not os.path.exists(config_path):
        logger.warning("config file not found, create a new one")
        save_default_config(config_path)

    with open(config_path, "r") as fp:
        conf = yaml.safe_load(fp)

    API_OTA_URL = conf["api_ota_url"]
    WEBSOCKET_URL = conf["websocket_url"]
    SAMPLE_RATE = conf["sample_rate"]
    CHANNELS = conf["channels"]
    FRAME_DURATION = conf["frame_duration"]
    MAC_ADDR = conf["mac_addr"]
    DEVICE_ID = conf["device_id"]
    CLIENT_ID = conf["client_id"]
