from socket import socket, AF_INET, SOCK_DGRAM
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from lib.client import Client
from lib.fileHandler import FileHandler
from lib.datagram_sending import finalizar_conexion, send_request
from lib.protocolo_amcgf import FLAG_MF, VER_SW, Datagrama, MsgType, make_ack, make_req_download, MTU, MSS

def define_flags():
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
    client = Client()
    
    client.verbose = args.verbose
    client.quiet = args.quiet
    client.host = args.host if args.host else client.host
    client.port = args.port if args.port else client.port
    client.src = args.dest if args.dest else client.src
    client.name = args.name if args.name else client.name
    client.protocol = args.protocol if args.protocol else client.protocol

    return client

def download(client: Client):
    # -d es el directorio destino local; -n es el nombre del archivo remoto.
    # Guardaremos el archivo con el mismo nombre en el directorio destino.
    dest_dir = client.src
    dest_filename = client.name
    fileHandler = FileHandler(dest_dir)
    request_download(dest_filename, client.host, client.port, fileHandler)

def request_download(filename: str, host: str, port: int, fileHandler: FileHandler):
    print(f"[DEBUG] Solicitando descarga de '{filename}' desde {host}:{port}")

    ctrl = socket(AF_INET, SOCK_DGRAM)

    # Server me responde por el nuevo socket
    download_conection = send_request(make_req_download, ctrl, (host, port), filename)
    print("[DEBUG] Recibido OK para DOWNLOAD")
    print(f"[DEBUG] Socket: {ctrl}")
    print(f"[DEBUG] Nueva dirección: {download_conection}")
    
    receive_content(ctrl, download_conection, fileHandler, filename)

    # FIN
    finalizar_conexion(ctrl, download_conection)
    ctrl.close()

def receive_content(ctrl, download_conection, fileHandler: FileHandler, filename: str):
    expected_seq = 0
    while True:
        print("[DEBUG] Por recibir...")
        data, _download_conection = ctrl.recvfrom(MTU)
        
        try:
            datagrama = Datagrama.decode(data)
            
        except Exception as e:
            print(f"[DEBUG] Error al decodificar datagrama: {e}")
            continue

        if datagrama.typ == MsgType.DATA:
            if datagrama.seq != expected_seq:
                # Fuera de orden para SW no debería ocurrir; re-ACK del último válido
                ack = make_ack(acknum=expected_seq, ver=VER_SW)
                ctrl.sendto(ack.encode(), download_conection)
                print(f"[DEBUG] Fuera de orden: esperado {expected_seq}, recibido {datagrama.seq}. Reenviado ACK {expected_seq}")
                continue

            data_chunk = datagrama.payload
            print(f"[DEBUG] Recibido {len(data_chunk)} bytes")
            print(f"[DEBUG] Recibido DATA con seq {datagrama.seq}")
            
            # Guardar chunk en la posición correcta (offset = seq * MSS)
            fileHandler.save_datagram(filename, datagrama, MSS)
            
            # Enviar ACK
            expected_seq += 1
            ack = make_ack(acknum=expected_seq, ver=VER_SW)
            ctrl.sendto(ack.encode(), download_conection)
            print(f"[DEBUG] Enviado ACK {expected_seq}")
            if not (datagrama.flags & FLAG_MF):
                print("Archivo recibido completo")
                break
        else:
            print(f"[DEBUG] Mensaje inesperado: {datagrama}")
            continue
    
    print(f"[DEBUG] Descarga de '{filename}' finalizada")


if __name__ == "__main__":
    
    parser = define_flags()
    args = parser.parse_args()
    
    client = process_args(args)
    
    download(client=client)