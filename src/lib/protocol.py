from abc import ABC, abstractmethod
from dataclasses import dataclass
from socket import socket, timeout as SocketTimeout
from typing import Optional, Callable

from lib.config import RTO, RETRY_MAX
from lib.logger import Logger
from lib.protocolo_amcgf import MTU, VER_GBN, VER_SW, BadChecksum, Datagram, Truncated
from lib.sw import StopAndWait
from lib.gbn import GoBackN

@dataclass
class Protocol(ABC):
    """
    Interfaz abstracta para protocolos de recuperación de errores.

    """

    rto: float = RTO
    sock: socket | None = None
    addr: tuple[str, int] | None = None
    recv_fn: Optional[Callable[[float], bytes | None]] | None = None
    
    def __post_init__(self):
        if not self.recv_fn:
            self.recv_fn = self._default_recv
        
    def _default_recv(self, timeout: float = RTO) -> Optional[bytes]:
        """Recibe datos directamente desde el socket (modo cliente)."""

        self.sock.settimeout(timeout)
        
        try:
            print("Recibiendo...")
            data, _ = self.sock.recvfrom(MTU)
            print("Recibido")
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

    # --------------------------------
    # MÉTODOS DE CONTROL DE CONEXIÓN
    # --------------------------------
    
    # @abstractmethod
    # def send_upload(self, filename: str) -> None:
    #     pass
    
    # @abstractmethod
    # def send_download(self, filename: str) -> None:
    #     pass
    
    # @abstractmethod
    # def receive_upload(self) -> Optional[Datagram]:
    #     pass
    
    # @abstractmethod
    # def receive_download(self) -> Optional[Datagram]:
    #     pass
    
    # ---------------------------------
    # MÉTODOS DE TRANSFERENCIA DE DATOS
    # ---------------------------------
    
    @abstractmethod
    def send_data(self, datagram: Datagram, logger: Optional[Logger] = None) -> bool:
        pass
    
    @abstractmethod
    def receive_data(self) -> Optional[Datagram]:
        pass
    
    @abstractmethod
    def send_ack(self, acknum: int) -> None:
        pass
    
    @abstractmethod
    def receive_ack(self) -> Optional[Datagram]:
        pass
    
    # -----------------------------
    # MÉTODOS DE CIERRE DE CONEXIÓN
    # -----------------------------
    
    @abstractmethod
    def send_bye_with_retry(self, max_retries: int = RETRY_MAX, quiet_time: float = 0.2) -> bool:
        pass
    
    @abstractmethod
    def await_bye_and_linger(self, linger_factor: int = 2, quiet_time: float = 0.2) -> None:
        pass
    
    @abstractmethod
    def send_ok(self) -> None:
        pass
    
    @abstractmethod
    def receive_ok(self) -> bool:
        pass

    @abstractmethod
    def send_bye(self) -> None:
        pass

# -------------------------------
# FACTORY PATTERN PARA PROTOCOLOS
# -------------------------------

def create_protocol(
        type: int,
        sock: socket,
        addr: tuple[str, int],
        rto: float = RTO,
        recv_fn: Optional[Callable[[float], bytes | None]] | None = None) -> Protocol:
    
    if type == VER_SW:
        return StopAndWait(sock=sock, addr=addr, rto=rto, recv_fn=recv_fn)

    elif type == VER_GBN:
        return GoBackN(sock=sock, addr=addr, rto=rto, recv_fn=recv_fn)

    else:
        raise ValueError(f"Tipo de protocolo no válido: {type}. Use 'SW' o 'GBN'")

# --------------------------------
# UTILS
# --------------------------------

@dataclass
class ProtocolMetrics:
    packets_sent: int = 0
    packets_received: int = 0
    retransmissions: int = 0
    timeouts: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def start_transfer(self) -> None:
        import time
        self.start_time = time.time()
    
    def end_transfer(self) -> None:
        import time
        self.end_time = time.time()
    
    def get_throughput(self, bytes_transferred: int) -> float:
        if not self.start_time or not self.end_time:
            return 0.0
        
        duration = self.end_time - self.start_time
        return bytes_transferred / duration if duration > 0 else 0.0
    
    def get_efficiency(self) -> float:
        total_transmissions = self.packets_sent + self.retransmissions
        if total_transmissions == 0:
            return 0.0
        
        return self.packets_sent / total_transmissions