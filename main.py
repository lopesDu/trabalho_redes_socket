import socket
from servidor.App.servidor_app import servidor_app

if __name__ == '__main__':
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("localhost", 12381))
    servidor.listen(5)

    print("Aguardando conexao...")

    try:
        conn, addr = servidor.accept()
        print(f"Conectado a {addr}")

        cliente = servidor_app(sock=conn)
        msg = "Ola! Conexao estabelecida.".encode("utf-8")
        cliente.send(msg)  # sem msg_length

        conn.close()
        servidor.close()
        print("Servidor encerrado.")

    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuario.")
        servidor.close()