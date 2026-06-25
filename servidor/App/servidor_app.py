import socket
import struct
import threading
import json
import os
import hashlib
import logging
import logging.handlers
from datetime import datetime

# ══════════════════════════════════════════════
#  Sistema de log centralizado
# ══════════════════════════════════════════════
os.makedirs("logs", exist_ok=True)

_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join("logs", "servidor.log"),
    maxBytes=1_000_000,
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(
    logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(
    logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
    )
)

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
log = logging.getLogger("servidor")


# ══════════════════════════════════════════════
#  Persistência de usuários
# ══════════════════════════════════════════════
ARQUIVO_USUARIOS = "usuarios.json"


def carregar_usuarios() -> dict:
    if not os.path.exists(ARQUIVO_USUARIOS):
        usuarios_padrao = {
            "admin":  {"senha": hashlib.sha256("admin".encode()).hexdigest(),  "role": "superuser"},
            "carlos": {"senha": hashlib.sha256("123456".encode()).hexdigest(), "role": "user"},
        }
        with open(ARQUIVO_USUARIOS, "w") as f:
            json.dump(usuarios_padrao, f, indent=4)
        log.info("USUARIOS_CRIADOS | arquivo padrão gerado: %s", ARQUIVO_USUARIOS)

    with open(ARQUIVO_USUARIOS, "r") as f:
        return json.load(f)


def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def is_superuser(username: str) -> bool:
    usuarios = carregar_usuarios()
    return usuarios.get(username, {}).get("role") == "superuser"


# ══════════════════════════════════════════════
#  Gerenciamento de sessões ativas
# ══════════════════════════════════════════════
sessoes_ativas: dict[str, tuple] = {}
clientes_conectados: dict[str, "servidor_app"] = {}
lock_sessoes = threading.Lock()


def usuario_ja_conectado(username: str) -> bool:
    with lock_sessoes:
        return username in sessoes_ativas


def registrar_sessao(username: str, endereco: tuple, cliente_obj: "servidor_app") -> None:
    with lock_sessoes:
        sessoes_ativas[username] = endereco
        clientes_conectados[username] = cliente_obj
    log.info("SESSAO_REGISTRADA | usuario=%s endereco=%s:%d", username, *endereco)


def encerrar_sessao(username: str) -> None:
    with lock_sessoes:
        endereco = sessoes_ativas.pop(username, None)
        clientes_conectados.pop(username, None)
    if endereco:
        log.info("SESSAO_ENCERRADA | usuario=%s endereco=%s:%d", username, *endereco)
    else:
        log.info("SESSAO_ENCERRADA | usuario=%s (endereço desconhecido)", username)

def enviar_para_todos(remetente, mensagem):
    with lock_sessoes:
        for usuario, cliente in clientes_conectados.items():
            try:
                if usuario == remetente:
                    cliente.send(f"[MENSAGEM PÚBLICA ENVIADA] {mensagem}".encode())
                else:
                    cliente.send(f"[MENSAGEM PÚBLICA] Recebido de {remetente}: {mensagem}".encode())
            except:
                pass

# ══════════════════════════════════════════════
#  Texto de ajuda
# ══════════════════════════════════════════════
AJUDA = (
    "\n╔═════════════════════════════════════════════════════════════╗\n"
    "║                    COMANDOS DISPONÍVEIS                     ║\n"
    "╠═════════════════════════════════════════════════════════════╣\n"
    "║ /msgpublica <texto>      Envia mensagem pública             ║\n"
    "║ /msg <usuario> <texto>   Envia mensagem privada             ║\n"
    "║ /usuarios                Lista usuários online              ║\n"
    "║ /ajuda                   Exibe esta mensagem                ║\n"
    "║ /cadastrar <u> <s>       Cadastra usuário (superuser)       ║\n"
    "║ /promover <usuario>      Promove usuário (superuser)        ║\n"
    "║ /sair                    Encerra a conexão                  ║\n"
    "╚═════════════════════════════════════════════════════════════╝"
)


