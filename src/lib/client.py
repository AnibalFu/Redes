from attr import dataclass
from lib.connection import Connection

PROTOCOL_SW = 1
PROTOCOL_GBN = 2

@dataclass
class Client(Connection):
    src: str = 'data/host/'
    name: str = 'file.txt'