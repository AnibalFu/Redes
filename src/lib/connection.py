from dataclasses import dataclass
from socket import socket, AF_INET, SOCK_DGRAM
from lib.sw import StopAndWait
from lib.datagram_sending import *

@dataclass
class Connection:
    verbose: bool = True
    quiet: bool = False
    host: str = '10.0.0.1'
    port: int = 6379
    protocol: int | None = None 

    def _make_udp_socket(self, timeout: float | None = None, bind_addr: tuple[str, int] | None = None) -> socket:
        """Create a UDP socket with optional timeout and optional bind address."""
        sock = socket(AF_INET, SOCK_DGRAM)
        if bind_addr is not None:
            sock.bind(bind_addr)
        if timeout is not None:
            sock.settimeout(timeout)
        return sock

    def _send_control_and_prepare_sw(self, req_bytes: bytes, timeout: float = 1.0, rto: float = 1.0) -> tuple[StopAndWait | None, tuple[str, int] | None, socket | None]:
        """
        Client-side helper.
        Sends a control request (already encoded), waits for response, handles ERR, and returns a configured StopAndWait instance,
        the peer address, and the underlying control socket. Returns (None, None, None) on ERR.
        """
        ctrl = self._make_udp_socket(timeout=timeout)
        ctrl.sendto(req_bytes, (self.host, self.port))

        data, connection_addr = ctrl.recvfrom(MTU)
        ok = Datagrama.decode(data)
        if ok.typ == MsgType.ERR:
            ctrl.close()
            return None, None, None

        sw = StopAndWait(ctrl, connection_addr, rto=rto)
        return sw, connection_addr, ctrl

    def _send_ok_and_prepare_sw(self, sock: socket, peer_addr: tuple[str, int], rto: float = 1.0) -> StopAndWait:
        """
        Server-side helper. Sends OK to the peer and returns a configured StopAndWait instance.
        """
        ok = make_ok(ver=VER_SW)
        sock.sendto(ok.encode(), peer_addr)
        return StopAndWait(sock, peer_addr, rto=rto)