# ══════════════════════════════════════════════
#  Processamento de comandos
# ══════════════════════════════════════════════
def processar_comando(remetente: str, mensagem: str, cliente_obj: "servidor_app") -> bool:
    """
    Processa um comando enviado pelo cliente.
    Retorna True se a conexão deve ser encerrada (/sair).
    """
    partes  = mensagem.strip().split(" ", 2)
    comando = partes[0].lower()

    log.info("COMANDO | usuario=%s comando=%s", remetente, comando)

    if comando == "/sair":
        cliente_obj.send(b"[Servidor] Ate logo!")
        log.info("SAIR | usuario=%s", remetente)
        return True

    elif comando == "/ajuda":
        cliente_obj.send(AJUDA.encode())

    elif comando == "/usuarios":
        with lock_sessoes:
            online = list(sessoes_ativas.keys())
            log.info("LISTA_USUARIOS | solicitado_por=%s online=%s", remetente, online)
        if online:
            cliente_obj.send(f"[Servidor] Usuarios online: {', '.join(online)}".encode())
        else:
            cliente_obj.send(b"[Servidor] Nenhum usuario online.")

    elif comando == "/listausuarios":
        with lock_sessoes:
            online = list(sessoes_ativas.keys())
        cliente_obj.send(f"[LISTA_USUARIOS]{','.join(online)}".encode())

    elif comando == "/msg":
        if len(partes) < 3 or not partes[2].strip():
            cliente_obj.send(b"[Servidor] Uso correto: /msg <usuario> <texto>")
            log.warning("MSG_PRIVADA_MAL_FORMADA | remetente=%s", remetente)
            return False

        destinatario = partes[1]
        texto = partes[2]

        if destinatario == remetente:
            cliente_obj.send(b"[Servidor] Voce nao pode enviar mensagem para si mesmo.")
            log.warning("MSG_PRIVADA_SELF | usuario=%s", remetente)
            return False

        with lock_sessoes:
            destino_obj = clientes_conectados.get(destinatario)

        if destino_obj is None:
            cliente_obj.send(
                f"[Servidor] Usuario '{destinatario}' nao encontrado ou offline.".encode()
            )
            log.warning(
                "MSG_PRIVADA_FALHOU | remetente=%s destinatario=%s motivo=offline",
                remetente, destinatario,
            )
            return False

        try:
            destino_obj.send(f"[Privado de {remetente}]: {texto}".encode())
            cliente_obj.send(f"[Servidor] Mensagem enviada para {destinatario}.".encode())
            log.info(
                "MSG_PRIVADA | de=%s para=%s tamanho=%d chars",
                remetente, destinatario, len(texto),
            )
        except RuntimeError as e:
            cliente_obj.send(
                f"[Servidor] Falha ao entregar mensagem para '{destinatario}'.".encode()
            )
            log.error(
                "MSG_PRIVADA_ERRO_ENTREGA | de=%s para=%s erro=%s",
                remetente, destinatario, e,
            )
    elif comando == "/msgpublica":
        if len(partes) < 2:
            cliente_obj.send(b"[Servidor] Uso: /msgpublica <mensagem>")
            return False

        texto = mensagem[len("/msgpublica"):].strip()

        enviar_para_todos(remetente, texto)

        log.info(
            "MSG_PUBLICA | remetente=%s mensagem=%s",
            remetente,
            texto,
        )

    elif comando == "/cadastrar":
        if not is_superuser(remetente):
            cliente_obj.send(b"[Servidor] Permissao negada. Apenas superusers podem cadastrar usuarios.")
            log.warning("CADASTRAR_NEGADO | usuario=%s nao e superuser", remetente)
            return False

        if len(partes) < 3 or not partes[1].strip() or not partes[2].strip():
            cliente_obj.send(b"[Servidor] Uso: /cadastrar <usuario> <senha>")
            return False

        novo_user  = partes[1].strip()
        nova_senha = partes[2].strip()
        usuarios   = carregar_usuarios()

        if novo_user in usuarios:
            cliente_obj.send(f"[Servidor] Usuario '{novo_user}' ja existe.".encode())
            log.warning("CADASTRAR_DUPLICADO | tentativa=%s por=%s", novo_user, remetente)
            return False

        usuarios[novo_user] = {"senha": hash_senha(nova_senha), "role": "user"}
        with open(ARQUIVO_USUARIOS, "w") as f:
            json.dump(usuarios, f, indent=4)

        cliente_obj.send(f"[Servidor] Usuario '{novo_user}' cadastrado com sucesso.".encode())
        log.info("USUARIO_CADASTRADO | novo=%s por=%s", novo_user, remetente)

    elif comando == "/promover":
        if not is_superuser(remetente):
            cliente_obj.send(b"[Servidor] Permissao negada. Apenas superusers podem promover usuarios.")
            log.warning("PROMOVER_NEGADO | usuario=%s nao e superuser", remetente)
            return False

        if len(partes) < 2 or not partes[1].strip():
            cliente_obj.send(b"[Servidor] Uso: /promover <usuario>")
            return False

        alvo     = partes[1].strip()
        usuarios = carregar_usuarios()

        if alvo not in usuarios:
            cliente_obj.send(f"[Servidor] Usuario '{alvo}' nao encontrado.".encode())
            log.warning("PROMOVER_NAO_ENCONTRADO | alvo=%s por=%s", alvo, remetente)
            return False

        if usuarios[alvo].get("role") == "superuser":
            cliente_obj.send(f"[Servidor] '{alvo}' ja e superuser.".encode())
            return False

        usuarios[alvo]["role"] = "superuser"
        with open(ARQUIVO_USUARIOS, "w") as f:
            json.dump(usuarios, f, indent=4)

        cliente_obj.send(f"[Servidor] '{alvo}' agora e superuser.".encode())
        log.info("USUARIO_PROMOVIDO | alvo=%s por=%s", alvo, remetente)

    else:
        cliente_obj.send(
            f"[Servidor] Comando '{comando}' desconhecido. Digite /ajuda.".encode()
        )
        log.warning("COMANDO_DESCONHECIDO | usuario=%s comando=%s", remetente, comando)

    return False


