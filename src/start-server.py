import sys

from lib.server import Server
from lib.flags import SERVER_FLAGS
from lib.utils import split

def process_args(args: list[str]):
    server = Server()
    
    for arg in args:
        try:
            (flag, body) = arg.split(' ', maxsplit=2)
        except ValueError:
            flag = arg
            body = None

        function = SERVER_FLAGS.get(flag)

        if function:
            function(flag=flag, body=body, entity=server)
        else:
            print(f'Warning: Bad Flag {flag}')

    return server

if __name__ == '__main__':
    args = split(sys.argv)

    server = process_args(args)

    print(server)