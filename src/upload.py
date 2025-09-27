from socket import socket, AF_INET, SOCK_DGRAM
from argparse import ArgumentParser, RawDescriptionHelpFormatter, Namespace

from lib.datagram_sending import send_bye
from lib.protocolo_amcgf import *
from lib.client import Client

def define_flags():
    parser = ArgumentParser(description='Upload file program', formatter_class=RawDescriptionHelpFormatter)
    
    parser.add_argument('-v', '--verbose', required=False, action='store_true', help='increase output verbosity')
    parser.add_argument('-q', '--quiet', required=False, action='store_true', help='decrease output verbosity')
    parser.add_argument('-H', '--host', required=False, type=str, metavar='HOST', help='server IP address')
    parser.add_argument('-p', '--port', required=False, type=int, metavar='PORT', help='server port')
    parser.add_argument('-s', '--src', required=False, type=str, metavar='SRC', help='source file path')
    parser.add_argument('-n', '--name', required=False, type=str, metavar='FILENAME', help='file name')
    parser.add_argument('-r', '--protocol', required=False, type=str, metavar='PROTOCOL', help='error recovery protocol')

    return parser

def process_args(args: Namespace):
    client = Client()

    client.verbose = args.verbose
    client.quiet = args.quiet
    client.host = args.host if args.host else client.host
    client.port = args.port if args.port else client.port
    client.src = args.src if args.src else client.src
    client.name = args.name if args.name else client.name
    client.protocol = args.protocol if args.protocol else client.protocol    

    return client

def request_upload(filename: str, src_path: str, host: str, port: int, chunk_size=MSS):
    SERVER = (host, port)
    BUF = 16

    ctrl = socket(AF_INET, SOCK_DGRAM)

    # 1. REQUEST_UPLOAD directo
    request = make_req_upload(filename, 0, VER_SW)
    ctrl.sendto(request.encode(), SERVER)

    # 2. Espera OK desde el nuevo puerto y guarda la dirección
    data, new_server_addr = ctrl.recvfrom(BUF)
    datagrama = Datagrama.decode(data)
    if datagrama.typ != MsgType.OK:
        print("Error: no se recibió OK")
        ctrl.close()
        return

    print(f"Recibido OK para UPLOAD, nueva dirección: {new_server_addr}")

    # 3. Transferencia de datos por la nueva dirección, leyendo por partes
    # transfer_sock = socket(AF_INET, SOCK_DGRAM)
    seq = 0
    with open(src_path + "prueba.bin", "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            mf = f.peek(1) != b'' if hasattr(f, 'peek') else True  # MF si hay más datos
            datagrama = make_data(seq=seq, chunk=chunk, ver=VER_SW, mf=mf)
            encoded = datagrama.encode()
            ack_ok = False
            while not ack_ok:
                ctrl.sendto(encoded, new_server_addr)
                print(f"Enviado DATA con seq {seq}, MF={mf}")
                try:
                    data, _ = ctrl.recvfrom(BUF)
                    datagram = Datagrama.decode(data)
                    if datagram.typ == MsgType.ACK and datagram.ack == seq + 1:
                        print(f"ACK correcto recibido: {datagram}")
                        ack_ok = True
                    else:
                        print(f"ACK incorrecto (esperaba {seq+1}), reenviando DATA seq {seq}")
                except TimeoutError:
                    print(f"Timeout esperando ACK para seq {seq}, reenviando DATA")
            seq += 1

    # FIN
    send_bye(ctrl, new_server_addr, BUF)
    ctrl.close()


def upload(client: Client):
    request_upload(client.name, client.src, client.host, client.port)

if __name__ == '__main__':

    parser = define_flags()
    args = parser.parse_args()

    client = process_args(args)
    upload(client=client)