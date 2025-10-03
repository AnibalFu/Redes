import os
import io

from io import BufferedRandom
from dataclasses import dataclass, field

from lib.protocolo_amcgf import Datagram, FLAG_MF

"""Clase para manejar operaciones de archivos en el servidor"""
@dataclass
class FileHandler:
    path: str | None = None
    open_files: dict[str, BufferedRandom] | None = None

    def __init__(self, path: str) -> None:
        self.path = path
        self.open_files = dict()
        os.makedirs(self.path, exist_ok=True)

    def is_filename_used(self, filename: str) -> bool:
        """Verifica si el nombre de archivo ya está en uso"""

        file_path = os.path.join(self.path, filename)
        
        return os.path.exists(file_path)

    def open_file(self, filename: str, mode="wb"):
        file_path = os.path.join(self.path, filename)
        file = open(file_path, mode)
        
        self.open_files[filename] = file
        return file
    
    def save_datagram(self, filename: str, datagram: Datagram) -> None:
        if filename not in self.open_files:
            # Abrir siempre en 'wb' para truncar el archivo si ya existe (pisar contenido)
            self.open_file(filename, "wb")

        file = self.open_files[filename]
        file.write(datagram.payload)

        if not (datagram.flags & FLAG_MF): 
            print(f"[DEBUG] Archivo '{filename}' guardado completo")
            self.close_file(filename)
    
    def close_file(self, filename: str) -> None:
        if filename in self.open_files:
            self.open_files[filename].close()
            del self.open_files[filename]

    def get_file_chunks(self, filename: str, chunk_size: int):
        """Generador que devuelve el archivo en chunks de tamaño chunk_size"""
        
        filepath = os.path.join(self.path, filename)
        filesize = os.path.getsize(filepath)
        
        with open(filepath, 'rb') as file:
            while True:
                payload = file.read(chunk_size)
                
                if not payload:
                    break
                
                more_fragments = file.tell() < filesize
                print(f"[DEBUG] Enviando payload: '{payload}' MF={more_fragments} de tamaño {len(payload)}")
                
                yield payload, more_fragments
