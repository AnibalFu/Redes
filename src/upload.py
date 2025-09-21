import sys

from socket import socket, AF_INET, SOCK_DGRAM
from lib.protocolo_amcgf import *
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

def upload(client: Client):
    with open(client.src, "rb") as f:
        contenido = f.read()
    request_upload(client.name, contenido, client.host, client.port)

def request_upload(filename: str, content: bytes, host: str, port: int):
    SERVER = (host, port)
    BUF = 4096

    ctrl = socket(AF_INET, SOCK_DGRAM)

    # 1. HELLO
    hello = make_hello(proto="SW")
    ctrl.sendto(hello.encode(), SERVER)
    ans, _ = ctrl.recvfrom(BUF)
    resp = Datagrama.decode(ans)
    assert resp.typ == MsgType.HELLO, "Esperaba HELLO ACK"
    print("Recibido HELLO ACK")

    # 2. UPLOAD
    req = make_req_upload(filename, 0, VER_SW)  # El campo data puede ser 0 o vacío, solo nombre
    ctrl.sendto(req.encode(), SERVER)
    ans, _ = ctrl.recvfrom(BUF)
    resp = Datagrama.decode(ans)
    assert resp.typ == MsgType.OK, "Esperaba OK tras UPLOAD"
    print("Recibido OK para UPLOAD")

    # 3. Empieza la transferencia de datos
    # (podemos negociar el puerto aca si queremos)
    seq = 0
    chunk = 6
    for i in range(0, len(content), chunk):
        payload = content[i:i+chunk]
        mf = (i + chunk) < len(content)
        datagrama = make_data(seq=seq, chunk=payload, ver=VER_SW, mf=mf)
        ctrl.sendto(datagrama.encode(), SERVER)
        # Espera ACK antes de enviar el siguiente
        data, sender_address = ctrl.recvfrom(4096)
        datagram = Datagrama.decode(data)
        assert datagram.typ == MsgType.ACK, "Esperaba ACK tras DATA"
        seq += 1
        print(datagram.pretty_print())

    # FIN
    bye = make_bye(VER_SW)
    ctrl.sendto(bye.encode(), SERVER)
    ans, _ = ctrl.recvfrom(BUF)
    resp = Datagrama.decode(ans)
    assert resp.typ == MsgType.OK, "Esperaba OK tras BYE"
    print("Transferencia finalizada correctamente")
    ctrl.close()

if __name__ == '__main__':
    args = split(sys.argv)
    client = process_args(args)
    upload(client=client)