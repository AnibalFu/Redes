import pytest
import struct
from protocolo_amcgf import (
    Datagrama, MsgType,
    HDR_FMT, HDR_SIZE, MAGIC, VER_SW, VER_GBN, MSS, MAX_FRAME,
    payload_encode, payload_decode,
    inet_checksum,
    FrameTooBig, Truncated, BadMagic, BadChecksum,
    make_hello, make_negotiate, make_negotiate_ok,
    make_req_upload, make_req_download,
    make_ok, make_err, make_data, make_ack, make_bye
)

def test_dic_roundtrip():
    d = {"a": "1", "b": "hola", "mss": 1200}
    enc = payload_encode(d)
    dec = payload_decode(enc)
    assert dec["a"] == "1"
    assert dec["b"] == "hola"
    assert dec["mss"] == "1200"

def test_encode_decode_empty_payload():
    pkt = Datagrama(VER_SW, MsgType.HELLO, ack=0, seq=0, payload=b"")
    buf = pkt.encode()
    dec = Datagrama.decode(buf)
    assert dec.ver == VER_SW
    assert dec.typ == MsgType.HELLO
    assert dec.ack == 0
    assert dec.seq == 0
    assert dec.payload == b""

def test_encode_decode_with_payload():
    payload = b"hola mundo"
    pkt = Datagrama(VER_GBN, MsgType.DATA, ack=7, seq=42, payload=payload)
    buf = pkt.encode()
    dec = Datagrama.decode(buf)
    assert dec.ver == VER_GBN
    assert dec.typ == MsgType.DATA
    assert dec.ack == 7
    assert dec.seq == 42
    assert dec.payload == payload

def test_checksum_detection():
    payload = b"xyz"
    pkt = Datagrama(VER_SW, MsgType.DATA, seq=1, payload=payload)
    buf = bytearray(pkt.encode())
    buf[-1] ^= 0xFF
    with pytest.raises(BadChecksum):
        Datagrama.decode(bytes(buf))

def test_truncated_header():
    payload = b"abc"
    pkt = Datagrama(VER_SW, MsgType.DATA, seq=2, payload=payload)
    buf = pkt.encode()
    with pytest.raises(Truncated):
        Datagrama.decode(buf[:HDR_SIZE-1])

def test_truncated_payload():
    payload = b"abcdef"
    pkt = Datagrama(VER_SW, MsgType.DATA, seq=3, payload=payload)
    buf = pkt.encode()
    header = buf[:HDR_SIZE]
    magic, ver, typ, ack, seq, length, ck = struct.unpack(HDR_FMT, header)
    new_len = length + 5
    header_wo_ck = struct.pack(HDR_FMT, magic, ver, typ, ack, seq, new_len, 0)
    ck2 = inet_checksum(header_wo_ck + buf[HDR_SIZE:])
    new_header = struct.pack(HDR_FMT, magic, ver, typ, ack, seq, new_len, ck2)
    tampered = new_header + buf[HDR_SIZE:]
    with pytest.raises(Truncated):
        Datagrama.decode(tampered)

def test_mss_enforced():
    payload = b"x" * (MSS + 1)
    with pytest.raises(FrameTooBig):
        Datagrama(VER_SW, MsgType.DATA, seq=0, payload=payload).encode()

def test_magic_validation():
    payload = b"hi"
    pkt = Datagrama(VER_SW, MsgType.DATA, seq=10, payload=payload)
    buf = bytearray(pkt.encode())
    wrong_magic = 0xBEEF
    struct.pack_into("!H", buf, 0, wrong_magic)
    with pytest.raises(BadMagic):
        Datagrama.decode(bytes(buf))

def test_make_hello():
    p1 = make_hello("SW")
    p2 = make_hello("GBN")
    assert p1.ver == VER_SW and p1.typ == MsgType.HELLO and p1.payload == b""
    assert p2.ver == VER_GBN and p2.typ == MsgType.HELLO

def test_make_negotiate_and_ok():
    n = make_negotiate("GBN", mss=1000, win=8, rto_ms=250)
    assert n.ver == VER_GBN and n.typ == MsgType.NEGOTIATE
    d = payload_decode(n.payload)
    assert d["mss"] == "1000" and d["win"] == "8" and d["rto_ms"] == "250"
    ok = make_negotiate_ok(VER_GBN, 1000, win=8, rto_ms=250)
    d2 = payload_decode(ok.payload)
    assert ok.typ == MsgType.NEGOTIATE_OK
    assert d2["ver"] == str(VER_GBN) and d2["mss"] == "1000" and d2["win"] == "8" and d2["rto_ms"] == "250"

def test_make_req_upload_download():
    up = make_req_upload("archivo.bin", 123456, VER_SW)
    du = payload_decode(up.payload)
    assert up.typ == MsgType.REQUEST_UPLOAD and du["name"] == "archivo.bin" and du["size"] == "123456"
    down = make_req_download("archivo.bin", VER_GBN)
    dd = payload_decode(down.payload)
    assert down.typ == MsgType.REQUEST_DOWNLOAD and dd["name"] == "archivo.bin"

def test_make_ok_err():
    ok = make_ok({"ready": "yes"}, ver=VER_GBN)
    eo = payload_decode(ok.payload)
    assert ok.typ == MsgType.OK and eo["ready"] == "yes" and ok.ver == VER_GBN
    err = make_err("ENOENT", "no existe", ver=VER_SW)
    de = payload_decode(err.payload)
    assert err.typ == MsgType.ERR and de["code"] == "ENOENT" and de["message"] == "no existe"

def test_make_data_ack_bye():
    data = make_data(seq=123, chunk=b"A"*100, ver=VER_SW)
    assert data.typ == MsgType.DATA and data.seq == 123 and len(data.payload) == 100
    ack = make_ack(acknum=123, ver=VER_SW)
    assert ack.typ == MsgType.ACK and ack.ack == 123
    bye = make_bye(VER_GBN)
    assert bye.typ == MsgType.BYE and bye.ver == VER_GBN

def test_max_frame_constant():
    assert MAX_FRAME == HDR_SIZE + MSS
