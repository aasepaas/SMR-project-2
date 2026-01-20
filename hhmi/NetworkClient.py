import socket as sck
import threading
import time
import queue

class Network_client:
    """
    Server that runs accept() and recv() in background threads and
    exposes a thread-safe queue of incoming messages.

    Behavior change:
    - The accept loop will only accept new clients when self._accept_allowed is True.
      start_server()/strt_socket() sets _accept_allowed True. After a client is accepted
      the class automatically clears _accept_allowed so no further clients are accepted
      until start_server() is called again. This prevents automatic re-accept while the
      UI is on Page2 after an error/close.
    """

    def __init__(self, IP, PORT):
        self.addr = (IP, PORT)
        print(f'Network_client: configured for address: {self.addr}')
        self.server_socket = None
        self.client_socket = None
        self.client_addr = None
        self.serverAan = False

        self._recv_queue = queue.Queue()
        self._stop_event = threading.Event()

        self._accept_thread = None
        self._recv_thread = None

        # protect client_socket/client_addr changes
        self._client_lock = threading.Lock()

        # control whether accept loop is allowed to accept new clients
        self._accept_allowed = False

    def strt_socket(self):
        # public alias used elsewhere
        return self.start_server()

    def start_server(self):
        """
        Start the server listening thread and allow a single client accept.
        Calling this while an accept thread is already running will re-enable accepting.
        """
        # If accept thread already running, just allow accepting again
        if self._accept_thread and self._accept_thread.is_alive():
            self._accept_allowed = True
            self.serverAan = True
            return True

        try:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except Exception:
                    pass

            self.server_socket = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
            self.server_socket.setsockopt(sck.SOL_SOCKET, sck.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)  # accept will timeout periodically
            self.server_socket.bind(self.addr)
            self.server_socket.listen(1)
            self._stop_event.clear()

            self._accept_allowed = True  # allow accepting one (or more until we clear) client(s)
            self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._accept_thread.start()

            self.serverAan = True
            print(f"Network_client: listening on {self.addr}")
            return True
        except Exception as e:
            print(f"Network_client.start_server error: {e}")
            return False

    def _accept_loop(self):
        """
        Accept loop that will only call accept() when _accept_allowed is True.
        After accepting a client we clear _accept_allowed so that no further clients
        are accepted until start_server() is called again.
        """
        while not self._stop_event.is_set():
            if not self._accept_allowed:
                # Not allowed to accept new clients now; wait and re-check
                time.sleep(0.1)
                continue

            try:
                client_sock, client_addr = self.server_socket.accept()
            except Exception as e:
                # timeout or closed -> loop back
                if self._stop_event.is_set():
                    break
                continue

            # Once a client is accepted, prevent further accepts until restarted explicitly
            self._accept_allowed = False

            with self._client_lock:
                self.client_socket = client_sock
                self.client_addr = client_addr
                try:
                    # set recv timeout so recv loop can periodically check stop flag
                    self.client_socket.settimeout(1.0)
                except Exception:
                    pass

            print(f"Network_client: client connected from {client_addr} at {time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}")
            try:
                try:
                    self.client_socket.send("Server connection ESTABLISHED".encode('utf-8'))
                except Exception:
                    pass
            except Exception:
                pass

            # Start receive thread for this client
            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()

            # Wait for recv thread to finish (client disconnected) before accepting next client,
            # but because _accept_allowed is False we won't accept automatically.
            self._recv_thread.join()

        # ensure client closed on exit
        self._handle_client_disconnect()

    def _recv_loop(self):
        """Read from client socket and push decoded messages onto the queue."""
        while not self._stop_event.is_set():
            with self._client_lock:
                sock = self.client_socket
                addr = self.client_addr
            if not sock:
                break

            try:
                data = sock.recv(2048)
            except sck.timeout:
                # expected due to socket timeout
                continue
            except Exception as e:
                # Non-timeout exception -> treat as disconnect
                print(f"Network_client._recv_loop: recv exception {repr(e)}")
                self._handle_client_disconnect()
                break

            if not data:
                # remote closed connection
                print(f"Network_client: client {addr} closed connection")
                self._handle_client_disconnect()
                break

            try:
                decoded = data.decode('utf-8')
            except Exception:
                decoded = None

            if decoded is not None:
                self._recv_queue.put(decoded)
                print(f"Network_client: received data from {addr}: {decoded}")

        # ensure client closed on exit
        self._handle_client_disconnect()

    def _handle_client_disconnect(self):
        with self._client_lock:
            try:
                if self.client_socket:
                    try:
                        self.client_socket.shutdown(sck.SHUT_RDWR)
                    except Exception:
                        pass
                    try:
                        self.client_socket.close()
                    except Exception:
                        pass
            finally:
                self.client_socket = None
                self.client_addr = None

    def connect_client(self):
        return self.is_connected()

    def isServerOn(self):
        return self.serverAan

    def is_connected(self):
        with self._client_lock:
            return self.client_socket is not None

    def get_message(self, timeout=None):
        try:
            return self._recv_queue.get(timeout=timeout)
        except queue.Empty:
            raise

    def receive_client(self, timeout=None):
        try:
            return self.get_message(timeout=timeout)
        except queue.Empty:
            return None

    def send_client(self, message):
        with self._client_lock:
            sock = self.client_socket
            addr = self.client_addr
        if not sock:
            print("Network_client.send_client: no connected client")
            return False
        if not isinstance(message, str):
            message = str(message).replace("[", "(").replace("]", ")")

        try:
            print(f"Network_client: sending to {addr}: {message}")
            sock.send(message.encode('utf-8'))
            return True
        except Exception as e:
            print(f"Network_client.send_client exception: {e}")
            self._handle_client_disconnect()
            return False

    def disconnect_client(self):
        print("Network_client.disconnect_client: closing client socket if present")
        self._handle_client_disconnect()

    def clse_socket(self):
        return self.stop_socket()

    def sendErrorToClient(self, message):
        print(message)
        with self._client_lock:
            sock = self.client_socket
            addr = self.client_addr
        if not sock:
            print("Network_client.send_client: no connected client")
            return False
        try:
            print(f"Network_client: sending to {addr}: {message}")
            sock.send(message.encode('utf-8'))
            return True
        except Exception as e:
            print(f"Network_client.send_client exception: {e}")
            self._handle_client_disconnect()
            return False

    def stop_socket(self):
        """
        Stop listening and close server & client sockets. After this call no new clients
        will be accepted until start_server()/strt_socket() is called again.
        """
        self.serverAan = False
        print("Network_client.stop_socket: stopping server")
        self._stop_event.set()
        # disallow further accepts
        self._accept_allowed = False

        try:
            if self.server_socket:
                try:
                    self.server_socket.shutdown(sck.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.server_socket.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"Network_client.stop_socket server close error: {e}")
        finally:
            self.server_socket = None

        # ensure client disconnected
        self._handle_client_disconnect()

        # join threads (with timeout to avoid blocking indefinitely)
        if self._accept_thread and self._accept_thread.is_alive():
            self._accept_thread.join(timeout=1.0)
        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=1.0)

        self._accept_thread = None
        self._recv_thread = None
        # clear stop_event to keep object reusable; accept will not happen until start_server called
        self._stop_event.clear()
        return True

    def try_receive(self, timeout=0.0):
        try:
            return self.get_message(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self):
        """Leeg de ontvangen berichtenqueue volledig."""
        while not self._recv_queue.empty():
            try:
                self._recv_queue.get_nowait()
            except queue.Empty:
                break