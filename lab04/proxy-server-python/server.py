import socket
import ssl

from http_parser.http import HttpStream
from http_parser.reader import SocketReader

from datetime import datetime
import pickle

import os
import sys

ssl_context = ssl.create_default_context()

def read_http_message(socket: socket.socket) -> HttpStream:
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


def print_log(msg: str):
    logs.write(msg)
    logs.flush()


def parse_uri(uri: str) -> (str, str):
    """
    Разделяет полученное сервером URI на хост и имя файла на хосте
    """
    n = uri.find('/', 1)
    if n == -1:
        host = uri[1:]
        file = '/'
    else:
        host = uri[1:n]
        file = uri[n:]
    return host, file


def headers_to_str(headers: dict) -> str:
    """
    Возвращает строку из всех заголовков (для их отправки по http)
    """
    return "\r\n".join([f'{k}: {v}' for k, v in headers.items()])


def get_gmt_time() -> str:
    """
    Функция оказалась ненужной, зато теперь я знаю как работать со временем в питоне
    """
    return datetime.utcnow().strftime("%a, %d %b %Y %T %zGMT")


def read_str(path: str) -> str | None:
    with open(path, 'r') as f:
        return f.read()
    
def write_str(path: str, str: str):
    with open(path, 'w') as f:
        f.write(str)

def write_bytes(path: str, bytes: bytes):
    with open(path, 'wb') as f:
        f.write(bytes)


def send_http_request_header(socket, method, file, headers):
    """ 
    Отправляет заголовок http запроса
    """
    socket.send(f"{method} {file} HTTP/1.1\r\n{headers_to_str(headers)}\r\n\r\n".encode())


def send_http_response_header(socket, status, headers):
    """ 
    Отправляет заголовок http ответа
    """
    socket.send(f"HTTP/1.1 {status}\r\n{headers_to_str(headers)}\r\n\r\n".encode())


