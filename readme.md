# TCPCOM Library

An event-based Python library for TCP communication between multiple devices.

The goal of this was to be easy to use, reliable and applicable to different computers.

The library has been reliably tested with 3 Unix devices in the pipeline

- PC acting as the server
- Raspberry Pi 3 as a client issuing commands
- Lego Mindstorm EV3 receiving commands and controlling a robot

This is implimented via 2 different calsses - `TCPServer` and `TCPClient`. There always must be at least one server, but you can have multiple clients. Actions are triggered on state changes when given a callback function. Naturally, the server must be started first before any other clients

For simplicity the library was chosen to be event-based with 4 differnt events:

- `LISTENING` - waiting for another device to connect
- `CONNECTED` - another device has successfully connected.
- `MESSAGE` - a message has been received
- `DISCONNECTED` - all devices have been disconnected

The library itself is contained in the `tcpcom.py` and there are 2 examples usages in `server.py` and `client.py`.

** The library also impliments a useful debug mode which can be enabled via the isVerbose flag on class initlisation. **
