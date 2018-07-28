#!/usr/bin/python3

'''
Event-based TCP library for communcation between multiple devices.
The library impliments Server and Client classes.
There always must be at least one server, but you can have multiple clients.
Actions are triggered on state changes when given a callback function. Please
look at the example files on how to impliment this.

The library also impliments a useful debug mode which can be enabled via
the isVerbose flag on class initlisation.
 '''

from threading import Thread
import socket
import time
import sys

TCPCOM_VERSION = "1.26 - Jan. 17, 2018"


# ================================== Server ================================
# ---------------------- class TimeoutThread ------------------------
class TimeoutThread(Thread):
    def __init__(self, server, timeout):
        Thread.__init__(self)
        self.server = server
        self.timeout = timeout
        self.count = 0

    def run(self):
        TCPServer.debug("TimeoutThread starting")
        self.isRunning = True
        isTimeout = False
        while self.isRunning:
            time.sleep(0.01)
            self.count += 1
            if self.count == 100 * self.timeout:
                self.isRunning = False
                isTimeout = True
        if isTimeout:
            TCPServer.debug("TimeoutThread terminated with timeout")
            self.server.disconnect()
        else:
            TCPServer.debug("TimeoutThread terminated without timeout")

    def reset(self):
        self.count = 0

    def stop(self):
        self.isRunning = False


