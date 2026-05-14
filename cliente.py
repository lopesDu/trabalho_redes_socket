import socket
from tkinter import messagebox, Tk

try:
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    cliente.connect(("localhost", 12381))

    data_recebida = cliente.recv(1024).decode()

    cliente.close()

    janela = Tk()
    janela.withdraw()

    messagebox.showinfo(
        "Mensagem",
        f"Data recebida do servidor: {data_recebida}"
    )

    print("Conexão encerrada")

except Exception as erro:
    print("Erro:", erro)