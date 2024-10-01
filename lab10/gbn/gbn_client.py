from gbn import *
from send_and_recv import *


n = 15  # число сегментов


def on_ack_good_receive(gbn: gbn_socket, s: gbn_segment):
    for i in range(n):
        if i == gbn.send_number:
            print('\033[102m', end='')  # зелёный

        if i == s.segment_number:   
            print('\033[44m', end='')  # синий
        
        if i == gbn.send_number + gbn.sended:   
            print('\033[0m', end='')  # обычный

        print(i, end=' ')
    print('\033[0m', end='')  # обычный
    print()


def on_ack_repeat_receive(gbn: gbn_socket, s: gbn_segment):
    for i in range(n):
        if i == gbn.send_number:
            print('\033[101m', end='')  # красный

        if i == gbn.send_number + 1:
            print('\033[44m', end='')  # синий
        
        if i == gbn.send_number + gbn.sended:   
            print('\033[0m', end='')  # обычный

        print(i, end=' ')
    print('\033[0m', end='')  # обычный
    print()
    

def main():

    # Настравиваем udp сокеты для использования протоколом rdt
    udp_socket_1 = create_udp_socket(50001)

    # функции отправки и получения, имитирующие 30% потерю пакетов
    loss_prob = 0.3
    send_1 = create_send(udp_socket_1, ("127.0.0.1", 50002), loss_prob)
    recv_1 = create_recv(udp_socket_1, ("127.0.0.1", 50002), loss_prob)

    timeout = 0.1
    print(f'Таймаут: {timeout} секунд')

    N = 4
    print(f'Размер окна: {N}')


    callbacks_1 = {
        "ack_good_receive": on_ack_good_receive,
        "ack_repeat_receive": on_ack_repeat_receive,
    }
    rdt_socket_1 = gbn_socket(send_1, recv_1, timeout=timeout, N=N, callbacks=callbacks_1)

    
    segments = [('hello' + str(i)).encode() for i in range(n)]
    # segments.append(None)

    # Отправляем всё
    for s in segments:
        rdt_socket_1.send(s)

    # print('\nКлиент отправил все пакеты!!!')


main()