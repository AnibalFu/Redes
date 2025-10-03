from abc import ABC, abstractmethod
from socket import socket
from typing import Optional, Tuple
from lib.gbn import GoBackN
from lib.logger import Logger
from lib.protocolo_amcgf import VER_GBN, VER_SW, Datagrama
from lib.sw import StopAndWait


class Protocol(ABC):
    """
    Interfaz abstracta para protocolos de recuperación de errores.

    """
    
    def __init__(self, sock: socket, client_addr: Tuple[str, int], rto: float):

        self.udp_socket = sock
        self.client_addr = client_addr
        self.rto = rto
    
    # --------------------------------
    # MÉTODOS DE CONTROL DE CONEXIÓN
    # --------------------------------
    
    @abstractmethod
    def send_upload(self, filename: str) -> None:
        pass
    
    @abstractmethod
    def send_download(self, filename: str) -> None:
        pass
    
    @abstractmethod
    def receive_upload(self) -> Optional[Datagrama]:
        pass
    
    @abstractmethod
    def receive_download(self) -> Optional[Datagrama]:
        pass
    
    # ---------------------------------
    # MÉTODOS DE TRANSFERENCIA DE DATOS
    # ---------------------------------
    
    @abstractmethod
    def send_data(self, datagrama: Datagrama, logger: Optional[Logger] = None) -> None:
        pass
    
    @abstractmethod
    def receive_data(self) -> Optional[Datagrama]:
        pass
    
    @abstractmethod
    def send_ack(self, acknum: int) -> None:
        pass
    
    @abstractmethod
    def receive_ack(self) -> Optional[Datagrama]:
        pass
    
    # -----------------------------
    # MÉTODOS DE CIERRE DE CONEXIÓN
    # -----------------------------
    
    @abstractmethod
    def send_bye_with_retry(self, max_retries: int = 8, quiet_time: float = 0.2) -> bool:
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


# -------------------------------
# FACTORY PATTERN PARA PROTOCOLOS
# -------------------------------

def create_protocol(protocol_type: int, sock: socket, client_addr: Tuple[str, int], rto: float = 1.0) -> Protocol:

    if protocol_type == VER_SW:
        return StopAndWait(udp_socket=sock, peer=client_addr, rto=rto)
    
    elif protocol_type == VER_GBN:
        return GoBackN(sock=sock, client_addr=client_addr, rto=rto)
    
    else:
        raise ValueError(f"Tipo de protocolo no válido: {protocol_type}. Use 'SW' o 'GBN'")


# --------------------------------
# UTILS
# --------------------------------

class ProtocolMetrics:
    
    def __init__(self):
        self.packets_sent = 0
        self.packets_received = 0
        self.retransmissions = 0
        self.timeouts = 0
        self.start_time = None
        self.end_time = None
    
    def start_transfer(self):
        import time
        self.start_time = time.time()
    
    def end_transfer(self):
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