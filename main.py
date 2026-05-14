import servidor.App.servidor_app
import socket
from servidor.App.servidor_app import servidor_app

if __name__ == '__main__':

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("0.0.0.0", 8080))
    servidor.listen(5)

    conn, addr = servidor.accept()
    cliente = servidor_app(sock=conn)  # passa o socket já existente
    dados = cliente.receive(1024)
    cliente.send(b"resposta", 1024)