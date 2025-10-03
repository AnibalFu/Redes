import threading
from dataclasses import dataclass
from socket import socket
from typing import Tuple
from lib.fileHandler import FileHandler
from lib.connection import Connection
from lib.config import *
from lib.protocol import Protocol
from lib.protocolo_amcgf import *
        
# A futuro restar key de data
CHUNK_SIZE = MSS
DEFAULT_STORAGE_PATH = './storage_data'

@dataclass
class Server(Connection):
    fileHandler: FileHandler = None

    def run(self):
        """
        Ejecuta el servidor principal

        Por cada cliente se crea un thread para manejar la transferencia
        """
        server_socket = self._make_udp_socket()
        server_socket.bind((self.host, self.port))
        print(f"Servidor escuchando en {self.host}:{self.port}")

        while True:
            packet, client_addr = server_socket.recvfrom(MTU)
            if len(packet) < HDR_SIZE:
                print("[DEBUG] Mensaje de control recibido:", packet)
                continue

            try:
                datagram = Datagrama.decode(packet)
            except Exception as e:
                err = make_err("Error al decodificar datagrama")
                server_socket.sendto(err.encode(), client_addr)
                print(f"[DEBUG] Error al decodificar datagrama: {e}")
                continue
        
            # Tipos de mensajes aceptados de cliente
            if datagram.typ == MsgType.REQUEST_UPLOAD:
                payload = payload_decode(datagram.payload)
                protocol = datagram.ver
                print(f"[DEBUG] REQUEST_UPLOAD de {client_addr} payload: {payload}")
                
                filename = payload[PAYLOAD_FILENAME_KEY]
                file_size = payload[FILE_SIZE_KEY]

                if file_size > MAX_FILE_SIZE:
                    err = make_err(f"El tamaño del archivo excede el máximo permitido de {MAX_FILE_SIZE} bytes")
                    server_socket.sendto(err.encode(), client_addr)
                    print(f"[DEBUG] El tamaño del archivo excede el máximo permitido de {MAX_FILE_SIZE} bytes")
                    continue
                
                udp_socket = self._make_udp_socket(bind_addr=('', 0))
                
                threading.Thread(target=self.handle_upload, args=(udp_socket, client_addr, filename, protocol), daemon=True).start()

            elif datagram.typ == MsgType.REQUEST_DOWNLOAD:
                payload = payload_decode(datagram.payload)
                protocol = datagram.ver
                print(f"[DEBUG] REQUEST_DOWNLOAD de {client_addr} payload: {payload}")
                
                filename = payload[PAYLOAD_FILENAME_KEY]

                if not self.fileHandler.is_filename_used(filename):
                    err = make_err(f"El archivo '{filename}' no existe en el servidor")
                    server_socket.sendto(err.encode(), client_addr)
                    print(f"[DEBUG] El archivo '{filename}' no existe en el servidor")
                    continue

                print(f"[DEBUG] Filename: {filename}")
                
                udp_socket = self._make_udp_socket(bind_addr=('', 0))
                
                threading.Thread(target=self.handle_download, args=(udp_socket, client_addr, filename, protocol), daemon=True).start()

    def handle_upload(self, udp_socket: socket, client_addr: Tuple[str, int], filename: str, ver: int):
        # Parte del handshake
        protocol = self._send_ok_and_prepare_protocol(ver, udp_socket, client_addr, rto=RTO)
        print(f"[DEBUG] Handle upload en puerto {udp_socket.getsockname()[1]} para {client_addr}")

        seq_number = 0
        while True:

            datagram = protocol.receive_data()
            if not datagram:
                continue
            
            if datagram.typ == MsgType.DATA:
                print(f"[DEBUG] Recibido DATA con seq {datagram.seq} esperado {seq_number}")
                
                if datagram.seq == seq_number:
                    self.fileHandler.save_datagram(filename=filename, datagram=datagram)
                    seq_number += 1
                    protocol.send_ack(acknum=datagram.seq)
                
                else:

                    # Paquete fuera de orden, reenviar ACK del último paquete correcto
                    if seq_number > 0:
                        protocol.send_ack(acknum=seq_number - 1)
                
                if not (datagram.flags & FLAG_MF):
                    print("[DEBUG] LAST FRAGMENT RECEIVED")
                    break
    
        protocol.await_bye_and_linger(linger_factor=3, quiet_time=0.2)
        udp_socket.close()
        
    def handle_download(self, udp_socket: socket, client_addr: tuple[str, int], filename: str, ver: int):
        protocol = self._send_ok_and_prepare_protocol(ver, udp_socket, client_addr, rto=RTO)

        for seq_number, (payload, mf) in enumerate(self.fileHandler.get_file_chunks(filename, CHUNK_SIZE)):
            protocol.send_data(datagrama=make_data(seq=seq_number, chunk=payload, ver=VER_GBN, mf=mf))
            
        protocol.send_bye_with_retry(max_retries=8, quiet_time=0.2)
        udp_socket.close()