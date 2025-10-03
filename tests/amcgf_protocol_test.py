from lib.protocolo_amcgf import *

def test_encode_decode_json():
    """Testing encode/decode de un JSON con distintos tipos"""
    
    json = {'number': 1, 'string': 'Hola, Mundo!', 'boolean': True, 'binary': b'Hallo, Welt!'}
    encoded = payload_encode(json)
    decoded = payload_decode(encoded)
    
    assert decoded['number'] == 1 \
        and decoded['string'] == 'Hola, Mundo!' \
        and decoded['boolean'] == True \
        and decoded['binary'] == "b'Hallo, Welt!'"

def test_encode_decode_datagram():
    """Testing encode/decode de un Datagram"""
    
    datagram = Datagram(ver=VER_SW, typ=1, ack=0, seq=0, payload=b'Hallo Welt!')

    encoded = datagram.encode()
    decoded = Datagram.decode(encoded)
    
    assert decoded.ver == VER_SW \
        and decoded.typ == 1 \
        and decoded.ack == 0 \
        and decoded.seq == 0 \
        and decoded.payload == b'Hallo Welt!'

def test_exception_badchecksum():
    """Testing de excepción BadChecksum"""
    
    datagram = Datagram(ver=VER_SW, typ=5, seq=1, payload=b'Hello World!')
    
    hex = bytearray(datagram.encode())
    hex[-1] ^= 0xFF
    
    try:
        Datagram.decode(bytes(hex))
        assert False, 'Should have raised BadChecksum'
    except Exception as e:
        assert 'BadChecksum' in str(type(e).__name__)

def test_exception_truncated():
    """Testing de excepción Truncated"""

    datagram = Datagram(ver=VER_SW, typ=5, seq=2, payload=b'VM: VirtualBox')
    encoded = datagram.encode()
    
    try:
        Datagram.decode(encoded[:HDR_SIZE - 1])
        assert False, 'Should have raised Truncated'
    except Exception as e:
        assert 'Truncated' in str(type(e).__name__)

def test_exception_frametoobig():
    """Testing de excepción FrameTooBig"""

    try:
        Datagram(ver=VER_SW, typ=5, seq=0, payload=b'x' * (MSS + 1)).encode()
        assert False, "Debería haber lanzado FrameTooBig"
    except Exception as e:
        assert 'FrameTooBig' in str(type(e).__name__)

def test_ack_flag_behavior():
    """Testing del comportamiento del FLAG_ACK"""
    
    ack = make_ack(acknum=123, ver=VER_SW)
    encoded = ack.encode()
    datagram = Datagram.decode(encoded)

    assert datagram.typ == MsgType.ACK and datagram.flags & FLAG_ACK and datagram.ack == 123

    ok = make_ok(ver=VER_SW, ack=123)
    encoded = ok.encode()
    datagram = Datagram.decode(encoded)

    assert datagram.typ == MsgType.OK and datagram.flags & FLAG_ACK and datagram.ack == 123

    data = make_data(seq=123, chunk=b'Hello World!', ver=VER_SW)
    encoded = data.encode()
    datagram = Datagram.decode(encoded)

    assert datagram.typ == MsgType.DATA and (datagram.flags & FLAG_ACK) == 0

def test_make_req_upload():
    upload = make_req_upload(filename='file.bin', ver=VER_SW, data_size=64)
    
    assert upload.typ == MsgType.REQUEST_UPLOAD

def test_make_req_download():
    download = make_req_download(filename='file.bin', ver=VER_SW)

    assert download.typ == MsgType.REQUEST_DOWNLOAD

def test_make_ok():
    ok = make_ok(ver=VER_GBN)

    assert ok.typ == MsgType.OK and ok.ver == VER_GBN

def test_make_err():
    err = make_err(msg='Error', ver=VER_SW)

    assert err.typ == MsgType.ERR

def test_mf_flag_behavior():
    """Testing del comportamiento del FLAG_MF"""

    datagram = make_data(seq=10, chunk=b'x' * 10, ver=VER_SW, mf=True)
    encoded = datagram.encode()
    decoded = Datagram.decode(encoded)

    assert decoded.typ == MsgType.DATA and decoded.flags & FLAG_MF

    datagram = make_data(seq=10, chunk=b'x' * 10, ver=VER_SW, mf=False)
    encoded = datagram.encode()
    decoded = Datagram.decode(encoded)

    assert decoded.typ == MsgType.DATA and (decoded.flags & FLAG_MF) == 0