import socket
import struct
from tkinter import messagebox, Tk

try:
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cliente.connect(("localhost", 12381))

    # Lê os 4 bytes do prefixo para saber o tamanho da mensagem
    header = b''
    while len(header) < 4:
        parte = cliente.recv(4 - len(header))
        if parte == b'':
            raise RuntimeError("A conexão via socket caiu.")
        header += parte

    msg_length = struct.unpack('>I', header)[0]

    # Lê a mensagem completa
    data_recebida = b''
    while len(data_recebida) < msg_length:
        chunk = cliente.recv(min(msg_length - len(data_recebida), 2048))
        if chunk == b'':
            raise RuntimeError("A conexão via socket caiu.")
        data_recebida += chunk

    cliente.close()

    janela = Tk()
    janela.withdraw()

    messagebox.showinfo(
        "Mensagem",
        f"Data recebida do servidor: {data_recebida.decode('utf-8')}"
    )

    print("Conexão encerrada")

except Exception as erro:
    print("Erro:", erro)