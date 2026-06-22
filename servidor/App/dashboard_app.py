"""
Dashboard de monitoramento do servidor de chat TCP.

Executa o servidor (servidor_app) em uma thread separada e exibe, em tempo
real:
  - status do servidor (online / offline / erro) e tempo de atividade
  - estatísticas gerais (conexões ativas, total de conexões, mensagens
    processadas, tentativas de login falhas)
  - tabela com os usuários conectados (endereço, horário de conexão e
    duração da sessão)
  - log de atividade do servidor, colorido por nível, com filtros

A interface segue a mesma paleta de cores e estilo visual do cliente
(cliente_app.py), para manter a identidade visual do projeto.
"""

import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime, timedelta

# Ajuste o import abaixo conforme a estrutura de pacotes do seu projeto.
from servidor.App.servidor_app import servidor_app, sessoes_ativas, lock_sessoes, log


# ══════════════════════════════════════════════
#  Paleta de cores (mesma do cliente)
# ══════════════════════════════════════════════
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
#  Handler de log → fila thread-safe
# ══════════════════════════════════════════════
class QueueHandler(logging.Handler):
    """Encaminha cada LogRecord emitido pelo logger 'servidor' para uma fila,
    que a thread principal (tkinter) consome periodicamente."""

    def __init__(self, fila: queue.Queue):
        super().__init__()
        self.fila = fila

    def emit(self, record: logging.LogRecord) -> None:
        self.fila.put(record)


