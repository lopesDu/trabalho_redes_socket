import socket
import struct
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime
import logging
import os

#  Log do cliente

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler("logs/cliente.log", encoding="utf-8")],
)
log = logging.getLogger("cliente_gui")


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
        raise RuntimeError(f"Tamanho inválido: {msg_length} B")
    chunks, bytes_recd = [], 0
    while bytes_recd < msg_length:
        chunk = sock.recv(min(msg_length - bytes_recd, 2048))
        if chunk == b'':
            raise RuntimeError("Conexão caiu durante leitura.")
        chunks.append(chunk)
        bytes_recd += len(chunk)
    return b''.join(chunks)


# ──────────────────────────────────────────────
#  Paleta de cores
# ──────────────────────────────────────────────
COR = {
    "bg":           "#1e1e2e",   # fundo principal
    "bg_painel":    "#2a2a3e",   # painéis laterais / campos
    "bg_entrada":   "#313145",   # campo de texto
    "borda":        "#44475a",   # bordas sutis
    "texto":        "#cdd6f4",   # texto principal
    "texto_dim":    "#6c7086",   # texto secundário / timestamp
    "servidor":     "#89b4fa",   # mensagens do servidor  (azul)
    "privado":      "#cba6f7",   # mensagens privadas     (lilás)
    "enviado":      "#a6e3a1",   # mensagens enviadas     (verde)
    "erro":         "#f38ba8",   # erros                  (vermelho)
    "sistema":      "#fab387",   # avisos do sistema      (laranja)
    "acento":       "#89dceb",   # destaques / botão      (ciano)
    "acento_hover": "#74c7ec",
    "online":       "#a6e3a1",   # indicador online
}


