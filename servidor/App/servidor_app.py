import socket
import struct
import threading
import json
import os
import hashlib

ARQUIVO_USUARIOS = "usuarios.json"

def carregar_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS):
        usuarios_padrao = {
            "admin": hashlib.sha256("admin".encode()).hexdigest(),
            "carlos": hashlib.sha256("123456".encode()).hexdigest(),
        }
        with open(ARQUIVO_USUARIOS, "w") as f:
            json.dump(usuarios_padrao, f, indent=4)
        print("[*] Arquivo de usuários criado com usuários padrão.")

    with open(ARQUIVO_USUARIOS, "r") as f:
        return json.load(f)

def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()

sessoes_ativas = {}        # username -> endereço IP
clientes_conectados = {}   # username -> objeto servidor_app  ← NOVO
lock_sessoes = threading.Lock()

def usuario_ja_conectado(username):
    with lock_sessoes:
        return username in sessoes_ativas

def registrar_sessao(username, endereco, cliente_obj):
    with lock_sessoes:
        sessoes_ativas[username] = endereco
        clientes_conectados[username] = cliente_obj          # ← NOVO
    print(f"[+] Sessão registrada: {username} @ {endereco}")

def encerrar_sessao(username):
    with lock_sessoes:
        sessoes_ativas.pop(username, None)
        clientes_conectados.pop(username, None)              # ← NOVO
    print(f"[-] Sessão encerrada: {username}")

# comados disponíveis que voce pode acessar
AJUDA = (
    "Comandos disponíveis:\n"
    "  /msg <usuario> <texto>  — envia mensagem privada\n"
    "  /usuarios               — lista usuários online\n"
    "  /ajuda                  — exibe esta mensagem\n"
    "  /sair                   — encerra a conexão"
)

def processar_comando(remetente: str, mensagem: str, cliente_obj) -> bool:
    """
    Processa um comando enviado pelo cliente.
    Retorna True se a conexão deve ser encerrada (/sair), False caso contrário.
    """
    partes = mensagem.strip().split(" ", 2)
    comando = partes[0].lower()

    if comando == "/sair":
        cliente_obj.send(b"[Servidor] Ate logo!")
        return True  # sinaliza encerramento

    elif comando == "/ajuda":
        cliente_obj.send(AJUDA.encode())

    elif comando == "/usuarios":
        with lock_sessoes:
            online = list(sessoes_ativas.keys())
        if online:
            lista = ", ".join(online)
            cliente_obj.send(f"[Servidor] Usuarios online: {lista}".encode())
        else:
            cliente_obj.send(b"[Servidor] Nenhum usuario online.")

    elif comando == "/msg":
        if len(partes) < 3:
            cliente_obj.send(b"[Servidor] Uso correto: /msg <usuario> <texto>")
            return False

        destinatario = partes[1]
        texto        = partes[2]

        # não pode mandar mensagem para si mesmo
        if destinatario == remetente:
            cliente_obj.send(b"[Servidor] Voce nao pode enviar mensagem para si mesmo.")
            return False

        with lock_sessoes:
            destino_obj = clientes_conectados.get(destinatario)

        if destino_obj is None:
            cliente_obj.send(
                f"[Servidor] Usuario '{destinatario}' nao encontrado ou offline.".encode()
            )
            return False

        # envia para o destinatário
        try:
            destino_obj.send(f"[Privado de {remetente}]: {texto}".encode())
            cliente_obj.send(f"[Servidor] Mensagem enviada para {destinatario}.".encode())
            print(f"[PM] {remetente} -> {destinatario}: {texto}")
        except RuntimeError:
            cliente_obj.send(
                f"[Servidor] Falha ao entregar mensagem para '{destinatario}'.".encode()
            )

#   caso voce digite um comando nada ver, ele retorna essa mensagem
    else:
        cliente_obj.send(
            f"[Servidor] Comando '{comando}' desconhecido. Digite /ajuda.".encode()
        )

    return False  # continua conectado