# ══════════════════════════════════════════════
#  Janela principal do Dashboard
# ══════════════════════════════════════════════
class DashboardApp(tk.Tk):
    def __init__(self, host: str = "", porta: int = 5000):
        super().__init__()
        self.title("Dashboard — Servidor Chat TCP")
        self.configure(bg=COR["bg"])
        self.minsize(960, 620)
        self._centralizar(1080, 680)

        self.host  = host or "0.0.0.0"
        self.porta = porta
        self.inicio = datetime.now()

        # ── estatísticas acumuladas ───────────
        self.total_conexoes        = 0
        self.mensagens_processadas = 0
        self.falhas_login          = 0
        self.usuarios_desde: dict[str, datetime] = {}

        self.fila_logs: queue.Queue = queue.Queue()
        self.filtro_atual = "TUDO"

        self._construir_ui()
        self._registrar_handler_log()
        self._iniciar_servidor()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self._loop_atualizacao()

    # ══════════════════════════════════════════
    #  Construção da interface
    # ══════════════════════════════════════════
    def _construir_ui(self) -> None:
        self._construir_barra_topo()
        self._construir_cards()
        self._construir_corpo()

    # ── Barra superior ─────────────────────────
    def _construir_barra_topo(self) -> None:
        barra = tk.Frame(self, bg=COR["bg_painel"], height=52)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        tk.Label(barra, text="📊  Dashboard — Servidor Chat TCP",
                 font=("Segoe UI", 13, "bold"),
                 bg=COR["bg_painel"], fg=COR["texto"]).pack(side="left", padx=16)

        tk.Label(barra, text=f"{self.host}:{self.porta}",
                 font=("Consolas", 10),
                 bg=COR["bg_painel"], fg=COR["texto_dim"]).pack(side="left", padx=(0, 16))

        self.lbl_uptime = tk.Label(barra, text="Uptime: 00:00:00",
                                    font=("Segoe UI", 9),
                                    bg=COR["bg_painel"], fg=COR["texto_dim"])
        self.lbl_uptime.pack(side="right", padx=16)

        self.lbl_status = tk.Label(barra, text="● iniciando...",
                                    font=("Segoe UI", 9, "bold"),
                                    bg=COR["bg_painel"], fg=COR["sistema"])
        self.lbl_status.pack(side="right", padx=(0, 4))

    # ── Cards de estatísticas ──────────────────
    def _construir_cards(self) -> None:
        frame = tk.Frame(self, bg=COR["bg"])
        frame.pack(fill="x", padx=10, pady=10)

        especificacoes = [
            ("ativos",    "Conexões ativas",       COR["online"]),
            ("total",     "Total de conexões",     COR["acento"]),
            ("mensagens", "Mensagens processadas", COR["servidor"]),
            ("falhas",    "Tentativas falhas",     COR["erro"]),
        ]

        self.cards: dict[str, tk.Label] = {}
        for chave, titulo, cor in especificacoes:
            card = tk.Frame(frame, bg=COR["bg_painel"],
                            highlightthickness=1, highlightbackground=COR["borda"])
            card.pack(side="left", expand=True, fill="both", padx=6)

            tk.Label(card, text=titulo, font=("Segoe UI", 9),
                     bg=COR["bg_painel"], fg=COR["texto_dim"]
                     ).pack(anchor="w", padx=12, pady=(10, 0))

            lbl_valor = tk.Label(card, text="0", font=("Segoe UI", 22, "bold"),
                                  bg=COR["bg_painel"], fg=cor)
            lbl_valor.pack(anchor="w", padx=12, pady=(0, 10))
            self.cards[chave] = lbl_valor

    # ── Corpo: tabela de usuários + log ────────
    def _construir_corpo(self) -> None:
        corpo = tk.Frame(self, bg=COR["bg"])
        corpo.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._construir_painel_usuarios(corpo)
        self._construir_painel_log(corpo)

    def _construir_painel_usuarios(self, pai: tk.Frame) -> None:
        painel = tk.Frame(pai, bg=COR["bg_painel"])
        painel.pack(side="left", fill="both", expand=True, padx=(0, 6))

        tk.Label(painel, text="Usuários conectados",
                 font=("Segoe UI", 10, "bold"),
                 bg=COR["bg_painel"], fg=COR["texto"]
                 ).pack(anchor="w", padx=10, pady=(8, 4))

        self._configurar_estilo_treeview()

        colunas = ("usuario", "endereco", "desde", "duracao")
        self.tabela = ttk.Treeview(painel, columns=colunas, show="headings", height=14)
        for col, titulo, largura in [
            ("usuario",  "Usuário",         140),
            ("endereco", "Endereço",        160),
            ("desde",    "Conectado desde", 120),
            ("duracao",  "Duração",         100),
        ]:
            self.tabela.heading(col, text=titulo)
            self.tabela.column(col, width=largura, anchor="center")
        self.tabela.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _construir_painel_log(self, pai: tk.Frame) -> None:
        painel = tk.Frame(pai, bg=COR["bg_painel"])
        painel.pack(side="left", fill="both", expand=True, padx=(6, 0))

        topo = tk.Frame(painel, bg=COR["bg_painel"])
        topo.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(topo, text="Atividade do servidor",
                 font=("Segoe UI", 10, "bold"),
                 bg=COR["bg_painel"], fg=COR["texto"]).pack(side="left")

        self.filtros: dict[str, tk.Button] = {}
        for nivel, cor in [("TUDO", COR["texto"]), ("INFO", COR["servidor"]),
                           ("WARNING", COR["sistema"]), ("ERROR", COR["erro"])]:
            btn = tk.Button(
                topo, text=nivel, font=("Segoe UI", 8),
                bg=COR["bg_entrada"], fg=cor,
                activebackground=COR["borda"], relief="flat",
                cursor="hand2", padx=8, pady=2,
                command=lambda n=nivel: self._filtrar_log(n),
            )
            btn.pack(side="right", padx=2)
            self.filtros[nivel] = btn
        self.filtros["TUDO"].configure(relief="sunken")

        self.area_log = scrolledtext.ScrolledText(
            painel, bg=COR["bg"], fg=COR["texto"],
            font=("Consolas", 9), relief="flat", bd=0,
            state="disabled", wrap="word",
        )
        self.area_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # tags de cor por nível
        self.area_log.tag_configure("INFO",    foreground=COR["servidor"])
        self.area_log.tag_configure("WARNING", foreground=COR["sistema"])
        self.area_log.tag_configure("ERROR",   foreground=COR["erro"])
        self.area_log.tag_configure("ts",      foreground=COR["texto_dim"], font=("Consolas", 8))

    def _configurar_estilo_treeview(self) -> None:
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure(
            "Treeview",
            background=COR["bg_painel"], fieldbackground=COR["bg_painel"],
            foreground=COR["texto"], rowheight=26,
            font=("Consolas", 10), borderwidth=0,
        )
        estilo.configure(
            "Treeview.Heading",
            background=COR["bg_entrada"], foreground=COR["texto_dim"],
            font=("Segoe UI", 9, "bold"), relief="flat",
        )
        estilo.map(
            "Treeview",
            background=[("selected", COR["borda"])],
            foreground=[("selected", COR["texto"])],
        )

    # ══════════════════════════════════════════
    #  Logging
    # ══════════════════════════════════════════
    def _registrar_handler_log(self) -> None:
        """Conecta-se ao logger 'servidor' já existente, sem alterar os
        handlers de arquivo/console que ele já possui."""
        handler = QueueHandler(self.fila_logs)
        handler.setLevel(logging.INFO)
        log.addHandler(handler)

    # ══════════════════════════════════════════
    #  Inicialização do servidor (thread separada)
    # ══════════════════════════════════════════
    def _iniciar_servidor(self) -> None:
        self.servidor = servidor_app()

        def _executar() -> None:
            try:
                self.after(0, lambda: self.lbl_status.configure(
                    text="● online", fg=COR["online"]))
                self.servidor.iniciar(self.host, self.porta)
            except OSError as e:
                msg = str(e)
                self.after(0, lambda: self.lbl_status.configure(
                    text=f"● erro ao iniciar ({msg})", fg=COR["erro"]))

        threading.Thread(target=_executar, daemon=True).start()

    # ══════════════════════════════════════════
    #  Loop de atualização periódica
    # ══════════════════════════════════════════
    def _loop_atualizacao(self) -> None:
        self._processar_fila_log()
        self._atualizar_tabela_usuarios()
        self._atualizar_uptime()
        self.after(500, self._loop_atualizacao)

    # ── Processa novas entradas de log ─────────
    def _processar_fila_log(self) -> None:
        while not self.fila_logs.empty():
            record = self.fila_logs.get_nowait()
            msg = record.getMessage()

            if "NOVA_CONEXAO" in msg:
                self.total_conexoes += 1
            elif "MSG_RECEBIDA" in msg:
                self.mensagens_processadas += 1
            elif "AUTH_FALHOU" in msg:
                self.falhas_login += 1

            self._inserir_log(record, msg)

        self.cards["ativos"].configure(text=str(len(sessoes_ativas)))
        self.cards["total"].configure(text=str(self.total_conexoes))
        self.cards["mensagens"].configure(text=str(self.mensagens_processadas))
        self.cards["falhas"].configure(text=str(self.falhas_login))

    def _inserir_log(self, record: logging.LogRecord, msg: str) -> None:
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        nivel = record.levelname if record.levelname in ("INFO", "WARNING", "ERROR") else "INFO"
        linha_tag = f"linha_{nivel}"

        self.area_log.configure(state="normal")
        inicio = self.area_log.index("end-1c")
        self.area_log.insert("end", f"[{ts}] ", "ts")
        self.area_log.insert("end", f"{msg}\n", nivel)
        fim = self.area_log.index("end-1c")
        self.area_log.tag_add(linha_tag, inicio, fim)
        self.area_log.configure(state="disabled")
        self.area_log.see("end")

    # ── Filtro de nível de log ──────────────────
    def _filtrar_log(self, nivel: str) -> None:
        self.filtro_atual = nivel
        for n in ("INFO", "WARNING", "ERROR"):
            oculto = nivel != "TUDO" and nivel != n
            self.area_log.tag_configure(f"linha_{n}", elide=oculto)

        for n, btn in self.filtros.items():
            btn.configure(relief="sunken" if n == nivel else "flat")

    # ══════════════════════════════════════════
    #  Tabela de usuários conectados
    # ══════════════════════════════════════════
    def _atualizar_tabela_usuarios(self) -> None:
        with lock_sessoes:
            atuais = dict(sessoes_ativas)

        agora = datetime.now()

        # remove quem desconectou
        for usuario in list(self.usuarios_desde):
            if usuario not in atuais:
                del self.usuarios_desde[usuario]

        # registra horário de entrada de quem conectou agora
        for usuario in atuais:
            if usuario not in self.usuarios_desde:
                self.usuarios_desde[usuario] = agora

        self.tabela.delete(*self.tabela.get_children())
        for usuario, endereco in atuais.items():
            desde = self.usuarios_desde[usuario]
            duracao = agora - desde
            self.tabela.insert("", "end", values=(
                usuario,
                f"{endereco[0]}:{endereco[1]}",
                desde.strftime("%H:%M:%S"),
                str(timedelta(seconds=int(duracao.total_seconds()))),
            ))

    # ══════════════════════════════════════════
    #  Uptime
    # ══════════════════════════════════════════
    def _atualizar_uptime(self) -> None:
        delta = datetime.now() - self.inicio
        self.lbl_uptime.configure(
            text=f"Uptime: {timedelta(seconds=int(delta.total_seconds()))}"
        )

    # ══════════════════════════════════════════
    #  Encerramento
    # ══════════════════════════════════════════
    def _ao_fechar(self) -> None:
        try:
            self.servidor.sock.close()
        except OSError:
            pass
        self.destroy()

    def _centralizar(self, w: int, h: int) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


if __name__ == "__main__":
    DashboardApp(host="", porta=5000).mainloop()
