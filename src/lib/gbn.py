from dataclasses import dataclass
from socket import socket

from lib.logger import Logger
from src.lib.protocolo_amcgf import Datagram

@dataclass  
class GoBackN:
    def __init__(self, sock: socket, client_addr: tuple[str, int]):
        self.sock = sock
        self.client_addr = client_addr
            
    def send_data(self, datagram: Datagram, logger: Logger | None):
        pass
        
    def receive_data(self):
       pass 
    
    def send_ack(self, acknum: int):
        pass
    
    def receive_ack(self):
        pass