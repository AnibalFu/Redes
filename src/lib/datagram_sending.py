from socket import socket
from pyparsing import Callable

from lib.client import Client
from lib.protocolo_amcgf import VER_GBN, VER_SW, Datagrama, MsgType, make_bye, make_data, make_hello

def send_content(sender_socket, receiver_addr, content, chunk_size, timeout=2):
    sender_socket.settimeout(timeout)
    seq = 0
    for i in range(0, len(content), chunk_size):
        payload = content[i:i + chunk_size]
        mf = (i + chunk_size) < len(content)
        datagrama = make_data(seq=seq, chunk=payload, ver=VER_SW, mf=mf)
        encoded = datagrama.encode()
        ack_ok = False
        while not ack_ok:
            sender_socket.sendto(encoded, receiver_addr)
            print(f"Enviado DATA con seq {seq}, MF={mf}")
            try:
                data, _ = sender_socket.recvfrom(4096)
                datagram = Datagrama.decode(data)
                if datagram.typ == MsgType.ACK and datagram.ack == seq + 1:
                    print(f"ACK correcto recibido: {datagram}")
                    ack_ok = True
                else:
                    print(f"ACK incorrecto (esperaba {seq+1}), reenviando DATA seq {seq}")
            except TimeoutError:
                print(f"Timeout esperando ACK para seq {seq}, reenviando DATA")
        seq += 1
    sender_socket.settimeout(None)  # Restablece el timeout

def send_request(make_request: Callable, sender_socket: socket, addr: tuple[str, int], client: Client):
    """Envía un datagrama REQUEST y espera un OK de respuesta. Devuelve la nueva dirección (ip, puerto) del servidor."""
    
    proto = VER_SW if client.protocol == 'SW' else VER_GBN

    try:
        encoded = make_request(client.name, 0, proto).encode()
    except Exception:
        raise

    sender_socket.sendto(encoded, addr)

    data, new_addr = sender_socket.recvfrom(4096)

    try:
        datagram = Datagrama.decode(data)
    except Exception:
        raise

    assert datagram.typ == MsgType.OK, "Expecting OK after REQUEST"
    
    return new_addr

def send_bye(sender_socket: socket, receiver_addr: tuple[str, int], bufsize: int):
    """Envía un datagrama BYE y espera un OK de respuesta."""
        
    try:
        encoded = make_bye(VER_SW).encode()
    except Exception:
        raise
    
    sender_socket.sendto(encoded, receiver_addr)

    data, _ = sender_socket.recvfrom(bufsize)
    
    try:
        datagram = Datagrama.decode(data)
    except Exception:
        raise

    assert datagram.typ == MsgType.OK, "Expecting OK after BYE"
    sender_socket.close()