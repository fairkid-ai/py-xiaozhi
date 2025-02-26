import requests
import json
import config
from log import logger


def connect_api_server():
    global mqtt_info
    res = requests.post(
        config.API_OTA_URL,
        headers={"Device-Id": config.DEVICE_ID, "Content-Type": "application/json"},
        json={
            "flash_size": 16777216,
            "minimum_free_heap_size": 8318916,
            "mac_address": config.MAC_ADDR,
            "chip_model_name": "esp32s3",
            "chip_info": {"model": 9, "cores": 2, "revision": 2, "features": 18},
            "application": {
                "name": "xiaozhi",
                "version": "1.1.2",
                "compile_time": "Jan 22 2025T20:40:23Z",
                "idf_version": "v5.3.2-dirty",
                "elf_sha256": "22986216df095587c42f8aeb06b239781c68ad8df80321e260556da7fcf5f522",
            },
            "partition_table": [
                {
                    "label": "nvs",
                    "type": 1,
                    "subtype": 2,
                    "address": 36864,
                    "size": 16384,
                },
                {
                    "label": "otadata",
                    "type": 1,
                    "subtype": 0,
                    "address": 53248,
                    "size": 8192,
                },
                {
                    "label": "phy_init",
                    "type": 1,
                    "subtype": 1,
                    "address": 61440,
                    "size": 4096,
                },
                {
                    "label": "model",
                    "type": 1,
                    "subtype": 130,
                    "address": 65536,
                    "size": 983040,
                },
                {
                    "label": "storage",
                    "type": 1,
                    "subtype": 130,
                    "address": 1048576,
                    "size": 1048576,
                },
                {
                    "label": "factory",
                    "type": 0,
                    "subtype": 0,
                    "address": 2097152,
                    "size": 4194304,
                },
                {
                    "label": "ota_0",
                    "type": 0,
                    "subtype": 16,
                    "address": 6291456,
                    "size": 4194304,
                },
                {
                    "label": "ota_1",
                    "type": 0,
                    "subtype": 17,
                    "address": 10485760,
                    "size": 4194304,
                },
            ],
            "ota": {"label": "factory"},
            "board": {
                "type": "bread-compact-wifi",
                "ssid": "PPAN",
                "rssi": -58,
                "channel": 6,
                "ip": "10.1.1.150",
                "mac": config.MAC_ADDR,
            },
        },
    )
    if res.status_code != 200:
        logger.error(f"connect api server failed: {res.status_code}")
        raise

    j_res = res.json()
    logger.info(j_res)
    return j_res
