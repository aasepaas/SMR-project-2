import socket as sck
import time

class Network_client:
    def __init__(self, IP, PORT):
        self.addr = (IP, PORT)
        print(f'Socket created on following address: {self.addr}')

        self.server_socket = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
        self.server_socket.setsockopt(sck.SOL_SOCKET, sck.SO_REUSEADDR, 1)
        self.server_socket.bind(self.addr)

        self.client_socket = None
        self.client_addr = None

    def strt_socket(self):
        self.server_socket.listen(5)
        print(f"Socket with address: {self.addr} Started listening")

    def clse_socket(self):
        # Wordt aangeroepen vanaf GUI-thread om accept() te unblokken
        try:
            print(f"Closing server socket: {self.addr}")
            # probeer eerst shutdown (kan excepties geven als nog niet verbonden)
            try:
                self.server_socket.shutdown(sck.SHUT_RDWR)
            except Exception:
                pass
            self.server_socket.close()
        except Exception as e:
            print("Error closing server socket:", e)

    def connect_client(self):
        # blocking accept() — kan unblocked worden door clse_socket() vanuit andere thread
        try:
            self.client_socket, self.client_addr = self.server_socket.accept()
            print(f"Client connection ESTABLISHED From {self.client_addr} at {time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}")
            try:
                self.client_socket.send("Server connection ESTABLISHED".encode('utf-8'))
            except Exception:
                pass
            return True
        except Exception as e:
            # wanneer server_socket closed vanuit andere thread, hier een exceptie
            print("connect_client exception:", repr(e))
            return False

    def disconnect_client(self):
        # Wordt aangeroepen vanaf GUI-thread om recv() in worker te unblokken
        try:
            if self.client_socket:
                print(f"Shutting down client socket: {self.client_addr}")
                try:
                    self.client_socket.shutdown(sck.SHUT_RDWR)
                except Exception:
                    pass
                self.client_socket.close()
        except Exception as e:
            print("Error closing client socket:", e)
        finally:
            self.client_socket = None
            self.client_addr = None

    def receive_client(self):
        # blocking recv() — zal unblocked/afgebroken worden als disconnect_client() wordt aangeroepen
        if not self.client_socket:
            return None
        try:
            data = self.client_socket.recv(2048)
            if not data:
                # client closed cleanly
                return None
            decoded = data.decode('utf-8')
            print(f"Data RECEIVED From: {self.client_addr} \n Data: {decoded}")
            return decoded
        except Exception as e:
            print("receive_client exception:", repr(e))
            return None

    def send_client(self, message):
        if not self.client_socket:
            print("No connected client to send to")
            return False
        if type(message) != str:
            message = str(message).replace("[", "(").replace("]", ")")
        try:
            print(f"DATA TO SEND: {message}\n SENDING to : {self.client_addr}")
            self.client_socket.send(message.encode('utf-8'))
            return True
        except Exception as e:
            print("send_client exception:", repr(e))
            return False