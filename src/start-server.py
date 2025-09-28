import sys

from signal import SIGINT, signal
from types import FrameType
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from lib.server import DEFAULT_STORAGE_PATH, Server   
from lib.protocolo_amcgf import *
from lib.fileHandler import FileHandler


def sigint_handler(_: int, frame: FrameType | None):
    server_socket = frame.f_locals['server_socket']
    try:
        server_socket.close()
    except:
        print(f'\nError: Socket {server_socket} could not be closed')
        sys.exit(-1)
    print('\nGraceful Exit')
    sys.exit(0)    

def define_flags():
    parser = ArgumentParser(description='File server program', formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-v', '--verbose', required=False, action='store_true', help='increase output verbosity')
    parser.add_argument('-q', '--quiet', required=False, action='store_true', help='decrease output verbosity')
    parser.add_argument('-H', '--host', required=False, type=str, metavar='HOST', help='server IP address')
    parser.add_argument('-p', '--port', required=False, type=int, metavar='PORT', help='server port')
    parser.add_argument('-s', '--storage', required=False, type=str, metavar='DIRPATH', help='destination file path')
    return parser

def process_args(args: Namespace):
    server = Server()
    server.verbose = args.verbose
    server.quiet = args.quiet
    server.host = args.host if args.host else server.host
    server.port = args.port if args.port else server.port    
    server.fileHandler = FileHandler(args.storage) if args.storage else FileHandler(DEFAULT_STORAGE_PATH)

    return server


if __name__ == '__main__':
    signal(SIGINT, sigint_handler)
    parser = define_flags()
    args = parser.parse_args()
    server = process_args(args)
    server.run()
