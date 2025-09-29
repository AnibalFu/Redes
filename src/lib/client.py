from dataclasses import dataclass

from lib.connection import Connection
from lib.fileHandler import FileHandler
from lib.protocolo_amcgf import FLAG_MF, MSS, VER_SW, MsgType, make_data, make_req_download, make_req_upload

DEFAULT_NAME = "file.txt"
DEFAULT_SRC = "./storage_personal"

@dataclass
class Client(Connection):
    src: str = None
    name: str = None
    fileHandler: FileHandler = None

    def upload(self):
        req = make_req_upload(self.name, self.protocol)

        try:
            encoded = req.encode()
        except Exception:
            return

        sw, _, client_socket = self._send_control_and_prepare_sw(req_bytes=encoded, timeout=1.0, rto=1.0)
        
        if not sw:
            return

        seq_number = 0
        # Envio de datos
        with open(self.src, 'rb') as file:
            while True:
                chunk = file.read(MSS)
                if not chunk:
                    break

                more_fragments = file.peek(1) != b''
                
                datagram = make_data(seq=seq_number, chunk=chunk, ver=self.protocol, mf=more_fragments)
                sw.send_data(datagram)

                seq_number += 1

        # FIN 
        ok = sw.send_bye_with_retry(max_retries=8, quiet_time=0.2)
        
        print("[DEBUG] Archivo enviado completo espero BYE")
        client_socket.close()

    def download(self):
        print(f"[DEBUG] Solicitando descarga de '{self.name}' desde {self.host}:{self.port}")

        req = make_req_download(self.name, VER_SW)

        try:
            encoded = req.encode()
        except Exception:
            return

        sw, _, client_socket = self._send_control_and_prepare_sw(req_bytes=encoded, timeout=1.0, rto=1.0)
        
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
                self.fileHandler.save_datagram(self.name, datagram)
                
                seq_number += 1
                sw.send_ack(seq_number)
                
                if not (datagram.flags & FLAG_MF):
                    break
                
        sw.await_bye_and_linger(linger_factor=1, quiet_time=0.2)        
        print("[DEBUG] Descarga finalizada correctamente")
        client_socket.close()