# ---------------------- class TCPServer ------------------------
class TCPServer(Thread):
    '''
    Class that represents a TCP socket based server.
    '''
    isVerbose = False
    PORT_IN_USE = "PORT_IN_USE"
    CONNECTED = "CONNECTED"
    LISTENING = "LISTENING"
    TERMINATED = "TERMINATED"
    MESSAGE = "MESSAGE"

    def __init__(self, port, stateChanged, endOfBlock=b'\0', isVerbose=False):
        '''
        Creates a TCP socket server that listens on TCP port
        for a connecting client. The server runs in its own thread, so the
        constructor returns immediately. State changes invoke the callback
        onStateChanged().

        @param port: the IP port where to listen (0..65535)
        @param stateChange: the callback function to register
        @param endOfBlock: character indicating end of a data block
        @param isVerbose: if true, debug messages are written to System.out
        '''
        Thread.__init__(self)
        self.port = port
        self.endOfBlock = endOfBlock
        self.timeout = 0
        self.stateChanged = stateChanged
        TCPServer.isVerbose = isVerbose
        self.isClientConnected = False
        self.terminateServer = False
        self.isServerRunning = False
        self.start()

    def setTimeout(self, timeout):
        '''
        Sets the maximum time (in seconds) to wait in blocking recv() for an
        incoming message. If the timeout is exceeded, the link to the client
        is disconnected.
        '''
        if timeout < 0:
            self.timeout = 0
        else:
            self.timeout = timeout

    def run(self):
        TCPServer.debug("TCPServer thread started")
        HOSTNAME = ""  # Symbolic name meaning all available interfaces
        self.conn = None
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # close port when process exits
        self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        TCPServer.debug("Socket created")
        try:
            self.serverSocket.bind((HOSTNAME, self.port))
        except socket.error as msg:
            print("Fatal error while creating TCPServer: Bind failed.",
                  msg[0], msg[1])
            sys.exit()
        try:
            self.serverSocket.listen(10)
        except:
            print("Fatal error while creating TCPServer: Port",
                  self.port, "already in use")
            try:
                self.stateChanged(TCPServer.PORT_IN_USE, str(self.port))
            except Exception as e:
                print("Caught exception in TCPServer.PORT_IN_USE:", e)
            sys.exit()

        try:
            self.stateChanged(TCPServer.LISTENING, str(self.port))
        except Exception as e:
            print("Caught exception in TCPServer.LISTENING:", e)

        self.isServerRunning = True

        while True:
            TCPServer.debug("Calling blocking accept()...")
            conn, self.addr = self.serverSocket.accept()
            if self.terminateServer:
                self.conn = conn
                break
            if self.isClientConnected:
                TCPServer.debug("Returning form blocking accept(). Client refused")
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
                continue
            self.conn = conn
            self.isClientConnected = True
            self.socketHandler = ServerHandler(self, self.endOfBlock)
            self.socketHandler.setDaemon(True)  # necessary to terminate thread
            self.socketHandler.start()
            try:
                self.stateChanged(TCPServer.CONNECTED, self.addr[0])
            except Exception as e:
                print("Caught exception in TCPServer.CONNECTED:", e)
        self.conn.close()
        self.serverSocket.close()
        self.isClientConnected = False
        try:
            self.stateChanged(TCPServer.TERMINATED, "")
        except Exception as e:
            print("Caught exception in TCPServer.TERMINATED:", e)
        self.isServerRunning = False
        TCPServer.debug("TCPServer thread terminated")

    def terminate(self):
        '''
        Closes the connection and terminates the server thread.
        Releases the IP port.
        '''
        TCPServer.debug("Calling terminate()")
        if not self.isServerRunning:
            TCPServer.debug("Server not running")
            return
        self.terminateServer = True
        TCPServer.debug("Disconnect by a dummy connection...")
        if self.conn is not None:
            self.conn.close()
            self.isClientConnected = False
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', self.port))  # dummy connection

    def disconnect(self):
        '''
        Closes the connection with the client and enters
        the LISTENING state
        '''
        TCPServer.debug("Calling Server.disconnect()")
        if self.isClientConnected:
            self.isClientConnected = False
            try:
                self.stateChanged(TCPServer.LISTENING, str(self.port))
            except Exception as e:
                print("Caught exception in TCPServer.LISTENING:", e)
            TCPServer.debug("Shutdown socket now")
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.conn.close()

    def sendMessage(self, msg):
        '''
        Sends the information msg to the client (as String, the character
        endOfBlock (defaut: ASCII 0) serves as end of
        string indicator, it is transparently added and removed)
        @param msg: the message to send
        '''
        TCPServer.debug("sendMessage() with msg: " + msg)
        if not self.isClientConnected:
            TCPServer.debug("Not connected")
            return
        try:
            msg += "\0"  # Append \0
            self.conn.sendall(msg.encode())
        except:
            TCPClient.debug("Exception in sendMessage()")

    def isConnected(self):
        '''
        Returns True, if a client is connected to the server.
        @return: True, if the communication link is established
        '''
        return self.isClientConnected

    def loopForever(self):
        '''
        Blocks forever with little processor consumption until a keyboard
        interrupt is detected.
        '''
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        self.terminate()

    def isTerminated(self):
        '''
        @return: True, if the server thread is terminated
        '''
        return self.terminateServer

    @staticmethod
    def debug(msg):
        if TCPServer.isVerbose:
            print("   TCPServer-> " + msg)

    @staticmethod
    def getIPAddress():
        '''
        Hacky way to get your IP. Not fully tested.
        '''
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP


# ---------------------- class ServerHandler ------------------------
class ServerHandler(Thread):
    def __init__(self, server, endOfBlock=b'\0'):
        Thread.__init__(self)
        self.server = server
        self.endOfBlock = endOfBlock

    def run(self):
        TCPServer.debug("ServerHandler started")
        timeoutThread = None
        if self.server.timeout > 0:
            timeoutThread = TimeoutThread(self.server, self.server.timeout)
            timeoutThread.start()
        bufSize = 4096
        try:
            while True:
                data = ""
                reply = ""
                isRunning = True
                while not reply[-1:] == self.endOfBlock:
                    TCPServer.debug("Calling blocking conn.recv() " +
                                    str(bufSize))
                    reply = self.server.conn.recv(bufSize)
                    TCPServer.debug("Returned from conn.recv() with " +
                                    str(reply.decode()))
                    if reply is None or len(reply) == 0:  # Client disconnected
                        TCPServer.debug("conn.recv() returned None")
                        isRunning = False
                        break
                    data += reply.decode()
                if not isRunning:
                    break
                TCPServer.debug("Received msg: " + data + "; len: " +
                                str(len(data)))
                junk = data.split(self.endOfBlock.decode())
                for i in range(len(junk) - 1):
                    try:
                        TCPServer.debug("Returning message to state changer")
                        self.server.stateChanged(TCPServer.MESSAGE, junk[i])
                    except Exception as e:
                        print("Caught exception in TCPServer.MESSAGE:", e)
                if not self.server.isClientConnected:
                    if timeoutThread is not None:
                        timeoutThread.stop()
                    TCPServer.debug("Callback disconnected client.")
                    return
                if timeoutThread is not None:
                    timeoutThread.reset()
                return
        except:  # May happen if client peer is resetted
            TCPServer.debug("Exception from blocking conn.recv(), Msg: " +
                            str(sys.exc_info()[0]) +
                            " at line # " + str(sys.exc_info()[-1].tb_lineno))
        self.server.disconnect()
        if timeoutThread is not None:
            timeoutThread.stop()
        TCPServer.debug("ServerHandler terminated")


