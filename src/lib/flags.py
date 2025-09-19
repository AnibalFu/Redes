from lib.client import PROTOCOL_GBN, PROTOCOL_SW, Client
from lib.server import Server
from lib.connection import Connection

def show_help():
    print('usage: upload -[h] [-v | -q] [-H ADDR] [-p PORT] [-s FILEPATH], [-n FILENAME] [-r PROTOCOL]')
    print('<command description>')
    print('optional arguments:')
    print('-h, --help\tshow this help message and exit')
    print('-v, --verbose\tincrease output verbosity')
    print('-q, --quiet\tdecrease output verbosity')
    print('-H, --host\tserver ip address')
    print('-p, --port\tserver port')
    print('-s, --src\tsource file path')
    print('-n, --name\tfile name')
    print('-r, --protocol\terror recovery protocol')

def set_verbose(flag: str, body: str | None, entity: Connection):
    if body is not None:
        print(f'Warning: Flag {flag} does not take an argument')
    
    entity.verbose = True

def set_quiet(flag: str, body: str | None, entity: Connection):
    if body is not None:
        print(f'Warning: Flag {flag} does not take an argument')
    
    entity.verbose = False

def set_host(flag: str, body: str | None, entity: Connection):
    if body is None:
        print(f'Warning: {flag} {body} is not valid')
    else:
        entity.host = body

def set_port(flag: str, body: str | None, entity: Connection):
    if body is None:
        print(f'Warning: {flag} {body} is not valid')
    else:
        try:
            entity.port = int(body)
        except:
            print(f'Warning: {flag} {body} must be numeric')
            return

def set_src(flag: str, body: str | None, entity: Client):
    if body is None:
        print(f'Warning: {flag} {body} is not valid')
    else:
        entity.src = body

def set_name(flag: str, body: str | None, entity: Client):
    if body is None:
        print(f'Warning: {flag} {body} is not valid')
    else:
        entity.name = body

def set_protocol(flag: str, body: str | None, entity: Client):
    if body == 'GBN':
        entity.protocol = PROTOCOL_GBN
    elif body == 'SW':
        entity.protocol = PROTOCOL_SW
    else:
        print(f'Warning: {flag} {body} does not exist')

def set_storage(flag: str, body: str | None, entity: Server):
    if body is None:
        print(f'Warning: {flag} {body} is not valid')
    else:
        entity.storage = body

USER_FLAGS = {
    '-h': show_help,
    '-v': set_verbose,
    '--verbose': set_verbose,
    '-q': set_quiet,
    '--quiet': set_quiet,
    '-H': set_host,
    '--host': set_host,
    '-p': set_port,
    '--port': set_port,
    '-s': set_src,
    '--src': set_src,
    '-n': set_name,
    '--name': set_name,
    '-r': set_protocol,
    '--protocol': set_protocol
}

SERVER_FLAGS = {
    '-h': show_help,
    '-v': set_verbose,
    '--verbose': set_verbose,
    '-q': set_quiet,
    '--quiet': set_quiet,
    '-H': set_host,
    '--host': set_host,
    '-p': set_port,
    '--port': set_port,
    '-s': set_storage,
    '--storage': set_storage
}
