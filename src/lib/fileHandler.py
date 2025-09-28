import os
import io
from lib.protocolo_amcgf import Datagrama, FLAG_MF

class FileHandlerError(Exception): ...
class KeyNotFoundError(FileHandlerError): ...

"""Clase para manejar operaciones de archivos en el servidor"""
class FileHandler:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.open_files: dict[str, 'io.BufferedRandom'] = {}
        os.makedirs(self.data_path, exist_ok=True)

    def is_filename_used(self, filename: str) -> bool:
        """Verifica si el nombre de archivo ya está en uso"""
        file_path = os.path.join(self.data_path, filename)
        return os.path.exists(file_path)

    def open_file(self, filename: str, mode="wb"):
        file_path = os.path.join(self.data_path, filename)
        f = open(file_path, mode)
        self.open_files[filename] = f
        return f
    
    def save_datagram(self, filename: str, datagram: Datagrama, chunk_size: int):
        if filename not in self.open_files:
            mode = "r+b" if self.is_filename_used(filename) else "wb"
            self.open_file(filename, mode)

        f = self.open_files[filename]
        offset = datagram.seq * chunk_size
        f.seek(offset)
        f.write(datagram.payload)

        if not (datagram.flags & FLAG_MF): 
            self.close_file(filename)
    
    def close_file(self, filename: str):
        if filename in self.open_files:
            self.open_files[filename].close()
            del self.open_files[filename]

    def get_file(self, filename: str) -> bytes:
        """Devuelve el contenido del archivo completo"""
        if not self.is_filename_used(filename):
            raise KeyNotFoundError(f"Archivo '{filename}' no encontrado")
        
        filepath = os.path.join(self.data_path, filename)
        with open(filepath, 'rb') as f:
            return f.read()
        
        

    