# ══════════════════════════════════════════════
#  Classe principal do servidor
# ══════════════════════════════════════════════
class servidor_app:
    def __init__(self, sock: socket.socket | None = None):
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.lock_envio = threading.Lock()
        self._rodando = threading.Event()

   # ── Inicialização ─────────────────────────
   # iniciar: substituir o bloco try/while
    def iniciar(self, host: str = '', porta: int = 5000) -> None:
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, porta))
        self.sock.listen(5)
        self.sock.settimeout(1.0) # permite checar _rodando a cada 1s
        self._rodando.set()
        log.info("SERVIDOR_INICIADO | host=%s porta=%d", host or "0.0.0.0", porta)

        try:
            while self._rodando.is_set():
                try:
                    conn, addr = self.sock.accept()
                except socket.timeout:
                    continue # apenas checa o Event e volta
                log.info("NOVA_CONEXAO | endereco=%s:%d threads_ativas=%d",
                        addr[0], addr[1], threading.active_count())
                threading.Thread(
                    target=self.listen_multiclient,
                    args=(conn, addr),
                    daemon=True,
                ).start()

        except KeyboardInterrupt:
            log.info("SERVIDOR_ENCERRADO | interrupção manual")
        finally:
            self.sock.close()

    def parar(self) -> None:
        self._rodando.clear()

        # avisa e desconecta todos os clientes ativos
        with lock_sessoes:
            clientes = list(clientes_conectados.values())

        for cliente in clientes:
            try:
                cliente.send("[Servidor] O servidor foi encerrado. Até logo!".encode())
                cliente.sock.shutdown(socket.SHUT_RDWR)
                cliente.sock.close()
            except OSError:
                pass

        try:
            self.sock.close()
        except OSError:
            pass

        log.info("SERVIDOR_PARADO | solicitação via dashboard")

    # ── Envio com prefixo de 4 bytes ──────────
    def send(self, msg: bytes) -> None:
        header = struct.pack('>I', len(msg))
        dados  = header + msg
        with self.lock_envio:
            totalsent = 0
            while totalsent < len(dados):
                try:
                    sent = self.sock.send(dados[totalsent:])
                    if sent == 0:
                        raise RuntimeError("Conexão via socket caiu.")
                    totalsent += sent
                except OSError as e:
                    raise RuntimeError(f"Erro ao enviar dados: {e}")

    # ── Recepção com prefixo de 4 bytes ───────
    def receive(self) -> bytes:
        header = b''
        while len(header) < 4:
            try:
                parte = self.sock.recv(4 - len(header))
            except OSError as e:
                raise RuntimeError(f"Erro ao ler header: {e}")
            if parte == b'':
                raise RuntimeError("Conexão via socket caiu.")
            header += parte

        msg_length = struct.unpack('>I', header)[0]

        MAX_MSG = 10 * 1024 * 1024
        if msg_length > MAX_MSG:
            raise RuntimeError(f"Tamanho inválido: {msg_length} bytes")

        chunks, bytes_recd = [], 0
        while bytes_recd < msg_length:
            try:
                chunk = self.sock.recv(min(msg_length - bytes_recd, 2048))
            except OSError as e:
                raise RuntimeError(f"Erro ao ler corpo: {e}")
            if chunk == b'':
                raise RuntimeError("Conexão caiu durante a leitura.")
            chunks.append(chunk)
            bytes_recd += len(chunk)

        return b''.join(chunks)

    # ── Autenticação ──────────────────────────
    def autenticar(self, endereco: tuple) -> str | None:
        usuarios       = carregar_usuarios()
        MAX_TENTATIVAS = 3

        self.send(b"USUARIO:")
        log.info("AUTH_INICIO | endereco=%s:%d", *endereco)

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                username = self.receive().decode().strip()
                self.send(b"SENHA:")
                senha = self.receive().decode().strip()
            except RuntimeError:
                log.warning("AUTH_DESCONEXAO | endereco=%s:%d durante_login", *endereco)
                return None

            if username in usuarios and usuarios[username]["senha"] == hash_senha(senha):
                if usuario_ja_conectado(username):
                    self.send(b"ERRO: Usuario ja conectado em outra sessao.")
                    log.warning(
                        "AUTH_DUPLICADA | usuario=%s endereco=%s:%d",
                        username, *endereco,
                    )
                    return None

                self.send(b"LOGIN_OK")
                registrar_sessao(username, endereco, self)
                return username

            else:
                restantes = MAX_TENTATIVAS - tentativa
                log.warning(
                    "AUTH_FALHOU | usuario=%s tentativa=%d/%d endereco=%s:%d",
                    username, tentativa, MAX_TENTATIVAS, *endereco,
                )
                if restantes > 0:
                    self.send(
                        f"ERRO: Credenciais invalidas. Tentativas restantes: {restantes}".encode()
                    )
                else:
                    self.send(b"ERRO: Tentativas esgotadas. Conexao encerrada.")
                    log.warning("AUTH_BLOQUEADO | endereco=%s:%d", *endereco)

        return None

    # ── Thread por cliente ────────────────────
    def listen_multiclient(self, cliente_socket: socket.socket, endereco: tuple) -> None:
        cliente  = servidor_app(sock=cliente_socket)
        username = None

        try:
            username = cliente.autenticar(endereco)
            if username is None:
                log.info("ACESSO_NEGADO | endereco=%s:%d", *endereco)
                return

            cliente.send(
                "[Servidor] Bem-vindo! Digite /ajuda para ver os comandos.".encode()
            )
            log.info("AUTENTICADO | usuario=%s endereco=%s:%d", username, *endereco)

            while True:
                dados = cliente.receive()
                if not dados:
                    log.info("DESCONEXAO_LIMPA | usuario=%s", username)
                    break

                mensagem = dados.decode(errors="replace")
                log.info("MSG_RECEBIDA | usuario=%s tamanho=%d conteudo=%s",
                         username, len(mensagem), mensagem[:120])

                if mensagem.startswith("/"):
                    encerrar = processar_comando(username, mensagem, cliente)
                    if encerrar:
                        break
                else:
                    cliente.send(
                            b"[Servidor] Mensagem invalida. Utilize /msgpublica <texto> para enviar uma mensagem publica ou /ajuda para ver os comandos."
                        )

        except RuntimeError as e:
            log.error("CONEXAO_ENCERRADA | usuario=%s erro=%s", username or str(endereco), e)
        except OSError as e:
            log.error("OS_ERROR | usuario=%s erro=%s", username or str(endereco), e)
        finally:
            if username:
                encerrar_sessao(username)
            try:
                cliente_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            cliente_socket.close()
            log.info("RECURSOS_LIBERADOS | usuario=%s", username or str(endereco))