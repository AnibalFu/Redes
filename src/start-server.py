import sys

from lib.server import Server
from lib.flags import SERVER_FLAGS
from lib.utils import split
from lib.protocolo_amcgf import *

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


"""
Esto me devolvio GPT quizas sirva de algo
"""
def handle_packet(pkt: Datagrama, state) -> list[Datagrama]:
    out: list[Datagrama] = []
    if pkt.typ == MsgType.HELLO:
        params = payload_decode(pkt.payload)
        # valida op/name/size/proto...
        out.append(make_ok({"transfer_id": state.alloc_tid()}, ver=pkt.ver))
        state.begin(params, ver=pkt.ver)
    elif pkt.typ == MsgType.DATA:
        if pkt.ver == VER_SW:
            if pkt.seq == state.expected_seq and state.check_and_write(pkt.payload):
                state.expected_seq ^= 1
            # en S&W se ACKea el último válido (puntual)
            out.append(make_ack(state.expected_seq ^ 1, ver=pkt.ver))
        else:  # VER_GBN
            if pkt.seq == state.expected_seq and state.check_and_write(pkt.payload):
                state.expected_seq += 1
            # en GBN ACK acumulativo del último in-order
            out.append(make_ack(state.expected_seq - 1, ver=pkt.ver))
    elif pkt.typ == MsgType.BYE:
        state.finish()
        out.append(make_ok(ver=pkt.ver))
    return out
