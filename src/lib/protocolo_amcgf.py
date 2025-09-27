# amcgf_proto.py

"""
File Transfer / Go-Back-N / Stop-and-Wait (AMCGF) Header

    0               1             2               3
    0 1 2 3 4 5 6 7 0 1 2 3 4 5 6 7 0 1 2 3 4 5 6 7 0 1 2 3 4 5 6 7 
   +---------------+---------------+-------------------------------+
   |     Type      |    Version    |             Flags             |
   +---------------+---------------+-------------------------------+
   |            Length             |           Checksum            |
   +---------------------------------------------------------------+
   |                        AckNum (32 bits)                       |
   +---------------------------------------------------------------+
   |                        SeqNum (32 bits)                       |
   +---------------------------------------------------------------+
   |                            Payload                            |
   +---------------------------------------------------------------+
"""

from dataclasses import dataclass
from enum import IntEnum
import struct

# Definicion de constantes y enum

# Header nuevo (16 bytes):
# | TYPE(1) | VER(1) | FLAGS(2) | LEN(2) | CHECKSUM(2) | ACKNUM(4) | SEQNUM(4) |
# Ordenado para uso simple con struct.pack en big-endian.
HDR_FMT  = "!BBHHHII"  # B=1, B=1, H=2, H=2, H=2, I=4, I=4  => 16 bytes
HDR_SIZE = struct.calcsize(HDR_FMT)

# Version del RDT (Stop-and-Wait o Go-Back-N)
VER_SW  = 1  # Stop-and-Wait
VER_GBN = 2  # Go-Back-N

# MTU de payload (recomendado por el TP)
MSS = 1200
MTU = HDR_SIZE + MSS

# Flags de 16 bits
# Se usa el bit mas alto (0x8000) como "ACK flag" (0x8000 = 1000 0000 0000 0000)
FLAG_ACK = 0x8000
# Flag MF (More Fragments)
FLAG_MF  = 0x4000   

# Convencion: ack == 0 => no hay ACK piggyback
ACK_NONE = 0

# Payload key
PAYLOAD_DATA_KEY = "chunk"
PAYLOAD_FILENAME_KEY = "filename"
PAYLOAD_ERR_MSG_KEY = "message"


class MsgType(IntEnum):
    REQUEST_UPLOAD   = 0
    REQUEST_DOWNLOAD = 1
    OK               = 2
    ERR              = 3
    DATA             = 4 
    ACK              = 5
    BYE              = 6 

# Errores
class ProtoError(Exception): ...
class BadChecksum(ProtoError): ...
class Truncated(ProtoError): ...
class FrameTooBig(ProtoError): ...

# Checksum estilo Internet sobre header (con checksum en 0) + payload
def inet_checksum(data: bytes) -> int:
    # Si el largo es impar, agregar un byte 0
    if len(data) % 2:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) | data[i + 1]
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF

@dataclass
class Datagrama:
    ver: int                  # VER_SW o VER_GBN
    typ: MsgType              # Tipo de mensaje
    ack: int = 0              # Numero de ACK (piggyback o para MsgType.ACK)
    seq: int = 0              # Numero de secuencia para DATA
    payload: bytes = b""      # Datos
    flags: int = 0            # Flags de 16 bits (FLAG_ACK si corresponde)

    def encode(self) -> bytes:
        if len(self.payload) > MSS:
            raise FrameTooBig(f"DATA payload {len(self.payload)} > MSS {MSS}")

        # Encendido automatico del flag ACK si:
        # - el tipo es ACK, o
        # - hay piggyback (ack != 0)
        flags = self.flags
        if self.typ == MsgType.ACK or self.ack != 0:
            flags |= FLAG_ACK

        # Encendido automatico del flag MF si:
        # - el tipo es DATA, y
        # - el flag ya viene seteado en self.flags
        if (self.typ == MsgType.DATA or self.typ == MsgType.REQUEST_DOWNLOAD or self.typ == MsgType.REQUEST_UPLOAD) and (self.flags & FLAG_MF):
            flags |= FLAG_MF

        # Header con checksum en 0 para calcularlo
        header_wo_ck = struct.pack(
            HDR_FMT,
            int(self.typ),          # TYPE
            self.ver,               # VER
            flags,                  # FLAGS
            len(self.payload),      # LEN
            0,                      # CHECKSUM (0 para el calculo)
            self.ack,               # ACKNUM
            self.seq,               # SEQNUM
        )
        
        ck = inet_checksum(header_wo_ck + self.payload)

        # Header final con checksum real
        header = struct.pack(
            HDR_FMT,
            int(self.typ),
            self.ver,
            flags,
            len(self.payload),
            ck,
            self.ack,
            self.seq,
        )

        return header + self.payload

    @staticmethod
    def decode(buf: bytes) -> "Datagrama":
        # Verificar largo minimo de header
        if len(buf) < HDR_SIZE:
            raise Truncated(f"{len(buf)} < HDR_SIZE {HDR_SIZE}")

        typ, ver, flags, length, ck, ack, seq = struct.unpack(HDR_FMT, buf[:HDR_SIZE])

        # Extraer payload
        payload = buf[HDR_SIZE:HDR_SIZE + length]
        if len(payload) != length:
            raise Truncated(f"payload {len(payload)} != {length}")

        # Recalcular checksum con campo en 0
        header_zero = struct.pack(
            HDR_FMT,
            typ,
            ver,
            flags,
            length,
            0,      # checksum cero para validar
            ack,
            seq,
        )
        if inet_checksum(header_zero + payload) != ck:
            raise BadChecksum("checksum mismatch")

        return Datagrama(
            ver=ver,
            typ=MsgType(typ),
            ack=ack,
            seq=seq,
            payload=payload,
            flags=flags,
        )


    def __str__(self) -> str:
        # Traduccion de version a nombre
        ver_name = "SW" if self.ver == VER_SW else "GBN" if self.ver == VER_GBN else str(self.ver)

        # Decodificacion de flags
        flags_list = []
        if self.flags & FLAG_ACK:
            flags_list.append("ACK")
        if self.flags & FLAG_MF:
            flags_list.append("MF")
        flags_str = "[" + ", ".join(flags_list) + "]" if flags_list else "[]"

        # Longitud del payload
        plen = len(self.payload)

        # Preview de payload (primeros 20 bytes)
        if plen > 0:
            preview = self.payload[:20]
            if isinstance(preview, bytes):
                try:
                    preview_str = preview.decode("utf-8", "ignore")
                except Exception:
                    preview_str = preview.hex()
            else:
                preview_str = str(preview)
        else:
            preview_str = "(empty)"

        return (
            f"Datagrama {{\n"
            f"  type={self.typ.name} ({int(self.typ)})\n"
            f"  ver={ver_name}\n"
            f"  flags=0x{self.flags:04X} {flags_str}\n"
            f"  ack={self.ack}\n"
            f"  seq={self.seq}\n"
            f"  payload_len={plen}\n"
            f"  payload_preview={preview_str}\n"
            f"}}"
        )




