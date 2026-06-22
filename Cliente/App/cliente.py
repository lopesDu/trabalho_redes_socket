import socket
import struct
import threading
import sys
import os
from datetime import datetime

# ──────────────────────────────────────────────
#  Configuração de log do cliente
# ──────────────────────────────────────────────
import logging

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join("logs", "cliente.log"), encoding="utf-8"),
        # NÃO imprime no console — usamos print() para controlar o prompt
    ],
)
log = logging.getLogger("cliente")


# ──────────────────────────────────────────────
#  Protocolo: envio / recepção com prefixo 4 B
# ──────────────────────────────────────────────
def send(sock: socket.socket, msg: bytes) -> None:
    header = struct.pack('>I', len(msg))
    dados = header + msg
    totalsent = 0
    while totalsent < len(dados):
        sent = sock.send(dados[totalsent:])
        if sent == 0:
            raise RuntimeError("Conexão caiu.")
        totalsent += sent


def receive(sock: socket.socket) -> bytes:
    header = b''
    while len(header) < 4:
        parte = sock.recv(4 - len(header))
        if parte == b'':
            raise RuntimeError("Conexão caiu.")
        header += parte

    msg_length = struct.unpack('>I', header)[0]

    MAX_MSG = 10 * 1024 * 1024
    if msg_length > MAX_MSG:
        raise RuntimeError(f"Tamanho de mensagem inválido: {msg_length} B")

    chunks, bytes_recd = [], 0
    while bytes_recd < msg_length:
        chunk = sock.recv(min(msg_length - bytes_recd, 2048))
        if chunk == b'':
            raise RuntimeError("Conexão caiu durante leitura.")
        chunks.append(chunk)
        bytes_recd += len(chunk)

    return b''.join(chunks)


# ──────────────────────────────────────────────
#  Classificação de mensagens recebidas
# ──────────────────────────────────────────────
def _prefixo_msg(texto: str) -> str:
    """Retorna um prefixo colorido/simbólico de acordo com o tipo da mensagem."""
    if texto.startswith("[Privado de "):
        return "💬 PRIVADO"
    if texto.startswith("[Servidor]"):
        return "🔔 SERVIDOR"
    return "📨 MSG"


def _formatar_recebida(texto: str) -> str:
    ts = datetime.now().strftime("%H:%M:%S")
    prefixo = _prefixo_msg(texto)
    return f"\n[{ts}] {prefixo} » {texto}"


# ──────────────────────────────────────────────
#  Thread de recepção contínua
# ──────────────────────────────────────────────
_lock_print = threading.Lock()  # evita sobreposição de linhas no terminal


def receber_mensagens(sock: socket.socket, username: str) -> None:
    while True:
        try:
            resposta = receive(sock).decode(errors="replace")

            with _lock_print:
                # apaga o prompt atual antes de imprimir
                sys.stdout.write("\r" + " " * 60 + "\r")
                print(_formatar_recebida(resposta))
                print(f"[{username}]: ", end="", flush=True)

            # log classificado
            if "[Privado de " in resposta:
                log.info("MSG_PRIVADA_RECEBIDA | %s", resposta)
            elif resposta.startswith("[Servidor]"):
                log.info("RESPOSTA_SERVIDOR | %s", resposta)
            else:
                log.info("MSG_RECEBIDA | %s", resposta)

        except RuntimeError:
            with _lock_print:
                print("\n[*] Conexão com o servidor encerrada.")
            log.warning("Conexão encerrada pelo servidor.")
            break


# ──────────────────────────────────────────────
#  Fluxo de autenticação
# ──────────────────────────────────────────────
def autenticar(sock: socket.socket) -> str:
    """
    Conduz o handshake de login.
    Retorna o username em caso de sucesso; levanta RuntimeError em falha.
    """
    # Servidor envia "USUARIO:"
    solicitacao = receive(sock).decode()
    print(f"\n[?] {solicitacao}", end=" ")
    username = input()
    send(sock, username.encode())
    log.info("TENTATIVA_LOGIN | usuario=%s", username)

    # Servidor envia "SENHA:"
    solicitacao = receive(sock).decode()
    print(f"[?] {solicitacao}", end=" ")
    import getpass
    try:
        senha = getpass.getpass("")   # oculta a senha no terminal
    except Exception:
        senha = input()
    send(sock, senha.encode())

    resposta = receive(sock).decode()

    if resposta.startswith("LOGIN_OK"):
        log.info("LOGIN_OK | usuario=%s", username)
        print(f"\n[✓] {resposta}")
        return username
    else:
        log.warning("LOGIN_FALHOU | usuario=%s | motivo=%s", username, resposta)
        raise RuntimeError(resposta)


