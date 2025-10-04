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
    host: str = IP_SERVER_DEFAULT
    port: int = PORT_SERVER_DEFAULT
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
            _recv_fn: Optional[Callable[[float], bytes | None]] | None = None
            ) -> tuple[Protocol | None, tuple[str, int] | None, socket | None]:
        """
        Client-side helper.
        Sends a control request (already encoded), waits for response, handles ERR, and returns a configured Protocol instance,
        the peer address, and the underlying control socket. Returns (None, None, None) on ERR.
        """

        sock = self._make_udp_socket(timeout=timeout)
        
        # Handshake: termina cuando recibo OK, con reintentos maximos
        addr = None
        ok_datagram = None
        for i in range(1, RETRY_MAX + 2):
            try:
                sock.settimeout(timeout * i)   
                sock.sendto(req_bytes, (self.host, self.port))
                data, addr = sock.recvfrom(MTU)
                # Intentar decodificar
                try:
                    d = Datagram.decode(data)
                except Exception:
                    # paquete invalido, reintentar
                    continue

                if d.typ == MsgType.OK:
                    ok_datagram = d
                    break
                
                if d.typ == MsgType.ERR:
                    if logger:
                        try:
                            msg = d.payload.decode().replace(f"{PAYLOAD_ERR_MSG_KEY}=", "")
                        except Exception:
                            msg = "Unknown error"
                        logger.log_error(f"[ERROR] {msg}")
                    sock.close()
                    return None, None, None
                
                # Otro tipo inesperado, reintentar
                continue
            except Exception:
                # timeout u otro error, reintentar hasta agotar RETRY_MAX
                continue
        
        # Si no hubo OK en los reintentos, fallar
        if ok_datagram is None or addr is None:
            if logger:
                logger.log_error("[ERROR] Handshake no completado: no se recibio OK")
            try:
                sock.close()
            except Exception:
                pass
            return None, None, None

        # Exito: devolver el protocolo configurado
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
        Server-side helper. Sends OK to the peer and returns a configured StopAndWait or GoBackN instance.
        """

        try:
            encoded = make_ok().encode()
        except Exception:
            raise

        sock.sendto(encoded, addr)

        return create_protocol(type=ver, sock=sock, addr=addr, rto=rto, recv_fn=recv_fn)