# ================================== Client ================================
# -------------------------------- class TCPClient --------------------------
class TCPClient():
    '''
    Class that represents a TCP socket based client.
    '''
    isVerbose = False
    CONNECTING = "CONNECTING"
    SERVER_OCCUPIED = "SERVER_OCCUPIED"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    MESSAGE = "MESSAGE"

    def __init__(self, ipAddress, port, stateChanged, isVerbose=False):
        '''
        Creates a TCP socket client prepared for a connection with a
        TCPServer at given address and port.

        @param host: the IP address of the host
        @param port: the IP port where to listen (0..65535)
        @param stateChanged: the callback function to register
        @param isVerbose: if true, debug messages are written to System.out
        '''
        self.isClientConnected = False
        self.isClientConnecting = False
        self.ipAddress = ipAddress
        self.port = port
        self.stateChanged = stateChanged
        self.checkRefused = False
        self.isRefused = False

        TCPClient.isVerbose = isVerbose

    def sendMessage(self, msg, responseTime=0):
        '''
        Sends the information msg to the server (as String, the character \0
        (ASCII 0) serves as end of string indicator, it is transparently added
        and removed).  For responseTime > 0 the method blocks and waits
        for maximum responseTime seconds for a server reply.
        @param msg: the message to send
        @param responseTime: the maximum time to wait for a server reply (in s)
        @return: the message or null, if a timeout occured
        '''
        TCPClient.debug("sendMessage() with msg = " + msg)
        if not self.isClientConnected:
            TCPClient.debug("sendMessage(): Connection closed.")
            return None
        reply = None
        try:
            msg += "\0"  # Append \0
            if responseTime > 0:
                reply = self._waitForReply(responseTime)  # Blocking
        except:
            TCPClient.debug("Exception in sendMessage()")
            self.disconnect()
        return reply

    def _waitForReply(self, responseTime):
        TCPClient.debug("Calling _waitForReply()")
        self.receiverResponse = None
        startTime = time.time()
        while self.isClientConnected and self.receiverResponse is None \
                and time.time() - startTime < responseTime:
            time.sleep(0.01)
        if self.receiverResponse is None:
            TCPClient.debug("Timeout while waiting for reply")
        else:
            TCPClient.debug("Response = " + self.receiverResponse +
                            " time elapsed: " + str(int(1000 * (time.time() -
                                                    startTime))) + " ms")
        return self.receiverResponse

    def connect(self, timeout=0):
        '''
        Creates a connection to the server (blocking until timeout).
        @param timeout: the maximum time (in s) for the connection trial
        @return: True, if the connection is established; False, if the server
        is not available or occupied
        '''
        if timeout == 0:
            timeout = None
        try:
            self.stateChanged(TCPClient.CONNECTING, self.ipAddress + ":" +
                              str(self.port))
        except Exception as e:
            print("Caught exception in TCPClient.CONNECTING:", e)
        try:
            self.isClientConnecting = True
            host = (self.ipAddress, self.port)
            if self.ipAddress == "localhost" or self.ipAddress == "127.0.0.1":
                timeout = None
            self.sock = socket.create_connection(host, timeout)
            self.sock.settimeout(None)
            self.isClientConnecting = False
            self.isClientConnected = True
        except:
            self.isClientConnecting = False
            try:
                self.stateChanged(TCPClient.CONNECTION_FAILED, self.ipAddress +
                                  ":" + str(self.port))
            except Exception as e:
                print("Caught exception in TCPClient.CONNECTION_FAILED:", e)
            TCPClient.debug("Connection failed.")
            return False
        ClientHandler(self)

        # Check if connection is refused
        self.checkRefused = True
        self.isRefused = False
        startTime = time.time()
        while time.time() - startTime < 2 and not self.isRefused:
            time.sleep(0.001)
        if self.isRefused:
            TCPClient.debug("Connection refused")
            try:
                self.stateChanged(TCPClient.SERVER_OCCUPIED, self.ipAddress +
                                  ":" + str(self.port))
            except Exception as e:
                print("Caught exception in TCPClient.SERVER_OCCUPIED:", e)
            return False

        try:
            self.stateChanged(TCPClient.CONNECTED, self.ipAddress + ":" +
                              str(self.port))
        except Exception as e:
            print("Caught exception in TCPClient.CONNECTED:", e)
        TCPClient.debug("Successfully connected")
        return True

    def disconnect(self):
        '''
        Closes the connection with the server.
        '''
        TCPClient.debug("Client.disconnect()")
        if not self.isClientConnected:
            TCPClient.debug("Connection already closed")
            return
        self.isClientConnected = False
        TCPClient.debug("Closing socket")
        try:  # catch Exception "transport endpoint is not connected"
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        self.sock.close()

    def isConnecting(self):
        '''
        Returns True during a connection trial.
        @return: True, while the client tries to connect
        '''
        return self.isClientConnecting

    def isConnected(self):
        '''
        Returns True of client is connnected to the server.
        @return: True, if the connection is established
        '''
        return self.isClientConnected

    @staticmethod
    def debug(msg):
        if TCPClient.isVerbose:
            print("   TCPClient-> " + msg)

    @staticmethod
    def getVersion():
        '''
        Returns the library version.
        @return: the current version of the library
        '''
        return TCPCOM_VERSION


