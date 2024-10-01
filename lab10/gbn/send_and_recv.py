
"""
Файл содержит функции для симуляции потери пакетов:
* create_udp_socket - создаёт UDP сокет на данном порту
* create_recv - создаёт функцию для получения с симуляцией потери
* create_send - создаёт функцию для отправки с симуляцией потери
"""

import socket
import random


def create_udp_socket(port):
    """
    создаёт UDP сокет на данном порту
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("0.0.0.0", port))
    return udp_socket

def create_recv(udp_socket: socket.socket, addr, loss_probability):
    """
    ненадёжное получение из данного UDP сокета от данного адреса
    является блокирующим
    """
    def recv():
        while(1):
            data, _addr = udp_socket.recvfrom(1500)
            if _addr == addr and random.random() > loss_probability:
                return data
    return recv


def create_send(udp_socket: socket.socket, addr, loss_probability):
    """
    ненадёжная отправка из данного UDP сокета данному адресу
    является неблокирующей
    """
    def send(data):
        if random.random() > loss_probability:
            udp_socket.sendto(data, addr)
    return send