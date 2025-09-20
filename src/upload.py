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
    # Mejor poner la conexion aparte  
    up_socket = socket(AF_INET, SOCK_DGRAM)  # creo el socket UDP
    server_address = (client.host, client.port)  # dirección del servidor

    with open(client.src, "rb") as f:  # Abro un archivo en modo binario
        while True:   
            contenido = f.read(20) # Leo de a 20 bytes del archivo
            datagrama = make_req_upload(client.name, contenido, VER_SW, mf=False) #Creo datagrama seguro faltan campos
            print(datagrama.payload)
            up_socket.sendto(datagrama.encode(), server_address) 
            if len(contenido) < 20:
                break
        # Bye

        return

if __name__ == '__main__':
    args = split(sys.argv)

    client = process_args(args)

    upload(client=client)