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

import struct

from dataclasses import dataclass
from enum import IntEnum

# Definicion de constantes y enum

# Header nuevo (16 bytes):
# | TYPE(1) | VER(1) | FLAGS(2) | LEN(2) | CHECKSUM(2) | ACKNUM(4) | SEQNUM(4) |
# Ordenado para uso simple con struct.pack en big-endian.
HDR_FMT  = "!BBHHHII"  # B=1, B=1, H=2, H=2, H=2, I=4, I=4  => 16 bytes
HDR_SIZE = struct.calcsize(HDR_FMT)

VER_SW  = 1  # Stop-and-Wait
VER_GBN = 2  # Go-Back-N


# Se usa el bit mas alto (0x8000) como "ACK flag" (0x8000 = 1000 0000 0000 0000)
FLAG_ACK = 0x8000
# Flag MF (More Fragments) | 0x4000 = 0100 0000 0000 0000
FLAG_MF  = 0x4000   

# ack == 0 => no hay ACK piggyback
ACK_NONE = 0

PAYLOAD_DATA_KEY = "chunk" # deprecado
PAYLOAD_FILENAME_KEY = "filename" # deprecado
PAYLOAD_ERR_MSG_KEY = "message" # deprecado
PAYLOAD_FILE_SIZE_KEY = "file_size"  # deprecado

class MsgType(IntEnum):
    REQUEST_UPLOAD   = 0
    REQUEST_DOWNLOAD = 1
    OK               = 2
    ERR              = 3
    DATA             = 4 
    ACK              = 5
    BYE              = 6 

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
class Datagram:
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
    def decode(buf: bytes) -> 'Datagram':
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

        return Datagram(
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
            preview = self.payload
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
            f"Datagram {{\n"
            f"  type={self.typ.name} ({int(self.typ)})\n"
            f"  ver={ver_name}\n"
            f"  flags=0x{self.flags:04X} {flags_str}\n"
            f"  ack={self.ack}\n"
            f"  seq={self.seq}\n"
            f"  payload_len={plen}\n"
            f"  payload_preview={preview_str}\n"
            f"}}"
        )

def _encode_value(v) -> str:
    if isinstance(v, bool):
        return 'true' if v else 'false'
    elif isinstance(v, (int, float, str)):
        return str(v)
    elif isinstance(v, bytes):
        return v
    else:
        raise ValueError(f"Unsupported type for encoding: {type(v)}")

def _decode_value(k: str, v: str) -> str | bool | int | float:
    if k == PAYLOAD_DATA_KEY:
        return v
    elif v.lower() in ('true', 'false'):
        return v.lower() == 'true'
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v

def payload_encode(d: dict) -> bytes:
    # Caso especial: payload binario puro bajo la clave de datos.
    # Formato: b"<KEY>=" + <bytes>
    if (
        len(d) == 1
        and PAYLOAD_DATA_KEY in d
        and isinstance(d[PAYLOAD_DATA_KEY], (bytes, bytearray, memoryview))
    ):
        v = bytes(d[PAYLOAD_DATA_KEY])
        return PAYLOAD_DATA_KEY.encode('utf-8') + b'=' + v

    # Caso general (texto): k=v por linea, UTF-8
    items = []
    for k, v in d.items():
        items.append(f'{k}={_encode_value(v)}')
    return '\n'.join(items).encode('utf-8')

def payload_decode(b: bytes) -> dict:
    out = {}
    if not b:
        return out

    # Caso especial binario: "<KEY>=" + bytes crudos
    prefix = (PAYLOAD_DATA_KEY + '=').encode('utf-8')
    if b.startswith(prefix):
        out[PAYLOAD_DATA_KEY] = b[len(prefix):]
        return out

    # Caso general (texto): k=v por linea, UTF-8
    for line in b.decode('utf-8', 'strict').splitlines():
        if not line or '=' not in line:
            continue
        k, v = line.split('=', 1)
        out[k.strip()] = _decode_value(k.strip(), v.strip())
    return out

# -------------------- API --------------------

def make_req_upload(filename: str, ver: int, data_size: int) -> Datagram:
    """Crea un datagrama de solicitud de subida de archivo."""

    return Datagram(ver, MsgType.REQUEST_UPLOAD, payload=payload_encode({PAYLOAD_FILENAME_KEY: filename, PAYLOAD_FILE_SIZE_KEY: data_size}))

def make_req_download(filename: str, ver: int) -> Datagram:
    """Crea un datagrama de solicitud de descarga de archivo."""

    return Datagram(ver, MsgType.REQUEST_DOWNLOAD, payload=payload_encode({PAYLOAD_FILENAME_KEY: filename}))

def make_ok(extra: dict | None = None, ver: int = VER_SW, ack: int = ACK_NONE) -> Datagram:
    """Crea un datagrama de OK, con campos extra opcionales en el payload."""
    
    return Datagram(ver, MsgType.OK, ack=ack, payload=payload_encode(extra or {}))

def make_err(msg: str, ver: int = VER_SW, ack: int = ACK_NONE) -> Datagram:
    """Crea un datagrama de error con mensaje."""
    
    return Datagram(ver, MsgType.ERR, ack=ack, payload=payload_encode({PAYLOAD_ERR_MSG_KEY: msg}))

def make_data(seq: int, chunk: bytes, ver: int, ack: int = ACK_NONE, mf: bool = False) -> Datagram:
    """Crea un datagrama de datos con numero de secuencia y payload."""
    
    return Datagram(ver, MsgType.DATA, ack=ack, seq=seq, payload=chunk, flags=FLAG_MF if mf else 0)

def make_ack(acknum: int, ver: int) -> Datagram:
    """Crea un datagrama de ACK con numero de ACK."""

    return Datagram(ver, MsgType.ACK, ack=acknum)

def make_bye(ver: int) -> Datagram:
    """Crea un datagrama de BYE para finalizar la conexion."""
    
    return Datagram(ver, MsgType.BYE)
