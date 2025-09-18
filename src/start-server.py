from lib.protocolo_amcgf import *

"""
Esto me devolvio GPT quizas sirva de algo
"""
def handle_packet(pkt: Datagrama, state) -> list[Datagrama]:
    out: list[Datagrama] = []
    if pkt.typ == MsgType.HELLO:
        params = dic_decode(pkt.payload)
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
