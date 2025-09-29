from dataclasses import dataclass
from socket import socket, timeout as SocketTimeout
from typing import Tuple, Optional
from lib.protocolo_amcgf import *
import time
from lib.config import *

@dataclass
class StopAndWait:
    sock: socket # Mio
    peer: Tuple[str, int] # Suyo
    rto: float = RTO # Retardo de timeout
    
    #########################
    def send_upload(self, filename: str) -> None:
        req = make_req_upload(filename, VER_SW)
        self.send_data(req)
        
    def send_download(self, filename: str) -> None:
        req = make_req_download(filename, VER_SW)
        self.send_data(req)

    def receive_upload(self) -> Optional["Datagrama"]:
        while True:
            d = self.receive_data()
            if d is None:
                continue
            if d.typ == MsgType.REQUEST_UPLOAD:
                return d

    def receive_download(self) -> Optional["Datagrama"]:
        while True:
            d = self.receive_data()
            if d is None:
                continue
            if d.typ == MsgType.REQUEST_DOWNLOAD:
                return d
    #########################


    # Se lo mando a peer
    def send_data(self, datagrama: "Datagrama") -> int:
        encoded = datagrama.encode()
        expected_ack = datagrama.seq + 1
        self.sock.settimeout(self.rto)
          
        while True:       
            self.sock.sendto(encoded, self.peer)
            t0 = time.time()
            
            while True:
                try:
                    data, _ = self.sock.recvfrom(MTU)
                except SocketTimeout:
                    break
                
                try:
                    d = Datagrama.decode(data)
                except (Truncated, BadChecksum):
                    break
                
                if d.typ != MsgType.ACK:
                    continue
                
                elif d.ack == expected_ack:
                    return len(encoded)
                
                elif d.ack < expected_ack:
                    continue
                
                elif time.time() - t0 > self.rto:
                    break

    # Recibo de peer
    def receive_data(self) -> Optional["Datagrama"]:
        self.sock.settimeout(self.rto)
        try:
            data, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return None
        
        try:
            d = Datagrama.decode(data)
        except (Truncated, BadChecksum):
            return None
        
        return d

    # Se lo mando a peer
    def send_ack(self, acknum: int) -> None:
        ack = make_ack(acknum=acknum, ver=VER_SW)
        self.sock.sendto(ack.encode(), self.peer)

    # Recibo de peer
    def receive_ack(self, expected_ack: int) -> bool:
        self.sock.settimeout(self.rto)
        try:
            data, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return False
        try:
            d = Datagrama.decode(data)
        except (Truncated, BadChecksum):
            return False
        
        return d.typ == MsgType.ACK and d.ack == expected_ack

    # Se lo mando a peer
    def send_bye(self) -> None:
        bye = make_bye(ver=VER_SW)
        self.sock.sendto(bye.encode(), self.peer)
        
    # Recibo de peer
    def receive_bye(self) -> bool:
        self.sock.settimeout(self.rto)
        try:
            data, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return False
        try:
            d = Datagrama.decode(data)
        except (Truncated, BadChecksum):
            return False
        
        return d.typ == MsgType.BYE
    
    
    def send_bye_with_retry(self, max_retries: int = 8, quiet_time: float = 0.2) -> bool:
        payload = make_bye(ver=VER_SW).encode()
        self.sock.settimeout(self.rto)
        for _ in range(max_retries):
            self.sock.sendto(payload, self.peer)
            try:
                data, _ = self.sock.recvfrom(MTU)
            except SocketTimeout:
                continue
            
            try:
                d = Datagrama.decode(data)
            except (Truncated, BadChecksum):
                continue
            
            # Si recibo OK modela el LINGER (espero a que el peer cierre)
            if d.typ == MsgType.OK:
                t_end = time.time() + quiet_time
                self.sock.settimeout(quiet_time)
                
                while time.time() < t_end:
                    try:
                        self.sock.recvfrom(MTU)
                    except SocketTimeout:
                        break
                    
                return True
            
        return False

    def await_bye_and_linger(self, linger_factor: int = 2, quiet_time: float = 0.2) -> None:
        self.sock.settimeout(self.rto)
        while True:
            try:
                data, _ = self.sock.recvfrom(MTU)
            except SocketTimeout:
                continue
            
            try:
                d = Datagrama.decode(data)
            except (Truncated, BadChecksum):
                continue
            
            # Si recibo BYE modela el LINGER (espero a que el peer cierre)
            if d.typ == MsgType.BYE:
                print("[DEBUG] Recibido BYE de peer, enviando OK MODO LINGER")
                self.send_ok()
                t_end = time.time() + linger_factor * self.rto
                self.sock.settimeout(quiet_time)
                
                # LINGER
                while time.time() < t_end:
                    try:
                        data2, _ = self.sock.recvfrom(MTU)
                    except SocketTimeout:
                        continue
                    
                    try:
                        d2 = Datagrama.decode(data2)
                    except (Truncated, BadChecksum):
                        continue
                    
                    if d2.typ == MsgType.BYE:
                        print("[DEBUG] REENVIO OK")
                        self.send_ok()
                        t_end = time.time() + linger_factor * self.rto
                
                return
            
    def send_ok(self) -> None:
        self.sock.sendto(make_ok(ver=VER_SW).encode(), self.peer)

    def receive_ok(self) -> bool:
        self.sock.settimeout(self.rto)
        try:
            data, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return False
        try:
            d = Datagrama.decode(data)
        except (Truncated, BadChecksum):
            return False
        return d.typ == MsgType.OK