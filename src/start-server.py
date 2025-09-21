import sys

from socket import socket, AF_INET, SOCK_DGRAM
from signal import SIGINT, signal
from types import FrameType

from lib.datagram_sending import send_content
from lib.server import Server
from lib.flags import SERVER_FLAGS
from lib.utils import split
from lib.protocolo_amcgf import *

def sigint_handler(_: int, frame: FrameType | None):
    server_socket = frame.f_locals['server_socket']
    
    try:
        server_socket.close()
    except:
        print(f'\nError: Socket {server_socket} could not be closed')
        sys.exit(-1)
    
    print('\nGraceful Exit')
    sys.exit(0)    

def process_args(args: list[str]):
    server = Server()
    
    for arg in args:
        try:
            (flag, body) = arg.split(' ', maxsplit=2)
        except ValueError:
            flag = arg
            body = None

        function = SERVER_FLAGS.get(flag)

        if function:
            function(flag=flag, body=body, entity=server)
        else:
            print(f'Warning: Bad Flag {flag}')

    return server

def run(server: Server):
    server_socket = socket(AF_INET, SOCK_DGRAM)
    server_socket.bind((server.host, server.port))

    # Estado por cliente (para pruebas, usa address como clave)
    client_states = {}

    while True:
        data, sender_address = server_socket.recvfrom(4096)
        if len(data) < HDR_SIZE:
            print("Mensaje de control recibido:", data)
            continue

        try:
            datagrama = Datagrama.decode(data)
        except Exception as e:
            print(f"Error al decodificar datagrama: {e}")
            continue

        state = client_states.get(sender_address, {"step": 0, "filedata": b""})

        if datagrama.typ == MsgType.HELLO and state["step"] == 0:
            print("HELLO recibido")
            resp = make_hello(proto="SW")
            server_socket.sendto(resp.encode(), sender_address)
            state["step"] = 1

        elif datagrama.typ == MsgType.REQUEST_UPLOAD and state["step"] == 1:
            print("UPLOAD recibido")
            resp = make_ok(ver=VER_SW)
            server_socket.sendto(resp.encode(), sender_address)
            state["step"] = 2

        elif datagrama.typ == MsgType.REQUEST_DOWNLOAD and state["step"] == 1:
            print("DOWNLOAD recibido")
            filename = datagrama.payload.decode().split('=', maxsplit=1)[1]
            resp = make_ok(ver=VER_SW)
            server_socket.sendto(resp.encode(), sender_address)
            state["step"] = 2
            handle_download(server_socket, sender_address, filename)
            
        elif datagrama.typ == MsgType.DATA and state["step"] == 1:
            print("DATA RECIBIDA recibido")
            resp = make_ack(acknum=datagrama.seq + 1,ver=VER_SW)
            server_socket.sendto(resp.encode(), sender_address)
            # Puedes guardar el nombre del archivo aquí si quieres

        elif datagrama.typ == MsgType.DATA and state["step"] == 2:
            print(f"DATA recibido seq={datagrama.seq} len={len(datagrama.payload)} payload={datagrama.payload}")
            state["filedata"] += datagrama.payload
            # Enviar ACK por cada DATA recibido
            resp = make_ack(acknum=datagrama.seq + 1,ver=VER_SW)
            server_socket.sendto(resp.encode(), sender_address)
            # Si no hay MF, es el último fragmento
            if not (datagrama.flags & FLAG_MF):
                print("Archivo recibido completo, esperando BYE...")

        elif datagrama.typ == MsgType.BYE and state["step"] == 2:
            print("BYE recibido, guardando archivo y respondiendo OK")
            # Aquí podrías guardar el archivo en disco si quieres
            # with open("archivo_recibido", "wb") as f:
            #     f.write(state["filedata"])
            resp = make_ok(ver=VER_SW)
            server_socket.sendto(resp.encode(), sender_address)
            state["step"] = 0
            state["filedata"] = b""

        client_states[sender_address] = state

    server_socket.close()

def handle_download(server_socket: socket, sender_address, filename: str):
    print(f"Preparando para enviar el archivo: {filename}") # debug
    # Asumo que despues no vamos a cargar todo el archivo en memoria,
    # por eso lo abstraigo
    with open(filename, "rb") as f:
        content = f.read()
    send_content(server_socket, sender_address, content, chunk_size=6)


if __name__ == '__main__':

    # Piso la señal de SIGINT
    signal(SIGINT, sigint_handler)

    args = split(sys.argv)

    server = process_args(args)

    run(server=server)

"""
Esto me devolvio GPT quizas sirva de algo
"""
def handle_packet(pkt: Datagrama, state) -> list[Datagrama]:
    out: list[Datagrama] = []
    if pkt.typ == MsgType.HELLO:
        params = payload_decode(pkt.payload)
        # valida op/name/size/proto...
        out.append(make_ok({"transfer_id": state.alloc_tid()}, ver=pkt.ver))
        state.begin(params, ver=pkt.ver)
    elif pkt.typ == MsgType.DATA:
        if pkt.ver == VER_SW:
            if pkt.seq == state.expected_seq and state.check_and_write(pkt.payload):
                state.expected_seq ^= 1
            # en S&W se ACKea el último válido (puntual)
            out.append(make_ack(state.expected_seq ^ 1, ver=pkt.ver))
        else:  # VER_GBN
            if pkt.seq == state.expected_seq and state.check_and_write(pkt.payload):
                state.expected_seq += 1
            # en GBN ACK acumulativo del último in-order
            out.append(make_ack(state.expected_seq - 1, ver=pkt.ver))
    elif pkt.typ == MsgType.BYE:
        state.finish()
        out.append(make_ok(ver=pkt.ver))
    return out
