from attr import dataclass

@dataclass
class Connection:
    verbose: bool = True
    host: str = '10.0.0.1'
    port: int = 6379