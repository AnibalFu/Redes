import os

class FileHandlerError(Exception): ...
class KeyNotFoundError(FileHandlerError): ...

"""Clase para manejar operaciones de archivos en el servidor"""
class FileHandler:
    def __init__(self, data_path: str):
        self.data_path = data_path
        os.makedirs(self.data_path, exist_ok=True)

    def is_filename_used(self, filename: str) -> bool:
        """Verifica si el nombre de archivo ya está en uso"""
        file_path = os.path.join(self.data_path, filename)
        return os.path.exists(file_path)

    def save_datagram(self, filename: str, datagram, chunk_size: int) -> None:
        """Guarda un datagram en la posición correcta dentro del archivo"""
        file_path = os.path.join(self.data_path, filename)
        offset = datagram.seq * chunk_size

        with open(file_path, "r+b" if self.is_filename_used(filename) else "wb") as f:
            f.seek(offset)
            f.write(datagram.payload)

    def get_file(self, filename: str) -> bytes:
        """Devuelve el contenido del archivo completo"""
        if not self.is_filename_used(filename):
            raise KeyNotFoundError(f"Archivo '{filename}' no encontrado")
        
        filepath = os.path.join(self.data_path, filename)
        with open(filepath, 'rb') as f:
            return f.read()
        
        

    
