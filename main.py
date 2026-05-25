import threading
import servidor.App.servidor_app
import socket

if __name__ == '__main__':
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # evita "porta em uso"
    servidor.bind(('localhost', 12381))
    servidor.listen(5)
    print("Servidor aguardando conexões...")

    while True:
        conn, addr = servidor.accept()  # bloqueia até um cliente conectar

        # Cria uma thread exclusiva para esse cliente
        thread = threading.Thread(target=listen_multiclient, args=(conn, addr))
        thread.daemon = True  # encerra junto com o programa principal
        thread.start()

        print(f"[Threads ativas]: {threading.active_count() - 1}")