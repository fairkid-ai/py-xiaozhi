import json
import requests
import time
import opuslib
import socket
import pyaudio
import pynput
import opuslib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import threading
from enum import Enum
import paho.mqtt.client as mqtt
import config
from log import logger
from api_server import connect_api_server


class ClientState(Enum):
    Idle = "idle"
    Connecting = "connecting"
    Connected = "connected"
    Listening = "listening"
    Speaking = "speaking"


class KeyboardKeyState(Enum):
    Pressed = "pressed"
    Released = "released"


stop_token = False
audio = None
audio_sequence = 0
space_key_state = KeyboardKeyState.Released
client_state = ClientState.Idle
mqttc = None
mqtt_info = None
udp_socket = None
udp_info = None
audio_info = None
session_id = None
send_audio_thread = None
recv_audio_thread = None


def aes_ctr_encrypt(key, nonce, plaintext):
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(plaintext) + encryptor.finalize()


def aes_ctr_decrypt(key, nonce, ciphertext):
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext


def udp_send_audio_task():
    global udp_socket, udp_info, audio
    global session_id, client_state, stop_token

    aes_key = bytes.fromhex(udp_info["key"])
    aes_nonce = udp_info["nonce"]
    server_ip = udp_info["server"]
    server_port = udp_info["port"]

    frame_size = config.SAMPLE_RATE * config.CHANNELS * config.FRAME_DURATION // 1000

    # init opus encoder
    opus_encoder = opuslib.Encoder(
        config.SAMPLE_RATE, config.CHANNELS, opuslib.APPLICATION_AUDIO
    )

    # open microphone
    microphone = audio.open(
        format=pyaudio.paInt16,
        channels=config.CHANNELS,
        rate=config.SAMPLE_RATE,
        input=True,
        frames_per_buffer=frame_size,
    )
    audio_sequence = 0

    logger.info(f"start sending audio stream")
    try:
        while not stop_token:
            if client_state == ClientState.Speaking:
                time.sleep(0.1)
                continue

            # read microphone data
            pcm_data = microphone.read(frame_size)
            opus_data = opus_encoder.encode(pcm_data, frame_size)
            audio_sequence += 1
            new_nonce = bytes.fromhex(
                aes_nonce[0:4]
                + format(len(opus_data), "04x")
                + aes_nonce[8:24]
                + format(audio_sequence, "08x")
            )
            encrypt_data = aes_ctr_encrypt(aes_key, new_nonce, opus_data)
            udp_data = new_nonce + encrypt_data
            udp_socket.sendto(udp_data, (server_ip, server_port))
    except Exception as e:
        logger.error(f"udp send audio exception: {e}")
    finally:
        logger.info("stop sending audio stream")
        stop_token = True
        udp_socket.close()
        microphone.stop_stream()
        microphone.close()


def udp_recv_audio_task():
    global udp_socket, udp_info, audio_info, audio
    global client_state, stop_token

    aes_key = bytes.fromhex(udp_info["key"])
    sample_rate = audio_info["sample_rate"]
    channels = audio_info["channels"]
    frame_duration = audio_info["frame_duration"]
    frame_size = frame_duration * sample_rate // 1000
    print(
        f"recv audio: sample_rate -> {sample_rate}, frame_duration -> {frame_duration}, frame_size -> {frame_size}"
    )

    # create opus decoder
    opus_decoder = opuslib.Decoder(sample_rate, channels)
    speaker = audio.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=sample_rate,
        output=True,
        frames_per_buffer=frame_size,
    )

    logger.info("start receiving audio stream")
    try:
        while not stop_token:
            client_state = ClientState.Listening
            udp_data, remote_addr = udp_socket.recvfrom(4096)
            client_state = ClientState.Speaking

            # decrypt data
            aes_nonce = udp_data[:16]
            encrypt_data = udp_data[16:]
            opus_data = aes_ctr_decrypt(aes_key, aes_nonce, encrypt_data)
            pcm_data = opus_decoder.decode(opus_data, frame_size)
            speaker.write(pcm_data)
    except Exception as e:
        logger.error(f"udp recv audio exception: {e}")
    finally:
        logger.info("stop receiving audio stream")
        stop_token = True
        udp_socket.close()
        speaker.stop_stream()
        speaker.close()


