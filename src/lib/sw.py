import time

from dataclasses import dataclass
from socket import socket, timeout as SocketTimeout
from typing import Tuple, Optional
from lib.protocolo_amcgf import *
import time
from lib.config import *

@dataclass
class StopAndWait:
    udp_socket: socket # Mio
    peer: Tuple[str, int] # Suyo
    rto: float = RTO # Retardo de timeout
    
    def send_upload(self, filename: str) -> None:
        req = make_req_upload(filename=filename, ver=VER_SW)
        self.send_data(req)
        
    def send_download(self, filename: str) -> None:
        req = make_req_download(filename=filename, ver=VER_SW)
        self.send_data(req)

    def receive_upload(self) -> Optional[Datagrama]:
        while True:
            datagram = self.receive_data()
            if not datagram:
                continue
            
            if datagram.typ == MsgType.REQUEST_UPLOAD:
                return datagram

    def receive_download(self) -> Optional[Datagrama]:
        while True:
            datagram = self.receive_data()
            if not datagram:
                continue
            if datagram.typ == MsgType.REQUEST_DOWNLOAD:
                return datagram

    # Se lo mando a peer
    def send_data(self, datagrama: Datagrama) -> int:
        self.udp_socket.settimeout(self.rto)
        
        try:
            encoded = datagrama.encode()
        except Exception:
            raise

        expected_ack = datagrama.seq + 1
          
        while True:       
            self.udp_socket.sendto(encoded, self.peer)
            t0 = time.time()
            
            while True:
                try:
                    bytes, _ = self.udp_socket.recvfrom(MTU)
                except SocketTimeout:
                    break
                
                try:
                    datagram = Datagrama.decode(bytes)
                except (Truncated, BadChecksum):
                    break
                
                if datagram.typ != MsgType.ACK:
                    continue
                
                elif datagram.ack == expected_ack:
                    return len(encoded)
                
                elif datagram.ack < expected_ack:
                    continue
                
                elif time.time() - t0 > self.rto:
                    break

    def receive_data(self) -> Optional[Datagrama]:
        self.udp_socket.settimeout(self.rto)

        try:
            bytes, _ = self.udp_socket.recvfrom(MTU)
        except SocketTimeout:
            return None
        
        try:
            datagram = Datagrama.decode(bytes)
        except (Truncated, BadChecksum):
            return None
        
        return datagram

    # Se lo mando a peer
    def send_ack(self, acknum: int) -> None:
        ack = make_ack(acknum=acknum, ver=VER_SW)
        try:
            encoded = ack.encode()
        except Exception:
            raise
        
        self.udp_socket.sendto(encoded, self.peer)

    # Recibo de peer
    def receive_ack(self, expected_ack: int) -> bool:
        self.udp_socket.settimeout(self.rto)
        
        try:
            bytes, _ = self.udp_socket.recvfrom(MTU)
        except SocketTimeout:
            return False
        try:
            datagram = Datagrama.decode(bytes)
        except (Truncated, BadChecksum):
            return False
        
        return datagram.typ == MsgType.ACK and datagram.ack == expected_ack

    # Se lo mando a peer
    def send_bye(self) -> None:
        bye = make_bye(ver=VER_SW)

        try:
            encoded = bye.encode()
        except Exception:
            raise

        self.udp_socket.sendto(encoded, self.peer)
        
    # Recibo de peer
    def receive_bye(self) -> bool:
        self.udp_socket.settimeout(self.rto)

        try:
            bytes, _ = self.udp_socket.recvfrom(MTU)
        except SocketTimeout:
            return False
        
        try:
            datagram = Datagrama.decode(bytes)
        except (Truncated, BadChecksum):
            return False
        
        return datagram.typ == MsgType.BYE
    
    def send_bye_with_retry(self, max_retries: int = 8, quiet_time: float = 0.2) -> bool:
        self.udp_socket.settimeout(self.rto)
        
        bye = make_bye(ver=VER_SW)

        try:
            encoded = bye.encode()
        except Exception:
            raise

        for _ in range(max_retries):
            self.udp_socket.sendto(encoded, self.peer)
            
            try:
                bytes, _ = self.udp_socket.recvfrom(MTU)
            except SocketTimeout:
                continue
            
            try:
                datagram = Datagrama.decode(bytes)
            except (Truncated, BadChecksum):
                continue
            
            # Si recibo OK modela el LINGER (espero a que el peer cierre)
            if datagram.typ == MsgType.OK:
                t_end = time.time() + quiet_time
                self.udp_socket.settimeout(quiet_time)
                
                while time.time() < t_end:
                    try:
                        self.udp_socket.recvfrom(MTU)
                    except SocketTimeout:
                        break
                    
                return True
            
        return False

    def await_bye_and_linger(self, linger_factor: int = 2, quiet_time: float = 0.2) -> None:
        self.udp_socket.settimeout(self.rto)

        while True:
            try:
                bytes, _ = self.udp_socket.recvfrom(MTU)
            except SocketTimeout:
                continue
            
            try:
                datagram = Datagrama.decode(bytes)
            except (Truncated, BadChecksum):
                continue
            
            # Si recibo BYE modela el LINGER (espero a que el peer cierre)
            if datagram.typ == MsgType.BYE:
                print("[DEBUG] Recibido BYE de peer, enviando OK MODO LINGER")
                self.send_ok()
                
                t_end = time.time() + linger_factor * self.rto
                self.udp_socket.settimeout(quiet_time)
                
                # LINGER
                while time.time() < t_end:
                    try:
                        bytes, _ = self.udp_socket.recvfrom(MTU)
                    except SocketTimeout:
                        continue
                    
                    try:
                        datagram = Datagrama.decode(bytes)
                    except (Truncated, BadChecksum):
                        continue
                    
                    if datagram.typ == MsgType.BYE:
                        print("[DEBUG] REENVIO OK")
                        self.send_ok()
                        t_end = time.time() + linger_factor * self.rto
                
                return
            
    def send_ok(self) -> None:
        ok = make_ok(ver=VER_SW)

        try:
            encoded = ok.encode()
        except Exception:
            raise

        self.udp_socket.sendto(encoded, self.peer)

    def receive_ok(self) -> bool:
        self.udp_socket.settimeout(self.rto)
        
        try:
            bytes, _ = self.udp_socket.recvfrom(MTU)
        except SocketTimeout:
            return False
        
        try:
            datagram = Datagrama.decode(bytes)
        except (Truncated, BadChecksum):
            return False
        
        return datagram.typ == MsgType.OK