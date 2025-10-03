from dataclasses import dataclass

from lib.file_handler import FileHandler
from socket import socket, AF_INET, SOCK_DGRAM

from lib.protocolo_amcgf import MTU, PAYLOAD_ERR_MSG_KEY, Datagram, MsgType, make_ok
from lib.sw import StopAndWait
from lib.config import *

@dataclass
class Connection:
    verbose: bool = True
    quiet: bool = False
    host: str = '10.0.0.1'
    port: int = 6379
    protocol: int | None = None
    file_handler: FileHandler | None = None

    def _make_udp_socket(self, timeout: float | None = None, bind_addr: tuple[str, int] | None = None) -> socket:
        """Create a UDP socket with optional timeout and optional bind address."""
        sock = socket(AF_INET, SOCK_DGRAM)
        
        if bind_addr:
            sock.bind(bind_addr)
        if timeout:
            sock.settimeout(timeout)
        
        return sock

    def _send_control_and_prepare_sw(self, req_bytes: bytes, timeout: float = TIMEOUT_MAX, rto: float = RTO) -> tuple[StopAndWait | None, tuple[str, int] | None, socket | None]:
        """
        Client-side helper.
        Sends a control request (already encoded), waits for response, handles ERR, and returns a configured StopAndWait instance,
        the peer address, and the underlying control socket. Returns (None, None, None) on ERR.
        """

        sock = self._make_udp_socket(timeout=timeout)
        sock.sendto(req_bytes, (self.host, self.port))

        bytes, addr = sock.recvfrom(MTU)
        
        try:
            ok = Datagram.decode(bytes)
        except Exception:
            raise
        
        if ok.typ == MsgType.ERR:
            print(f"[ERROR] {ok.payload.decode().replace(f'{PAYLOAD_ERR_MSG_KEY}=', '')}")
            sock.close()
            return None, None, None

        sw = StopAndWait(sock=sock, peer=addr, rto=rto)
        
        return sw, addr, sock

    def _send_ok_and_prepare_sw(self, sock: socket, peer_addr: tuple[str, int], rto: float = RTO, rcv = None) -> StopAndWait:
        """
        Server-side helper. Sends OK to the peer and returns a configured StopAndWait instance.
        """

        ok = make_ok()
        
        try:
            encoded = ok.encode()
        except Exception:
            raise
        
        sock.sendto(encoded, peer_addr)
        
        return StopAndWait(sock=sock, peer=peer_addr, rto=rto, recv_fn=rcv)