def test_audio():
    aes_key = b"1234567890123456"  # AES-256 key
    aes_nonce = b"1234567890123456"  # Initialization vector (IV) or nonce for CTR mode
    print(f"aes_key: {aes_key}, aes_nonce: {aes_nonce}")

    frame_size = config.SAMPLE_RATE * config.CHANNELS * config.FRAME_DURATION // 1000
    encoder = opuslib.Encoder(
        config.SAMPLE_RATE, config.CHANNELS, opuslib.APPLICATION_AUDIO
    )
    decoder = opuslib.Decoder(config.SAMPLE_RATE, config.CHANNELS)
    audio = pyaudio.PyAudio()

    # open microphone
    microphone = audio.open(
        format=pyaudio.paInt16,
        channels=config.CHANNELS,
        rate=config.SAMPLE_RATE,
        input=True,
        frames_per_buffer=frame_size,
    )

    # open speaker
    speaker = audio.open(
        format=pyaudio.paInt16,
        channels=config.CHANNELS,
        rate=config.SAMPLE_RATE,
        output=True,
        frames_per_buffer=frame_size,
    )

    try:
        while True:
            # read microphone
            pcm_data = microphone.read(frame_size)
            # encode pcm
            opus_data = encoder.encode(pcm_data, frame_size)
            # encryption
            encyrpted_data = aes_ctr_encrypt(aes_key, aes_nonce, opus_data)
            udp_data = aes_nonce + encyrpted_data

            # decrypting
            recv_nonce = udp_data[: len(aes_nonce)]
            encyrpted_data = udp_data[len(aes_nonce) :]
            opus_data = aes_ctr_decrypt(aes_key, recv_nonce, encyrpted_data)
            # decoding
            pcm_data = decoder.decode(opus_data, frame_size)
            speaker.write(pcm_data)
    except KeyboardInterrupt:
        print("Stop recording.")
    finally:
        microphone.stop_stream()
        microphone.close()
        speaker.stop_stream()
        speaker.close()
        audio.terminate()


def mqtt_on_connect(client, userdata, flags, rs, pr):
    global mqtt_info
    logger.info("connected to mqtt server")
    sub_topic = mqtt_info["subscribe_topic"]
    client.subscribe(sub_topic)
    logger.info(f"subscribed to topic: {sub_topic}")


def mqtt_on_message(client, userdata, message):
    global udp_socket, udp_info, client_state
    global audio_info, session_id, stop_token
    global recv_audio_thread, send_audio_thread

    j_msg = json.loads(message.payload)
    logger.info(f"recv mqtt message: {j_msg}")

    msg_type = j_msg["type"]
    if msg_type == "hello":
        client_state = ClientState.Connected
        udp_info = j_msg["udp"]
        audio_info = j_msg["audio_params"]
        session_id = j_msg["session_id"]
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.connect((udp_info["server"], udp_info["port"]))
        if recv_audio_thread is None:
            recv_audio_thread = threading.Thread(target=udp_recv_audio_task)
            recv_audio_thread.start()
        if send_audio_thread is None:
            send_audio_thread = threading.Thread(target=udp_send_audio_task)
            send_audio_thread.start()
    elif msg_type == "goodbye":
        if listen_state == ClientState.Idle:
            return

        time.sleep(1)
        stop_token = True
        if udp_socket:
            udp_socket.close()
        if recv_audio_thread is not None:
            recv_audio_thread.join()
            recv_audio_thread = None
        if send_audio_thread is not None:
            send_audio_thread.join()
            send_audio_thread = None
    elif msg_type == "tts":
        tts_state = j_msg["state"]
        logger.info(f"tts_state: {tts_state}")
    else:
        logger.warning(f"not supported message type: {msg_type}")


