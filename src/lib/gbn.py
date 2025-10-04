from dataclasses import dataclass
from socket import socket, timeout as SocketTimeout
import time
from typing import Optional

from lib.config import RTO
from lib.logger import Logger
from lib.protocol import Protocol
from lib.protocolo_amcgf import FLAG_MF, MTU, VER_GBN, VER_SW, BadChecksum, Datagrama, MsgType, Truncated, make_ack, make_bye, make_ok, make_req_download, make_req_upload
from lib.window import Window

@dataclass  
class GoBackN(Protocol):
    rto: float = RTO 
    
    def __init__(self, sock: socket, client_addr: tuple[str, int], rto: float = RTO):
        super().__init__(sock, client_addr, rto)
        self.udp_socket = sock
        self.client_addr = client_addr
        self.rto = rto
        self.window = Window()
        self.timer = None
        self.expected_seq = 0 # Para el receiver

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

    def send_data(self, datagrama: Datagrama, logger: Logger | None = None) -> bool:
        # Verificar timeout
        print(f"[DEBUG] Timer: {self.timer}, RTO: {self.rto}")
        if self.timer is not None and (time.time() - self.timer) > self.rto:
            print("[DEBUG] Timeout - reenviando ventana completa")
            # Reenviar todos los paquetes en la ventana
            for i in range(self.window.base, self.window.next_seq_num):
                packet_data = self.window.get_packet(i)
                if packet_data is not None:
                    self.send_datagram(Datagrama.decode(packet_data), logger)
            self.timer = time.time()
            
        # Procesar ACKs disponibles
        self._process_available_acks()
        
        # Enviar nuevo paquete si hay espacio en la ventana
        if self.window.can_send():
            # Simulación de pérdida para testing
            ''' if datagrama.seq == 4 or datagrama.seq == 8:
                print("[DEBUG] Simulando pérdida de paquete con seq 4")
                if self.window.base == datagrama.seq:
                    self.timer = time.time()
                    
                # Guardar el paquete codificado en la ventana
                self.window.mark_sent(datagrama.encode())
                return True '''

            self.send_datagram(datagrama, logger)
            return True
        else:
            print("[DEBUG] Ventana llena, no se puede enviar")
            return False

    def send_datagram(self, datagrama: Datagrama, logger: Logger | None = None):      
        try:
            encoded = datagrama.encode()
        except Exception:
            raise
          
        self.udp_socket.sendto(encoded, self.client_addr)
        print(f"[DEBUG] Enviado paquete con seq: {datagrama.seq}")

        print(f"[DEBUG] Window base: {self.window.base}, datagrama seq: {datagrama.seq}")
        if self.window.base == datagrama.seq:
            self.timer = time.time()
            
        self.window.mark_sent(encoded)
        

    def _process_available_acks(self):
        """Procesa ACKs disponibles sin bloquear"""
        self.udp_socket.settimeout(self.rto)  
        
        try:
            while True:
                try:
                    bytes_data, _ = self.udp_socket.recvfrom(MTU)
                    
                    try:
                        datagram = Datagrama.decode(bytes_data)
                        if datagram.typ == MsgType.ACK:
                            print(f"[DEBUG] Recibido ACK para seq: {datagram.ack}")
                            
                            if datagram.ack >= self.window.base:
                                self.window.mark_received(datagram.ack)
                                
                                if self.window.base == datagram.ack:
                                    self.timer = None  
                                else:
                                    self.timer = time.time()  
                                    
                    except (Truncated, BadChecksum):
                        continue
                        
                except SocketTimeout:
                    break
                    
        finally:
            self.udp_socket.settimeout(self.rto)  

    def receive_ack(self) -> Optional[Datagrama]:
        self.udp_socket.settimeout(self.rto)

        try:
            bytes_data, _ = self.udp_socket.recvfrom(MTU)
            
            try:
                datagram = Datagrama.decode(bytes_data)
                if datagram.typ == MsgType.ACK:
                    print(f"[DEBUG] Recibido ACK para seq: {datagram.ack}")
                    
                    # ACK acumulativo
                    if datagram.ack >= self.window.base:
                        self.window.mark_received(datagram.ack)
                        
                        # Manejar timer
                        if self.window.base == self.window.next_seq_num:
                            self.timer = None
                        else:
                            self.timer = time.time()
                            
                    return datagram
                    
            except (Truncated, BadChecksum):
                return None
                
        except SocketTimeout:
            return None

    ''' A USAR POR EL RECEIVER '''
        
    def receive_data(self) -> Optional[Datagrama]:
        self.udp_socket.settimeout(self.rto)

        try:
            bytes_data, _ = self.udp_socket.recvfrom(MTU)
        except SocketTimeout:
            return None
        
        try:
            datagram = Datagrama.decode(bytes_data)
            #print(f"[DEBUG] Recibido DATA GBN con seq {datagram.seq}")
            #print(f"[DEBUG] Esperando seq {self.expected_seq}")
            
            if datagram.seq == self.expected_seq:
                self.expected_seq += 1
                return datagram
            else:
                # Paquete fuera de orden - se descarta
                #print(f"[DEBUG] Paquete fuera de orden, descartado")
                return None
        
        except (Truncated, BadChecksum):
            return None
        
    def send_ack(self, acknum: int):
        ack = make_ack(acknum=acknum, ver=VER_GBN)
        
        try:
            encoded = ack.encode()
        except Exception:
            raise
        
        print(f"[DEBUG] Enviando ACK {acknum}")
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
                bytes_data, _ = self.udp_socket.recvfrom(MTU)
            except SocketTimeout:
                continue
            
            try:
                datagram = Datagrama.decode(bytes_data)
            except (Truncated, BadChecksum):
                continue
            
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
                bytes_data, _ = self.udp_socket.recvfrom(MTU)
            except SocketTimeout:
                continue
            
            try:
                datagram = Datagrama.decode(bytes_data)
            except (Truncated, BadChecksum):
                continue
            
            if datagram.typ == MsgType.BYE:
                print("[DEBUG] Recibido BYE de peer, enviando OK MODO LINGER")
                self.send_ok()
                
                t_end = time.time() + linger_factor * self.rto
                self.udp_socket.settimeout(quiet_time)
                
                while time.time() < t_end:
                    try:
                        bytes_data, _ = self.udp_socket.recvfrom(MTU)
                    except SocketTimeout:
                        continue
                    
                    try:
                        datagram = Datagrama.decode(bytes_data)
                    except (Truncated, BadChecksum):
                        continue
                    
                    if datagram.typ == MsgType.BYE:
                        print("[DEBUG] REENVIO OK")
                        self.send_ok()
                        t_end = time.time() + linger_factor * self.rto
                
                return

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
            bytes_data, _ = self.udp_socket.recvfrom(MTU)
        except SocketTimeout:
            return False
        
        try:
            datagram = Datagrama.decode(bytes_data)
        except (Truncated, BadChecksum):
            return False
        
        return datagram.typ == MsgType.OK