class servidor_app:
    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock

    # Iniciar servidor  172.22.70.26
    def iniciar(self, host='', porta=5000):
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, porta))
        self.sock.listen(5)
        print(f"[*] Servidor aguardando conexões em {host}:{porta}")

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

    # Envio
    def send(self, msg: bytes):
        header = struct.pack('>I', len(msg))
        dados = header + msg
        totalsent = 0
        while totalsent < len(dados):
            try:
                sent = self.sock.send(dados[totalsent:])
                if sent == 0:
                    raise RuntimeError("A conexão via socket caiu.")
                totalsent += sent
            except OSError as e:
                raise RuntimeError(f"Erro ao enviar dados: {e}")

    #  Recepção
    def receive(self) -> bytes:
        header = b''
        while len(header) < 4:
            try:
                parte = self.sock.recv(4 - len(header))
            except OSError as e:
                raise RuntimeError(f"Erro ao ler header: {e}")
            if parte == b'':
                raise RuntimeError("A conexão via socket caiu.")
            header += parte

        msg_length = struct.unpack('>I', header)[0]

        MAX_MSG = 10 * 1024 * 1024
        if msg_length > MAX_MSG:
            raise RuntimeError(f"Tamanho inválido: {msg_length} bytes")

        chunks = []
        bytes_recd = 0
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

    # Autenticação
    def autenticar(self, endereco) -> str | None:
        usuarios = carregar_usuarios()
        MAX_TENTATIVAS = 3

        self.send(b"USUARIO:")

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                username = self.receive().decode().strip()
                self.send(b"SENHA:")
                senha = self.receive().decode().strip()
            except RuntimeError:
                print(f"[!] {endereco} desconectou durante o login.")
                return None

            if username in usuarios and usuarios[username] == hash_senha(senha):
                if usuario_ja_conectado(username):
                    self.send(b"ERRO: Usuario ja conectado em outra sessao.")
                    print(f"[!] Login duplicado bloqueado: {username}")
                    return None

                self.send(b"LOGIN_OK")
                registrar_sessao(username, endereco, self)   # ← passa self
                return username

            else:
                restantes = MAX_TENTATIVAS - tentativa
                if restantes > 0:
                    self.send(
                        f"ERRO: Credenciais invalidas. Tentativas restantes: {restantes}".encode()
                    )
                    print(f"[!] Tentativa {tentativa}/{MAX_TENTATIVAS} falhou — {endereco}")
                else:
                    self.send(b"ERRO: Tentativas esgotadas. Conexao encerrada.")
                    print(f"[x] {endereco} bloqueado por excesso de tentativas.")

        return None

    # Thread por cliente
    def listen_multiclient(self, cliente_socket, endereco):
        cliente = servidor_app(sock=cliente_socket)
        print(f"[+] Nova conexão: {endereco}")
        username = None

        try:
            # Etapa 1: autenticação obrigatória
            username = cliente.autenticar(endereco)
            if username is None:
                print(f"[-] Acesso negado: {endereco}")
                return

            # Avisa os comandos disponíveis logo após o login
            cliente.send(
                ("[Servidor] Bem-vindo! Digite /ajuda para ver os comandos.").encode()
            )

            # Etapa 2: comunicação autenticada
            print(f"[✓] {username} autenticado. Sessão iniciada.")
            while True:
                dados = cliente.receive()
                if not dados:
                    print(f"[~] {username} encerrou a conexão.")
                    break

                mensagem = dados.decode()
                print(f"[>] {username}: {mensagem}")

                # ── Verifica se é um comando (/msg, /usuarios, /ajuda, /sair)
                if mensagem.startswith("/"):
                    encerrar = processar_comando(username, mensagem, cliente)
                    if encerrar:
                        print(f"[~] {username} solicitou /sair.")
                        break
                else:
                    # mensagem normal → eco
                    cliente.send(f"[Servidor] Recebido: {mensagem}".encode())

        except RuntimeError as e:
            print(f"[!] Conexão encerrada ({username or endereco}): {e}")
        except OSError as e:
            print(f"[x] Erro de socket ({username or endereco}): {e}")
        finally:
            if username:
                encerrar_sessao(username)
            try:
                cliente_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            cliente_socket.close()
            print(f"[-] Recursos liberados: {username or endereco}")