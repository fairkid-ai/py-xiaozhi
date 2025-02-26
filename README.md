# py-xiaozhi
This is a Python implemention of the Xiaozhi client. It supports both websocket and UDP+MQTT protocols. It was developed to assist in debugging another project. If you like it, take it and enjoy!

This project takes a lot of ideas from [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) and [zhh827/py-xiaozhi](https://github.com/zhh827/py-xiaozhi). Credits given to the developers of these two projects.

## Dependencies
* Setup Python environment
  ```
  conda create -n py-xiaozhi python=3.12
  conda activate py-xiaozhi
  ```
* Install dependencies
  ```
  pip install -r requirements.txt
  ```
* Install libopus
  * (Windows) Copy `opus.dll` to `C:\Windows\System32` folder.
  * (Linux) `sudo apt install libopus-dev`
  * (MAC) I do not know.

## Usage
* Websocket client
  ```
  python websocket-client.py
  ```
  * Press and release space key to initiate the websocket connection.
  * After connected, press and hold the space key to start speaking.
  * Press and release Esc key to exit.
* UDP+MQTT client
  ```
  python udp-client.py
  ```
  * Press and release space key to initiate the UDP+MQTT connection.
  * After connected, press and hold the space key to speak.
  * Press Ctrl-C to quit.
* Notes:
  * On the first run, it creates a configuration file named `config.yml` in the project folder. In most cases, you do not need to modify it. But if it is required, modify it accordingly.
  * Bind your client to the Xiozhi server: [xiaozhi.me](https://xiaozhi.me/) before talking to it.
  * Refer to [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) for more help on how to use Xiaozhi.
## Known issues and limitations
 - [ ] The Websocket client does not currently support multiple conversations. Quit and restart the client to start a new conversation. Ihe issue will be addressed in future updates.

## Requirements and Contributions
Contributions are warmly welcome! Please submit issues or pull requests if you have any suggestions or improvements..

## Credits
 * [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
 * [zhh827/py-xiaozhi](https://github.com/zhh827/py-xiaozhi)
