from attr import dataclass
from socket import socket, AF_INET, SOCK_DGRAM
from lib.fileHandler import FileHandler
from lib.connection import Connection
from lib.datagram_sending import *
from lib.sw import StopAndWait
import threading
from typing import Tuple
        
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
        server_socket = socket(AF_INET, SOCK_DGRAM)
        server_socket.bind((self.host, self.port))
        print(f"Servidor escuchando en {self.host}:{self.port}")

        while True:
            packet, client_addr = server_socket.recvfrom(MTU)
            if len(packet) < HDR_SIZE:
                print("[DEBUG] Mensaje de control recibido:", packet)
                continue

            try:
                datagrama = Datagrama.decode(packet)
            except Exception as e:
                err = make_err("Error al decodificar datagrama")
                server_socket.sendto(err.encode(), client_addr)
                print(f"[DEBUG] Error al decodificar datagrama: {e}")
                continue
        
            # Tipos de mensajes aceptados de cliente
            if datagrama.typ == MsgType.REQUEST_UPLOAD:
                payload = payload_decode(datagrama.payload)
                print(f"[DEBUG] REQUEST_UPLOAD de {client_addr} payload: {payload}")
                filename = payload[PAYLOAD_FILENAME_KEY]
                sock = socket(AF_INET, SOCK_DGRAM)
                sock.bind(('', 0))  # Puerto libre asignado por el SO
                threading.Thread(target=self.handle_upload, args=(sock, client_addr, filename), daemon=True).start()


            elif datagrama.typ == MsgType.REQUEST_DOWNLOAD:
                payload = payload_decode(datagrama.payload)
                print(f"[DEBUG] REQUEST_DOWNLOAD de {client_addr} payload: {payload}")
                filename = payload[PAYLOAD_FILENAME_KEY]
                print(f"[DEBUG] Filename: {filename}")
                sock = socket(AF_INET, SOCK_DGRAM)
                sock.bind(('', 0))  # Puerto libre asignado por el SO
                threading.Thread(target=self.handle_download, args=(sock, client_addr, filename), daemon=True).start()

    # server_socket.close()
    
    def handle_upload(self, sock: socket, client_addr: Tuple[str, int], filename: str):
        # Parte del handshake
        ok = make_ok(ver=VER_SW)
        sock.sendto(ok.encode(), client_addr)

        sw = StopAndWait(sock, client_addr, rto=1.0)
        print(f"[DEBUG] Handle upload en puerto {sock.getsockname()[1]} para {client_addr}")

        seq = 0
        while True:
            d = sw.receive_data()
            
            if d is None:
                continue
            
            if d.typ == MsgType.DATA and d.seq < seq:
                sw.send_ack(d.seq + 1)
                continue
            
            if d.typ == MsgType.DATA and d.seq == seq:
                self.fileHandler.save_datagram(filename, d)
                seq += 1
                sw.send_ack(seq)
                if not (d.flags & FLAG_MF):
                    pass
                
            elif d.typ == MsgType.BYE:
                sw.send_bye()
                break
                
        print("[DEBUG] Transferencia finalizada correctamente")
        print("[DEBUG] --------------------------------------")
        sock.close()
        
        
    def handle_download(self, sock: socket, client_addr: tuple[str, int], filename: str):
        # Parte del handshake
        ok = make_ok(ver=VER_SW)
        sock.sendto(ok.encode(), client_addr)
        
        sw = StopAndWait(sock, client_addr, rto=1.0)
        # Mando DATA
        for seq, (payload, mf) in enumerate(self.fileHandler.get_file_chunks(filename, CHUNK_SIZE)):
            d = make_data(seq=seq, chunk=payload, ver=VER_SW, mf=mf)
            print(f"[DEBUG] Enviando DATA con seq {seq}")
            sw.send_data(d)

        # Mando BYE
        while True:
            print("[DEBUG] Enviando BYE")
            sw.send_bye()
            if sw.receive_bye():
                break

        sock.close()
