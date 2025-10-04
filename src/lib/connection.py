from dataclasses import dataclass
from logging import Logger
from socket import socket, AF_INET, SOCK_DGRAM
from typing import Callable, Optional, Protocol

from lib.config import *
from lib.file_handler import FileHandler
from lib.protocol import Protocol, create_protocol
from lib.protocolo_amcgf import MTU, PAYLOAD_ERR_MSG_KEY, Datagram, MsgType, make_ok

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
    
    def _send_control(
            self,
            ver: int,
            req_bytes: bytes,
            timeout: float = TIMEOUT_MAX,
            rto: float = RTO,
            logger: Logger | None = None,
            recv_fn: Optional[Callable[[float], bytes | None]] | None = None
            ) -> tuple[Protocol | None, tuple[str, int] | None, socket | None]:
        """
        Client-side helper.
        Sends a control request (already encoded), waits for response, handles ERR, and returns a configured Protocol instance,
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
            logger.log_error(f"{ok.payload.decode().replace(f'{PAYLOAD_ERR_MSG_KEY}=', '')}")
            sock.close()
            return None, None, None

        return create_protocol(type=ver, sock=sock, addr=addr, rto=rto), addr, sock

    def _send_ok(
            self,
            ver: int,
            sock: socket,
            addr: tuple[str, int],
            rto: float = RTO,
            recv_fn: Optional[Callable[[float], bytes | None]] | None = None
            ) -> Protocol:
        """
        Server-side helper. Sends OK to the peer and returns a configured StopAndWait instance.
        """

        try:
            encoded = make_ok().encode()
        except Exception:
            raise

        sock.sendto(encoded, addr)

        return create_protocol(type=ver, sock=sock, addr=addr, rto=rto, recv_fn=recv_fn)
