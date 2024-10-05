import socket
import sys


def main(host, port, text):
    """
    отправляет данному хосту на данный порт сообщение с текстом,
    затем ожидает ответа и возвращает полученный текст
    использует соединение по IPv6
    """
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)
    s.connect((host, port, 0, 0))

    send_data = text.encode()
    s.send(send_data)

    recv_data = s.recv(len(send_data))
    s.close()

    return recv_data.decode()


# main('localhost', 50000, 'hellooooo')

print(main(sys.argv[1], int(sys.argv[2]), sys.stdin.read()), end='')