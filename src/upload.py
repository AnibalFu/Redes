from socket import socket, AF_INET, SOCK_DGRAM
from argparse import ArgumentParser, RawDescriptionHelpFormatter, Namespace

from lib.datagram_sending import send_bye, send_request
from lib.protocolo_amcgf import *
from lib.client import Client

MSS = 32
BUF = 16

def define_flags():
    """Define command line flags."""
    
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
    """Process command line arguments and return a configured Client instance."""

    client = Client()

    client.verbose = args.verbose
    client.quiet = args.quiet
    client.host = args.host if args.host else client.host
    client.port = args.port if args.port else client.port
    client.src = args.src if args.src else client.src
    client.name = args.name if args.name else client.name
    client.protocol = args.protocol if args.protocol else client.protocol    

    return client

def upload_file(path: str, addr: tuple[str, int], chunk_size: int = MSS):
    transfer_socket = socket(AF_INET, SOCK_DGRAM)
    seq_number = 0
    
    with open(path, "rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            
            more_fragments = file.peek(1) != b'' if hasattr(file, 'peek') else True  # MF si hay más datos
            
            try:
                encoded = make_data(seq=seq_number, chunk=chunk, ver=VER_SW, mf=more_fragments).encode()
            except Exception:
                raise

            ack_ok = False
            while not ack_ok:
                transfer_socket.sendto(encoded, addr)
                
                try:
                    data, _ = transfer_socket.recvfrom(BUF)
                    
                    try:
                        datagram = Datagrama.decode(data)
                    except Exception:
                        raise
                    
                    if datagram.typ == MsgType.ACK and datagram.ack == seq_number + 1:
                        print(f"ACK correcto recibido: {datagram}")
                        ack_ok = True
                    else:
                        print(f"ACK incorrecto (esperaba {seq_number+1}), reenviando DATA seq {seq_number}")
                
                except TimeoutError:
                    print(f"Timeout esperando ACK para seq {seq_number}, reenviando DATA")
            
            seq_number += 1

    try:
        send_bye(transfer_socket, addr, BUF)
    except Exception as e:
        print(f"Error: Error during BYE: {e}")
    finally:
        transfer_socket.close()

def upload(client: Client):
    SERVER = (client.host, client.port)
    
    req_socket = socket(AF_INET, SOCK_DGRAM)

    try:
        addr = send_request(make_request=make_req_upload, sender_socket=req_socket, addr=SERVER, client=client)
    except Exception as e:
        print(f"Error: Error during REQUEST_UPLOAD: {e}")
        req_socket.close()
        return

    upload_file(path=client.src + client.name, addr=addr)
    req_socket.close()

if __name__ == '__main__':
    parser = define_flags()
    args = parser.parse_args()

    upload(client=process_args(args))