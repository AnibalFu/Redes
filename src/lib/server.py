import threading

from queue import Empty, Queue
from socket import AF_INET, SOCK_DGRAM, socket
from dataclasses import dataclass, field
from typing import NoReturn

from lib.protocol import *
from lib.config import *
from lib.protocolo_amcgf import *
from lib.connection import Connection
        
# A futuro restar key de data
CHUNK_SIZE = MSS
DEFAULT_STORAGE_PATH = './storage_data'

@dataclass
class Server(Connection):
    queues: dict = field(default_factory=dict)

    @staticmethod
    def _queue_recv_fn(timeout: float, queue: Queue) -> bytes | None:
        try:
            return queue.get(timeout=timeout)
        except Empty:
            return None

    def _process_client(self, addr: tuple[str, int], sock: socket, queue: Queue) -> None:
        data = queue.get(block=True)
        
        try:
            datagram = Datagram.decode(buf=data)
        except Exception:
            try:
                encoded = make_err("Error: Error al decodificar datagrama").encode()
            except Exception:
                raise

            sock.sendto(encoded, addr)
            return
            
        self.protocol = datagram.ver

        if datagram.typ == MsgType.REQUEST_UPLOAD:
            payload = payload_decode(datagram.payload)
            
            filename = payload[PAYLOAD_FILENAME_KEY]
            file_size = payload[PAYLOAD_FILE_SIZE_KEY]

            if file_size > MAX_FILE_SIZE:
                try:
                    encoded = make_err(f"Tamaño máximo de archivo permitido de {MAX_FILE_SIZE} bytes").encode()
                except Exception:
                    raise
                
                sock.sendto(encoded, addr)
                return
            
            self._handle_upload(sock=sock, addr=addr, filename=filename, queue=queue)

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
            
            self._handle_download(sock=sock, addr=addr, filename=filename, queue=queue)
    
    def _handle_upload(self, sock: socket, addr: tuple[str, int], filename: str, queue: Queue) -> None:
        proto = self._send_ok(ver=self.protocol, sock=sock, addr=addr, recv_fn=lambda t: Server._queue_recv_fn(t, queue))

        expected_seq = 0
        while True:
            datagram = proto.receive_data()
            if not datagram:
                continue
                        
            if datagram.typ == MsgType.DATA:
                if datagram.seq == expected_seq:
                    self.file_handler.save_datagram(filename=filename, datagram=datagram)
                    expected_seq += 1
                
                proto.send_ack(acknum=expected_seq)
                
                if not (datagram.flags & FLAG_MF):
                    break
    
        proto.await_bye_and_linger(linger_factor=3, quiet_time=0.2)

        del self.queues[addr]

    def _handle_download(self, sock: socket, addr: tuple[str, int], filename: str, queue: Queue) -> None:
        proto = self._send_ok(ver=self.protocol, sock=sock, addr=addr, recv_fn=lambda t: self._queue_recv_fn(t, queue))

        chunks = self.file_handler.get_file_chunks(filename, CHUNK_SIZE)
        for seq_number, (payload, mf) in enumerate(chunks):
            while not proto.send_data(datagram=make_data(seq=seq_number, chunk=payload, ver=self.protocol, mf=mf)):
                pass

        proto.send_bye_with_retry()

        del self.queues[addr]    

    def run(self) -> NoReturn:
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

                threading.Thread(target=self._process_client, args=(addr, sock, queue), daemon=True).start()
            else:
                queue = self.queues[addr]

            queue.put(data)
