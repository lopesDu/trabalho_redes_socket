import socket
import struct
import threading


def send(sock, msg: bytes):
    header = struct.pack('>I', len(msg))
    dados = header + msg
    totalsent = 0
    while totalsent < len(dados):
        sent = sock.send(dados[totalsent:])
        if sent == 0:
            raise RuntimeError("Conexão caiu.")
        totalsent += sent


def receive(sock) -> bytes:
    header = b''
    while len(header) < 4:
        parte = sock.recv(4 - len(header))
        if parte == b'':
            raise RuntimeError("Conexão caiu.")
        header += parte
    msg_length = struct.unpack('>I', header)[0]
    chunks = []
    bytes_recd = 0
    while bytes_recd < msg_length:
        chunk = sock.recv(min(msg_length - bytes_recd, 2048))
        if chunk == b'':
            raise RuntimeError("Conexão caiu durante leitura.")
        chunks.append(chunk)
        bytes_recd += len(chunk)
    return b''.join(chunks)


def receber_mensagens(sock):
    while True:
        try:
            resposta = receive(sock)
            print(f"\n{resposta.decode()}")
            print("[Você]: ", end="", flush=True)
        except RuntimeError:
            print("\n[*] Conexão com o servidor encerrada.")
            break


if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect(('localhost', 5000))
        print("[*] Conectado ao servidor.")

        solicitacao = receive(sock).decode()
        print(f"[?] {solicitacao}")
        username = input("Usuario: ")
        send(sock, username.encode())

        solicitacao = receive(sock).decode()
        print(f"[?] {solicitacao}")
        senha = input("Senha: ")
        send(sock, senha.encode())

        resposta_login = receive(sock).decode()
        print(f"[*] {resposta_login}")

        if not resposta_login.startswith("LOGIN_OK"):
            raise RuntimeError(resposta_login)

        boas_vindas = receive(sock).decode()
        print(f"[*] {boas_vindas}")

        t_recv = threading.Thread(target=receber_mensagens, args=(sock,), daemon=True)
        t_recv.start()

        print("Comandos: /msg <usuario> <texto>  |  /usuarios  |  /ajuda  |  /sair")
        while True:
            try:
                msg = input("[Você]: ")
            except EOFError:
                break
            if not msg.strip():
                continue
            send(sock, msg.encode())
            if msg.strip().lower() == "/sair":
                break

    except ConnectionRefusedError:
        print("[x] Conexão recusada. O servidor está online?")
    except RuntimeError as e:
        print(f"[!] Erro: {e}")
    except OSError as e:
        print(f"[x] Erro de socket: {e}")
    finally:
        sock.close()
        print("[*] Conexão encerrada.")
