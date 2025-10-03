import time

from dataclasses import dataclass
from socket import socket, timeout as SocketTimeout
from typing import Callable, Tuple, Optional

from lib.logger import Logger
from lib.protocolo_amcgf import *
from lib.config import *

@dataclass
class StopAndWait:
    rto: float = RTO
    sock: socket | None = None
    peer: Tuple[str, int] | None = None
    recv_fn: Optional[Callable[[float], bytes | None]] | None = None

    def __post_init__(self):
        if not self.recv_fn:
            self.recv_fn = self._default_recv
    
    def _default_recv(self, timeout: float = RTO) -> Optional[bytes]:
        """Recibe datos directamente desde el socket (modo cliente)."""

        self.sock.settimeout(timeout)
        
        try:
            data, _ = self.sock.recvfrom(MTU)
            return data
        except SocketTimeout:
            return None

    def _safe_encode(self, datagrama: Datagram) -> bytes | None:
        try:
            encoded = datagrama.encode()
        except Exception:
            return None
        
        return encoded
    
    def _safe_decode(self, data: bytes) -> Optional[Datagram] | None:
        try:
            datagram = Datagram.decode(data)
        except (Truncated, BadChecksum):
            return None
        
        return datagram

    def send_data(self, datagrama: Datagram, logger: Logger | None = None) -> int:
        expected_ack = datagrama.seq + 1
        
        encoded = self._safe_encode(datagrama)
        if not encoded:
            return 0

        while True:       
            self.sock.sendto(encoded, self.peer)
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
                
                    return len(encoded)
                
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
        
        self.sock.sendto(encoded, self.peer)

    def receive_ack(self, expected_ack: int) -> bool:
        self.sock.settimeout(self.rto)
        
        try:
            bytes, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return False
        
        try:
            datagram = Datagram.decode(bytes)
        except (Truncated, BadChecksum):
            return False
        
        return datagram.typ == MsgType.ACK and datagram.ack == expected_ack

    def send_bye(self) -> None:
        bye = make_bye(ver=VER_SW)

        try:
            encoded = bye.encode()
        except Exception:
            raise

        self.sock.sendto(encoded, self.peer)
        
    def send_bye_with_retry(self, retries: int = 8, quiet_time: float = 0.2) -> bool:
        """Envía BYE y espera un OK. Funciona tanto en server (cola) como en cliente (socket)."""

        for _ in range(retries):
            encoded = self._safe_encode(make_bye(ver=VER_SW))
            if not encoded:
                continue
            
            self.sock.sendto(encoded, self.peer)

            raw_bytes = self.recv_fn(self.rto)
            if not raw_bytes:
                continue

            datagram = self._safe_decode(raw_bytes)
            if datagram is None:
                continue

            if datagram.typ == MsgType.OK:
                # Modo LINGER
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
                
                self.sock.sendto(encoded, self.peer)

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
                        
                        self.sock.sendto(encoded, self.peer)
                        # resetear linger
                        t_end = time.time() + linger_factor * self.rto
                return

    def receive_bye(self) -> bool:
        self.sock.settimeout(self.rto)

        try:
            bytes, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return False
        
        try:
            datagram = Datagram.decode(bytes)
        except (Truncated, BadChecksum):
            return False
        
        return datagram.typ == MsgType.BYE
    
    def send_ok(self) -> None:
        ok = make_ok(ver=VER_SW)

        try:
            encoded = ok.encode()
        except Exception:
            raise

        self.sock.sendto(encoded, self.peer)

    def receive_ok(self) -> bool:
        self.sock.settimeout(self.rto)
        
        try:
            bytes, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return False
        
        try:
            datagram = Datagram.decode(bytes)
        except (Truncated, BadChecksum):
            return False
        
        return datagram.typ == MsgType.OK