

import socket
import sys


def run_server(port):
    """
    запускает сервер, слушающий входящие IPv6 TCP соединения на данном порту
    при установки соединения считывает данные, переводит текст в верхний регистр,
    отправляет обратно изменённый текст и закрывает соединение
    """
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)
    s.bind(('', port, 0, 0))
    s.listen(10)

    print(f'Слушаем на порту {port}')

    while(True):
        conn, addr = s.accept()
        data = conn.recv(1500)
        print(f'запрос от {addr}: "{data}"')

        text = data.decode().upper()
        conn.send(text.encode())
        conn.close()

run_server(int(sys.argv[1]))