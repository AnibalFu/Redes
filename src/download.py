import sys

from lib.client import Client
from lib.flags import USER_FLAGS
from lib.utils import split

def process_args(args: list[str]):
    client = Client()
    
    for arg in args:
        try:
            (flag, body) = arg.split(' ', maxsplit=2)
        except ValueError:
            flag = arg
            body = None

        function = USER_FLAGS.get(flag)

        if function:
            function(flag=flag, body=body, entity=client)
        else:
            print(f'Warning: Bad Flag {flag}')

    return client

if __name__ == '__main__':
    args = split(sys.argv)

    client = process_args(args)

    print(client)
    
    
    
"""
from socket import *
import time

SERVER = ("127.0.0.1", 12000)
BUF = 1500

def request_download(filename: str):
    # 1) Control
    ctrl = socket(AF_INET, SOCK_DGRAM)
    ctrl.sendto(f"DOWNLOAD {filename}".encode(), SERVER)
    ans, addr = ctrl.recvfrom(BUF)
    ctrl.close()

    tag, port_str = ans.decode().split()
    assert tag == "DATA_PORT"
    data_port = int(port_str)
    
    # 2) Datos: nuevo socket hacia el puerto dedicado
    data_sock = socket(AF_INET, SOCK_DGRAM)
    data_sock.connect((SERVER[0], data_port))

    # Handshake de llegada
    data_sock.send(b"HELLO_DATA")
    ok = data_sock.recv(BUF)
    assert ok == b"SESSION_OK"

    # Recibir archivo
    chunks = []
    while True:
        pkt = data_sock.recv(BUF)
        if pkt == b"FIN":
            break
        chunks.append(pkt)

    data = b"".join(chunks)
    print("Descargado:", len(data), "bytes", data)

def request_upload(filename: str, content: bytes):
    ctrl = socket(AF_INET, SOCK_DGRAM)
    ctrl.sendto(f"UPLOAD {filename}".encode(), SERVER)
    ans, _ = ctrl.recvfrom(BUF)
    ctrl.close()

    tag, port_str = ans.decode().split()
    assert tag == "DATA_PORT"
    data_port = int(port_str)

    data_sock = socket(AF_INET, SOCK_DGRAM)
    data_sock.connect((SERVER[0], data_port))

    data_sock.send(b"HELLO_DATA")
    ok = data_sock.recv(BUF)
    assert ok == b"SESSION_OK"

    # Enviar contenido en chunks
    chunk = 1200
    for i in range(0, len(content), chunk):
        data_sock.send(content[i:i+chunk])
        # acá podés meter tu ARQ (seq/ack/timeout) si querés confiabilidad
    data_sock.send(b"FIN")
    resp = data_sock.recv(BUF)
    print("Servidor dice:", resp.decode())

if __name__ == "__main__":
    request_download("demo.txt")
    request_upload("subida.bin", b"A"*5000)

"""