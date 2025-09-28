from attr import dataclass
from socket import socket, AF_INET, SOCK_DGRAM
from lib.fileHandler import FileHandler
from lib.connection import Connection
from lib.datagram_sending import *
from lib.sw import StopAndWait
import threading

        
# A futuro restar key de data
CHUNK_SIZE = MSS

@dataclass
class Server(Connection):
    fileHandler: FileHandler = FileHandler('../storage_data')
    # sw: StopAndWait = StopAndWait(socket(AF_INET, SOCK_DGRAM), ('', 0))

    def run(self):
        """
        Ejecuta el servidor principal

        Por cada cliente se crea un thread para manejar la transferencia
        """
        server_socket = socket(AF_INET, SOCK_DGRAM)
        server_socket.bind((self.host, self.port))
        print(f"Servidor escuchando en {self.host}:{self.port}")

        while True:
            packet, sender_address = server_socket.recvfrom(MTU)
            if len(packet) < HDR_SIZE:
                print("[DEBUG] Mensaje de control recibido:", packet)
                continue

            try:
                datagrama = Datagrama.decode(packet)
            except Exception as e:
                err = make_err("Error al decodificar datagrama")
                server_socket.sendto(err.encode(), sender_address)
                print(f"[DEBUG] Error al decodificar datagrama: {e}")
                continue
        
            # Tipos de mensajes aceptados de cliente
            if datagrama.typ == MsgType.REQUEST_UPLOAD:
                payload = payload_decode(datagrama.payload)
                print(f"[DEBUG] REQUEST_UPLOAD de {sender_address} payload: {payload}")
                filename = payload[PAYLOAD_FILENAME_KEY]
                sock = socket(AF_INET, SOCK_DGRAM)
                sock.bind(('', 0))  # Puerto libre asignado por el SO
                threading.Thread(target=self.handle_upload, args=(sock, sender_address, self.fileHandler, filename), daemon=True).start()


            elif datagrama.typ == MsgType.REQUEST_DOWNLOAD:
                payload = payload_decode(datagrama.payload)
                print(f"[DEBUG] REQUEST_DOWNLOAD de {sender_address} payload: {payload}")
                filename = payload[PAYLOAD_FILENAME_KEY]
                print(f"[DEBUG] Filename: {filename}")
                sock = socket(AF_INET, SOCK_DGRAM)
                sock.bind(('', 0))  # Puerto libre asignado por el SO
                threading.Thread(target=self.handle_download, args=(sock, sender_address, filename, self.fileHandler), daemon=True).start()

    # server_socket.close()
    
    def handle_upload(self, sock: socket, client_addr: tuple[str, int], fileHandler: FileHandler, filename: str):
        """Maneja la recepción de un archivo por UDP en un puerto efímero."""
        ok = make_ok(ver=VER_SW)
        sock.sendto(ok.encode(), client_addr)
        
        print(f"[DEBUG] Upload handler en puerto {sock.getsockname()[1]} para {client_addr}")
        
        # Va para SW llamando self.sw.send_data
        ###########################
        while True:
            packet, _client_addr = sock.recvfrom(MTU)
            
            # Si ocurre un error al decodificar el datagrama ignoro el paquete (simulo SW paquete corrupto)
            try:
                datagrama = Datagrama.decode(packet)
                
            except (Truncated, BadChecksum) as e:
                print(f"[DEBUG] Error al decodificar datagrama: {e}")
                continue
            
            if datagrama.typ == MsgType.DATA:
                fileHandler.save_datagram(filename, datagrama)
                ack = make_ack(acknum=datagrama.seq + 1, ver=VER_SW)
                sock.sendto(ack.encode(), client_addr)
                
                if not (datagrama.flags & FLAG_MF):
                    print("[DEBUG] Archivo recibido completo, esperando BYE...")
                    
            elif datagrama.typ == MsgType.BYE:
                print(f"[DEBUG] BYE recibido, guardando archivo y respondiendo OK")
                ok = make_ok(ver=VER_SW)
                sock.sendto(ok.encode(), client_addr)
                break
        ###########################    
        
        sock.close()

    def handle_download(self, sock: socket, client_addr: tuple[str, int], filename: str, fileHandler: FileHandler):
        """Maneja el envío de un archivo por UDP en un puerto efímero."""
        ok = make_ok(ver=VER_SW)
        sock.sendto(ok.encode(), client_addr)  # Enviar OK desde el nuevo socket
        print(f"[DEBUG] Download handler en puerto {sock.getsockname()[1]} para {client_addr}")
        
        content = fileHandler.get_file(filename)  
        sock.settimeout(0.1)
        seq = 0
        
        for i in range(0, len(content), CHUNK_SIZE):
            payload = content[i:i + CHUNK_SIZE]
            mf = (i + CHUNK_SIZE) < len(content)
            datagrama = make_data(seq=seq, chunk=payload, ver=VER_SW, mf=mf)
            encoded = datagrama.encode()
            
            # Logica de SW
            #####################################
            ack_ok = False
            
            # Logica de SW
            while not ack_ok:
                sock.sendto(encoded, client_addr)
                print(f"[DEBUG] Enviado DATA con seq {seq}, MF={mf}")
                try:
                    data, _ = sock.recvfrom(MTU)
                    datagram = Datagrama.decode(data)
                    if datagram.typ == MsgType.ACK and datagram.ack == seq + 1:
                        print(f"[DEBUG] ACK correcto recibido: {datagram}")
                        ack_ok = True
                    else:
                        print(f"[DEBUG] ACK incorrecto (esperaba {seq+1}), reenviando DATA seq {seq}")
                except TimeoutError:
                    print(f"[DEBUG] Timeout esperando ACK para seq {seq}, reenviando DATA")
            #####################################
            
            seq += 1
        
        # Esperar BYE
        data, _ = sock.recvfrom(MTU)
        resp = Datagrama.decode(data)
        assert resp.typ == MsgType.BYE, "Esperaba BYE tras DATA"
        print("Transferencia finalizada correctamente")
        ok = make_ok(ver=VER_SW)
        sock.sendto(ok.encode(), client_addr)
        
        sock.close()
