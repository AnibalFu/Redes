
from asyncio.trsock import _RetAddress
from socket import socket, AF_INET, SOCK_DGRAM
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from lib.client import Client
from lib.datagram_sending import send_bye, send_hello, send_request
from lib.protocolo_amcgf import FLAG_MF, VER_SW, Datagrama, MsgType, make_ack, make_req_download

BUF = 4096

def define_flags():
    """Define command line flags for the download client."""
    
    parser = ArgumentParser(description='Download file program', formatter_class=RawDescriptionHelpFormatter)

    parser.add_argument('-v', '--verbose', required=False, action='store_true', help='increase output verbosity')
    parser.add_argument('-q', '--quiet', required=False, action='store_true', help='decrease output verbosity')
    parser.add_argument('-H', '--host', required=False, type=str, metavar='HOST', help='server IP address')
    parser.add_argument('-p', '--port', required=False, type=int, metavar='PORT', help='server port')
    parser.add_argument('-d', '--dest', required=False, type=str, metavar='FILEPATH', help='destination file path')
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
    client.src = args.dest if args.dest else client.src
    client.name = args.name if args.name else client.name
    client.protocol = args.protocol if args.protocol else client.protocol

    return client

def download_file(addr: _RetAddress, src: str):
    transfer_socket = socket(AF_INET, SOCK_DGRAM)
    expected_seq = 0
    
    while True:
        data, _ = transfer_socket.recvfrom(BUF)
        # sender = (SERVER[0], sender_address[1]), cuando tengamos la concurrencia
        
        try:
            datagram = Datagrama.decode(data)
        except Exception:
            raise

        if datagram.typ == MsgType.DATA:
            if expected_seq == 0:
                expected_seq = datagram.seq

            payload = datagram.payload
            with open(src, "ab") as file:
                file.write(payload)
            
            try:
                encoded = make_ack(acknum=expected_seq + 1, ver=VER_SW).encode()
            except Exception:
                raise
            
            transfer_socket.sendto(encoded, addr)

            if not (datagram.flags & FLAG_MF):
                print("Archivo recibido completo")
                break
            if datagram.seq == expected_seq:
                expected_seq += 1

        else:
            print(f"Mensaje inesperado: {datagram.pretty_print()}")
            continue

    try:
        send_bye(transfer_socket, addr, BUF)
    except Exception:
        raise
    finally:
        transfer_socket.close()

def download(client: Client):
    SERVER = (client.host, client.port)
    
    req_socket = socket(AF_INET, SOCK_DGRAM)

    try:
        send_hello(sender_socket=req_socket, addr=SERVER, bufsize=BUF, proto=client.protocol)
    except Exception as e:
        print(f"Error: Error during HELLO: {e}")
        req_socket.close()
        return

    try:
        addr = send_request(make_request=make_req_download, sender_socket=req_socket, addr=SERVER, filename=client.name)
    except Exception as e:
        print(f"Error: Error during REQUEST_DOWNLOAD: {e}")
        req_socket.close()
        return

    download_file(addr=addr, src=client.src)
    req_socket.close()

if __name__ == "__main__":
    parser = define_flags()
    args = parser.parse_args()
        
    download(client=process_args(args))
