import socket as sck
import time

class Network_client:
    def __init__(self, IP, PORT):
        self.addr = (IP,PORT)
        
        print(f'Socket created on following address: {self.addr}')
        
        self.server_socket = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
        self.server_socket.bind(self.addr)
    
    def strt_socket(self):
        self.server_socket.listen(5)
        print(f"Socket with address: {self.addr} Started listening")
        
    def clse_socket(self):
        print(f"!!!Socket with address: {self.addr} is CLOSING DOWN!!!")
        self.server_socket.close()
    
    def connect_client(self):
        self.client_socket, self.client_addr = self.server_socket.accept()
        print(f"Client connection ESTABLISHED From {self.client_addr} at {time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}")
        self.client_socket.send("Server connection ESTABLISHED".encode('utf-8'))
    
    def disconnect_client(self):
        print(f"CLOSING: {self.client_addr}")
        self.client_socket.close() 
    
    def receive_client(self):
        
            try:
                data_receive = self.client_socket.recv(2048).decode('utf-8')
                print(f"AWAITING Data from: {self.client_addr}")
            
        
                if not data_receive:
                    return None
                else:
                    print(f"Data RECEIVED From: {self.client_addr} \n Data: {data_receive}")
                    return data_receive
            except ConnectionResetError:
                    print(f"Connection LOST from: {self.client_addr}")

    def send_client(self, message):
        if type(message) != str :
            message = str(message).replace("[","(").replace("]",")")
        
        print(f"DATA TO SEND: {message}\n SENDING to : {self.client_addr}")
        testje = self.client_socket.send(str(message).encode('utf-8'))