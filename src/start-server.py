from asyncio.trsock import _RetAddress
import sys
import threading
import random

from socket import socket, AF_INET, SOCK_DGRAM
from signal import SIGINT, signal
from types import FrameType
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from lib.datagram_sending import send_content
from lib.server import Server
from lib.protocolo_amcgf import *

def sigint_handler(_: int, frame: FrameType | None):
    """Handle SIGINT for graceful shutdown."""

    server_socket = frame.f_locals['server_socket']
    try:
        server_socket.close()
    except:
        print(f'\nError: Socket {server_socket} could not be closed')
        sys.exit(-1)
    
    print('\nGraceful Exit')
    sys.exit(0)    

def define_flags():
    """Define command line flags."""

    parser = ArgumentParser(description='File server program', formatter_class=RawDescriptionHelpFormatter)
    
    parser.add_argument('-v', '--verbose', required=False, action='store_true', help='increase output verbosity')
    parser.add_argument('-q', '--quiet', required=False, action='store_true', help='decrease output verbosity')
    parser.add_argument('-H', '--host', required=False, type=str, metavar='HOST', help='server IP address')
    parser.add_argument('-p', '--port', required=False, type=int, metavar='PORT', help='server port')
    parser.add_argument('-s', '--storage', required=False, type=str, metavar='DIRPATH', help='destination file path')
    
    return parser

def process_args(args: Namespace):
    """Process command line arguments and return a configured Server instance."""

    server = Server()
    
    server.verbose = args.verbose
    server.quiet = args.quiet
    server.host = args.host if args.host else server.host
    server.port = args.port if args.port else server.port    
    server.storage = args.storage if args.storage else server.storage
    
    return server

def handle_upload(handle_socket: socket, client_addr: _RetAddress):
    ok = make_ok(ver=VER_SW)
    
    # Hay que ver que hacer en este caso de error.
    try:
        encoded = ok.encode()
    except Exception as e:
        print(f"Error: Error while trying to encode Datagram: {e}")
        return
    
    handle_socket.sendto(encoded, client_addr)
    print(f"Upload handler en puerto {handle_socket.getsockname()[1]} para {client_addr}")
    
    filedata = b""
    while True:
        data, client_addr = handle_socket.recvfrom(4096)

        # Hay que ver que hacer en este caso de error.
        try:
            datagram = Datagrama.decode(data)
        except Exception as e:
            print(f"Error: Error while trying to decode Datagram: {e}")
            return

        if datagram.typ == MsgType.DATA:
            filedata += datagram.payload
            ack = make_ack(acknum=datagram.seq + 1, ver=VER_SW)

            # Hay que ver que hacer en este caso de error.
            try:
                encoded = ack.encode()
            except Exception as e:
                print(f"Error: Error while trying to encode ACK Datagram: {e}")
                return

            handle_socket.sendto(encoded, client_addr)

            if not (datagram.flags & FLAG_MF):
                print("Archivo recibido completo, esperando BYE...")
        
        elif datagram.typ == MsgType.BYE:
            print("BYE recibido, guardando archivo y respondiendo OK")
            ok = make_ok(ver=VER_SW)

            # Hay que ver que hacer en este caso de error.
            try:
                encoded = ok.encode()
            except Exception as e:
                print(f"Error: Error while trying to encode OK Datagram: {e}")
                return

            handle_socket.sendto(encoded, client_addr)
            break
    
    print(filedata)
    handle_socket.close()

def handle_download(handle_socket: socket, client_addr: _RetAddress, filename: str):
    ok = make_ok(ver=VER_SW)

    try:
        encoded = ok.encode()
    except Exception as e:
        print(f"Error: Error while trying to encode Datagram: {e}")
        return

    handle_socket.sendto(encoded, client_addr)  # Enviar OK desde el nuevo socket
    
    print(f"Download handler en puerto {handle_socket.getsockname()[1]} para {client_addr}")
    with open(filename, "rb") as file:
        content = file.read()
    
    send_content(handle_socket, client_addr, content, chunk_size=6)
    
    handle_socket.close()

def run(server: Server):
    server_socket = socket(AF_INET, SOCK_DGRAM)
    server_socket.bind((server.host, server.port))
    
    print(f"Server listening at {server.host}:{server.port}")

    while True:
        data, client_addr = server_socket.recvfrom(4096)
        if len(data) < HDR_SIZE:
            print("Control message received:", data)
            continue
           
        try:
            datagram = Datagrama.decode(data)
        except Exception as e:
            raise

        if datagram.typ == MsgType.REQUEST_UPLOAD:
            handle_socket = socket(AF_INET, SOCK_DGRAM)
            handle_socket.bind(('', 0))
            
            threading.Thread(target=handle_upload, args=(handle_socket, client_addr), daemon=True).start()

        elif datagram.typ == MsgType.REQUEST_DOWNLOAD:
            filename = datagram.payload.decode().split('=', maxsplit=1)[1]
            
            handle_socket = socket(AF_INET, SOCK_DGRAM)
            handle_socket.bind(('', 0))

            threading.Thread(target=handle_download, args=(handle_socket, client_addr, filename), daemon=True).start()

if __name__ == '__main__':
    signal(SIGINT, sigint_handler)

    parser = define_flags()
    args = parser.parse_args()
    
    run(server=process_args(args))
