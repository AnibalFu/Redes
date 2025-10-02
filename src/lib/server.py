import threading

from time import time
from typing import Tuple
from queue import Empty, Queue
from socket import AF_INET, SOCK_DGRAM, socket
from dataclasses import dataclass

from lib.fileHandler import FileHandler
from lib.connection import Connection
from lib.config import *
from lib.protocolo_amcgf import *
        
# A futuro restar key de data
CHUNK_SIZE = MSS
DEFAULT_STORAGE_PATH = './storage_data'

@dataclass
class Server(Connection):
    file_handler: FileHandler = None
    queues = dict()

    def run(self):
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.bind((self.host, self.port))

        print(f"Server listening at {self.host}:{self.port}")

        while True:
            data, addr = sock.recvfrom(MTU)
            if len(data) < HDR_SIZE:
                continue 

            if addr not in self.queues:
                queue = Queue()
                self.queues[addr] = queue

                threading.Thread(target=self.process_client, args=(addr, sock, queue), daemon=True).start()
            else:
                queue = self.queues[addr]

            queue.put(data)

    def process_client(self, addr: tuple[str, int], sock: socket, queue: Queue):
        data = queue.get(block=True)
        
        try:
            datagram = Datagrama.decode(buf=data)
        except Exception:
            try:
                encoded = make_err("Error: Error al decodificar datagrama").encode()
            except Exception:
                raise

            sock.sendto(encoded, addr)
            return
            
        if datagram.typ == MsgType.REQUEST_UPLOAD:
            payload = payload_decode(datagram.payload)
            
            filename = payload[PAYLOAD_FILENAME_KEY]
            file_size = payload[FILE_SIZE_KEY]

            if file_size > MAX_FILE_SIZE:
                try:
                    encoded = make_err(f"Error: Tamaño máximo de archivo permitido de {MAX_FILE_SIZE} bytes").encode()
                except Exception:
                    raise
                
                sock.sendto(encoded, addr)
                return
            
            self.handle_upload(sock=sock, addr=addr, filename=filename, queue=queue)

        elif datagram.typ == MsgType.REQUEST_DOWNLOAD:
            payload = payload_decode(datagram.payload)
            
            filename = payload[PAYLOAD_FILENAME_KEY]

            if not self.file_handler.is_filename_used(filename):
                try:
                    encoded = make_err(f"Error: Archivo '{filename}' no existe").encode()
                except Exception:
                    raise
                
                sock.sendto(encoded, addr)
                return
            
            self.handle_download(sock=sock, addr=addr, filename=filename, queue=queue)

    def handle_upload(self, sock: socket, addr: Tuple[str, int], filename: str, queue: Queue):
        # sw = self._send_ok_and_prepare_sw(sock=sock, peer_addr=addr, rto=RTO)

        try:
            encoded = make_ok(ver=VER_SW).encode()
        except Exception:
            raise
        
        sock.sendto(encoded, addr)    

        seq_number = 0
        while True:
            data = queue.get(block=True)

            try:
                datagram = Datagrama.decode(buf=data)
            except Exception:
                try:
                    encoded = make_err("Error: Error al decodificar datagrama").encode()
                except Exception:
                    raise

                sock.sendto(encoded, addr)
                return

            # datagram = sw.receive_data()
                        
            if datagram.typ == MsgType.DATA:
                print(f"[DEBUG] - Receive data with sequence_number={datagram.seq}, expecting={seq_number}")
                
                if datagram.seq == seq_number:
                    self.file_handler.save_datagram(filename=filename, datagram=datagram)
                    seq_number += 1
                
                try:
                    encoded = make_ack(acknum=seq_number, ver=VER_SW).encode()
                except Exception:
                    continue
    
                sock.sendto(encoded, addr)

                # sw.send_ack(acknum=seq_number)
                
                # if not (datagram.flags & FLAG_MF):
                #     break
            
            elif datagram.typ == MsgType.BYE:
                print("[DEBUG] - Receive bye")

                try:
                    encoded = make_ok(ver=VER_SW).encode()
                except Exception:
                    raise

                sock.sendto(encoded, addr)
                break

        # sw.await_bye_and_linger(linger_factor=3, quiet_time=0.2)
        
        del self.queues[addr]

    def handle_download(self, sock: socket, addr: tuple[str, int], filename: str, queue: Queue):
        # sw = self._send_ok_and_prepare_sw(sock=sock, peer_addr=addr, rto=RTO)

        try:
            encoded = make_ok(ver=VER_SW).encode()
        except Exception:
            raise
        
        sock.sendto(encoded, addr)    
        
        chunks = self.file_handler.get_file_chunks(filename=filename, chunk_size=CHUNK_SIZE)
        
        for seq_number, (payload, mf) in enumerate(chunks):
            # sw.send_data(datagrama=make_data(seq=seq_number, chunk=payload, ver=VER_SW, mf=mf), logger=None)
            
            try:
                encoded = make_data(seq=seq_number, chunk=payload, ver=VER_SW, mf=mf).encode()
            except Exception:
                raise

            expected_ack = seq_number + 1
            while True:
                sock.sendto(encoded, addr)

                try:
                    data = queue.get(block=True, timeout=RTO)
                except Empty:
                    continue
                    
                try:
                    datagram = Datagrama.decode(data)
                except (Truncated, BadChecksum):
                    continue
                    
                if datagram.ack >= expected_ack:
                    break

        try:
            encoded = make_bye(ver=VER_SW).encode()
        except Exception:
            raise

        sock.sendto(encoded, addr)

        del self.queues[addr]
        # sw.send_bye_with_retry(max_retries=8, quiet_time=0.2)
