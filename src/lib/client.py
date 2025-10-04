import os
from dataclasses import dataclass
from lib.connection import Connection
from lib.config import *
from lib.fileHandler import FileHandler
from lib.logger import Logger
from lib.protocol import create_protocol, Protocol
from lib.protocolo_amcgf import FLAG_MF, MSS, MsgType, make_data, make_req_download, make_req_upload

DEFAULT_NAME = "file.txt"
DEFAULT_SRC = "./storage_personal"

class ClientError(Exception): ...

@dataclass
class Client(Connection):
    src: str = None
    name: str = None
    fileHandler: FileHandler = None
    logger: Logger = None
    
    def _create_protocol_instance(self, socket, connection_addr) -> Protocol:
        return create_protocol(self._get_protocol_type(), socket, connection_addr, rto=RTO)

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

        req = make_req_upload(self.name, self.protocol, os.path.getsize(self.src))
        
        protocol_instance, _connection_addr, client_socket = self._send_control_and_prepare_protocol(self.protocol, req.encode(), timeout=TIMEOUT_MAX + 0.1, rto=RTO)    
        if protocol_instance is None:
            return
        
         
        seq_number = 0
        # Envio de datos
        with open(self.src, 'rb') as file:
            while True:
                #chunk = file.read(MSS)
                chunk = file.read(8)  # para probar mas facil
                if not chunk:
                    break

                more_fragments = file.peek(1) != b''
                print(f"[DEBUG] more_fragments: {more_fragments}")

                datagram = make_data(seq=seq_number, chunk=chunk, ver=self.protocol, mf=more_fragments)
                print(f"[DEBUG] seq: {seq_number}, flag more_fragments: {datagram.flags & FLAG_MF}")
                protocol_instance.send_data(datagram, self.logger)

                self.logger.add_bytes(len(chunk))

                seq_number += 1

        # Cerrar conexión usando polimorfismo
        ok = protocol_instance.send_bye_with_retry(max_retries=8, quiet_time=0.2)
        self.logger.log_final(filename=f"{self.name}_metrics.txt")
        self.logger.log("Archivo enviado completo, espero BYE")
        client_socket.close()

    def download(self):
        self.logger.log(f"Solicitando descarga de '{self.name}' desde {self.host}:{self.port}")

        self.logger.start_transfer()

        req = make_req_download(self.name, self.protocol)

        protocol_instance, _connection_addr, client_socket = self._send_control_and_prepare_protocol(self.protocol, req.encode(), timeout=TIMEOUT_MAX + 0.1, rto=RTO)  
        if protocol_instance is None:
            return

        seq_number = 0
        while True:
            datagram = protocol_instance.receive_data()
            
            if not datagram:
                continue
            
            if datagram.typ == MsgType.DATA and datagram.seq < seq_number:
                protocol_instance.send_ack(datagram.seq + 1)
                continue
            
            if datagram.typ == MsgType.DATA and datagram.seq == seq_number:
                self.fileHandler.save_datagram(self.name, datagram)
                
                self.logger.add_bytes(len(datagram.payload))
                
                seq_number += 1
                protocol_instance.send_ack(seq_number)
                
                if not (datagram.flags & FLAG_MF):
                    print("[DEBUG] LAST FRAGMENT RECEIVED")
                    break
                
        protocol_instance.await_bye_and_linger(linger_factor=1, quiet_time=0.2)
        self.logger.log_final(filename=f"{self.name}_metrics.txt")
        self.logger.log("Descarga finalizada correctamente")
        client_socket.close()