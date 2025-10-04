from socket import socket
import time

from dataclasses import dataclass
from typing import Callable, Optional

from lib.protocol import Protocol
from lib.config import *
from lib.logger import Logger
from lib.protocolo_amcgf import *

@dataclass
class StopAndWait(Protocol):

    def __init__(
            self,
            sock: socket,
            addr: tuple[str, int],
            rto: float = RTO,
            recv_fn: Optional[Callable[[float], bytes | None]] | None = None) -> None:

        super().__init__(rto=rto, sock=sock, addr=addr, recv_fn=recv_fn)

    # --------------------------------
    # MÉTODOS DE CONTROL DE CONEXIÓN
    # --------------------------------

    def send_upload(self, filename: str):
        req = make_req_upload(filename=filename, ver=VER_SW)
        self.send_data(req)

    def send_download(self, filename: str):
        req = make_req_download(filename=filename, ver=VER_SW)
        self.send_data(req)

    def receive_upload(self) -> Optional[Datagram]:
        """Espera un REQUEST_UPLOAD y lo devuelve decodificado."""

        while True:
            datagram = self.receive_data()
            if not datagram:
                continue
            
            if datagram.typ == MsgType.REQUEST_UPLOAD:
                return datagram
    
    def receive_download(self) -> Optional[Datagram]:
        """Espera un REQUEST_DOWNLOAD y lo devuelve decodificado."""

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
        expected_ack = datagram.seq + 1
        
        encoded = self._safe_encode(datagram)
        if not encoded:
            return 0

        while True:
            self.sock.sendto(encoded, self.addr)
            
            t0 = time.time()
            while True:
                raw = self.recv_fn(self.rto)   
                if raw is None:
                    break
                
                datagram = self._safe_decode(raw)
                if datagram is None:
                    continue
                
                if datagram.typ != MsgType.ACK:
                    continue
                
                if datagram.ack == expected_ack:
                    if logger:
                        rtt = time.time() - t0  
                        logger.log_rtt(rtt * 1000) 
                
                    return True
                
                elif datagram.ack < expected_ack:
                    continue
                
                elif time.time() - t0 > self.rto:
                    break
        
    def receive_data(self) -> Optional[Datagram]:
        """Recibe un datagrama decodificado usando la función recv_fn."""

        raw_bytes = self.recv_fn(self.rto)
        
        if not raw_bytes:
            return None
        
        return self._safe_decode(raw_bytes)

    def send_ack(self, acknum: int) -> None:
        try:
            encoded = make_ack(acknum=acknum, ver=VER_SW).encode()
        except Exception:
            raise

        self.sock.sendto(encoded, self.addr)

    def receive_ack(self, expected_ack: int) -> bool:
        raw_bytes = self.recv_fn(self.rto)
        if not raw_bytes:
            return False
        
        try:
            datagram = Datagram.decode(raw_bytes)
        except (Truncated, BadChecksum):
            return False
        
        return datagram.typ == MsgType.ACK and datagram.ack == expected_ack

    # -----------------------------
    # MÉTODOS DE CIERRE DE CONEXIÓN
    # -----------------------------

    def send_bye_with_retry(self, max_retries: int = 8, quiet_time: float = 0.2) -> bool:
        """Envía BYE y espera un OK. Funciona tanto en server (cola) como en cliente (socket)."""

        for _ in range(max_retries):
            encoded = self._safe_encode(make_bye(ver=VER_SW))
            if not encoded:
                continue
            
            self.sock.sendto(encoded, self.addr)

            raw_bytes = self.recv_fn(self.rto)
            if not raw_bytes:
                continue

            datagram = self._safe_decode(raw_bytes)
            if datagram is None:
                continue

            if datagram.typ == MsgType.OK:
                t_end = time.time() + quiet_time
                while time.time() < t_end:
                    raw = self.recv_fn(quiet_time)
                    if raw is None:
                        break
                
                    datagram = self._safe_decode(raw)
                    if datagram and datagram.typ == MsgType.OK:
                        # ignorar reenvíos de OK
                        continue
                
                return True

        return False

    def await_bye_and_linger(self, linger_factor: int = 2, quiet_time: float = 0.2) -> None:
        """Espera un BYE del peer y responde con OK, manejando linger.
        Funciona tanto en server (cola) como en cliente (socket)."""
        
        while True:
            raw = self.recv_fn(self.rto)
            if raw is None:
                continue

            datagram = self._safe_decode(raw)
            if datagram is None:
                continue

            if datagram.typ == MsgType.BYE:
                encoded = self._safe_encode(make_ok(ver=VER_SW))
                if not encoded:
                    continue
                
                self.sock.sendto(encoded, self.addr)

                t_end = time.time() + linger_factor * self.rto

                while time.time() < t_end:
                    raw = self.recv_fn(quiet_time)
                    if raw is None:
                        continue

                    datagram = self._safe_decode(raw)
                    if datagram is None:
                        continue

                    if datagram.typ == MsgType.BYE:
                        encoded = self._safe_encode(make_ok(ver=VER_SW))
                        if not encoded:
                            continue
                        
                        self.sock.sendto(encoded, self.addr)
                        # resetear linger
                        t_end = time.time() + linger_factor * self.rto
                return

    def send_ok(self) -> None:
        try:
            encoded = make_ok(ver=VER_SW).encode()
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
    
    def send_bye(self) -> None:
        try:
            encoded = make_bye(ver=VER_SW).encode()
        except Exception:
            raise

        self.sock.sendto(encoded, self.addr)        