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
        ctrl = socket(AF_INET, SOCK_DGRAM)
        ctrl.settimeout(1)

        req = make_req_upload(self.name, VER_SW)
        ctrl.sendto(req.encode(), (self.host, self.port))

        data, connection_addr = ctrl.recvfrom(MTU)
        ok = Datagrama.decode(data)
        if ok.typ == MsgType.ERR:
            ctrl.close()
            return

        sw = StopAndWait(ctrl, connection_addr, rto=1.0)

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
        while True:
            print("[DEBUG] Enviando BYE")
            sw.send_bye()
            if sw.receive_bye():
                break

        print("[DEBUG] Archivo enviado completo espero BYE")
        ctrl.close()


    def download(self):
        print(f"[DEBUG] Solicitando descarga de '{self.name}' desde {self.host}:{self.port}")

        ctrl = socket(AF_INET, SOCK_DGRAM)
        ctrl.settimeout(1)

        req = make_req_download(self.name, VER_SW)
        ctrl.sendto(req.encode(), (self.host, self.port))

        data, connection_addr = ctrl.recvfrom(MTU)
        ok = Datagrama.decode(data)
        if ok.typ == MsgType.ERR:
            ctrl.close()
            return

        sw = StopAndWait(ctrl, connection_addr, rto=1.0)
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
                    pass
                
            elif d.typ == MsgType.BYE:
                sw.send_bye()
                break
                
        print("[DEBUG] Descarga finalizada correctamente")
        ctrl.close()
