import socket
from servidor.App.servidor_app import servidor_app

if __name__ == '__main__':
    cliente = servidor_app()

    try:
        cliente.sock.connect(('172.22.70.2', 5000))
        print("[*] Conectado ao servidor.")

        # ── Etapa 1: Login ───────────────────
        solicitacao = cliente.receive().decode()   # recebe "USUARIO:"
        print(f"[?] {solicitacao}")
        username = input("Usuario: ")
        cliente.send(username.encode())

        solicitacao = cliente.receive().decode()   # recebe "SENHA:"
        print(f"[?] {solicitacao}")
        senha = input("Senha: ")
        cliente.send(senha.encode())

        resposta_login = cliente.receive().decode()
        print(f"[*] {resposta_login}")

        # Encerra se login falhou
        if not resposta_login.startswith("LOGIN_OK"):
            raise RuntimeError(resposta_login)

        # ── Etapa 2: Comunicação ─────────────
        while True:
            msg = input("[Você]: ")
            if msg.lower() == "sair":
                break

            cliente.send(msg.encode())
            resposta = cliente.receive()
            print(f"[Servidor]: {resposta.decode()}")

    except ConnectionRefusedError:
        print("[x] Conexão recusada. O servidor está online?")
    except RuntimeError as e:
        print(f"[!] Erro: {e}")
    except OSError as e:
        print(f"[x] Erro de socket: {e}")
    finally:
        cliente.sock.close()
        print("[*] Conexão encerrada.")