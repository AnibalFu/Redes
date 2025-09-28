from socket import socket, AF_INET, SOCK_DGRAM
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from lib.client import Client
from lib.fileHandler import FileHandler
from lib.datagram_sending import finalizar_conexion, send_request
from lib.protocolo_amcgf import FLAG_MF, VER_SW, Datagrama, MsgType, make_ack, make_req_download, MTU, MSS

def define_flags():
    parser = ArgumentParser(description='Download file program', formatter_class=RawDescriptionHelpFormatter)

    parser.add_argument('-v', '--verbose', required=False, action='store_true', help='increase output verbosity')
    parser.add_argument('-q', '--quiet', required=False, action='store_true', help='decrease output verbosity')
    parser.add_argument('-H', '--host', required=False, type=str, metavar='HOST', help='server IP address')
    parser.add_argument('-p', '--port', required=False, type=int, metavar='PORT', help='server port')
    parser.add_argument('-d', '--dest', required=False, type=str, metavar='FILEPATH', help='destination file path')
    parser.add_argument('-n', '--name', required=False, type=str, metavar='FILENAME', help='file name')
    parser.add_argument('-r', '--protocol', required=False, type=str, metavar='PROTOCOL', help='error recovery protocol')

    return parser

def process_args(args: Namespace):
    client = Client()
    
    client.verbose = args.verbose
    client.quiet = args.quiet
    client.host = args.host if args.host else client.host
    client.port = args.port if args.port else client.port
    client.src = args.dest if args.dest else client.src
    client.name = args.name if args.name else client.name
    client.protocol = args.protocol if args.protocol else client.protocol

    return client


if __name__ == "__main__":
    
    parser = define_flags()
    args = parser.parse_args()
    
    client = process_args(args)
    print(client)
    client.download()