# Funciones auxiliares payload | encode y decode texto plano
def _encode_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    elif isinstance(v, (int, float, str)):
        return str(v)
    elif isinstance(v, bytes):
        return v.hex()
    else:
        raise ValueError(f"Unsupported type for encoding: {type(v)}")

def _decode_value(k: str, v: str):
    if k == "chunk":
        return bytes.fromhex(v)
    elif v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v

def payload_encode(d: dict) -> bytes:
    items = []
    for k, v in d.items():
        items.append(f"{k}={_encode_value(v)}")
    return "\n".join(items).encode("utf-8")

def payload_decode(b: bytes) -> dict:
    out = {}
    if not b:
        return out
    for line in b.decode("utf-8", "strict").splitlines():
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = _decode_value(k.strip(), v.strip())
    return out

# -------------------- API --------------------

def make_req_upload(filename: str, ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.REQUEST_UPLOAD, payload=payload_encode({PAYLOAD_FILENAME_KEY: filename}))

def make_req_download(filename: str, ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.REQUEST_DOWNLOAD, payload=payload_encode({PAYLOAD_FILENAME_KEY: filename}))

# OK / ERR con piggyback opcional de ACK (ack != 0 => ACK valido y se encendera FLAG_ACK)
def make_ok(extra: dict | None = None, ver: int = VER_SW, ack: int = ACK_NONE) -> Datagrama:
    return Datagrama(ver, MsgType.OK, ack=ack, payload=payload_encode(extra or {}))

def make_err(msg: str, ver: int = VER_SW, ack: int = ACK_NONE) -> Datagrama:
    return Datagrama(ver, MsgType.ERR, ack=ack, payload=payload_encode({PAYLOAD_ERR_MSG_KEY: msg}))

# DATA con seq obligatorio y ACK piggyback opcional
def make_data(seq: int, chunk: bytes, ver: int, ack: int = ACK_NONE, mf: bool = False) -> Datagrama:
    flags = FLAG_MF if mf else 0
    return Datagrama(ver, MsgType.DATA, ack=ack, seq=seq, payload=payload_encode({PAYLOAD_DATA_KEY: chunk}), flags=flags)

# ACK puro
def make_ack(acknum: int, ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.ACK, ack=acknum)

def make_bye(ver: int) -> Datagrama:
    return Datagrama(ver, MsgType.BYE)


"""
# Ejemplo de checksum [DEBUG]
# print(inet_checksum(b"hello"))
msg = b"ABCD"     # en ASCII: 41 42 43 44 hex
# Palabras de 16 bits: 0x4142, 0x4344
# Suma: 0x4142 + 0x4344 = 0x8476
# Complemento a uno: ~0x8476 = 0x7B79
print(hex(inet_checksum(msg)))  # '0x7b79'


# DATA
d = {"segmento": True, "data": b"hola"}
enc = payload_encode(d)
dec = payload_decode(enc)
print(f"Bytes: {enc!r}")
print(f"Hex: {enc.hex(' ', 1)}")
print(f"Dec: {dec!r}")

print("=======================================")
a = b"holaaaaaaaaaaaaaaaaaaaaaa"
for i in range(0, len(a), 3):
    print(i)
    print(a[i:i+3])
    
d = make_ok(extra={"ready": True}, ver=VER_SW, ack=42)
d = d.encode()
d = Datagrama.decode(d)
print(d)

# 2 fragmentos y un ultimo
d1 = make_data(seq=0, chunk=b"A"*100, ver=VER_SW, mf=True)
d2 = make_data(seq=1, chunk=b"B"*100, ver=VER_SW, mf=True, ack=42)
d3 = make_data(seq=2, chunk=b"C"*60,  ver=VER_SW, mf=False)  # ultimo

for d in (d1, d2, d3):
    dec = Datagrama.decode(d.encode())
    print(dec.pretty_print())   # deberias ver [MF] en los primeros dos, y sin MF en el ultimo
"""