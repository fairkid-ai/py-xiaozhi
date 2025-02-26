from enum import Enum
import json
import pyaudio
import opuslib
import time
import threading
import websocket
import pynput
from log import logger
import config
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
audio_info = None
session_id = None
ws_client = None
ws_client_thread = None
send_audio_thread = None
send_audio_stop_token = False


# decoder and speaker for playing server sent audio
opus_decoder = None
speaker = None


def send_audio_task():
    global ws_client, audio, client_state, send_audio_stop_token

    # opus frame size
    frame_size = config.SAMPLE_RATE * config.FRAME_DURATION * config.CHANNELS // 1000

    # init opus encoder
    opus_encoder = opuslib.Encoder(
        config.SAMPLE_RATE, config.CHANNELS, opuslib.APPLICATION_AUDIO
    )

    # open microphone
    microphone = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=config.SAMPLE_RATE,
        input=True,
        frames_per_buffer=frame_size,
    )

    logger.info(f"start sending audio stream")
    try:
        while not send_audio_stop_token:
            if client_state == ClientState.Speaking:
                time.sleep(0.1)
                continue

            # read microphone data
            pcm_data = microphone.read(frame_size)
            opus_data = opus_encoder.encode(pcm_data, frame_size)
            ws_client.send_bytes(opus_data)
    except Exception as e:
        logger.error(f"send audio exception: {e}")
    finally:
        logger.info("stop sending audio stream")
        stop_token = True
        microphone.stop_stream()
        microphone.close()


def websocket_on_open(ws):
    global client_state
    logger.info("websocket open")
    client_state = ClientState.Connected

    # send hello message
    msg = {
        "type": "hello",
        "version": 1,
        "transport": "websocket",
        "audio_params": {
            "format": "opus",
            "sample_rate": config.SAMPLE_RATE,
            "channels": 1,
            "frame_duration": config.FRAME_DURATION,
        },
    }
    ws.send_text(json.dumps(msg))
    logger.info(f"sent hello message: {msg}")


def websocket_on_close(ws, status_code, close_msg):
    logger.info(
        f"websocket closed, status code: {status_code}, close message: {close_msg}"
    )


def websocket_on_error(ws, err):
    logger.error(f"error occurs: {err}")


def websocket_on_data(ws, data, data_type, continue_flag):
    if data_type == websocket.ABNF.OPCODE_BINARY:
        websocket_on_binary(ws, data)
    elif data_type == websocket.ABNF.OPCODE_TEXT:
        websocket_on_message(ws, data)


def websocket_on_binary(ws, data):
    # receive audio data
    global speaker, opus_decoder, audio_info
    if opus_decoder and speaker:
        sample_rate = audio_info["sample_rate"]
        channels = audio_info["channels"]
        frame_duration = audio_info["frame_duration"]
        opus_data = data
        frame_size = sample_rate * frame_duration * channels // 1000
        pcm_data = opus_decoder.decode(opus_data, frame_size)
        speaker.write(pcm_data)


def websocket_on_message(ws, msg):
    global audio_info, session_id, speaker, opus_decoder
    global send_audio_thread, send_audio_stop_token, client_state

    j_msg = json.loads(msg)
    logger.info(f"recv json message: {j_msg}")

    msg_type = j_msg["type"]
    if msg_type == "hello":
        audio_info = j_msg["audio_params"]
        session_id = j_msg["session_id"]

        sample_rate = audio_info["sample_rate"]
        channels = audio_info["channels"]
        frame_duration = audio_info["frame_duration"]
        frame_size = sample_rate * frame_duration * channels // 1000
        opus_decoder = opuslib.Decoder(sample_rate, channels)
        speaker = audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            output=True,
            frames_per_buffer=frame_size,
        )

        if send_audio_thread and send_audio_thread.is_alive():
            send_audio_stop_token = True
            send_audio_thread.join()
        send_audio_stop_token = False
        send_audio_thread = threading.Thread(target=send_audio_task)
        send_audio_thread.start()

        client_state = ClientState.Listening

    elif msg_type == "goodbye":
        cleanup()


def open_websocket():
    global ws_client_thread
    ws_client = websocket.WebSocketApp(
        config.WEBSOCKET_URL,
        header={
            "Authorization": "Bearer test-token",
            "Protocol-Version": "1",
            "Device-Id": config.DEVICE_ID,
            "Client-Id": config.CLIENT_ID,
        },
        on_open=websocket_on_open,
        on_close=websocket_on_close,
        on_error=websocket_on_error,
        on_data=websocket_on_data,
    )

    ws_client_thread = threading.Thread(target=ws_client.run_forever)
    ws_client_thread.start()
    return ws_client


def keyboard_on_space_pressed():
    global ws_client
    global space_key_state, listen_state, session_id
    if space_key_state == KeyboardKeyState.Pressed:
        return
    space_key_state = KeyboardKeyState.Pressed

    if client_state == ClientState.Idle:
        listen_state = ClientState.Connecting
        # send hello message to start connection
        ws_client = open_websocket()

    if session_id is not None:
        # send start message
        msg = {
            "session_id": session_id,
            "type": "listen",
            "state": "start",
            "mode": "manual",
        }
        ws_client.send_text(json.dumps(msg))
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
        ws_client.send_text(json.dumps(msg))
        logger.info(f"sent stop listening message: {msg}")


def keyboard_on_a_released():
    global client_state, session_id
    # send abort message
    if session_id:
        ws_client.send_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "type": "abort",
                    "reason": "abort key pressed",
                }
            )
        )
        client_state = ClientState.Listening


def keyboard_on_q_released():
    # global stop_token
    # stop_token = True
    # logger.info("stop listen")
    pass


def keyboard_on_press(key):
    if key == pynput.keyboard.Key.space:
        keyboard_on_space_pressed()


def keyboard_on_release(key):
    if key == pynput.keyboard.Key.space:
        keyboard_on_space_released()
    elif key == pynput.keyboard.KeyCode(char="a"):
        keyboard_on_a_released()
    elif key == pynput.keyboard.KeyCode(char="q"):
        keyboard_on_q_released()
    elif key == pynput.keyboard.Key.esc:
        return False


def cleanup():
    global send_audio_stop_token
    send_audio_stop_token = True
    if send_audio_thread and send_audio_thread.is_alive():
        send_audio_thread.join()
    if ws_client:
        ws_client.close()
    if ws_client_thread and ws_client_thread.is_alive():
        ws_client_thread.join()
    if speaker:
        speaker.stop_stream()
        speaker.close()
    if audio:
        audio.terminate()


def main():
    global audio, speaker
    global ws_client, ws_client_thread
    global send_audio_stop_token, send_audio_thread

    # load config
    config.load_config()

    # connect to api server
    j_res = connect_api_server()
    if "activation" in j_res:
        logger.info(f"activation code: {j_res['activation']}")
        return

    # init audio
    audio = pyaudio.PyAudio()

    # create keyboard listener
    keyboard_listener = pynput.keyboard.Listener(
        on_press=keyboard_on_press,
        on_release=keyboard_on_release,
    )
    keyboard_listener.start()

    logger.info("run until keyboard interupt ...")
    keyboard_listener.join()

    logger.info("quit, cleanup resources")
    cleanup()


if __name__ == "__main__":
    main()
