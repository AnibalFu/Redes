import os
from dataclasses import dataclass
from lib.connection import Connection
from lib.config import *
from lib.fileHandler import FileHandler
from lib.logger import Logger
from lib.protocolo_amcgf import FLAG_MF, MSS, VER_SW, MsgType, make_data, make_req_download, make_req_upload

DEFAULT_NAME = "file.txt"
DEFAULT_SRC = "./storage_personal"

class ClientError(Exception): ...

@dataclass
class Client(Connection):
    src: str = None
    name: str = None
    fileHandler: FileHandler = None
    logger: Logger = None

    def _check_file_exists(self, path: str) -> None: 
        """Valida que exista el archivo antes de usarlo.""" 
        if not path or not os.path.isfile(path): 
            raise ClientError(f"No se encontró el archivo de origen: {path}")

    def upload(self):
        print(f"Solicitando subida de '{self.name}' a {self.host}:{self.port}")
        try: 
            self._check_file_exists(self.src) 
        except ClientError as e: 
            self.logger.log(f"[CLIENT ERROR] {e}")
            return
        
    
        # Comienza la transferencia
        self.logger.start_transfer()

        req = make_req_upload(self.name, VER_SW, os.path.getsize(self.src))
        #sw, _connection_addr, client_socket = self._send_control_and_prepare_sw(req.encode(), timeout=TIMEOUT_MAX + 0.1, rto=RTO)
        #if sw is None:
            #return

        gbn, _connection_addr, client_socket = self._send_control_and_prepare_gbn(req.encode(), timeout=TIMEOUT_MAX + 0.1, rto=RTO)
        if gbn is None:
            return
        
        chunks = []
        with open(self.src, 'rb') as file:
            while True:
                chunk = file.read(MSS) 
                # chunk = file.read(8)  # para probar mas facil
                if not chunk:
                    break
                chunks.append(chunk)
                
        total_packets = len(chunks)
        print(f"[DEBUG] Total de paquetes a enviar: {total_packets}")
        
        seq_number = 0
        while seq_number < total_packets:

            # Envio hasta llenar la ventana
            while gbn.window.can_send() and seq_number < total_packets:
                chunk = chunks[seq_number]
                more_fragments = seq_number < total_packets - 1
                
                datagram = make_data(seq=seq_number, chunk=chunk, ver=self.protocol, mf=more_fragments)
                gbn.send_data(datagram, self.logger)
                
                self.logger.add_bytes(len(chunk))
                print(f"[DEBUG] Enviado paquete {seq_number + 1}/{total_packets}")
                seq_number += 1
            
            ack_received = gbn.receive_ack()
            if ack_received:
                print(f"[DEBUG] ACK recibido, ventana base ahora en: {gbn.window.base}")
            else:
                print("[DEBUG] Timeout esperando ACK")

         
        #ok = sw.send_bye_with_retry(max_retries=8, quiet_time=0.2)
        ok = gbn.send_bye_with_retry(max_retries=8, quiet_time=0.2)
        self.logger.log_final(filename=f"{self.name}_metrics.txt")
        self.logger.log("Archivo enviado completo, espero BYE")
        client_socket.close()

    def download(self):
        self.logger.log(f"Solicitando descarga de '{self.name}' desde {self.host}:{self.port}")

        self.logger.start_transfer()

        req = make_req_download(self.name, VER_SW)
        #sw, _connection_addr, client_socket = self._send_control_and_prepare_sw(req.encode(), timeout=TIMEOUT_MAX + 0.1, rto=RTO)
        #if sw is None:
            #return

        gbn, _connection_addr, client_socket = self._send_control_and_prepare_gbn(req.encode(), timeout=TIMEOUT_MAX + 0.1, rto=RTO)
        if gbn is None:
            return

        seq_number = 0
        while True:
            #datagram = sw.receive_data()
            datagram = gbn.receive_data()
            
            if not datagram:
                continue
            
            if datagram.typ == MsgType.DATA and datagram.seq < seq_number:
                #sw.send_ack(datagram.seq + 1)
                gbn.send_ack(datagram.seq + 1)
                continue
            
            if datagram.typ == MsgType.DATA and datagram.seq == seq_number:
                self.fileHandler.save_datagram(self.name, datagram)
                
                self.logger.add_bytes(len(datagram.payload)) # esto creo que no es asi
                
                seq_number += 1
                #sw.send_ack(seq_number)
                gbn.send_ack(seq_number)
                
                if not (datagram.flags & FLAG_MF):
                    break
                
        #sw.await_bye_and_linger(linger_factor=1, quiet_time=0.2) 
        #gbn.await_bye_and_linger(linger_factor=1, quiet_time=0.2)
        self.logger.log_final(filename=f"{self.name}_metrics.txt")
        self.logger.log("Descarga finalizada correctamente")
        client_socket.close()