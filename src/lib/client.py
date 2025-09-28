from dataclasses import dataclass
from lib.connection import Connection
from lib.fileHandler import FileHandler

PROTOCOL_SW = 1
PROTOCOL_GBN = 2

@dataclass
class Client(Connection):
    src: str = 'carpeta_personal/'
    name: str = 'file.txt'
    fileHandler: FileHandler = FileHandler('carpeta_personal/')