from dataclasses import dataclass
from socket import socket, AF_INET, SOCK_DGRAM

from lib.gbn import GoBackN
from lib.protocolo_amcgf import MTU, PAYLOAD_ERR_MSG_KEY, VER_GBN, VER_SW, Datagrama, MsgType, make_ok
from lib.sw import StopAndWait
from lib.config import *

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

    def _send_control_and_prepare_sw(self, req_bytes: bytes, timeout: float = TIMEOUT_MAX, rto: float = RTO) -> tuple[StopAndWait | None, tuple[str, int] | None, socket | None]:
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
            print(f"[SERVER ERROR] {ok.payload.decode().replace(f'{PAYLOAD_ERR_MSG_KEY}=', '')}")
            udp_socket.close()
            return None, None, None

        sw = StopAndWait(udp_socket=udp_socket, peer=addr, rto=rto)
        
        return sw, addr, udp_socket


    def _send_ok_and_prepare_sw(self, sock: socket, peer_addr: tuple[str, int], rto: float = RTO) -> StopAndWait:
        """
        Server-side helper. Sends OK to the peer and returns a configured StopAndWait instance.
        """

        ok = make_ok(ver=VER_SW)
        
        try:
            encoded = ok.encode()
        except Exception:
            raise
        
        sock.sendto(encoded, peer_addr)
        
        return StopAndWait(udp_socket=sock, peer=peer_addr, rto=rto)

    def _send_ok_and_prepare_gbn(self, sock: socket, peer_addr: tuple[str, int], rto: float = RTO) -> StopAndWait:
        """
        Server-side helper. Sends OK to the peer and returns a configured GoBackN instance.
        """

        ok = make_ok(ver=VER_GBN)
        
        try:
            encoded = ok.encode()
        except Exception:
            raise
        
        sock.sendto(encoded, peer_addr)
        
        return GoBackN(sock, peer_addr, rto=rto)

    def _send_control_and_prepare_gbn(self, req_bytes: bytes, timeout: float = TIMEOUT_MAX, rto: float = RTO) -> tuple[GoBackN | None, tuple[str, int] | None, socket | None]:
        """
        Client-side helper.
        Sends a control request (already encoded), waits for response, handles ERR, and returns a configured GoBackN instance,
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
            print(f"[SERVER ERROR] {ok.payload.decode().replace(f'{PAYLOAD_ERR_MSG_KEY}=', '')}")
            udp_socket.close()
            return None, None, None

        gbn = GoBackN(udp_socket, addr, rto)
        
        return gbn, addr, udp_socket