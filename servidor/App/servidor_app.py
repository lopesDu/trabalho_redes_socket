import socket
import struct
import threading
import json
import os
import hashlib

ARQUIVO_USUARIOS = "usuarios.json"

def carregar_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS):
        # Cria o arquivo com um admin padrão na primeira execução
        usuarios_padrao = {
            "admin": hashlib.sha256("admin".encode()).hexdigest(),
            "carlos": hashlib.sha256("123456".encode()).hexdigest(),
        }
        with open(ARQUIVO_USUARIOS, "w") as f:
            json.dump(usuarios_padrao, f, indent=4)
        print("[*] Arquivo de usuários criado com usuários padrão.")

    with open(ARQUIVO_USUARIOS, "r") as f:
        return json.load(f)

def salvar_usuarios(usuarios):
    with open(ARQUIVO_USUARIOS, "w") as f:
        json.dump(usuarios, f, indent=4)


def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()

sessoes_ativas = {}
lock_sessoes = threading.Lock()


def usuario_ja_conectado(username):
    with lock_sessoes:
        return username in sessoes_ativas


def registrar_sessao(username, endereco):
    with lock_sessoes:
        sessoes_ativas[username] = endereco
    print(f"[+] Sessão registrada: {username} @ {endereco}")


def encerrar_sessao(username):
    with lock_sessoes:
        if username in sessoes_ativas:
            del sessoes_ativas[username]
    print(f"[-] Sessão encerrada: {username}")

class servidor_app:
    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock

    def iniciar(self, host='', porta=5000):
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, porta))
        self.sock.listen(5)
        print(f"[*] Servidor aguardando conexões em {host or '0.0.0.0'}:{porta}")

        try:
            while True:
                conn, addr = self.sock.accept()
                thread = threading.Thread(
                    target=self.listen_multiclient,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()
                print(f"[*] Threads ativas: {threading.active_count() - 1}")

        except KeyboardInterrupt:
            print("\n[*] Servidor encerrado pelo usuário.")
        finally:
            self.sock.close()

    def send(self, msg, msg_length):
        totalsent = 0
        while totalsent < msg_length:
            try:
                sent = self.sock.send(msg[totalsent:])
                if sent == 0:
                    raise RuntimeError("A conexão via socket caiu.")
                totalsent += sent
            except OSError as e:
                raise RuntimeError(f"Erro ao enviar dados: {e}")

    def listen_multiclient(self, cliente_socket, endereco):
        cliente = servidor_app(sock=cliente_socket)
        print(f"[+] Cliente conectado: {endereco}")
        try:
            while True:
                dados = cliente.receive()

                # recebeu nada
                if not dados:
                    print(f"[~] Cliente {endereco} encerrou a conexão.")
                    break

                print(f"[>] Mensagem de {endereco}: {dados}")
                resposta = b"resposta do servidor"
                cliente.send(resposta, len(resposta))

        except RuntimeError as e:
            # Conexão caiu
            print(f"[!] Conexão encerrada com {endereco}: {e}")

        except OSError as e:
            # Erro de SO no socket
            print(f"[x] Erro de socket com {endereco}: {e}")

        finally:
            # Garante que o socket SEMPRE será fechado, independente do motivo
            try:
                cliente_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # Socket pode já estar fechado pelo lado do cliente
            cliente_socket.close()
            print(f"[-] Recursos liberados para: {endereco}")

    def receive(self):
        header = b''
        while len(header) < 4:
            try:
                parte = self.sock.recv(4 - len(header))
            except OSError as e:
                raise RuntimeError(f"Erro ao ler header: {e}")
            # recv retorna b'' quando o cliente fecha a conexão normalmente
            if parte == b'':
                raise RuntimeError("A conexão via socket caiu.")
            header += parte

        msg_length = struct.unpack('>I', header)[0]
        # Proteção contra tamanhos grande de msg
        MAX_MSG = 10 * 1024 * 1024  # 10 MB
        if msg_length > MAX_MSG:
            raise RuntimeError(f"Tamanho de mensagem inválido: {msg_length} bytes")

        chunks = []
        bytes_recd = 0
        while bytes_recd < msg_length:
            try:
                chunk = self.sock.recv(min(msg_length - bytes_recd, 2048))
            except OSError as e:
                raise RuntimeError(f"Erro ao ler corpo da mensagem: {e}")

            if chunk == b'':
                raise RuntimeError("A conexão via socket caiu durante a leitura.")
            chunks.append(chunk)
            bytes_recd += len(chunk)

        return b''.join(chunks)