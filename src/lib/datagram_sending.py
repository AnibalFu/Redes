from typing import Callable
from socket import socket

from lib.client import Client
from lib.protocolo_amcgf import *

def send_request(request: Callable, udp_socket: socket, addr: tuple[str, int], client: Client):
    try:
        encoded = request(client.name, client.protocol)
    except Exception:
        raise

    udp_socket.sendto(encoded, addr)

    _bytes, new_addr = udp_socket.recvfrom(MTU)

    # try:
    #     datagram = Datagrama.decode(buf=bytes)
    # except Exception:
    #     raise
    
    return new_addr

def send_bye(udp_socket: socket, addr: tuple[str, int]):
    bye = make_bye(VER_SW)

    try:
        encoded = bye.encode()
    except Exception:
        raise

    udp_socket.sendto(encoded, addr)

    bytes, _ = udp_socket.recvfrom(MTU)

    try:
        datagram = Datagrama.decode(buf=bytes)
    except Exception:
        raise

    udp_socket.close()
