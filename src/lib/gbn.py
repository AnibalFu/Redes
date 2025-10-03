from dataclasses import dataclass
from socket import socket, timeout as SocketTimeout
import time
from typing import Optional

from lib.config import RTO
from lib.logger import Logger
from lib.protocolo_amcgf import FLAG_MF, MTU, VER_GBN, VER_SW, BadChecksum, Datagrama, MsgType, Truncated, make_ack, make_bye, make_ok, make_req_download, make_req_upload
from lib.window import Window

@dataclass  
class GoBackN:
    rto: float = RTO 
    
    def __init__(self, sock: socket, client_addr: tuple[str, int], rto: float = RTO):
        self.udp_socket = sock
        self.client_addr = client_addr
        self.rto = rto
        self.window = Window()
        self.timer = None

    def send_upload(self, filename: str) -> None:
        req = make_req_upload(filename=filename, ver=VER_GBN)
        self.send_data(req)
        
    def send_download(self, filename: str) -> None:
        req = make_req_download(filename=filename, ver=VER_GBN)
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
            
    ''' A USAR POR EL SENDER '''

    def send_data(self, datagrama: Datagrama, logger: Logger | None = None) -> None:
        if self.window.can_send():
            self.send_datagram(datagrama, logger)

        else:
            # Procesar ACKs de forma no bloqueante 
            ack_received = self.receive_ack()
            if ack_received:
                print(f"[DEBUG] ACK recibido, ventana base ahora en: {self.window.base}")

    def send_datagram(self, datagrama: Datagrama, logger: Logger | None = None):
        # Verificar timeout primero
        if self.timer is not None and (time.time() - self.timer) > self.rto:
            print("[DEBUG] Timeout - reenviando ventana completa")
            # timeout, reenvío todos los paquetes desde base hasta next_seq_num-1
            for i in range(self.window.base, self.window.next_seq_num):
                packet = self.window.get_packet(i)
                if packet is not None:
                    self.udp_socket.sendto(packet, self.client_addr)
                    print(f"[DEBUG] Reenviado paquete seq {i}")
            self.timer = time.time()
            return        
        
        try:
            encoded = datagrama.encode()
        except Exception:
            raise
          
        if self.window.can_send():
            self.udp_socket.sendto(encoded, self.client_addr)
            print(f"[DEBUG] Enviado paquete con seq: {datagrama.seq}")
            self.window.mark_sent(encoded)
            
            # Iniciar timer si es el primer paquete de la ventana
            if self.window.base == self.window.next_seq_num:
                self.timer = time.time()
        else:
            print("[DEBUG] Ventana llena, no se puede enviar")

    def receive_ack(self):
        self.udp_socket.settimeout(self.rto)

        try:
            bytes, _ = self.udp_socket.recvfrom(MTU)
        except SocketTimeout:
            return None
        
        try:
            datagram = Datagrama.decode(bytes)
            if datagram.typ == MsgType.ACK:
                print(f"[DEBUG] Recibido ACK para seq: {datagram.ack}")
                self.window.mark_received(datagram.ack)
                
                # Si la ventana se vacía, parar el timer
                if self.window.is_at_base():
                    self.timer = None
                else:
                    # Si aún hay paquetes en la ventana, reiniciar timer
                    self.timer = time.time()
                    
            return datagram
        
        except (Truncated, BadChecksum):
            return None

    ''' A USAR POR EL RECEIVER '''
        
    def receive_data(self):
        self.udp_socket.settimeout(self.rto)

        try:
            bytes, _ = self.udp_socket.recvfrom(MTU)
        except SocketTimeout:
            return None
        
        try:
            datagram = Datagrama.decode(bytes)
            print(f"[DEBUG] Recibido DATA GBN con seq {datagram.seq}, esperando seq {self.window.base}")
            
            # En el receptor, verificar si es el paquete esperado
            print(f"[DEBUG] Paquete recibido seq={datagram.seq}, esperado={self.window.base}")
            return datagram
        
        except (Truncated, BadChecksum):
            return None
        
    
    def send_ack(self, acknum: int):
        ack = make_ack(acknum=acknum, ver=VER_GBN)
        
        try:
            encoded = ack.encode()
        except Exception:
            raise
        
        self.udp_socket.sendto(encoded, self.client_addr)
    
    ''' aux '''

    def send_bye_with_retry(self, max_retries: int = 8, quiet_time: float = 0.2) -> bool:
        self.udp_socket.settimeout(self.rto)
        
        bye = make_bye(ver=VER_GBN)

        try:
            encoded = bye.encode()
        except Exception:
            raise

        for _ in range(max_retries):
            self.udp_socket.sendto(encoded, self.client_addr)
            
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

    def send_ok(self) -> None:
        ok = make_ok(ver=VER_GBN)

        try:
            encoded = ok.encode()
        except Exception:
            raise

        self.udp_socket.sendto(encoded, self.client_addr)

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
                