def mqtt_pub_message(message):
    global mqtt_info, mqttc
    mqttc.publish(mqtt_info["publish_topic"], json.dumps(message))


def keyboard_on_space_pressed():
    global space_key_state, listen_state, session_id
    if space_key_state == KeyboardKeyState.Pressed:
        return
    space_key_state = KeyboardKeyState.Pressed

    if client_state == ClientState.Idle:
        listen_state = ClientState.Connecting
        # send hello message to start connection
        msg = {
            "type": "hello",
            "version": 3,
            "transport": "udp",
            "audio_params": {
                "format": "opus",
                "sample_rate": config.SAMPLE_RATE,
                "channels": config.CHANNELS,
                "frame_duration": config.FRAME_DURATION,
            },
        }
        mqtt_pub_message(msg)
        logger.info(f"sent hello message: {msg}")

    if session_id is not None:
        # send start message
        msg = {
            "session_id": session_id,
            "type": "listen",
            "state": "start",
            "mode": "manual",
        }
        mqtt_pub_message(msg)
        logger.info(f"sent start listening message: {msg}")


def keyboard_on_space_released():
    global space_key_state, session_id
    space_key_state = KeyboardKeyState.Released

    if session_id is not None:
        # send stop message
        msg = {
            "session_id": session_id,
            "type": "listen",
            "state": "stop",
        }
        mqtt_pub_message(msg)
        logger.info(f"sent stop listening message: {msg}")


def keyboard_on_a_released():
    global client_state
    # send abort message
    if client_state == ClientState.Speaking:
        mqtt_pub_message({"type": "abort"})
        client_state = ClientState.Listening


def keyboard_on_esc_released():
    global stop_token
    stop_token = True
    logger.info("stop listen")


def keyboard_on_press(key):
    if key == pynput.keyboard.Key.space:
        keyboard_on_space_pressed()


def keyboard_on_release(key):
    if key == pynput.keyboard.Key.space:
        keyboard_on_space_released()
    elif key == pynput.keyboard.KeyCode(char="a"):
        keyboard_on_a_released()
    elif key == pynput.keyboard.Key.esc:
        keyboard_on_esc_released()


def main():
    global mqttc, mqtt_info, audio, stop_token
    global udp_socket, send_audio_thread, recv_audio_thread

    # load config
    config.load_config()

    # connect to api server
    j_res = connect_api_server()
    if "activation" in j_res:
        logger.info(f"activation code: {j_res['activation']}")
        return
    mqtt_info = j_res["mqtt"]

    # create keyboard listener
    keyboard_listner = pynput.keyboard.Listener(
        on_press=keyboard_on_press,
        on_release=keyboard_on_release,
    )
    keyboard_listner.start()

    # init audio
    audio = pyaudio.PyAudio()

    # create mqtt client
    mqttc = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=mqtt_info["client_id"],
        clean_session=True,
    )
    mqttc.username_pw_set(
        username=mqtt_info["username"],
        password=mqtt_info["password"],
    )
    mqttc.tls_set(
        ca_certs=None,
        certfile=None,
        keyfile=None,
        cert_reqs=mqtt.ssl.CERT_REQUIRED,
        tls_version=mqtt.ssl.PROTOCOL_TLS,
        ciphers=None,
    )
    mqttc.on_connect = mqtt_on_connect
    mqttc.on_message = mqtt_on_message
    mqttc.connect(host=mqtt_info["endpoint"], port=8883)

    try:
        mqttc.loop_forever()
    except KeyboardInterrupt:
        logger.info("received Ctrl+C, stopping the program...")
    finally:
        if mqttc:
            logger.info("disconnecting from MQTT broker...")
            mqttc.loop_stop()
            mqttc.disconnect()
        stop_token = True
        if udp_socket:
            udp_socket.close()
        if send_audio_thread:
            send_audio_thread.join()
        if recv_audio_thread:
            recv_audio_thread.join()

        logger.info("program stopped.")


if __name__ == "__main__":
    # test_audio()
    main()
