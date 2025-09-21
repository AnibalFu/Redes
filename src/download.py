import sys

from socket import socket, AF_INET, SOCK_DGRAM
import time
from lib.client import Client
from lib.datagram_sending import send_bye, send_hello, send_request
from lib.flags import USER_FLAGS
from lib.protocolo_amcgf import FLAG_MF, VER_SW, Datagrama, MsgType, make_ack, make_bye, make_hello, make_req_download
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

def download(client: Client):
    request_download(client.name, client.host, client.port)

def request_download(filename: str, host: str, port: int):
    print(f"Solicitando descarga de '{filename}' desde {host}:{port}")

    SERVER = (host, port)
    BUF = 4096

    ctrl = socket(AF_INET, SOCK_DGRAM)

    # 1. HELLO
    send_hello(ctrl, SERVER, BUF)

    # 2. DOWNLOAD
    send_request(make_req_download, ctrl, SERVER, filename)
    print("Recibido OK para DOWNLOAD")

    # 3. Empieza a llegar la transferencia de datos
    # (podemos negociar el puerto aca si queremos)
    receive_content(ctrl, SERVER)

    # FIN
    send_bye(ctrl, SERVER, BUF)
    ctrl.close()

def receive_content(ctrl, SERVER):
    expected_seq = 0
    while True:
        print("Por recibir...")
        data, _ = ctrl.recvfrom(4096)
        # sender = (SERVER[0], sender_address[1]), cuando tengamos la concurrencia
        try:
            datagrama = Datagrama.decode(data)
        except Exception as e:
            print(f"Error al decodificar datagrama: {e}")
            continue

        if datagrama.typ == MsgType.DATA:
            if expected_seq == 0:
                expected_seq = datagrama.seq
            data = datagrama.payload
            print(f"Recibido {data}")
            print(f"Recibido DATA con seq {datagrama.seq}")
            # Enviar ACK
            ack = make_ack(acknum=expected_seq + 1, ver=VER_SW)
            ctrl.sendto(ack.encode(), SERVER)
            print(f"Enviado ACK {expected_seq + 1}")
            if not (datagrama.flags & FLAG_MF):
                print("Archivo recibido completo")
                break
            if datagrama.seq == expected_seq:
                expected_seq += 1

        else:
            print(f"Mensaje inesperado: {datagrama.pretty_print()}")
            continue


if __name__ == "__main__":
    args = split(sys.argv)
    client = process_args(args)
    download(client=client)
