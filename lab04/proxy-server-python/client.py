
import socket
from pprint import pprint

from http_parser.http import HttpStream
from http_parser.reader import SocketReader

from datetime import datetime
import time

import ssl



def read_http_message(socket: socket.socket):
    """ 
    Читает одно сообщение http из сокета.
    Возвращает объект типа HttpStream, читающий его лениво.

    Заголовок доступен из таких методов класса HttpStream, как .headers(), .url() и других.
    Тело можно прочитать из .body_file()
    """

    h = HttpStream(SocketReader(socket))

    """
    В http_parser есть баг: чтобы вызвать .method(), сначала нужно вызвать .url()!!!
    https://github.com/benoitc/http-parser/issues/72

    Поэтому сразу вызовем .url(), чтобы избавиться от него
    """
    h.url() 
    return h

context = ssl.create_default_context()

def main(host, file, port=443):
    """

    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s = context.wrap_socket(s, server_hostname=host)
    s.send(f"GET {file} HTTP/1.0\r\nHost: {host}\r\n\r\n".encode())
    h = read_http_message(s)

    print(h.status())
    pprint(dict(h.headers()))
    

    data = h.body_file().read()
    print(len(data), type(data))
    with open('data', 'wb') as f:
        f.write(data)



if __name__ == "__main__":

    # main('google.com', '/')
    # main('i.artfile.ru', '/2560x1600_835577_[www.ArtFile.ru].jpg')

    # artfile.me/404.php
    # main('artfile.me', '/404.php')

    # img.goodfon.ru/original/1920x1080/e/fe/landscape-field-flowers-sky.jpg
    # main('img.goodfon.ru', '/original/1920x1080/e/fe/landscape-field-flowers-sky.jpg')

    # https://img.badfon.ru/original/1920x1080/e/fe/landscape-field-flowers-sky.jpg
    # main('img.badfon.ru', '/original/1920x1080/e/fe/landscape-field-flowers-sky.jpg')


    # print(datetime.now(datetime.UTC).strftime("%a, %d %b %Y %T %zGMT"))
    # img.razrisyika.ru/kart/64/252763-gornyy-peyzazh-9.jpg
    main('img.razrisyika.ru', '/kart/64/252763-gornyy-peyzazh-9.jpg')

    # https://polinka.top/uploads/posts/2023-06/1685662834_polinka-top-p-krasivie-kartinki-prirodi-peizazhi-krasivo-69.jpg
    # main('polinka.top', '/uploads/posts/2023-06/1685662834_polinka-top-p-krasivie-kartinki-prirodi-peizazhi-krasivo-69.jpg')