# -------------------------------- class ClientHandler ------------------------
class ClientHandler(Thread):
    def __init__(self, client):
        Thread.__init__(self)
        self.client = client
        self.start()

    def run(self):
        TCPClient.debug("ClientHandler thread started")
        while True:
            try:
                junk = (self.readResponse().decode()).split("\x00")
                # more than 1 message may be received
                # if transfer is fast. data: xxxx\0yyyyy\0zzz\0
                for i in range(len(junk) - 1):
                    try:
                        self.client.stateChanged(TCPClient.MESSAGE, junk[i])
                    except Exception as e:
                        print("Caught exception in TCPClient.MESSAGE:", e)
            except:
                TCPClient.debug("Exception in readResponse() Msg: " +
                                str(sys.exc_info()[0]) + " at line # " +
                                str(sys.exc_info()[-1].tb_lineno))
                if self.client.checkRefused:
                    self.client.isRefused = True
                break
        try:
            self.client.stateChanged(TCPClient.DISCONNECTED, "")
        except Exception as e:
            print("Caught exception in TCPClient.DISCONNECTED:", e)
        TCPClient.debug("ClientHandler thread terminated")

    def readResponse(self):
        TCPClient.debug("Calling readResponse")
        bufSize = 4096
        data = bytearray()
        while not data[-1:] == b'\0':
            try:
                reply = self.client.sock.recv(bufSize)  # blocking
                if len(reply) == 0:
                    TCPClient.debug("recv returns null length")
                    raise Exception("recv returns null length")
            except:
                TCPClient.debug("Exception from blocking conn.recv(), Msg: " +
                                str(sys.exc_info()[0]) + " at line # " +
                                str(sys.exc_info()[-1].tb_lineno))
                raise Exception("Exception from blocking sock.recv()")
            data += reply
            self.receiverResponse = data[:-1]
        return data


