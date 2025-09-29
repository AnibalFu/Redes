from dataclasses import dataclass
from socket import socket, timeout as SocketTimeout
from typing import Tuple, Optional
from lib.protocolo_amcgf import *

@dataclass
class StopAndWait:
    sock: socket # Mio
    peer: Tuple[str, int] # Suyo
    rto: float = 1.0 # Retardo de timeout
    
    #########################
    def send_upload(self, filename: str) -> None:
        req = make_req_upload(filename, VER_SW)
        self.send_data(req)
        
    def send_download(self, filename: str) -> None:
        req = make_req_download(filename, VER_SW)
        self.send_data(req)

    def receive_upload(self) -> Optional["Datagrama"]:
        while True:
            d = self.receive_data()
            if d is None:
                continue
            if d.typ == MsgType.REQUEST_UPLOAD:
                return d

    def receive_download(self) -> Optional["Datagrama"]:
        while True:
            d = self.receive_data()
            if d is None:
                continue
            if d.typ == MsgType.REQUEST_DOWNLOAD:
                return d
    #########################


    # Se lo mando a peer
    def send_data(self, datagrama: "Datagrama") -> int:
        # Configurar timeout operativo
        self.sock.settimeout(self.rto)
        encoded = datagrama.encode()
        acknum_esperado = datagrama.seq + 1

        # 1) Drenar posibles ACKs/paquetes viejos que hayan quedado en el buffer
        #    para que el primer recvfrom de este ciclo no lea un ACK duplicado anterior.
        prev_timeout = self.sock.gettimeout()
        try:
            # Non-blocking drain
            self.sock.settimeout(0)
            while True:
                try:
                    _data, _ = self.sock.recvfrom(MTU)
                except SocketTimeout:
                    break
                except Exception:
                    break
        finally:
            # Restaurar timeout operativo
            self.sock.settimeout(prev_timeout)

        # 2) Bucle de envio/espera de ACK
        while True:
            self.sock.sendto(encoded, self.peer)

            # Esperar ACK o timeout
            try:
                data, _ = self.sock.recvfrom(MTU)
            except SocketTimeout:
                # Timeout: reintentar retransmitiendo
                continue

            # Decodificar y verificar ACK
            try:
                d = Datagrama.decode(data)
            except (Truncated, BadChecksum):
                # Corrupcion: ignorar y seguir esperando
                continue
            
            if d.typ == MsgType.ACK and d.ack == acknum_esperado:
                return len(encoded)
            
            # Si llega un ACK viejo/duplicado (d.ack != esperado), ignorar y seguir esperando
            # Tambien ignoramos cualquier otro tipo de mensaje inesperado en este contexto

    # Recibo de peer
    def receive_data(self) -> Optional["Datagrama"]:
        self.sock.settimeout(self.rto)
        try:
            data, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return None
        
        try:
            d = Datagrama.decode(data)
        except (Truncated, BadChecksum):
            return None
        
        return d

    # Se lo mando a peer
    def send_ack(self, acknum: int) -> None:
        ack = make_ack(acknum=acknum, ver=VER_SW)
        self.sock.sendto(ack.encode(), self.peer)

    # Recibo de peer
    def receive_ack(self, expected_ack: int) -> bool:
        self.sock.settimeout(self.rto)
        try:
            data, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return False
        try:
            d = Datagrama.decode(data)
        except (Truncated, BadChecksum):
            return False
        
        return d.typ == MsgType.ACK and d.ack == expected_ack

    # Se lo mando a peer
    def send_bye(self) -> None:
        bye = make_bye(ver=VER_SW)
        self.sock.sendto(bye.encode(), self.peer)
        
    # Recibo de peer
    def receive_bye(self) -> bool:
        self.sock.settimeout(self.rto)
        try:
            data, _ = self.sock.recvfrom(MTU)
        except SocketTimeout:
            return False
        try:
            d = Datagrama.decode(data)
        except (Truncated, BadChecksum):
            return False
        
        return d.typ == MsgType.BYE