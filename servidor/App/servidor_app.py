import socket
import struct
import threading
#criando a classe servidor app

class servidor_app:
    def __init__(self, sock=None):
        if sock is None:
            # Cria um novo socket. Recebe família de endereços (AF_INET para IPv4) e tipo (SOCK_STREAM para TCP).
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
    def send(self, msg, msg_length):
        totalsent = 0
        while totalsent < msg_length:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("A conexão via socket caiu.")
            totalsent = totalsent + sent

    def listen_multiclient(self, cliente_socket, endereco):
        cliente = servidor_app(sock=cliente_socket)
        print(f"[+] Cliente conectado: {endereco}")
        try:
            while True:
                dados = cliente.receive()
                if not dados:
                    break
                print(f"Mensagem de {endereco}: {dados}")
                resposta = b"resposta do servidor"
                cliente.send(resposta, len(resposta))
        except RuntimeError:
            print(f"[-] Cliente desconectado: {endereco}")
        finally:
            cliente_socket.close()

    def receive(self):
        # Lê os 4 bytes do prefixo para saber o tamanho da mensagem
        header = b''
        while len(header) < 4:
            parte = self.sock.recv(4 - len(header))
            if parte == b'':
                raise RuntimeError("A conexão via socket caiu.")
            header += parte

        msg_length = struct.unpack('>I', header)[0]

        # Lê a mensagem completa com o tamanho conhecido
        chunks = []
        bytes_recd = 0
        while bytes_recd < msg_length:
            chunk = self.sock.recv(min(msg_length - bytes_recd, 2048))
            if chunk == b'':
                raise RuntimeError("A conexão via socket caiu.")
            chunks.append(chunk)
            bytes_recd += len(chunk)

        return b''.join(chunks)


