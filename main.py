import socket
from servidor.App.servidor_app import servidor_app
if __name__ == '__main__':
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("localhost", 12381))
    servidor.listen(5)

    print("Aguardando conexão...")
    conn, addr = servidor.accept()
    print(f"Conectado a {addr}")

    cliente = servidor_app(sock=conn)
    msg = b"Ola! Conexao estabelecida."
    cliente.send(msg, len(msg))


    conn.close()
    servidor.close()