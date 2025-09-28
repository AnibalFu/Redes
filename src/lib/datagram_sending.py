from lib.protocolo_amcgf import *
from socket import socket


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

