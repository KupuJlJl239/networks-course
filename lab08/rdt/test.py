from rdt import *
import socket
import random



def create_udp_socket(port):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("0.0.0.0", port))
    return udp_socket

def create_recv(udp_socket: socket.socket, addr, loss_probability):
    def recv():
        while(1):
            data, _addr = udp_socket.recvfrom(1500)
            if _addr == addr and random.random() > loss_probability:
                return data
    return recv


def create_send(udp_socket: socket.socket, addr, loss_probability):
    def send(data):
        if random.random() > loss_probability:
            udp_socket.sendto(data, addr)
    return send



def main(): 
    udp_socket_1 = create_udp_socket(50001)
    udp_socket_2 = create_udp_socket(50002)

    send_1 = create_send(udp_socket_1, ("127.0.0.1", 50002), 0.3)
    recv_1 = create_recv(udp_socket_1, ("127.0.0.1", 50002), 0.3)

    send_2 = create_send(udp_socket_2, ("127.0.0.1", 50001), 0.3)
    recv_2 = create_recv(udp_socket_2, ("127.0.0.1", 50001), 0.3)

    rdt_socket_1 = rdt_socket(send_1, recv_1, timeout=0.1)
    rdt_socket_2 = rdt_socket(send_2, recv_2, timeout=0.1)


    rdt_socket_1.send(b'Hello 1')
    rdt_socket_1.send(b'Hello 2')
    rdt_socket_1.send(b'Hello 3')
    rdt_socket_1.send(b'Hello 4')
    rdt_socket_1.send(None)

    while(1):
        data = rdt_socket_2.recv()
        if(data == None):
            break
        print(f' --> {data}')

    print('END MAIN')
    # while(1): pass

main()