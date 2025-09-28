import sys
import threading

from socket import socket, AF_INET, SOCK_DGRAM
from signal import SIGINT, signal
from types import FrameType
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from lib.datagram_sending import send_content
from lib.server import Server   
from lib.protocolo_amcgf import *
from lib.fileHandler import FileHandler

def sigint_handler(_: int, frame: FrameType | None):
    server_socket = frame.f_locals['server_socket']
    try:
        server_socket.close()
    except:
        print(f'\nError: Socket {server_socket} could not be closed')
        sys.exit(-1)
    print('\nGraceful Exit')
    sys.exit(0)    

def define_flags():
    parser = ArgumentParser(description='File server program', formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-v', '--verbose', required=False, action='store_true', help='increase output verbosity')
    parser.add_argument('-q', '--quiet', required=False, action='store_true', help='decrease output verbosity')
    parser.add_argument('-H', '--host', required=False, type=str, metavar='HOST', help='server IP address')
    parser.add_argument('-p', '--port', required=False, type=int, metavar='PORT', help='server port')
    parser.add_argument('-s', '--storage', required=False, type=str, metavar='DIRPATH', help='destination file path')
    return parser

def process_args(args: Namespace):
    server = Server()
    server.verbose = args.verbose
    server.quiet = args.quiet
    server.host = args.host if args.host else server.host
    server.port = args.port if args.port else server.port    
    server.fileHandler = FileHandler(args.storage) if args.storage else server.fileHandler

    return server

def handle_upload(sock: socket, client_addr: tuple[str, int], fileHandler: FileHandler, filename: str):
    ok = make_ok(ver=VER_SW)
    sock.sendto(ok.encode(), client_addr)
    
    print(f"[DEBUG] Upload handler en puerto {sock.getsockname()[1]} para {client_addr}")
    
    while True:
        data, _client_addr = sock.recvfrom(MTU)
        
        # Si ocurre un error al decodificar el datagrama ignoro el paquete (simulo SW paquete corrupto)
        try:
            datagrama = Datagrama.decode(data)
            
        except (Truncated, BadChecksum) as e:
            print(f"[DEBUG] Error al decodificar datagrama: {e}")
            continue
        
        if datagrama.typ == MsgType.DATA:
            fileHandler.save_datagram(filename, datagrama, MSS-16)
            ack = make_ack(acknum=datagrama.seq + 1, ver=VER_SW)
            sock.sendto(ack.encode(), client_addr)
            
            if not (datagrama.flags & FLAG_MF):
                print("[DEBUG] Archivo recibido completo, esperando BYE...")
                
        elif datagrama.typ == MsgType.BYE:
            print(f"[DEBUG] BYE recibido, guardando archivo y respondiendo OK")
            ok = make_ok(ver=VER_SW)
            sock.sendto(ok.encode(), client_addr)
            break
        
    sock.close()

def handle_download(sock, client_addr, filename, fileHandler):
    ok = make_ok(ver=VER_SW)
    sock.sendto(ok.encode(), client_addr)  # Enviar OK desde el nuevo socket
    print(f"[DEBUG] Download handler en puerto {sock.getsockname()[1]} para {client_addr}")
    content = fileHandler.get_file(filename)  
    send_content(sock, client_addr, content, chunk_size=MSS)
    sock.close()

def run(server: Server):
    """
    Ejecuta el servidor principal
    """
    server_socket = socket(AF_INET, SOCK_DGRAM)
    server_socket.bind((server.host, server.port))
    print(f"Servidor escuchando en {server.host}:{server.port}")

    while True:
        data, sender_address = server_socket.recvfrom(MTU)
        if len(data) < HDR_SIZE:
            print("[DEBUG] Mensaje de control recibido:", data)
            continue

        try:
            datagrama = Datagrama.decode(data)
        except Exception as e:
            err = make_err("Error al decodificar datagrama")
            server_socket.sendto(err.encode(), sender_address)
            print(f"[DEBUG] Error al decodificar datagrama: {e}")
            continue
        
        # Tipos de mensajes aceptados de cliente
        if datagrama.typ == MsgType.REQUEST_UPLOAD:
            data = payload_decode(datagrama.payload)
            print(f"[DEBUG] UPLOAD recibido de {sender_address} data: {data}")
            filename = data[PAYLOAD_FILENAME_KEY]
            sock = socket(AF_INET, SOCK_DGRAM)
            sock.bind(('', 0))  # Puerto libre asignado por el SO
            threading.Thread(target=handle_upload, args=(sock, sender_address, server.fileHandler, filename), daemon=True).start()


        elif datagrama.typ == MsgType.REQUEST_DOWNLOAD:
            data = payload_decode(datagrama.payload)
            print(f"[DEBUG] DOWNLOAD recibido de {sender_address} data: {data}")
            filename = data[PAYLOAD_FILENAME_KEY]
            print(f"[DEBUG] Filename: {filename}")
            sock = socket(AF_INET, SOCK_DGRAM)
            sock.bind(('', 0))  # Puerto libre asignado por el SO
            threading.Thread(target=handle_download, args=(sock, sender_address, filename, server.fileHandler), daemon=True).start()

    # server_socket.close()


if __name__ == '__main__':
    signal(SIGINT, sigint_handler)
    parser = define_flags()
    args = parser.parse_args()
    server = process_args(args)
    run(server=server)
