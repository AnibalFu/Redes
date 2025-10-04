import time

from dataclasses import dataclass
from typing import Callable, Optional
from socket import socket

from lib.config import RTO
from lib.logger import Logger
from lib.window import Window
from lib.protocolo_amcgf import *
from lib.protocol import Protocol

@dataclass  
class GoBackN(Protocol):
    window: Window | None = None
    timer: float | None = None
    expected_seq: int = 0

    def __init__(
            self,
            sock: socket,
            addr: tuple[str, int],
            rto: float = RTO,
            recv_fn: Optional[Callable[[float], bytes | None]] | None = None) -> None:
        
        super().__init__(rto=rto, sock=sock, addr=addr, recv_fn=recv_fn)
        self.window = Window()
        self.timer = None

    # --------------------------------
    # MÉTODOS DE CONTROL DE CONEXIÓN
    # --------------------------------

    def send_upload(self, filename: str) -> None:
        req = make_req_upload(filename=filename, ver=VER_GBN)
        self.send_data(req)
        
    def send_download(self, filename: str) -> None:
        req = make_req_download(filename=filename, ver=VER_GBN)
        self.send_data(req)

    def receive_upload(self) -> Optional[Datagram]:
        while True:
            datagram = self.receive_data()
            if not datagram:
                continue
            
            if datagram.typ == MsgType.REQUEST_UPLOAD:
                return datagram

    def receive_download(self) -> Optional[Datagram]:
        while True:
            datagram = self.receive_data()
            if not datagram:
                continue
            if datagram.typ == MsgType.REQUEST_DOWNLOAD:
                return datagram
            
    # ---------------------------------
    # MÉTODOS DE TRANSFERENCIA DE DATOS
    # ---------------------------------

    def send_data(self, datagram: Datagram, logger: Logger | None = None) -> bool:
        # Verificar timeout
        print(f"[DEBUG] Timer: {self.timer}, RTO: {self.rto}")
        
        if self.timer is not None and (time.time() - self.timer) > self.rto:
            print("[DEBUG] Timeout - reenviando ventana completa")
            # Reenviar todos los paquetes en la ventana
            for i in range(self.window.base, self.window.next_seq_num):
                packet_data = self.window.get_packet(i)
                if packet_data is not None:
                    decoded = self._safe_decode(packet_data)
                    if not decoded:
                        return False

                    self._send_datagram(datagram=decoded, logger=logger)

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

            self._send_datagram(datagram=datagram, logger=logger)
            return True
        else:
            print("[DEBUG] Ventana llena, no se puede enviar")
            return False

    def receive_data(self) -> Optional[Datagram]:
        raw_bytes = self.recv_fn(self.rto)
        if not raw_bytes:
            return None
        
        datagram = self._safe_decode(raw_bytes)
        if not datagram:
            return None
        
        if datagram.seq == self.expected_seq:
            self.expected_seq += 1
            return datagram
        else:
            # Paquete fuera de orden - se descarta
            return None

    def send_ack(self, acknum: int) -> None:
        try:
            encoded = make_ack(acknum=acknum, ver=VER_GBN).encode()
        except Exception:
            raise
        
        self.sock.sendto(encoded, self.addr)

    def receive_ack(self) -> Optional[Datagram]:
        raw_bytes = self.recv_fn(self.rto)
        if not raw_bytes:
            return None
        
        datagram = self._safe_decode(raw_bytes)
        if not datagram:
            return None

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
        
        return None

    def _send_datagram(self, datagram: Datagram, logger: Logger | None = None) -> None:
        encoded = self._safe_encode(datagram)
        if not encoded:
            return
          
        self.sock.sendto(encoded, self.addr)
        print(f"[DEBUG] Enviado paquete con seq: {datagram.seq}")

        print(f"[DEBUG] Window base: {self.window.base}, datagrama seq: {datagram.seq}")
        if self.window.base == datagram.seq:
            self.timer = time.time()
            
        self.window.mark_sent(encoded)
        
    def _process_available_acks(self) -> None:
        """Procesa ACKs disponibles sin bloquear"""

        while True:
            raw_bytes = self.recv_fn(self.rto)
            if not raw_bytes:
                return None 
            
            datagram = self._safe_decode(raw_bytes)
            if not datagram:
                continue

            if datagram.typ == MsgType.ACK:
                print(f"[DEBUG] Recibido ACK para seq: {datagram.ack}")
                
                if datagram.ack >= self.window.base:
                    self.window.mark_received(datagram.ack)
                    
                    if self.window.base == datagram.ack:
                        self.timer = None  
                    else:
                        self.timer = time.time()  

    # -----------------------------
    # MÉTODOS DE CIERRE DE CONEXIÓN
    # -----------------------------

    def send_bye_with_retry(self, max_retries: int = 8, quiet_time: float = 0.2) -> bool:

        for _ in range(max_retries):
            try:
                self.send_bye()
            except Exception:
                continue

            raw_bytes = self.recv_fn(self.rto)
            if not raw_bytes:
                continue

            datagram = self._safe_decode(raw_bytes)
            if not datagram:
                continue
            
            if datagram.typ == MsgType.OK:
                t_end = time.time() + quiet_time
                
                while time.time() < t_end:
                    raw_bytes = self.recv_fn(self.rto)
                    if not raw_bytes:
                        break

                return True
            
        return False
    
    def await_bye_and_linger(self, linger_factor: int = 2, quiet_time: float = 0.2) -> None:
        while True:
            raw_bytes = self.recv_fn(self.rto)
            if not raw_bytes:
                continue

            datagram = self._safe_decode(raw_bytes)
            if not datagram:
                continue
            
            if datagram.typ == MsgType.BYE:
                print("[DEBUG] Recibido BYE de peer, enviando OK MODO LINGER")
                self.send_ok()
                
                t_end = time.time() + linger_factor * self.rto
                
                while time.time() < t_end:
                    raw_bytes = self.recv_fn(self.rto)
                    if not raw_bytes:
                        continue

                    datagram = self._safe_decode(raw_bytes)
                    if not datagram:
                        continue
                    
                    if datagram.typ == MsgType.BYE:
                        print("[DEBUG] REENVIO OK")
                        self.send_ok()
                        t_end = time.time() + linger_factor * self.rto
                
                return

    def send_ok(self) -> None:
        try:
            encoded = make_ok(ver=VER_GBN).encode()
        except Exception:
            raise

        self.sock.sendto(encoded, self.addr)

    def receive_ok(self) -> bool:
        raw_bytes = self.recv_fn(self.rto)
        if not raw_bytes:
            return False
        
        datagram = self._safe_decode(raw_bytes)
        if not datagram:
            return False
        
        return datagram.typ == MsgType.OK
    
    def send_bye(self):
        try:
            encoded = make_bye(ver=VER_GBN).encode()
        except Exception:
            raise

        self.sock.sendto(encoded, self.addr)