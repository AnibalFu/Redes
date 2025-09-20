"""
Tests del protocolo AMCGF (version sin MAGIC y con FLAG_ACK).

Header (big-endian, 16 bytes):
| TYPE(1) | VER(1) | FLAGS(2) | LEN(2) | CHECKSUM(2) | ACK(4) | SEQ(4) |

- Mensajes de control usan payload K=V (payload_encode/decode).
- DATA lleva bytes crudos y respeta MSS.
- CHECKSUM es complemento a uno de 16 bits sobre header(con ck=0)+payload.
- FLAG_ACK (0x8000) indica que el campo ACK es valido (ACK puro o piggyback).
"""

import pytest
import struct
from protocolo_amcgf import (
    Datagrama, MsgType,
    HDR_FMT, HDR_SIZE, VER_SW, VER_GBN, MSS, MAX_FRAME,
    FLAG_ACK, FLAG_MF, 
    payload_encode, payload_decode,
    inet_checksum,
    FrameTooBig, Truncated, BadChecksum,
    make_hello,
    make_req_upload, make_req_download,
    make_ok, make_err, make_data, make_ack, make_bye,
)

def test01_dic_roundtrip():
    # Codec de control: round-trip de tipos basicos (int/str).
    d = {"a": 1, "b": "hola", "mss": 1200}
    enc = payload_encode(d)
    dec = payload_decode(enc)
    assert dec["a"] == 1
    assert dec["b"] == "hola"
    assert dec["mss"] == 1200


def test02_payload_data_transfer_format():
    # Codec de control: soporta bool y bytes (ej: metadatos + muestra binaria).
    d = {"es_fragmento": True, "data": b"hola"}
    enc = payload_encode(d)
    dec = payload_decode(enc)
    assert dec["es_fragmento"] is True
    assert dec["data"] == b"hola"


def test03_encode_decode_empty_payload():
    # Control vacio: encode/decode conserva VER/TYPE/ACK/SEQ/PAYLOAD.
    pkt = Datagrama(VER_SW, MsgType.HELLO, ack=0, seq=0, payload=b"")
    buf = pkt.encode()
    dec = Datagrama.decode(buf)
    assert dec.ver == VER_SW
    assert dec.typ == MsgType.HELLO
    assert dec.ack == 0
    assert dec.seq == 0
    assert dec.payload == b""


def test04_encode_decode_with_payload():
    # DATA con payload binario: encode/decode preserva campos y bytes.
    payload = b"hola mundo"
    pkt = Datagrama(VER_GBN, MsgType.DATA, ack=7, seq=42, payload=payload)
    buf = pkt.encode()
    dec = Datagrama.decode(buf)
    assert dec.ver == VER_GBN
    assert dec.typ == MsgType.DATA
    assert dec.ack == 7
    assert dec.seq == 42
    assert dec.payload == payload


def test05_checksum_detection():
    # Corrupcion de bytes detectada por checksum -> BadChecksum.
    payload = b"xyz"
    pkt = Datagrama(VER_SW, MsgType.DATA, seq=1, payload=payload)
    buf = bytearray(pkt.encode())
    buf[-1] ^= 0xFF  # bit flip
    with pytest.raises(BadChecksum):
        Datagrama.decode(bytes(buf))


def test06_truncated_header():
    # Trama mas corta que el header minimo -> Truncated.
    payload = b"abc"
    pkt = Datagrama(VER_SW, MsgType.DATA, seq=2, payload=payload)
    buf = pkt.encode()
    with pytest.raises(Truncated):
        Datagrama.decode(buf[:HDR_SIZE - 1])


def test07_truncated_payload():
    # Header anuncia LEN mayor al payload real -> Truncated.
    payload = b"abcdef"
    pkt = Datagrama(VER_SW, MsgType.DATA, seq=3, payload=payload)
    buf = pkt.encode()

    # Desempaquetar header segun el formato nuevo:
    typ, ver, flags, length, ck, ack, seq = struct.unpack(HDR_FMT, buf[:HDR_SIZE])

    # Forzar un LEN mayor y recomputar checksum con ck=0
    new_len = length + 5
    header_wo_ck = struct.pack(HDR_FMT, typ, ver, flags, new_len, 0, ack, seq)
    ck2 = inet_checksum(header_wo_ck + buf[HDR_SIZE:])
    new_header = struct.pack(HDR_FMT, typ, ver, flags, new_len, ck2, ack, seq)
    tampered = new_header + buf[HDR_SIZE:]

    with pytest.raises(Truncated):
        Datagrama.decode(tampered)


def test08_mss_enforced():
    # DATA que excede MSS -> FrameTooBig.
    payload = b"x" * (MSS + 1)
    with pytest.raises(FrameTooBig):
        Datagrama(VER_SW, MsgType.DATA, seq=0, payload=payload).encode()


