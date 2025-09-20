from attr import dataclass
from lib.connection import Connection

@dataclass
class Server(Connection):
    storage: str = 'data/'