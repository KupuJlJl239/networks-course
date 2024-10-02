import socket
import threading
import time
import typing
from typing import List, Any
import pickle

def create_udp_socket(port):
    """
    создаёт UDP сокет на данном порту
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("0.0.0.0", port))
    return udp_socket


class Router:
    def __init__( 
        self, 
        ip: int, 
        dt: float, 
        timeout: float,
        udp_socket: socket.socket, 
        neighbours, 
        callbacks
    ):
        self.lock = threading.RLock()

        self.ip = ip
        self.dt = dt
        self.timeout = timeout
        self.neighbours = neighbours
        self.udp_socket = udp_socket
        self.callbacks = callbacks

        self.table = {self.ip: (None, 0)}

        self.udp_socket.settimeout(self.timeout)
        self.last_change_time = None

        def sender_thread_f():
            while True:
                time.sleep(dt)
                with self.lock:
                    self._send()
                    self._exit_if_timeout()
        
        def receiver_thread_f():
            while True:
                try:
                    data, addr = self.udp_socket.recvfrom(10000)
                except TimeoutError:
                    exit(0)

                msg = pickle.loads(data)
                with self.lock:
                    self._on_msg_receive(msg, addr)

    
        self.sender_thread = threading.Thread(target=sender_thread_f)
        self.receiver_thread = threading.Thread(target=receiver_thread_f)

    def start(self):
        """
        запускает виртуальный роутер с протоколом RIP
        """
        self._on_table_change()
        self.sender_thread.start()
        self.receiver_thread.start()

    def join(self):
        """
        ждёт завершения работы протокола RIP
        """
        self.sender_thread.join()
        self.receiver_thread.join()

    def _send(self):    
        """
        рассылаем нашу таблицу всем соседям
        """ 
        msg = {(ip, length) for ip, (_, length) in self.table.items()}
        data = pickle.dumps(msg)
        for addr, ip in self.neighbours.items():
            self.udp_socket.sendto(data, addr)
    

    def _on_msg_receive(self, msg, addr):
        """
        обрабатывает получение одного сообщения
        """
        # print(f'{self.ip} gets a message from {self.neighbours[addr]}')
        changed = False

        for ip, length in msg:
            new_length = length + 1
            _, old_length = self._get_route(ip)
            if new_length < old_length:       
                # print(f'now path from {self.ip} to {ip} is {new_length} hops')
                # self._on_table_change()
                self.table[ip] = (addr, new_length)
                changed = True

        if changed:
            self._on_table_change()
            
    def _get_route(self, ip):
        """
        возвращает информацию о маршруте до данного IP:
        пару (udp-адрес, длина пути до конечного узла)

        если маршрут неизвестен, возвращает (None, 16)
        """
        if ip in self.table:
            return self.table[ip]
        else:
            return (None, 16)
        

    def _on_table_change(self):
        """
        переставляет время поледнего изменения таблицы
        (должна вызываться при каждом изменении таблицы)
        """
        self._run_callback("on_table_change")
        self.last_change_time = time.time()


    def _exit_if_timeout(self):
        """
        завершает текущий поток, если превышен таймаут на изменение таблицы
        """
        if time.time() - self.last_change_time > self.timeout:
            exit(0)


    def print_table(self):
        """
        выводит текущую таблицу маршрутизации
        """
        with self.lock:
            print(f'[target IP]\t[next hope IP]\t[hops to target]')
            for ip, (addr, length) in sorted(self.table.items()):
                next_hope_ip = self.neighbours[addr] if addr is not None else '    -    '
                print(f'{ip}\t{next_hope_ip}\t\t{length}')


    def _run_callback(self, name, *args):
        """
        вызывает callback с данным именем
        """
        if name in self.callbacks: 
            self.callbacks[name](self, *args)



def create_network(
    vertices, 
    edges,
    dt,
    timeout, 
    callbacks = dict()
) -> List[Router]:
    """
    создаёт сеть
    * vertices - пары (порт UDP, ip адрес узла)
    * edges - пары (индекс в vertices, индекс в vertices)
    * dt - раз в какое время узлы будут отправлять сообщения соседям
    * timeout - если в течение этого времени таблица узла не обновлялась, 
        он завершит работу

    возвращает список роутеров, соединённых указанным образом
    """
    # Создаём роутеры с указанными UDP портами
    routers = [
        Router(
            ip=ip, dt=dt, timeout=timeout, 
            udp_socket=create_udp_socket(udp_port), 
            neighbours=dict(),
            callbacks=callbacks
        )
        for udp_port, ip in vertices
    ]

    # Проставляем связи между ними
    for i1, i2 in edges:
        r1, r2 = routers[i1], routers[i2]
        port1, port2 = vertices[i1][0], vertices[i2][0]
        r1.neighbours[('127.0.0.1', port2)] = r2.ip
        r2.neighbours[('127.0.0.1', port1)] = r1.ip

    return routers


if __name__ == '__main__':


    # Определяем граф сети
    V = [(50000, 'router_0'), (50001, 'router_1'), (50002, 'router_2'), (50003, 'router_3')]
    E = [(0, 1), (1, 2), (2, 3)]

    # Создаём callback, выводящий таблицу маршрутизации
    global_lock = threading.Lock()
    def on_table_change_callback(router: Router):
        with global_lock:
            print()
            print(f'{router.ip}: изменилась таблица маршрутизации')
            router.print_table()

    # Создаём все маршрутизаторы, связывая их между собой
    routers: List[Router] = create_network(
        V, E, dt=0.1, timeout=1, 
        callbacks={'on_table_change': on_table_change_callback}
    )

    # Запускаем из всех
    for r in routers:
        r.start()

    # Ждём завершения всех
    for r in routers:
        r.join()


    # Подводим итоги всех
    print()
    print('================================')
    print('=======   RIP завершён   =======')
    print('================================')

    for i, r in enumerate(routers):
        print()
        print(f'{r.ip}: итоговая таблица маршрутизации')
        r.print_table()