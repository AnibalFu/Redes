from dataclasses import dataclass
from lib.connection import Connection

@dataclass
class Client(Connection):
    src: str = 'data/host/'
    name: str = 'file.txt'