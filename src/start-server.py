import sys

from socket import socket, AF_INET, SOCK_DGRAM
from signal import SIGINT, signal
from types import FrameType

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

    while True:
        
        data, sender_address = server_socket.recvfrom(1000) #Tendria que leer el header nada mas
        print(f"Received {len(data)} bytes from {sender_address}")
        datagrama = Datagrama.decode(data)
        print("Payload recibido")
        print(payload_decode(datagrama.payload))
        #server_socket.recvfrom(datagrama.payload_len(),sender_address) #Aca con el dato del len payload leo el restante
        pass

    server_socket.close()

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


"""
from socket import *
import threading

CTRL_HOST = "127.0.0.1"
CTRL_PORT = 12000
BUF = 1500

def handle_session(sess_sock: socket, client_addr, mode: str, resource: str):
    try:
        # Handshake mínimo para confirmar que el cliente llegó al puerto de datos
        # (evita enviar datos “al vacío”). Aprendemos el puerto de datos del cliente
        # mediante recvfrom y luego conectamos el socket a ese peer.
        sess_sock.settimeout(5.0)
        try:
            ping, client_data_addr = sess_sock.recvfrom(BUF)
        except timeout:
            # Cliente no llegó; cerrar sesión
            return

        # Conectar al puerto de datos real del cliente
    
        # Responder ACK de sesión
        sess_sock.sendto(b"SESSION_OK", client_data_addr)

        if mode == "DOWNLOAD":
            # Demo: mandar contenido en chunks
            data = b"hola desde el servidor\n" * 10
            chunk = 1200
            for i in range(0, len(data), chunk):
                sess_sock.sendto(data[i:i+chunk], client_data_addr)
            sess_sock.sendto(b"FIN", client_data_addr)
        else:
            # UPLOAD: recibir hasta "FIN"
            received = bytearray()
            while True:
                pkt = sess_sock.recv(BUF)
                if pkt == b"FIN":
                    break
                received += pkt
            # demo: confirmar tamaño recibido
            sess_sock.sendto(f"RCV {len(received)} bytes".encode(), client_data_addr)
    finally:
        sess_sock.close()

def main():
    ctrl = socket(AF_INET, SOCK_DGRAM)
    ctrl.bind((CTRL_HOST, CTRL_PORT))
    print(f"Control UDP escuchando en {CTRL_HOST}:{CTRL_PORT}")

    while True:
        data, addr = ctrl.recvfrom(BUF)
        # Protocolo de control minimalista: "DOWNLOAD nombre" o "UPLOAD nombre"
        try:
            parts = data.decode().strip().split(maxsplit=1)
            mode = parts[0].upper()
            resource = parts[1] if len(parts) > 1 else ""
        except Exception:
            ctrl.sendto(b"ERR bad request", addr)
            continue

        # Crear socket/puerto dedicado
        sess_sock = socket(AF_INET, SOCK_DGRAM)
        sess_sock.bind((CTRL_HOST, 0))  # puerto efímero
        sess_port = sess_sock.getsockname()[1]

        # Responder al cliente por el puerto de control
        ctrl.sendto(f"DATA_PORT {sess_port}".encode(), addr)

        # Lanzar hilo de sesión
        t = threading.Thread(
            target=handle_session,
            args=(sess_sock, addr, mode, resource),
            daemon=True
        )
        t.start()

if __name__ == "__main__":
    main()

"""