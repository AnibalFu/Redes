import sys

from socket import socket, AF_INET, SOCK_DGRAM

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
    up_socket = socket(AF_INET, SOCK_DGRAM)
    up_socket.bind((client.host, client.port))

    # Handshake

    while True:
        # Subir archivo ...
        break

    # Bye

    return

if __name__ == '__main__':
    args = split(sys.argv)

    client = process_args(args)

    upload(client=client)