def connect_https(host, port=443):
    """
    Соединяется по https, при ошибке кидает исключение
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s = ssl_context.wrap_socket(s, server_hostname=host)
    except:
        Exception(f"не удалось подключиться к хосту '{host}':(")
    return s


def get_cache_dir(host, file):
    """
    Конструирует путь к директории с кешем для данного объекта
    """
    file_name = file.replace('/', '\\')
    return f"server-cache/{host}/{file_name}"


def update_cache(host, file) -> bool:
    """
    Обновляет закешированный файл file с сервера host \n
    Возвращает True, если объект не пришлось присылать с сервера, иначе False\n
    При любых ошибках кидает исключение с описанием проблемы \n

    1) Соединяется с сервером  \n
    2) Объект закеширован => условный GET, иначе обычный \n
    3) Код возврата 304 => обновлять кеш не нужно, завершаемся \n
    4) Код возврата НЕ 200 => ошибка, завершаемся \n
    5) Код возврата 200 => записываем новые данные на диск \n
    """

    # 1) Соединяется с сервером 
    server_conn = connect_https(host)
    cache_dir = get_cache_dir(host, file)
    headers = {
        'Host': host,
    }

    if os.path.isdir(cache_dir):    
        # 2) условный GET
        print('в кеше')
        headers = headers | {
            'If-Modified-Since': read_str(f"{cache_dir}/time"),
            'If-None-Match': read_str(f"{cache_dir}/etag")
        }
        send_http_request_header(server_conn, 'GET', file, headers)
    else:   
        # 2) обычный GET
        print('нет в кеше')
        send_http_request_header(server_conn, 'GET', file, headers)
            
    r = read_http_message(server_conn)

    # 3) Код возврата 304 => обновлять кеш не нужно, завершаемся
    if r.status_code() == 304:
        print("попадание в кеш")
        return True
    
    # 4) Код возврата НЕ 200 => ошибка, завершаемся
    if r.status_code() not in {200, 304}:
        raise Exception(f"статус ответа сервера '{r.status()}'")

    # 5) Код возврата 200 => записываем новые данные на диск
    h = dict(r.headers())

    # Проверяем наличие необходимых полей в ответе сервера
    for header in {'Last-Modified', 'ETag', 'Content-Type'}:
        if header not in h.keys():
            raise Exception(f"заголовок '{header}' не отправлен сервером")
        
    os.makedirs(cache_dir, exist_ok=True)   # создаём директории если надо

    # Время и etag хранятся строками
    write_str(f"{cache_dir}/time", h['Last-Modified'])  # time
    write_str(f"{cache_dir}/etag", h['ETag'])           # etag

    # Данные хранятся в двоичном формате (=тело сообщения)
    data = r.body_file().read()
    write_bytes(f"{cache_dir}/data", data)      # data

    # Заголовки хранятся в виде объекта pickle
    with open(f"{cache_dir}/headers", "wb") as f:   # headers
        pickle.dump({'Content-Type': h['Content-Type'], 'Content-Length': len(data)}, file=f)

    print("кеш обновлён")
    return False


def send_response_from_cache(client_conn: socket.socket, cache_dir: str):
    """
    Посылает клиенту данные из кеша: заголовки Content-Type и Content-Length + данные
    """
    saved_headers = pickle.load(open(f"{cache_dir}/headers", "rb"))
    send_http_response_header(client_conn, '200 OK', saved_headers)
    with open(f"{cache_dir}/data", 'rb') as f:
        client_conn.sendfile(f)


def process_request(client_conn: socket.socket):
    """
    Обрабатывает один запрос \n
    1) Читает метод и имена хоста и файла из запроса клиента \n
    2) Метод не GET => пересылаем сообщение, заканчиваем \n
    3) Обновляем кеш функцией update_cache (которая ходит на сервер) \n
    4) Отправляем ответ клиенту из кеша \n
    5) При любой ошибке отпраляем клиенту 404 Not Found \n
    """
    h = read_http_message(client_conn)
    print(f'URL = {h.url()}')
    host, file = parse_uri(h.url())

    try:
        # Проверяем хост на бан
        if host in banned_hosts:
            print_log(f"хост '{host}' забанен\n")
            raise Exception(f"хост '{host}' забанен")

        # Если метод не GET, просто пересылаем запрос и всё
        if h.method() != 'GET':
            server_conn = connect_https(host)
            send_http_request_header(server_conn, h.method(), file, h.headers())
            server_conn.send(h.body_file())
            return
        
        # Иначе обновляем кеш
        if update_cache(host, file):
            print_log(f"попадание в кеш: URL = '{h.url()}'\n")
        else:
            print_log(f"кеш обновлён:    URL = '{h.url()}'\n")

        # Из кеша посылаем ответ клиенту
        cache_dir = get_cache_dir(host, file)
        send_response_from_cache(client_conn, cache_dir)

    except Exception as e:

        # Посылаем клиенту ошибку с пояснением причины
        send_http_response_header(client_conn, '404 Not Found', {'Content-Type': 'text/plain; charset=UTF-8'})
        reason = str(e.args).encode()
        client_conn.send(reason)



def run_proxy_server(port):
    """
    Создаёт слушающий сокет на tcp порте port, 
    в цикле получает запросы и передаёт обработку 
    функции process_request.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', port))
    s.listen(1)

    print(f'Слушаем на tcp порте {port}...')
    print_log(f'Слушаем на tcp порте {port}...\n')
    while(True):
        conn, addr = s.accept()
        print(f'===== Соединяемся =====')
    
        try:
            process_request(conn)
        except Exception as e:
            print('ОШИБКА СОЕДИНЕНИЯ С КЛИЕНТОМ')
            print(e.args)
            print(e.__traceback__)

        print(f'===== Закрываем соединение =====')
        conn.close()



################################
#####   Начало программы   #####
################################

# Читаем забаненные хосты
banned_hosts = []
try:
    with open('banned_hosts.txt', 'r') as f:
        banned_hosts = f.read().split('\n')
except:
    print("Файл 'banned_hosts.txt' не найден, забаненных хостов нет")
print(f"Забаненных хостов: {len(banned_hosts)}")

# Создаём файл логов
logs = open('logs.txt', 'w')

# Запускаем сервер
port = int(sys.argv[1])
run_proxy_server(port)

    
    
    