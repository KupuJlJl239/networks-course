from gbn import *
import socket
import random
import sys



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

    # Настравиваем udp сокеты для использования протоколом rdt
    udp_socket_1 = create_udp_socket(50001)
    udp_socket_2 = create_udp_socket(50002)

    # функции отправки и получения, имитирующие 30% потерю пакетов
    loss_prob = 0.3
    send_1 = create_send(udp_socket_1, ("127.0.0.1", 50002), loss_prob)
    recv_1 = create_recv(udp_socket_1, ("127.0.0.1", 50002), loss_prob)

    send_2 = create_send(udp_socket_2, ("127.0.0.1", 50001), loss_prob)
    recv_2 = create_recv(udp_socket_2, ("127.0.0.1", 50001), loss_prob)

    timeout = 1
    print(f'Таймаут: {timeout} секунд')

    N = 4
    print(f'Размер окна: {N}')

    # Создаём два сокета, между которыми будут передаваться данные
    # Получаем 2 rdt сокета, связанных между собой в обе стороны
    # (благодаря верно указанным адресам в функциях send_* и recv_*)
    # По каждому пожно отправить порцию данных и получить от другого
    rdt_socket_1 = gbn_socket(send_1, recv_1, timeout=timeout, N=N)
    rdt_socket_2 = gbn_socket(send_2, recv_2, timeout=timeout, N=N)

    # Будем передавать всё сегментами по 500 байт
    segment_size = 500
    print(f'Размер сегмента: {segment_size} байт')

    # Передадим исходный код реализации rdt в обе стороны
    with open('gbn.py', 'rb') as f:
        data = f.read()

    # Разделяем данные на сегменты размера segment_size
    segments = [data[segment_size*i:segment_size*(i+1)] for i in range(len(data) // segment_size + 1)]
    # segments = [b'hello 1', b'hello 2', b'hello 3', b'hello 4', b'hello 5']
    # segments = [b'hello 1']

    print(f'Размер файла: {len(data)} байт')
    print(f'Число сегментов: {len(segments)}')

    # Сначала обе стороны отправляют данные (метод send сегмент в очередь и не блокирует исполнение)
    for s in segments:
        rdt_socket_1.send(s)
        rdt_socket_2.send(s)

    # Вызов .send(None) говорит что больше ничего отправлено не будет
    rdt_socket_1.send(None)
    rdt_socket_2.send(None)


    # Теперь получаем сегменты методом recv. 
    # Он блокирует исполнение до получения сегмента
    # Если сегменты кончились, всегда возвращает None

    segments_1 = [] # сегменты, полученные первым сокетом
    while(1):
        s = rdt_socket_1.recv()
        if s is not None:
            segments_1.append(s)
        else:
            break
    

    segments_2 = [] # сегменты, полученные вторым сокетом
    while(1):
        s = rdt_socket_2.recv()
        if s is not None:
            segments_2.append(s)
        else:
            break

    # собираем сегменты обратно
    data_1 = b''.join(segments_1) 
    data_2 = b''.join(segments_2)

    # Проверяем корректность
    assert data == data_1
    assert data == data_2

    print()
    print('Успех: полученные данные совпали с исходными!!!')

main()