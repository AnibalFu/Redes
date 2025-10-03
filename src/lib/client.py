import os

from dataclasses import dataclass

from lib.connection import Connection
from lib.config import *
from lib.protocolo_amcgf import FLAG_MF, MSS, MsgType, make_data, make_req_download, make_req_upload

DEFAULT_NAME = "file.txt"
DEFAULT_SRC = "./storage_personal"

class ClientError(Exception): ...

@dataclass
class Client(Connection):
    src: str | None = None
    name: str | None = None

    def _check_path(self, path: str) -> None: 
        """Valida que exista el archivo antes de usarlo."""

        if not path or not os.path.isfile(path): 
            raise ClientError(f"No se encontró el archivo de origen: {path}")

    def upload(self):
        try: 
            self._check_path(self.src) 
        except ClientError as e: 
            self.logger.log(f"[ERROR]: {e}")
            return
        
        # Comienza la transferencia
        self.logger.start_transfer()

        try:
            encoded = make_req_upload(self.name, self.protocol, os.path.getsize(self.src)).encode()
        except Exception as e:
            self.logger.log(f"[ERROR] No se pudo crear el datagrama de solicitud: {e}")
            return

        sw, _, sock = self._send_control_and_prepare_sw(req_bytes=encoded, timeout=TIMEOUT_MAX + 0.1)
        if not sw:
            return
        
        seq_number = 0
        with open(self.src, 'rb') as file:
            while True:
                chunk = file.read(MSS)
                if not chunk:
                    break

                more_fragments = file.peek(1) != b''
                
                datagram = make_data(seq=seq_number, chunk=chunk, ver=self.protocol, mf=more_fragments)
                sw.send_data(datagram, self.logger)

                self.logger.add_bytes(len(chunk))

                seq_number += 1

        sw.send_bye_with_retry(retries=8, quiet_time=0.2)

        self.logger.log_final(filename=f"{self.name}_metrics.txt")
        self.logger.log("[INFO] Archivo enviado completo, espero BYE")
        
        sock.close()

    def download(self):
        self.logger.log(f"[INFO] Solicitando descarga de '{self.name}' desde {self.host}:{self.port}")

        # Comienza la transferencia
        self.logger.start_transfer()

        try:
            encoded = make_req_download(self.name, self.protocol).encode()
        except Exception as e:
            self.logger.log(f"[ERROR] No se pudo crear el datagrama de solicitud: {e}")
            return

        sw, _, sock = self._send_control_and_prepare_sw(encoded, timeout=TIMEOUT_MAX + 0.1)
        if not sw:
            return

        seq_number = 0
        while True:
            datagram = sw.receive_data()
            
            if not datagram:
                continue
            
            if datagram.typ == MsgType.DATA and datagram.seq < seq_number:
                sw.send_ack(datagram.seq + 1)
                continue
            
            if datagram.typ == MsgType.DATA and datagram.seq == seq_number:
                self.file_handler.save_datagram(self.name, datagram)
                
                self.logger.add_bytes(len(datagram.payload))
                
                seq_number += 1
                sw.send_ack(seq_number)
                
                if not (datagram.flags & FLAG_MF):
                    break
                
        sw.await_bye_and_linger(linger_factor=1, quiet_time=0.2) 
        
        self.logger.log_final(filename=f"{self.name}_metrics.txt")
        self.logger.log("[INFO] Descarga finalizada correctamente")
        
        sock.close()
