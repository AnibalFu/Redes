from socket import socket, AF_INET, SOCK_DGRAM
from argparse import ArgumentParser, RawDescriptionHelpFormatter, Namespace

from lib.datagram_sending import finalizar_conexion
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

# Por ahora representa el protocolo SW con numero de secuencia cotinuo
def request_upload(filename: str, src_path: str, host: str, port: int):
    chunk_size = (MSS - 1) // 2 # // por que el payload es bytes crudos
    
    print(f"[DEBUG] Chunk size: {chunk_size}")
    ctrl = socket(AF_INET, SOCK_DGRAM)
    
    # Set timeout para recibir respuesta en 1 segundos
    ctrl.settimeout(1)
   
    
    # REQUEST_UPLOAD = handshake con el servidor
    request = make_req_upload(filename, VER_SW)
    print(f"[DEBUG] Enviado REQUEST_UPLOAD para {request}")
    ctrl.sendto(request.encode(), (host, port))

    # Espera OK desde el nuevo puerto
    data, connection_addr = ctrl.recvfrom(MTU)
    
    datagrama = Datagrama.decode(data)
    if datagrama.typ != MsgType.OK or datagrama.typ == MsgType.ERR:
        print(f"[ERROR] Error: {datagrama.payload.decode()[PAYLOAD_ERR_MSG_KEY]}")
        ctrl.close()
        return

    print(f"[DEBUG] Recibido OK para UPLOAD, nueva dirección: {connection_addr}")

    # Transferencia de datos por la nueva dirección, leyendo por partes
    seq = 0
    with open(src_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            mf = f.peek(1) != b''  # MF si hay más datos
            
            datagrama = make_data(seq=seq, chunk=chunk, ver=VER_SW, mf=mf)
            print(f"[DEBUG] {datagrama}")
            encoded = datagrama.encode()
            
            # Espero recibir ACK que espero seq+1
            ack_ok = False
            while not ack_ok:
                ctrl.sendto(encoded, connection_addr)
                print(f"[DEBUG] Enviado DATA con seq {seq}, MF={mf}")
                
                try:
                    data, _connection_addr = ctrl.recvfrom(MTU)
                    datagram = Datagrama.decode(data)
                    
                    if datagram.typ == MsgType.ACK and datagram.ack == seq + 1:
                        print(f"[DEBUG] ACK correcto recibido: {datagram}")
                        ack_ok = True
                        
                    else:
                        print(f"[DEBUG] ACK incorrecto (esperaba {seq+1}), reenviando DATA seq {seq}")
                        
                except TimeoutError:
                    print(f"[DEBUG] Timeout esperando ACK para seq {seq}, reenviando DATA")

                print(f"-------------------------" * 3)
            # Incremento seq
            seq += 1

    # FIN
    finalizar_conexion(ctrl, connection_addr)


def upload(client: Client):
    request_upload(client.name, client.src, client.host, client.port)

if __name__ == '__main__':

    parser = define_flags()
    args = parser.parse_args()

    client = process_args(args)
    upload(client=client)