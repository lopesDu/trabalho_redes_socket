import socket
import threading
from servidor.App.servidor_app import servidor_app

if __name__ == '__main__':
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(('localhost', 12381))
    servidor.listen(5)
    print("Servidor aguardando conexões...")

    app = servidor_app()  #cria uma instancia do servidor

    while True:
        conn, addr = servidor.accept()
        thread = threading.Thread(target=app.listen_multiclient, args=(conn, addr))
        thread.daemon = True
        thread.start()
        print(f"[Threads ativas]: {threading.active_count() - 1}")