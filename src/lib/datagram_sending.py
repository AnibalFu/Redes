from lib.protocolo_amcgf import *
from socket import socket

def send_content(sender_socket, receiver_addr, content, chunk_size, timeout=2):
    sender_socket.settimeout(timeout)
    seq = 0
    for i in range(0, len(content), chunk_size):
        payload = content[i:i + chunk_size]
        mf = (i + chunk_size) < len(content)
        datagrama = make_data(seq=seq, chunk=payload, ver=VER_SW, mf=mf)
        encoded = datagrama.encode()
        ack_ok = False
        while not ack_ok:
            sender_socket.sendto(encoded, receiver_addr)
            print(f"[DEBUG] Enviado DATA con seq {seq}, MF={mf}")
            try:
                data, _ = sender_socket.recvfrom(MTU)
                datagram = Datagrama.decode(data)
                if datagram.typ == MsgType.ACK and datagram.ack == seq + 1:
                    print(f"[DEBUG] ACK correcto recibido: {datagram}")
                    ack_ok = True
                else:
                    print(f"[DEBUG] ACK incorrecto (esperaba {seq+1}), reenviando DATA seq {seq}")
            except TimeoutError:
                print(f"[DEBUG] Timeout esperando ACK para seq {seq}, reenviando DATA")
        seq += 1
    
    data, _ = sender_socket.recvfrom(MTU)
    resp = Datagrama.decode(data)
    assert resp.typ == MsgType.BYE, "Esperaba BYE tras DATA"
    print("Transferencia finalizada correctamente")
    ok = make_ok(ver=VER_SW)
    sender_socket.sendto(ok.encode(), receiver_addr)
    
    sender_socket.settimeout(None)  # Restablece el timeout


def send_request(request_maker, sender_socket, receiver_addr, filename):
    request = request_maker(filename, VER_SW)
    sender_socket.sendto(request.encode(), receiver_addr)
    ans, new_server_addr = sender_socket.recvfrom(MTU)
    resp = Datagrama.decode(ans)
    assert resp.typ == MsgType.OK, "Esperaba OK tras REQUEST"
    return new_server_addr


def finalizar_conexion(sender_socket: socket, receiver_addr: socket):
    bye = make_bye(VER_SW)
    sender_socket.sendto(bye.encode(), receiver_addr)
    ans, _ = sender_socket.recvfrom(MTU)
    resp = Datagrama.decode(ans)
    assert resp.typ == MsgType.OK, "Esperaba OK tras BYE" # TODO: quitar assert
    print("Transferencia finalizada correctamente")
    sender_socket.close()

