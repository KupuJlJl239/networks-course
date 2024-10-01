from gbn import *
from send_and_recv import *


n = 15  # число сегментов

def on_data_receive(gbn: gbn_socket, s: gbn_segment):
    for i in range(n):
        if i == s.segment_number:
            print('\033[101m', end='')
        if i == gbn.recv_number:
            print('\033[102m', end='')
        print(i, end=' ')
        print('\033[0m', end='')
    print()

def main():

    # Настравиваем udp сокеты для использования протоколом rdt
    udp_socket_2 = create_udp_socket(50002)

    # функции отправки и получения, имитирующие 30% потерю пакетов
    loss_prob = 0.3
    send_2 = create_send(udp_socket_2, ("127.0.0.1", 50001), loss_prob)
    recv_2 = create_recv(udp_socket_2, ("127.0.0.1", 50001), loss_prob)

    timeout = 0.1
    # print(f'Таймаут: {timeout} секунд')

    N = 1
    # print(f'Размер окна: {N}')



    callbacks_2 = {
        "data_good_receive": on_data_receive,
        "data_bad_receive": on_data_receive,
    }
    rdt_socket_2 = gbn_socket(send_2, recv_2, timeout=timeout, N=N, callbacks=callbacks_2)

    # Говорим клиенту что ничего не будем отправлять
    rdt_socket_2.send(None)

    # Получаем всё
    segments = []
    while True:
        s = rdt_socket_2.recv()
        segments.append(s)
        if s != f'hello {n-1}':
            break

main()