# ══════════════════════════════════════════════
#  Tela de Login
# ══════════════════════════════════════════════
class TelaLogin(tk.Toplevel):
    def __init__(self, master, on_sucesso):
        super().__init__(master)
        self.on_sucesso  = on_sucesso
        self.sock        = None
        self.username    = None

        self.title("Login — Chat TCP")
        self.resizable(False, False)
        self.configure(bg=COR["bg"])
        self.grab_set()   # modal

        self._construir_ui()
        self._centralizar(360, 420)
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

    # ── Layout ────────────────────────────────
    def _construir_ui(self):
        pad = {"padx": 30, "pady": 8}

        # título
        tk.Label(self, text="💬", font=("Segoe UI Emoji", 36),
                 bg=COR["bg"], fg=COR["acento"]).pack(pady=(30, 0))
        tk.Label(self, text="Chat TCP",
                 font=("Segoe UI", 18, "bold"),
                 bg=COR["bg"], fg=COR["texto"]).pack()
        tk.Label(self, text="Entre com suas credenciais",
                 font=("Segoe UI", 9),
                 bg=COR["bg"], fg=COR["texto_dim"]).pack(pady=(2, 20))

        # host / porta
        frame_conn = tk.Frame(self, bg=COR["bg"])
        frame_conn.pack(**pad, fill="x")
        tk.Label(frame_conn, text="Servidor", width=8, anchor="w",
                 bg=COR["bg"], fg=COR["texto_dim"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.entry_host = self._entry(frame_conn, "localhost", width=16)
        self.entry_host.pack(side="left", padx=(0, 6))
        self.entry_porta = self._entry(frame_conn, "5000", width=6)
        self.entry_porta.pack(side="left")

        # usuário
        self._label("Usuário")
        self.entry_user = self._entry_full("seu usuário")
        self.entry_user.pack(**pad, fill="x")

        # senha
        self._label("Senha")
        self.entry_senha = self._entry_full("••••••", show="•")
        self.entry_senha.pack(**pad, fill="x")
        self.entry_senha.bind("<Return>", lambda _: self._conectar())

        # status
        self.lbl_status = tk.Label(self, text="",
                                   font=("Segoe UI", 9),
                                   bg=COR["bg"], fg=COR["erro"])
        self.lbl_status.pack()

        # botão
        self.btn = tk.Button(
            self, text="Conectar",
            font=("Segoe UI", 10, "bold"),
            bg=COR["acento"], fg=COR["bg"],
            activebackground=COR["acento_hover"],
            relief="flat", cursor="hand2",
            padx=20, pady=8,
            command=self._conectar,
        )
        self.btn.pack(pady=(10, 30))

    def _label(self, texto):
        tk.Label(self, text=texto, anchor="w",
                 font=("Segoe UI", 9),
                 bg=COR["bg"], fg=COR["texto_dim"]).pack(padx=30, fill="x")

    def _entry(self, parent, placeholder, show="", width=None):
        e = tk.Entry(parent, bg=COR["bg_entrada"], fg=COR["texto"],
                     insertbackground=COR["texto"],
                     relief="flat", font=("Segoe UI", 10),
                     show=show, **({"width": width} if width else {}))
        e.insert(0, placeholder)
        return e

    def _entry_full(self, placeholder, show=""):
        f = tk.Frame(self, bg=COR["bg_entrada"],
                     highlightthickness=1,
                     highlightbackground=COR["borda"],
                     highlightcolor=COR["acento"])
        e = tk.Entry(f, bg=COR["bg_entrada"], fg=COR["texto"],
                     insertbackground=COR["texto"],
                     relief="flat", font=("Segoe UI", 11),
                     show=show, bd=6)
        e.insert(0, placeholder)
        e.pack(fill="x")
        # guarda o frame junto para poder empacotar pelo frame
        e._frame = f
        # monkey-patch pack para empacotar o frame, não o Entry diretamente
        _orig_pack = e.pack
        def _pack_via_frame(**kw):
            f.pack(**kw)
        e.pack = _pack_via_frame
        return e

    # ── Ação de conectar ──────────────────────
    def _conectar(self):
        host   = self.entry_host.get().strip()
        porta  = self.entry_porta.get().strip()
        user   = self.entry_user.get().strip()
        senha  = self.entry_senha.get().strip()

        if not all([host, porta, user, senha]):
            self._status("Preencha todos os campos.", erro=True)
            return

        try:
            porta = int(porta)
        except ValueError:
            self._status("Porta inválida.", erro=True)
            return

        self._status("Conectando...", erro=False)
        self.btn.configure(state="disabled", text="Aguarde...")
        threading.Thread(
            target=self._thread_login,
            args=(host, porta, user, senha),
            daemon=True,
        ).start()

    def _thread_login(self, host, porta, user, senha):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, porta))
            log.info("CONECTADO | %s:%d", host, porta)

            # "USUARIO:"
            receive(sock)
            send(sock, user.encode())
            # "SENHA:"
            receive(sock)
            send(sock, senha.encode())

            resposta = receive(sock).decode()

            if resposta.startswith("LOGIN_OK"):
                boas_vindas = receive(sock).decode()
                log.info("LOGIN_OK | usuario=%s", user)
                self.sock     = sock
                self.username = user
                self.after(0, lambda: self.on_sucesso(sock, user, boas_vindas))
                self.after(0, self.destroy)
            else:
                log.warning("LOGIN_FALHOU | %s", resposta)
                sock.close()
                self.after(0, lambda: self._status(resposta.replace("ERRO: ", ""), erro=True))
                self.after(0, lambda: self.btn.configure(state="normal", text="Conectar"))

        except ConnectionRefusedError:
            self.after(0, lambda: self._status("Servidor offline ou inacessível.", erro=True))
            self.after(0, lambda: self.btn.configure(state="normal", text="Conectar"))
        except Exception as e:
            log.error("ERRO_LOGIN | %s", e)
            self.after(0, lambda: self._status(str(e), erro=True))
            self.after(0, lambda: self.btn.configure(state="normal", text="Conectar"))

    def _status(self, msg, erro=True):
        self.lbl_status.configure(
            text=msg,
            fg=COR["erro"] if erro else COR["sistema"],
        )

    def _cancelar(self):
        self.master.destroy()

    def _centralizar(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


# ══════════════════════════════════════════════
#  Janela principal do Chat
# ══════════════════════════════════════════════
class JanelaChat(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()   # esconde até o login terminar
        self.title("Chat TCP")
        self.configure(bg=COR["bg"])
        self.minsize(700, 480)
        self._centralizar(900, 560)
        self.protocol("WM_DELETE_WINDOW", self._sair)

        self.sock:     socket.socket | None = None
        self.username: str = ""
        self.lock_envio = threading.Lock()   # protege envios concorrentes no socket
        self._construir_ui()

        # abre login
        TelaLogin(self, self._pos_login)
        self.mainloop()

    # ── Layout principal ──────────────────────
    def _construir_ui(self):
        # ── Barra superior ────────────────────
        barra = tk.Frame(self, bg=COR["bg_painel"], height=44)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        tk.Label(barra, text="💬  Chat TCP",
                 font=("Segoe UI", 12, "bold"),
                 bg=COR["bg_painel"], fg=COR["texto"]).pack(side="left", padx=16)

        self.lbl_usuario = tk.Label(barra, text="",
                                    font=("Segoe UI", 9),
                                    bg=COR["bg_painel"], fg=COR["acento"])
        self.lbl_usuario.pack(side="right", padx=16)

        self.lbl_online = tk.Label(barra, text="● offline",
                                   font=("Segoe UI", 9),
                                   bg=COR["bg_painel"], fg=COR["erro"])
        self.lbl_online.pack(side="right", padx=(0, 4))

        # ── Corpo ─────────────────────────────
        corpo = tk.Frame(self, bg=COR["bg"])
        corpo.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        # painel lateral: usuários online
        painel_usuarios = tk.Frame(corpo, bg=COR["bg_painel"], width=150)
        painel_usuarios.pack(side="left", fill="y", padx=(0, 8))
        painel_usuarios.pack_propagate(False)

        tk.Label(painel_usuarios, text="Usuários online",
                 font=("Segoe UI", 9, "bold"),
                 bg=COR["bg_painel"], fg=COR["texto_dim"]
                 ).pack(anchor="w", padx=8, pady=(8, 4))

        self.lista_usuarios = tk.Listbox(
            painel_usuarios,
            bg=COR["bg_entrada"], fg=COR["texto"],
            selectbackground=COR["acento"], selectforeground=COR["bg"],
            relief="flat", bd=0, font=("Segoe UI", 10),
            activestyle="none", highlightthickness=0,
        )
        self.lista_usuarios.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.lista_usuarios.bind("<<ListboxSelect>>", self._selecionar_usuario)

        tk.Label(painel_usuarios, text="clique para responder",
                 font=("Segoe UI", 8),
                 bg=COR["bg_painel"], fg=COR["texto_dim"]
                 ).pack(anchor="w", padx=8, pady=(0, 8))

        # área de mensagens
        self.area_msgs = scrolledtext.ScrolledText(
            corpo,
            bg=COR["bg_painel"], fg=COR["texto"],
            font=("Consolas", 10),
            relief="flat", bd=0,
            state="disabled",
            wrap="word",
            padx=10, pady=8,
        )
        self.area_msgs.pack(side="left", fill="both", expand=True)
        self._configurar_tags()

        # ── Barra de comandos rápidos
        barra_cmd = tk.Frame(self, bg=COR["bg"], pady=4)
        barra_cmd.pack(fill="x", padx=10)

        for cmd, dica in [("/usuarios", "Quem está online"),
                          ("/ajuda",    "Ver comandos"),
                          ("/sair",     "Desconectar")]:
            tk.Button(
                barra_cmd, text=cmd,
                font=("Segoe UI", 8),
                bg=COR["bg_entrada"], fg=COR["texto_dim"],
                activebackground=COR["borda"],
                relief="flat", cursor="hand2",
                padx=8, pady=3,
                command=lambda c=cmd: self._enviar_texto(c),
            ).pack(side="left", padx=(0, 4))

        # ── Campo de entrada ──────────────────
        frame_entrada = tk.Frame(self, bg=COR["bg_entrada"],
                                 highlightthickness=1,
                                 highlightbackground=COR["borda"],
                                 highlightcolor=COR["acento"])
        frame_entrada.pack(fill="x", padx=10, pady=(4, 10))

        self.entry_msg = tk.Entry(
            frame_entrada,
            bg=COR["bg_entrada"], fg=COR["texto"],
            insertbackground=COR["texto"],
            relief="flat", font=("Segoe UI", 11), bd=8,
        )
        self.entry_msg.pack(side="left", fill="both", expand=True)
        self.entry_msg.bind("<Return>",     lambda _: self._enviar())
        self.entry_msg.bind("<KeyRelease>", self._atualizar_hint)

        self.lbl_hint = tk.Label(
            frame_entrada, text="",
            font=("Segoe UI", 8), width=26, anchor="e",
            bg=COR["bg_entrada"], fg=COR["texto_dim"],
        )
        self.lbl_hint.pack(side="left", padx=(0, 4))

        self.btn_enviar = tk.Button(
            frame_entrada, text="Enviar ↵",
            font=("Segoe UI", 10, "bold"),
            bg=COR["acento"], fg=COR["bg"],
            activebackground=COR["acento_hover"],
            relief="flat", cursor="hand2",
            padx=14, pady=6,
            command=self._enviar,
        )
        self.btn_enviar.pack(side="right")

    def _configurar_tags(self):
        """Tags de cor para cada tipo de mensagem."""
        self.area_msgs.tag_configure("ts",       foreground=COR["texto_dim"],  font=("Consolas", 9))
        self.area_msgs.tag_configure("servidor", foreground=COR["servidor"])
        self.area_msgs.tag_configure("privado",  foreground=COR["privado"],    font=("Consolas", 10, "bold"))
        self.area_msgs.tag_configure("enviado",  foreground=COR["enviado"])
        self.area_msgs.tag_configure("erro",     foreground=COR["erro"])
        self.area_msgs.tag_configure("sistema",  foreground=COR["sistema"])
        self.area_msgs.tag_configure("normal",   foreground=COR["texto"])

    # ── Pós-login ─────────────────────────────
    def _pos_login(self, sock: socket.socket, username: str, boas_vindas: str):
        self.sock     = sock
        self.username = username

        self.lbl_usuario.configure(text=f"  {username}")
        self.lbl_online.configure(text="● online", fg=COR["online"])
        self.entry_msg.focus_set()
        self.deiconify()

        self._inserir_msg(boas_vindas, "sistema")
        self._inserir_separador()

        # thread de recepção
        threading.Thread(target=self._receber_loop, daemon=True).start()
        # thread que mantém a lista de usuários online atualizada
        threading.Thread(target=self._thread_atualizar_usuarios, daemon=True).start()

    # ── Thread de recepção ────────────────────
    def _receber_loop(self):
        while True:
            try:
                dados = receive(self.sock).decode(errors="replace")
                self._classificar_e_inserir(dados)
                log.info("RECEBIDO | %s", dados[:120])
            except RuntimeError:
                self.after(0, lambda: self._inserir_msg(
                    "Conexão com o servidor encerrada.", "erro"))
                self.after(0, lambda: self.lbl_online.configure(
                    text="● offline", fg=COR["erro"]))
                log.warning("CONEXAO_ENCERRADA pelo servidor")
                break

    def _classificar_e_inserir(self, texto: str):
        # resposta "silenciosa" usada para popular a lista de usuários online
        if texto.startswith("[LISTA_USUARIOS]"):
            usuarios_str = texto[len("[LISTA_USUARIOS]"):]
            usuarios = [u for u in usuarios_str.split(",") if u and u != self.username]
            self.after(0, lambda: self._atualizar_lista_usuarios(usuarios))
            return

        if "[Privado de " in texto:
            tag = "privado"
            log.info("MSG_PRIVADA_RECEBIDA | %s", texto)
        elif texto.startswith("[Servidor]"):
            tag = "servidor"
        else:
            tag = "normal"
        self.after(0, lambda: self._inserir_msg(texto, tag))

    # ── Lista de usuários online ──────────────
    def _atualizar_lista_usuarios(self, usuarios: list[str]):
        self.lista_usuarios.delete(0, "end")
        for i, usuario in enumerate(sorted(usuarios)):
            self.lista_usuarios.insert("end", usuario)
            self.lista_usuarios.itemconfig(i, fg=COR["online"])

    def _selecionar_usuario(self, _event=None):
        selecao = self.lista_usuarios.curselection()
        if not selecao:
            return
        usuario = self.lista_usuarios.get(selecao[0])

        self.entry_msg.delete(0, "end")
        self.entry_msg.insert(0, f"/msg {usuario} ")
        self.entry_msg.icursor("end")
        self.entry_msg.focus_set()
        self._atualizar_hint()

        # libera a seleção para poder clicar de novo no mesmo usuário depois
        self.lista_usuarios.selection_clear(0, "end")

    # ── Thread de atualização periódica ───────
    def _thread_atualizar_usuarios(self):
        """A cada poucos segundos, pede ao servidor a lista de usuários
        online (comando silencioso, não aparece no chat)."""
        while True:
            try:
                with self.lock_envio:
                    send(self.sock, b"/listausuarios")
            except (RuntimeError, OSError):
                break
            time.sleep(4)

    # ── Inserção de mensagens ─────────────────
    def _inserir_msg(self, texto: str, tag: str = "normal"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.area_msgs.configure(state="normal")
        self.area_msgs.insert("end", f"[{ts}] ", "ts")
        self.area_msgs.insert("end", texto + "\n", tag)
        self.area_msgs.configure(state="disabled")
        self.area_msgs.see("end")

    def _inserir_separador(self):
        self.area_msgs.configure(state="normal")
        self.area_msgs.insert("end", "─" * 55 + "\n", "ts")
        self.area_msgs.configure(state="disabled")

    # ── Envio ─────────────────────────────────
    def _enviar(self):
        msg = self.entry_msg.get().strip()
        if not msg or self.sock is None:
            return

        erro = self._validar_comando(msg)
        if erro:
            self._inserir_msg(f"[!] {erro}", "erro")
            return

        try:
            with self.lock_envio:
                send(self.sock, msg.encode())
            self.entry_msg.delete(0, "end")
            self.lbl_hint.configure(text="")

            # eco local
            if msg.startswith("/msg "):
                partes = msg.split(" ", 2)
                dest   = partes[1] if len(partes) > 1 else "?"
                self._inserir_msg(f"[Para {dest}]: {partes[2] if len(partes) > 2 else ''}", "enviado")
                log.info("MSG_PRIVADA_ENVIADA | para=%s", dest)
            elif not msg.startswith("/"):
                self._inserir_msg(f"[Você]: {msg}", "enviado")
                log.info("MSG_ENVIADA | %s", msg[:80])

            if msg.lower() == "/sair":
                self.after(800, self.destroy)

        except RuntimeError as e:
            self._inserir_msg(f"Erro ao enviar: {e}", "erro")
            log.error("ERRO_ENVIO | %s", e)

    def _enviar_texto(self, texto: str):
        """Insere texto no campo e envia (usado pelos botões de comando rápido)."""
        self.entry_msg.delete(0, "end")
        self.entry_msg.insert(0, texto)
        self._enviar()

    # ── Hint de /msg ──────────────────────────
    def _atualizar_hint(self, _event=None):
        msg = self.entry_msg.get()
        if msg.startswith("/msg "):
            partes = msg.split(" ", 2)
            if len(partes) == 2:
                self.lbl_hint.configure(text="/msg <usuario> <texto>")
            elif len(partes) == 3:
                self.lbl_hint.configure(text=f"→ {partes[1]}")
        else:
            self.lbl_hint.configure(text="")

    # ── Validação local de comandos ───────────
    COMANDOS = {"/msg", "/usuarios", "/ajuda", "/sair", "/cadastrar", "/promover"}


    def _validar_comando(self, msg: str) -> str | None:
        if not msg.startswith("/"):
            return None
        partes = msg.strip().split(" ", 2)
        cmd    = partes[0].lower()
        if cmd not in self.COMANDOS:
            return f"Comando desconhecido: '{cmd}'. Use /ajuda."
        if cmd == "/msg" and (len(partes) < 3 or not partes[2].strip()):
            return "Uso: /msg <usuario> <mensagem>"
        if cmd == "/cadastrar" and (len(partes) < 3 or not partes[2].strip()):
            return "Uso: /cadastrar <usuario> <senha>"
        return None

    # ── Encerramento ──────────────────────────
    def _sair(self):
        if self.sock:
            try:
                send(self.sock, b"/sair")
            except Exception:
                pass
            finally:
                self.sock.close()
        self.destroy()

    def _centralizar(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


# ──────────────────────────────────────────────
if __name__ == "__main__":
    JanelaChat()