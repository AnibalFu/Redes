from dataclasses import dataclass
from lib.connection import Connection
from lib.fileHandler import FileHandler
from lib.datagram_sending import *
from socket import socket, AF_INET, SOCK_DGRAM


CHUNK_SIZE = MSS 
DEFAULT_NAME = "file.txt"
DEFAULT_SRC = "/personal_folder"


@dataclass
class Client(Connection):
    src: str = None
    name: str = None

    # Por ahora representa el protocolo SW con numero de secuencia cotinuo
    def upload(self):
        
        print(f"[DEBUG] Chunk size: {CHUNK_SIZE}")
        ctrl = socket(AF_INET, SOCK_DGRAM)
        
        # Set timeout para recibir respuesta en 1 segundos
        ctrl.settimeout(1)
        
        
        # REQUEST_UPLOAD = handshake con el servidor
        request = make_req_upload(self.name, VER_SW)
        print(f"[DEBUG] Enviado REQUEST_UPLOAD para {request}")
        ctrl.sendto(request.encode(), (self.host, self.port))

        # Espera OK desde el nuevo puerto
        data, connection_addr = ctrl.recvfrom(MTU)
        
        datagrama = Datagrama.decode(data)
        # Si recibo ERR, prox archivo muy pesado
        if datagrama.typ == MsgType.ERR:
            print(f"[ERROR] Error: {datagrama.payload.decode()['msg']}")
            ctrl.close()
            return

        print(f"[DEBUG] Recibido OK para UPLOAD, nueva dirección: {connection_addr}")

        # Transferencia de datos por la nueva dirección, leyendo por partes
        seq = 0
        with open(self.src, 'rb') as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                mf = f.peek(1) != b''  # MF si hay más datos
                
                datagrama = make_data(seq=seq, chunk=chunk, ver=VER_SW, mf=mf)
                print(f"[DEBUG] {datagrama}")
                encoded = datagrama.encode()
                
                # Logica de SW
                #####################################
                # Espero recibir ACK que espero seq+1
                ack_ok = False
                while not ack_ok:
                    ctrl.sendto(encoded, connection_addr)
                    print(f"[DEBUG] Enviado DATA con seq {seq}, MF={mf}")
                    
                    try:
                        data, _connection_addr = ctrl.recvfrom(MTU)
                        datagram = Datagrama.decode(data)
                        
                        if datagram.typ == MsgType.ACK and datagram.ack == seq + 1:
                            print(f"[DEBUG] ACK correcto recibido: {datagram}")
                            ack_ok = True
                        
                        else:
                            print(f"[DEBUG] ACK incorrecto (esperaba {seq+1}), reenviando DATA seq {seq}")
                            
                    except TimeoutError:
                        print(f"[DEBUG] Timeout esperando ACK para seq {seq}, reenviando DATA")

                    print(f"-------------------------" * 3)
                # Incremento seq
                #####################################
                seq += 1

        # FIN
        finalizar_conexion(ctrl, connection_addr)


    def download(self):
        print(f"[DEBUG] Solicitando descarga de '{self.name}' desde {self.host}:{self.port}")

        ctrl = socket(AF_INET, SOCK_DGRAM)

        # Server me responde por el nuevo socket
        download_conection = send_request(make_req_download, ctrl, (self.host, self.port), self.name)
        print("[DEBUG] Recibido OK para DOWNLOAD")
        print(f"[DEBUG] Socket: {ctrl}")
        print(f"[DEBUG] Nueva dirección: {download_conection}")
        
        self.receive_content(ctrl, download_conection)

        # FIN
        finalizar_conexion(ctrl, download_conection)
        ctrl.close()


    # Logica de SW
    def receive_content(self, ctrl: socket, download_conection: socket):
        expected_seq = 0
        while True:
            print("[DEBUG] Por recibir...")
            data, _download_conection = ctrl.recvfrom(MTU)
            
            try:
                datagrama = Datagrama.decode(data)
                
            except Exception as e:
                print(f"[DEBUG] Error al decodificar datagrama: {e}")
                continue

            if datagrama.typ == MsgType.DATA:
                if datagrama.seq != expected_seq:
                    # Fuera de orden para SW no debería ocurrir; re-ACK del último válido
                    ack = make_ack(acknum=expected_seq, ver=VER_SW)
                    ctrl.sendto(ack.encode(), download_conection)
                    print(f"[DEBUG] Fuera de orden: esperado {expected_seq}, recibido {datagrama.seq}. Reenviado ACK {expected_seq}")
                    continue

                data_chunk = datagrama.payload
                print(f"[DEBUG] Recibido {len(data_chunk)} bytes")
                print(f"[DEBUG] Recibido DATA con seq {datagrama.seq}")
                
                # Guardar chunk en la posición correcta (offset = seq * MSS)
                self.fileHandler.save_datagram(self.name, datagrama)
                
                # Enviar ACK
                expected_seq += 1
                
                ack = make_ack(acknum=expected_seq, ver=VER_SW)
                ctrl.sendto(ack.encode(), download_conection)
                
                print(f"[DEBUG] Enviado ACK {expected_seq}")
                
                if not (datagrama.flags & FLAG_MF):
                    print("Archivo recibido completo")
                    break
            
            else:
                print(f"[DEBUG] Mensaje inesperado: {datagrama}")
                continue
        
        print(f"[DEBUG] Descarga de '{self.name}' finalizada")
