import socket

class servidor_app:
    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print("criou novo socket")
        else:
            self.sock = sock

    def send(self, msg):
        self.sock.sendall(msg)
        self.sock.shutdown(socket.SHUT_WR)  # avisa o cliente que terminou

    def receive(self):
        chunks = []
        while True:
            chunk = self.sock.recv(2048)
            if not chunk:
                break
            chunks.append(chunk)
        return b''.join(chunks)