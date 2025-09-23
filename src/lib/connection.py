from attr import dataclass

@dataclass
class Connection:
    verbose: bool = True
    quiet: bool = False
    host: str = '10.0.0.1'
    port: int = 6379
    protocol: int | None = None 