# ──────────────────────────────────────────────
#  Validação local de comandos (feedback rápido)
# ──────────────────────────────────────────────
COMANDOS_VALIDOS = {"/msg", "/usuarios", "/ajuda", "/sair", "/cadastrar", "/promover"}

def _validar_comando(msg: str) -> str | None:
    """
    Retorna uma string de erro se o comando estiver mal formado,
    ou None se estiver OK (ou não for um comando).
    """
    if not msg.startswith("/"):
        return None

    partes = msg.strip().split(" ", 2)
    cmd = partes[0].lower()

    if cmd not in COMANDOS_VALIDOS:
        return f"Comando desconhecido: '{cmd}'. Use /ajuda para ver a lista."

    if cmd == "/msg":
        if len(partes) < 3 or not partes[2].strip():
            return "Uso: /msg <usuario> <mensagem>"

    if cmd == "/cadastrar" and (len(partes) < 3 or not partes[2].strip()):
        return "Uso: /cadastrar <usuario> <senha>"

    return None


# ──────────────────────────────────────────────
#  Loop principal do cliente
# ──────────────────────────────────────────────
def main() -> None:
    HOST = 'localhost'
    PORTA = 5000

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    log.info("INICIANDO | host=%s porta=%d", HOST, PORTA)

    try:
        sock.connect((HOST, PORTA))
        print(f"[*] Conectado ao servidor {HOST}:{PORTA}")
        log.info("CONECTADO | %s:%d", HOST, PORTA)

        # ── Autenticação ──────────────────────────────
        username = autenticar(sock)

        # ── Mensagem de boas-vindas do servidor ───────
        boas_vindas = receive(sock).decode()
        print(f"[*] {boas_vindas}\n")
        log.info("BOAS_VINDAS | %s", boas_vindas)

        print("─" * 55)
        print("  Comandos disponíveis:")
        print("  /msg <usuario> <texto>  — mensagem privada")
        print("  /usuarios               — usuários online")
        print("  /ajuda                  — ajuda do servidor")
        print("  /sair                   — encerrar sessão")
        print("─" * 55 + "\n")

        # ── Thread de recepção ────────────────────────
        t_recv = threading.Thread(
            target=receber_mensagens,
            args=(sock, username),
            daemon=True,
        )
        t_recv.start()

        # ── Loop de envio ─────────────────────────────
        while True:
            try:
                with _lock_print:
                    print(f"[{username}]: ", end="", flush=True)
                msg = input()
            except EOFError:
                break

            msg = msg.strip()
            if not msg:
                continue

            # validação local
            erro = _validar_comando(msg)
            if erro:
                with _lock_print:
                    print(f"[!] {erro}")
                log.warning("COMANDO_INVALIDO | %s", msg)
                continue

            # envia ao servidor
            send(sock, msg.encode())

            # log por tipo
            if msg.startswith("/msg "):
                partes = msg.split(" ", 2)
                dest = partes[1] if len(partes) > 1 else "?"
                log.info("MSG_PRIVADA_ENVIADA | de=%s para=%s", username, dest)
            elif msg.startswith("/"):
                log.info("COMANDO | %s | %s", username, msg)
            else:
                log.info("MSG_ENVIADA | %s | %s", username, msg)

            if msg.lower() == "/sair":
                print("[*] Encerrando sessão...")
                log.info("SAIR | %s", username)
                break

    except ConnectionRefusedError:
        print("[x] Conexão recusada. O servidor está online?")
        log.error("CONEXAO_RECUSADA | %s:%d", HOST, PORTA)
    except RuntimeError as e:
        print(f"[!] {e}")
        log.error("RUNTIME_ERROR | %s", e)
    except OSError as e:
        print(f"[x] Erro de socket: {e}")
        log.error("OS_ERROR | %s", e)
    finally:
        sock.close()
        print("[*] Conexão encerrada.")
        log.info("DESCONECTADO")


if __name__ == '__main__':
    main()