def test09_ack_flag_behavior():
    # (a) ACK puro debe encender FLAG_ACK
    a = make_ack(acknum=123, ver=VER_SW)
    buf = a.encode()
    dec = Datagrama.decode(buf)
    assert dec.typ == MsgType.ACK
    assert dec.flags & FLAG_ACK
    assert dec.ack == 123

    # (b) Piggyback en OK debe encender FLAG_ACK
    ok = make_ok({"ready": "yes"}, ver=VER_GBN, ack=77)
    dec2 = Datagrama.decode(ok.encode())
    assert dec2.typ == MsgType.OK
    assert dec2.flags & FLAG_ACK
    assert dec2.ack == 77

    # (c) DATA sin ack no debe encender FLAG_ACK
    data = make_data(seq=5, chunk=b"hi", ver=VER_SW, ack=0)
    dec3 = Datagrama.decode(data.encode())
    assert dec3.typ == MsgType.DATA
    assert (dec3.flags & FLAG_ACK) == 0
    assert dec3.ack == 0


def test10_make_hello_negotiation_payload():
    # HELLO con parametros en payload (negociacion via HELLO).
    h_sw = make_hello("SW", mss=1000, win=8, rto_ms=250)
    d1 = payload_decode(h_sw.payload)
    assert h_sw.ver == VER_SW and h_sw.typ == MsgType.HELLO
    assert d1["mss"] == 1000 and d1["win"] == 8 and d1["rto_ms"] == 250

    h_gbn = make_hello("GBN", mss=1200)
    d2 = payload_decode(h_gbn.payload)
    assert h_gbn.ver == VER_GBN and h_gbn.typ == MsgType.HELLO
    assert d2["mss"] == 1200


def test11_make_req_upload_download():
    # REQUEST_UPLOAD/REQUEST_DOWNLOAD: inicio de flujo (nombre y tamano).
    up = make_req_upload("archivo.bin", 123456, VER_SW)
    du = payload_decode(up.payload)
    assert up.typ == MsgType.REQUEST_UPLOAD and du["name"] == "archivo.bin" and du["size"] == 123456

    down = make_req_download("archivo.bin", VER_GBN)
    dd = payload_decode(down.payload)
    assert down.typ == MsgType.REQUEST_DOWNLOAD and dd["name"] == "archivo.bin"


def test12_make_ok_err():
    # OK/ERR: confirmacion y senializacion de error con codigo y mensaje.
    ok = make_ok({"ready": "yes"}, ver=VER_GBN)
    eo = payload_decode(ok.payload)
    assert ok.typ == MsgType.OK and eo["ready"] == "yes" and ok.ver == VER_GBN

    err = make_err("ENOENT", "no existe", ver=VER_SW)
    de = payload_decode(err.payload)
    assert err.typ == MsgType.ERR and de["code"] == "ENOENT" and de["message"] == "no existe"


def test13_make_data_ack_bye():
    # Primitivas de transferencia/cierre: DATA, ACK, BYE.
    data = make_data(seq=123, chunk=b"A" * 100, ver=VER_SW)
    assert data.typ == MsgType.DATA and data.seq == 123 and len(data.payload) == 100

    ack = make_ack(acknum=123, ver=VER_SW)
    assert ack.typ == MsgType.ACK and ack.ack == 123

    bye = make_bye(VER_GBN)
    assert bye.typ == MsgType.BYE and bye.ver == VER_GBN


def test14_max_frame_constant():
    # Constante MAX_FRAME coherente con definicion (header + MSS).
    assert MAX_FRAME == HDR_SIZE + MSS

def test15_mf_flag_behavior():
    # DATA con mf=True debe encender FLAG_MF
    d1 = make_data(seq=10, chunk=b"x"*10, ver=VER_SW, mf=True)
    r1 = Datagrama.decode(d1.encode())
    assert r1.typ == MsgType.DATA
    assert r1.flags & FLAG_MF

    # DATA con mf=False no debe encender FLAG_MF
    d2 = make_data(seq=11, chunk=b"y"*10, ver=VER_SW, mf=False)
    r2 = Datagrama.decode(d2.encode())
    assert r2.typ == MsgType.DATA
    assert (r2.flags & FLAG_MF) == 0

    # OK con mf=True no deberia importar MF (lo ignoramos en control)
    ok = make_ok({"ok": True}, ver=VER_SW, ack=0)
    ok.flags |= FLAG_MF   # si alguien lo setea por error
    r3 = Datagrama.decode(ok.encode())
    assert r3.typ == MsgType.OK
    # El receptor puede ignorar MF en tipos no DATA; no assert estricto aqui
