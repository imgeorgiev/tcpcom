#!/usr/bin/env python3

'''
Example usage of the TCPServer class from the TCPCOM library
'''

from tcpcom import TCPServer

# connection configuration settings
tcp_ip = "169.254.23.44"
tcp_port = 5005
tcp_reply = "Server message"


def onStateChanged(state, msg):
    global isConnected

    if state == "LISTENING":
        print("Server:-- Listening...")
    elif state == "CONNECTED":
        isConnected = True
        print("Server:-- Connected to" + msg)
    elif state == "MESSAGE":
        print("Server:-- Message received:", msg)
        server.sendMessage(tcp_reply)


def main():
    global server
    server = TCPServer(tcp_port, stateChanged=onStateChanged)


if __name__ == '__main__':
    main()
