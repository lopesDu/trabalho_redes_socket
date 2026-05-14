from reportlab.lib.pagesizes import legal

import servidor.App.servidor_app
import socket
from servidor.App.servidor_app import servidor_app

if __name__ == '__main__':

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(('localhost', 12381))
    servidor.listen(5)
    msg = b"resposta do servidor"
    conn, addr = servidor.accept()
    cliente = servidor_app(sock=conn)  # passa o socket já existente
    dados = cliente.receive(8)
    cliente.send(msg, len(msg))
    print(dados)