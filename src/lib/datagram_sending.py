from lib.protocolo_amcgf import VER_SW, Datagrama, MsgType, make_bye, make_data, make_hello, make_ok


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
            print(f"Enviado DATA con seq {seq}, MF={mf}")
            try:
                data, _ = sender_socket.recvfrom(4096)
                datagram = Datagrama.decode(data)
                if datagram.typ == MsgType.ACK and datagram.ack == seq + 1:
                    print(f"ACK correcto recibido: {datagram}")
                    ack_ok = True
                else:
                    print(f"ACK incorrecto (esperaba {seq+1}), reenviando DATA seq {seq}")
            except TimeoutError:
                print(f"Timeout esperando ACK para seq {seq}, reenviando DATA")
        seq += 1
    
    data, _ = sender_socket.recvfrom(4096)
    resp = Datagrama.decode(data)
    assert resp.typ == MsgType.BYE, "Esperaba BYE tras DATA"
    print("Transferencia finalizada correctamente")
    ok = make_ok(ver=VER_SW)
    sender_socket.sendto(ok.encode(), receiver_addr)
    
    sender_socket.settimeout(None)  # Restablece el timeout


def send_request(request_maker, sender_socket, receiver_addr, filename):
    request = request_maker(filename, 0, VER_SW)
    sender_socket.sendto(request.encode(), receiver_addr)
    ans, new_server_addr = sender_socket.recvfrom(4096)
    resp = Datagrama.decode(ans)
    assert resp.typ == MsgType.OK, "Esperaba OK tras REQUEST"
    return new_server_addr


def send_bye(sender_socket, receiver_addr, buf):
    bye = make_bye(VER_SW)
    sender_socket.sendto(bye.encode(), receiver_addr)
    ans, _ = sender_socket.recvfrom(buf)
    resp = Datagrama.decode(ans)
    assert resp.typ == MsgType.OK, "Esperaba OK tras BYE"
    print("Transferencia finalizada correctamente")

