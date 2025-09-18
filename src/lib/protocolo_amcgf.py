# amcgf_proto.py
from dataclasses import dataclass
from enum import IntEnum
import struct

# Definicion de constantes y enum

# Header: | MAGIC(2) | VER(1) | TYPE(1) | ACKNUM(4) | SEQNUM(4) | LEN(2) | CHECKSUM(2) | = 20 bytes
HDR_FMT  = "!HBBIIHH"             # big-endian tamaño total 20 bytes ! = big-endian, H = 2 bytes, B = 1 byte, I = 4 bytes
HDR_SIZE = struct.calcsize(HDR_FMT)

# 2 bytes: 0xAC 0xGF
MAGIC = 0xCAFE
VER_SW  = 1                       # Stop-and-Wait
VER_GBN = 2                       # Go-Back-N

MSS = 1200                        # payload max recomendado para DATA
MAX_FRAME = HDR_SIZE + MSS

class MsgType(IntEnum):
    HELLO            = 0
    NEGOTIATE        = 1
    NEGOTIATE_OK     = 2
    REQUEST_UPLOAD   = 3
    REQUEST_DOWNLOAD = 4
    OK    = 5
    ERR   = 6
    DATA  = 7
    ACK   = 8
    BYE   = 9

# Errores
class ProtoError(Exception): ...
class BadMagic(ProtoError): ...
class BadChecksum(ProtoError): ...
class Truncated(ProtoError): ...
class FrameTooBig(ProtoError): ...

# Algoritmo que hace checksum
def inet_checksum(data: bytes) -> int:
    # Si el tamaño es impar, agregamos un byte 0
    if len(data) % 2:
        data += b"\x00"
    # Sumamos todos los pares de bytes
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) | data[i+1]
        s = (s & 0xFFFF) + (s >> 16)
    # Devolvemos el checksum complemento
    return (~s) & 0xFFFF

# Clase Packet
@dataclass # Crea un constructor automatico
class Datagrama:
    ver: int # SW o GBN
    typ: MsgType # Tipo de mensaje
    ack: int = 0 # Número de ACK
    seq: int = 0 # Número de secuencia
    payload: bytes = b"" # Payload

    def encode(self) -> bytes:
        if len(self.payload) > MSS and self.typ == MsgType.DATA:
            raise FrameTooBig(f"DATA payload {len(self.payload)} > MSS {MSS}")
        
        # Header sin checksum
        header_wo_ck = struct.pack(
            HDR_FMT, MAGIC, self.ver, int(self.typ), self.ack, self.seq, len(self.payload), 0
        )
        
        # Calculo checksum
        ck = inet_checksum(header_wo_ck + self.payload)
        
        # Header con checksum
        header = struct.pack(
            HDR_FMT, MAGIC, self.ver, int(self.typ), self.ack, self.seq, len(self.payload), ck
        )
        
        return header + self.payload

    # Static method para desempaquetar requiere de la clase misma
    @staticmethod
    def decode(buf: bytes) -> "Datagrama":
        # Por lo menos el header
        if len(buf) < HDR_SIZE:
            raise Truncated(f"{len(buf)} < HDR_SIZE {HDR_SIZE}")
        
        # Desempaquetado del header
        magic, ver, typ, ack, seq, length, ck = struct.unpack(HDR_FMT, buf[:HDR_SIZE])
        
        # Validacion del magic
        if magic != MAGIC:
            raise BadMagic(hex(magic))          
        
        # Extraigo el payload
        payload = buf[HDR_SIZE:HDR_SIZE+length]
        if len(payload) != length:
            raise Truncated(f"payload {len(payload)} != {length}")
        
        # Header sin checksum
        header_zero = struct.pack(HDR_FMT, magic, ver, typ, ack, seq, length, 0)
        
        # Validacion del checksum
        if inet_checksum(header_zero + payload) != ck:
            raise BadChecksum("checksum mismatch")
        
        return Datagrama(ver=ver, typ=MsgType(typ), ack=ack, seq=seq, payload=payload)


#######################################################################################

# Funciones auxiliares
def payload_encode(d: dict[str, str | int]) -> bytes:
    return "\n".join(f"{k}={v}" for k, v in d.items()).encode("utf-8")

def payload_decode(b: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    if not b:
        return out
    for line in b.decode("utf-8", "strict").splitlines():
        if not line or "=" not in line: 
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out

#######################################################################################

# API

# HELLO
def make_hello(proto: str = "SW") -> Datagrama:
    ver = VER_SW if proto.upper() == "SW" else VER_GBN
    return Datagrama(ver, MsgType.HELLO, payload=payload_encode({}))

# NEGOTIATE
def make_negotiate(proto: str, mss: int = MSS, win: int | None = None, rto_ms: int | None = None) -> Datagrama:
    ver = VER_SW if proto.upper() == "SW" else VER_GBN
    
    d = {"mss": mss}
    
    # Por ahora los dejo en el payload 
    if win: d["win"] = win
    if rto_ms: d["rto_ms"] = rto_ms 
    
    return Datagrama(ver, MsgType.NEGOTIATE, payload=payload_encode(d))

# NEGOTIATE_OK
def make_negotiate_ok(ver: int, mss: int, win: int | None = None, rto_ms: int | None = None) -> Datagrama:
    d = {"ver": ver, "mss": mss}
    if win: d["win"] = win
    if rto_ms: d["rto_ms"] = rto_ms
    return Datagrama(ver, MsgType.NEGOTIATE_OK, payload=payload_encode(d))

# REQUEST_UPLOAD
def make_req_upload(name: str, size: int, ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.REQUEST_UPLOAD, payload=payload_encode({"name": name, "size": size}))

# REQUEST_DOWNLOAD
def make_req_download(name: str, ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.REQUEST_DOWNLOAD, payload=payload_encode({"name": name}))

# OK
def make_ok(extra: dict | None = None, ver: int = VER_SW) -> Datagrama:
    return Datagrama(
        ver,
        MsgType.OK,
        payload=payload_encode(extra or {})
    )

# ERR
def make_err(code: str, msg: str, ver: int = VER_SW) -> Datagrama:
    return Datagrama(
        ver,
        MsgType.ERR,
        payload=payload_encode({"code": code, "message": msg})
    )

# DATA
def make_data(seq: int, chunk: bytes, ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.DATA, seq=seq, payload=chunk)

# ACK
def make_ack(acknum: int, ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.ACK, ack=acknum)

# BYE
def make_bye(ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.BYE)




# Ejemplo de checksum
print(inet_checksum(b"hello"))
msg = b"ABCD"     # en ASCII: 41 42 43 44 hex
# Palabras de 16 bits: 0x4142, 0x4344
# Suma: 0x4142 + 0x4344 = 0x8476
# Complemento a uno: ~0x8476 = 0x7B79
print(hex(inet_checksum(msg)))  # '0x7b79'