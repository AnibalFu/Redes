import os
import time

from socket import socket
from dataclasses import dataclass

from lib.config import *
from lib.logger import Logger
from lib.connection import *
from lib.protocol import create_protocol, Protocol
from lib.protocolo_amcgf import FLAG_MF, MSS, MsgType, make_data, make_req_download, make_req_upload

DEFAULT_NAME = "file.txt"
DEFAULT_SRC = "./storage_personal"

class ClientError(Exception): ...

@dataclass
class Client(Connection):
    src: str | None = None
    name: str | None = None
    logger: Logger | None = None

    def _create_protocol_instance(self, sock: socket, addr: tuple[str, int]) -> Protocol:
        return create_protocol(self._get_protocol_type(), sock, addr)

    def _check_path(self, path: str) -> None: 
        """Valida que exista el archivo antes de usarlo."""

        if not path or not os.path.isfile(path): 
            raise ClientError(f"No se encontró el archivo de origen: {path}")

    def upload(self) -> None:
        try: 
            self._check_path(self.src) 
        except ClientError as e: 
            self.logger.log_error(f"[ERROR]: {e}")
            return
        
        self.logger.start_transfer(os.path.getsize(self.src), mode="Upload")

        try:
            encoded = make_req_upload(self.name, self.protocol, os.path.getsize(self.src)).encode()
        except Exception as e:
            self.logger.log_error(f"[ERROR] No se pudo crear el datagrama de solicitud: {e}")
            return

        proto, _, sock = self._send_control(ver=self.protocol, req_bytes=encoded, timeout=TIMEOUT_MAX + 0.1, logger=self.logger)
        if not proto:
            return
        
        seq_number = 0
        with open(self.src, 'rb') as file:
            while True:
                chunk = file.read(MSS)
                if not chunk:
                    break

                more_fragments = file.peek(1) != b''

                datagram = make_data(seq=seq_number, chunk=chunk, ver=self.protocol, mf=more_fragments)

                while not proto.send_data(datagram=datagram, logger=self.logger):
                    pass

                self.logger.add_bytes(len(chunk))

                seq_number += 1

        proto.send_bye_with_retry()
        
        self.logger.log_final(filename=f"{self.name}_metrics.txt")
        self.logger.log("[INFO] Archivo enviado completo, espero BYE")
        
        sock.close()

    def download(self) -> None:
        self.logger.start_transfer(None, mode="Download")

        try:
            encoded = make_req_download(self.name, self.protocol).encode()
        except Exception as e:
            self.logger.log_error(f"[ERROR] No se pudo crear el datagrama de solicitud: {e}")
            return

        proto, _, sock = self._send_control(ver=self.protocol, req_bytes=encoded, timeout=TIMEOUT_MAX + 0.1, logger=self.logger)
        if not proto:
            return

        expected_seq, t0 = 0, None
        while True:
            datagram = proto.receive_data()
            if not datagram:
                continue
            
            if datagram.typ == MsgType.DATA and datagram.seq < expected_seq:
                proto.send_ack(expected_seq)
                continue
            
            if datagram.typ == MsgType.DATA and datagram.seq == expected_seq:
                if t0 is not None:
                    rtt = time.time() - t0
                    self.logger.log_rtt(rtt * 1000)  

                self.file_handler.save_datagram(self.name, datagram)
                
                self.logger.add_bytes(len(datagram.payload))
                
                expected_seq += 1
                proto.send_ack(expected_seq)
                
                t0 = time.time()
                
                if not (datagram.flags & FLAG_MF):
                    break
                
        proto.await_bye_and_linger(linger_factor=1, quiet_time=0.2)

        self.logger.log_final(filename=os.path.basename(self.name) + "_metrics.txt")
        self.logger.log("[INFO] Descarga finalizada correctamente")

        sock.close()
