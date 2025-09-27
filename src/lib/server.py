from attr import dataclass
from lib.fileHandler import FileHandler
from lib.connection import Connection

@dataclass
class Server(Connection):
    fileHandler: FileHandler = FileHandler('../storage_data')
