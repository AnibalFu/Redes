from argparse import ArgumentParser, RawDescriptionHelpFormatter, Namespace

from lib.logger import Logger
from lib.protocolo_amcgf import *
from lib.client import DEFAULT_NAME, DEFAULT_SRC, Client

def define_flags():
    parser = ArgumentParser(description='Upload file program', formatter_class=RawDescriptionHelpFormatter)
    
    parser.add_argument('-v', '--verbose', required=False, action='store_true', help='increase output verbosity')
    parser.add_argument('-q', '--quiet', required=False, action='store_true', help='decrease output verbosity')
    parser.add_argument('-H', '--host', required=False, type=str, metavar='HOST', help='server IP address')
    parser.add_argument('-p', '--port', required=False, type=int, metavar='PORT', help='server port')
    parser.add_argument('-s', '--src', required=False, type=str, metavar='SRC', help='source file path')
    parser.add_argument('-n', '--name', required=False, type=str, metavar='FILENAME', help='file name')
    parser.add_argument('-r', '--protocol', required=False, type=str, metavar='PROTOCOL', help='error recovery protocol')

    return parser

def process_args(args: Namespace):
    client = Client()

    client.verbose = args.verbose
    client.quiet = args.quiet
    client.host = args.host if args.host else client.host
    client.port = args.port if args.port else client.port
    client.src = args.src if args.src else DEFAULT_SRC
    client.name = args.name if args.name else DEFAULT_NAME
    client.logger = Logger(client.verbose)

    if args.protocol == 'SW':
        client.protocol = VER_SW
    elif args.protocol == 'GBN':
        client.protocol = VER_GBN

    return client

if __name__ == '__main__':

    parser = define_flags()
    args = parser.parse_args()

    client = process_args(args)
    client.upload()