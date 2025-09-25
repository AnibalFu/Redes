from attr import dataclass
from lib.storage import Storage
from lib.connection import Connection

@dataclass
class Server(Connection):
    storage: Storage = Storage('/data/storage.bin')