from dataclasses import dataclass
from lib.connection import Connection
from lib.datagram_sending import *
from socket import socket, AF_INET, SOCK_DGRAM
from lib.sw import StopAndWait

DEFAULT_NAME = "file.txt"
DEFAULT_SRC = "/personal_folder"


@dataclass
class Client(Connection):
    src: str = None
    name: str = None

    def upload(self):
        req = make_req_upload(self.name, VER_SW)
        sw, _connection_addr, ctrl = self._send_control_and_prepare_sw(req.encode(), timeout=1.0, rto=1.0)
        if sw is None:
            return

        seq = 0
        # Envio de datos
        with open(self.src, "rb") as f:
            while True:
                chunk = f.read(MSS)
                if not chunk:
                    break
                mf = f.peek(1) != b""
                d = make_data(seq=seq, chunk=chunk, ver=VER_SW, mf=mf)
                sw.send_data(d)
                seq += 1

        # FIN 
        ok = sw.send_bye_with_retry(max_retries=8, quiet_time=0.2)
        
        print("[DEBUG] Archivo enviado completo espero BYE")
        ctrl.close()


    def download(self):
        print(f"[DEBUG] Solicitando descarga de '{self.name}' desde {self.host}:{self.port}")

        req = make_req_download(self.name, VER_SW)
        sw, _connection_addr, ctrl = self._send_control_and_prepare_sw(req.encode(), timeout=1.0, rto=1.0)
        if sw is None:
            return

        seq = 0
        while True:
            d = sw.receive_data()
            
            if d is None:
                continue
            
            if d.typ == MsgType.DATA and d.seq < seq:
                sw.send_ack(d.seq + 1)
                continue
            
            if d.typ == MsgType.DATA and d.seq == seq:
                self.fileHandler.save_datagram(self.name, d)
                seq += 1
                sw.send_ack(seq)
                
                if not (d.flags & FLAG_MF):
                    break
                
        sw.await_bye_and_linger(linger_factor=1, quiet_time=0.2)        
        print("[DEBUG] Descarga finalizada correctamente")
        ctrl.close()