# -------------------------------- class HTTPServer --------------------------
class HTTPServer(TCPServer):

    def getHeader1(self):
        return "HTTP/1.1 501 OK\r\nServer: " + self.serverName + "\r\nConnection: Closed\r\n"

    def getHeader2(self):
        return "HTTP/1.1 200 OK\r\nServer: " + self.serverName + "\r\nContent-Length: %d\r\nContent-Type: text/html\r\nConnection: Closed\r\n\r\n"

    def onStop(self):
        self.terminate()

    def __init__(self, requestHandler, serverName="PYSERVER",
                 port=80, isVerbose=False):
        '''
        Creates a HTTP server (inherited from TCPServer) that listens for a
        connecting client on given port (default = 80).
        Starts a thread that handles and returns HTTP GET requests. The HTTP
        respoonse header reports the given server name (default: "PYSERVER")

        requestHandler() is a callback function called when a GET request is
        received.

        Parameters:
            clientIP: the client's IP address in dotted format
            filename: the requested filename with preceeding '/'
            params: a tuple with format: ((param_key1, param_value1),
            (param_key2, param_value2), ...)  (all items are strings)

        Return values:
            msg: the HTTP text response (the header is automatically created)
            stateHandler: a callback function that is invoked immediately after
            the reponse is sent.
              If stateHandler = None, nothing is done. The function may include
              longer lasting server
              actions or a wait time, if sensors are not immediately ready for
              a new measurement.

        Call terminate() to stop the server. The connection is closed by the
        server at the end of each response. If the client connects,
        but does not send a request within 5 seconds, the connection is
        closed by the server.
        '''

        TCPServer.__init__(self, port, stateChanged=self.onStateChanged,
                           endOfBlock='\0', isVerbose=isVerbose)
        self.serverName = serverName
        self.requestHandler = requestHandler
        self.port = port
        self.verbose = isVerbose
        self.timeout = 5
        self.clientIP = ""

    def getClientIP(self):
        '''
        Returns the dotted IP of a connected client. If no client is connected,
        returns empty string.
        '''
        return self.clientIP

    def onStateChanged(self, state, msg):
        if state == "CONNECTED":
            self.clientIP = msg
            self.debug("Client " + msg + " connected.")
        elif state == "DISCONNECTED":
            self.clientIP = ""
            self.debug("Client disconnected.")
        elif state == "LISTENING":
            self.clientIP = ""
            self.debug("LISTENING")
        elif state == "MESSAGE":
            self.debug("request: " + msg)
            if len(msg) != 0:
                filename, params = self._parseURL(msg)
                if filename is None:
                    self.sendMessage(self.getHeader1().encode())
                else:
                    text, stateHandler = self.requestHandler(self.clientIP, filename, params)
                    self.sendMessage((self.getHeader2() % (len(text))).encode())
                    self.sendMessage(text.encode())
                    if stateHandler is not None:
                        try:
                            stateHandler()
                        except:
                            print("Exception in stateHandler()")
            else:
                self.sendMessage(self.getHeader1().encode())
            self.disconnect()

    def _parseURL(self, request):
        lines = request.split('\n')  # split lines
        params = []
        for line in lines:
            if line[0:4] == 'GET ':  # only GET request
                url = line.split()[1].strip()
                i = url.find('?')  # check for params
                if i != -1:  # params given
                    filename = url[0:i].strip()  # include leading /
                    params = []
                    urlParam = url[i + 1:]
                    for item in urlParam.split('&'):  # split parameters
                        i = item.find('=')
                        key = item[0:i]
                        value = item[i + 1:]
                        params.append((key, value))
                    return filename, tuple(params)
                return url.strip(), tuple([])
        return None, tuple([])

    def debug(self, msg):
        if self.verbose:
            print(("   HTTPServer-> " + msg))

    @staticmethod
    def getServerIP():
        '''
        Returns the server's IP address (static method).
        '''
        return TCPServer.getIPAddress()
