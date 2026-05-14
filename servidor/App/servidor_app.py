import socket

#criando a classe servidor app

class servidor_app:
    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock

    def connect(self, host, port):
        self.sock.connect((host, port))

    def send(self, msg, msg_length):
        totalsent = 0
        while totalsent < msg_length:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("A conexão via socket caiu.")
            totalsent = totalsent + sent

    def receive(self, msg_length):
        chunks = []
        bytes_recd = 0
        while bytes_recd < msg_length:
            chunk = self.sock.recv(min(msg_length - bytes_recd, 2048))
            if chunk == b'':
                raise RuntimeError("A conexão via socket caiu")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        return b''.join(chunks)
