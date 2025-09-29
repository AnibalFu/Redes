from dataclasses import dataclass
from socket import socket, AF_INET, SOCK_DGRAM

from lib.protocolo_amcgf import MTU, VER_SW, Datagrama, MsgType, make_ok
from lib.sw import StopAndWait

@dataclass
class Connection:
    verbose: bool = True
    quiet: bool = False
    host: str = '10.0.0.1'
    port: int = 6379
    protocol: int | None = None 

    def _make_udp_socket(self, timeout: float | None = None, bind_addr: tuple[str, int] | None = None) -> socket:
        """Create a UDP socket with optional timeout and optional bind address."""
        udp_socket = socket(AF_INET, SOCK_DGRAM)
        
        if bind_addr:
            udp_socket.bind(bind_addr)
        if timeout:
            udp_socket.settimeout(timeout)
        
        return udp_socket

    def _send_control_and_prepare_sw(self, req_bytes: bytes, timeout: float = 1.0, rto: float = 1.0) -> tuple[StopAndWait | None, tuple[str, int] | None, socket | None]:
        """
        Client-side helper.
        Sends a control request (already encoded), waits for response, handles ERR, and returns a configured StopAndWait instance,
        the peer address, and the underlying control socket. Returns (None, None, None) on ERR.
        """

        udp_socket = self._make_udp_socket(timeout=timeout)
        udp_socket.sendto(req_bytes, (self.host, self.port))

        bytes, addr = udp_socket.recvfrom(MTU)
        
        try:
            ok = Datagrama.decode(bytes)
        except Exception:
            raise
        
        if ok.typ == MsgType.ERR:
            udp_socket.close()
            return None, None, None

        sw = StopAndWait(udp_socket=udp_socket, peer=addr, rto=rto)

        return sw, addr, udp_socket

    def _send_ok_and_prepare_sw(self, udp_socket: socket, peer_addr: tuple[str, int], rto: float = 1.0) -> StopAndWait:
        """
        Server-side helper. Sends OK to the peer and returns a configured StopAndWait instance.
        """

        ok = make_ok(ver=VER_SW)
        
        try:
            encoded = ok.encode()
        except Exception:
            raise
        
        udp_socket.sendto(encoded, peer_addr)
        
        return StopAndWait(udp_socket=udp_socket, peer=peer_addr, rto=rto)