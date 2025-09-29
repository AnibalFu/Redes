import threading

from dataclasses import dataclass
from socket import socket
from typing import Tuple

from lib.fileHandler import FileHandler
from lib.connection import Connection
from lib.datagram_sending import *
        
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
                print(f"[DEBUG] REQUEST_UPLOAD de {client_addr} payload: {payload}")
                
                filename = payload[PAYLOAD_FILENAME_KEY]
                
                udp_socket = self._make_udp_socket(bind_addr=('', 0))
                
                threading.Thread(target=self.handle_upload, args=(udp_socket, client_addr, filename), daemon=True).start()

            elif datagram.typ == MsgType.REQUEST_DOWNLOAD:
                payload = payload_decode(datagram.payload)
                print(f"[DEBUG] REQUEST_DOWNLOAD de {client_addr} payload: {payload}")
                
                filename = payload[PAYLOAD_FILENAME_KEY]
                print(f"[DEBUG] Filename: {filename}")
                
                udp_socket = self._make_udp_socket(bind_addr=('', 0))
                
                threading.Thread(target=self.handle_download, args=(udp_socket, client_addr, filename), daemon=True).start()
    
    def handle_upload(self, udp_socket: socket, client_addr: Tuple[str, int], filename: str):
        # Parte del handshake
        sw = self._send_ok_and_prepare_sw(udp_socket=udp_socket, peer_addr=client_addr, rto=1.0)
        print(f"[DEBUG] Handle upload en puerto {udp_socket.getsockname()[1]} para {client_addr}")

        seq_number = 0
        while True:
            datagram = sw.receive_data()
            
            if not datagram:
                continue
            
            if datagram.typ == MsgType.DATA:
                print(f"[DEBUG] Recibido DATA con seq {datagram.seq} esperado {seq_number}")
                if datagram.seq == seq_number:
                    self.fileHandler.save_datagram(filename=filename, datagram=datagram)
                    seq_number += 1
                
                sw.send_ack(acknum=seq_number)
                
                if not (datagram.flags & FLAG_MF):
                    break
    
        sw.await_bye_and_linger(linger_factor=3, quiet_time=0.2)

        print("[DEBUG] Transferencia finalizada correctamente")
        print("[DEBUG] --------------------------------------")
        udp_socket.close()
        
    def handle_download(self, udp_socket: socket, client_addr: tuple[str, int], filename: str):
        # Parte del handshake
        sw = self._send_ok_and_prepare_sw(udp_socket, client_addr, rto=1.0)
        
        # Mando DATA
        for seq_number, (payload, mf) in enumerate(self.fileHandler.get_file_chunks(filename, CHUNK_SIZE)):
            print(f"[DEBUG] Enviando DATA con seq {seq_number}")
            sw.send_data(datagrama=make_data(seq=seq_number, chunk=payload, ver=VER_SW, mf=mf))

        # Mando BYE
        sw.send_bye_with_retry(max_retries=8, quiet_time=0.2)

        udp_socket.close()
