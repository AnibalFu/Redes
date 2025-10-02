from queue import Empty, Queue
import time

from dataclasses import dataclass
from socket import socket, timeout as SocketTimeout
from typing import Callable, Tuple, Optional
from lib.logger import Logger
from lib.protocolo_amcgf import *
import time
from lib.config import *

@dataclass
class StopAndWait:
    udp_socket: socket # Mio
    peer: Tuple[str, int] # Suyo
    recv_fn: Optional[Callable[[float], bytes | None]] = None
    rto: float = RTO # Retardo de timeout

    def __post_init__(self):
        if not self.recv_fn:
            self.recv_fn = self._default_recv
    
    def _default_recv(self, timeout: float) -> Optional[bytes]:
        """Recibe datos directamente desde el socket (modo cliente)."""
        self.udp_socket.settimeout(timeout)
        try:
            data, _ = self.udp_socket.recvfrom(MTU)
            return data
        except SocketTimeout:
            return None

    def safe_encode(self, datagrama: Datagrama) -> bytes:
        try:
            encoded = datagrama.encode()
        except Exception:
            raise
        return encoded
    
    def safe_decode(self, data: bytes) -> Optional[Datagrama]:
        try:
            datagram = Datagrama.decode(data)
        except (Truncated, BadChecksum):
            return None
        return datagram

    def send_data(self, datagrama: Datagrama, logger: Logger | None = None) -> int:
        encoded = self.safe_encode(datagrama)
        expected_ack = datagrama.seq + 1

        while True:       
            self.udp_socket.sendto(encoded, self.peer)
            t0 = time.time()
            
            while True:
                raw = self.recv_fn(self.rto)   
                if raw is None:
                    break  
                
                datagram = self.safe_decode(raw)
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

    def receive_data(self) -> Optional[Datagrama]:
        """Recibe un datagrama decodificado usando la función recv_fn."""
        raw = self.recv_fn(self.rto)
        if raw is None:
            return None
        return self.safe_decode(raw)

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
        """Envía BYE y espera un OK. Funciona tanto en server (cola) como en cliente (socket)."""
        bye = make_bye(ver=VER_SW)
        encoded = self.safe_encode(bye)

        for _ in range(max_retries):
            self.udp_socket.sendto(encoded, self.peer)

            raw = self.recv_fn(self.rto)
            if raw is None:
                continue

            datagram = self.safe_decode(raw)
            if datagram is None:
                continue

            if datagram.typ == MsgType.OK:
                # Modo LINGER
                t_end = time.time() + quiet_time
                while time.time() < t_end:
                    raw = self.recv_fn(quiet_time)
                    if raw is None:
                        break
                    datagram = self.safe_decode(raw)
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

            datagram = self.safe_decode(raw)
            if datagram is None:
                continue

            if datagram.typ == MsgType.BYE:
                print("[DEBUG] Recibido BYE de peer, enviando OK MODO LINGER")
                self.udp_socket.sendto(make_ok(ver=VER_SW).encode(), self.peer)

                t_end = time.time() + linger_factor * self.rto

                while time.time() < t_end:
                    raw = self.recv_fn(quiet_time)
                    if raw is None:
                        continue

                    datagram = self.safe_decode(raw)
                    if datagram is None:
                        continue

                    if datagram.typ == MsgType.BYE:
                        print("[DEBUG] REENVIO OK")
                        self.udp_socket.sendto(make_ok(ver=VER_SW).encode(), self.peer)
                        # resetear linger
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