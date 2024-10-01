
import threading
from check_sums import *
# import time



class gbn_segment:
    """
    Структура пакета:
    * тип пакета - 1 байт (0 - пакет с данными, 1 - подтверждение, 2 - конец передачи)
    * номер сегмента - 1 байт (=> номеров всего 256, размер окна должен быть не более 128)
    * данные - произвольный размер
    * контрольная сумма - 2 байта
    """
    def __init__(self, segment_type: int, segment_number: int, data: bytes, checksum=None):
        self.segment_type = segment_type
        self.segment_number = segment_number
        self.data = data
        self.checksum = checksum if checksum is not None else self.calc_checksum()

    def calc_checksum(self):
        return make_checksum(self.to_bytes_no_checksum())
    
    def check_checksum(self):
        return self.calc_checksum() == self.checksum

    def from_bytes(bytes: bytes):
        return gbn_segment(
            int(bytes[0]), 
            # int.from_bytes(bytes[1:2], 'little'),
            int(bytes[1]),
            bytes[2:-2], 
            int.from_bytes(bytes[-2:], 'little')
        )
    
    def to_bytes_no_checksum(self):
        return self.segment_type.to_bytes(1, 'little') + self.segment_number.to_bytes(1, 'little') + self.data
    
    def to_bytes(self):
        return self.to_bytes_no_checksum() + self.checksum.to_bytes(2, 'little')

    def to_str(self):
        return f'type={self.segment_type}, number={self.segment_number}, data={self.data}'



class gbn_socket:
    """
    Сокет для надёжной передачи датаграмм (сообщений)
    Имея две функции send_f и recv_f для ненадёжных отправки и получения
    сообщений, реализованы методы .send и .recv для надёжной доставки.

    Сокет поддерживает сопроцесс отвечающий за чтение из сокета, и сопроцесс для
    таймера для переотправки (если нужно). Они уничтожаются только при завершении главного 
    процесса.

    Параметры конструктора:
    * send_f: (bytes)->None - функция ненадёжной отправки пакета другой стороне (неблокирующая)
    * recv_f: ()->bytes - функция ненадёжного получения от другой стороны (блокирующая)
    * timeout: float - таймаут
    * N: int, 0 < N <= 128 - размер окна

    Интерфейс gbn_socket:
    * .send(data: bytes) - надёжная отправка (неблокирующая)
    * .recv() -> bytes|None - надёжное получение (блокирующее)
    """
    def __init__(self, send_f, recv_f, timeout, N, callbacks=None):
        self.send_f = send_f
        self.recv_f = recv_f
        self.next_number = 0
        self.timeout = timeout
        self.N = N
        self.callbacks = callbacks if callbacks is not None else dict()

        self.lock = threading.RLock()
        self.segment_received = threading.Condition(self.lock)

        self.recv_queue = []    # порции данных, ожидающие передачи прикладному уровню
        self.send_queue = []    # ещё не отправленные или неподтверждённые порции данных

        self.recv_number = 0    # следующий номер который мы ожидаем получить
        self.send_number = 0    # номер первого сегмента в self.send_queue 
        self.sended = 0  # число уже отправленных сегментов из self.send_queue, т.е. ожидающих подтверждения

        self.closed = False  # правда ли что другая сторона больше ничего не отправляет


        # Обрабатывает получение одного сегмента
        def on_segment_receive(s: gbn_segment):
            """
            обрабатывает получение одного сегмента
            есть 3 типа сегментов:
            * тип=0 - сегмент с данными
            * тип=1 - сегмент с подтверждением
            * тип=3 - сегмент с сообщением о конце передачи
            """
            # print(f'receive {s.to_str()}')
            if s.segment_type == 0: # сегмент с данными
                if s.segment_number == self.recv_number: # сегмент который мы ждали добавляем в очередь и оповещаем об этом
                    self._run_callback("data_good_receive", s)
                    self.recv_queue.append(s.data)
                    self.segment_received.notify_all()
                    self.recv_number = (self.recv_number + 1) % 256
                else:
                    self._run_callback("data_bad_receive", s)
                self._send_ack(self.recv_number)   # в любом случае шлём ACK c номером следующего ожидаемого сегмента

            elif s.segment_type == 1: # ACK сегмент 
                # idx - столько сегментов оказалось подтверждено
                # idx = s.segment_number - self.send_number (mod 256)
                idx = (s.segment_number - self.send_number) % 256 
                if idx < 0: idx += 256  # неуклюжая арифметика по модулю 256

                # Есть 3 случая:
                #   * подтверждение пришло повторно => переотправляем всё, перезапускаем таймер
                #   * подтверждение подтвердило какие-то пакеты => убираем эти пакеты из очереди
                #   * подтверждение не затрагивает ожидаемый диапазон => ничего не делаем

                if idx == 0:
                    #   * подтверждение пришло повторно   
                    self._run_callback("ack_repeat_receive", s)   
                    self._set_timeout(cancel=True)  # переустанавливаем таймаут
                    self._send_again()  # посылаем всё заново
            
                elif 0 < idx and idx <= self.sended:
                    #   * подтверждение подтвердило какие-то пакеты
                    self._run_callback("ack_good_receive", s)
                    self.send_queue = self.send_queue[idx:] # убираем подтверждённые сегменты из очереди
                    self.sended -= idx
                    self.send_number = (self.send_number + idx) % 256  # сдвигаем окно
                    self._send_new()    # раз что-то подтвердилось, то можем отправить что-то новое

                else:
                    #   * подтверждение не затрагивает ожидаемый диапазон
                    self._run_callback("ack_bad_receive", s)

            elif s.segment_type == 2: # закрытие соединения (другая сторона больше не будет отправлять) 
                if s.segment_number == self.recv_number: # сегмент тот который мы ждали
                    self.closed = True
                    self.segment_received.notify_all()
                    self.recv_number = (self.recv_number + 1) % 256
                self._send_ack(self.recv_number)     # в любом случае шлём ACK
                

        def receive_holder_f():
            """
            ждёт новых сообщений в цикле, проверяет контрольную сумму 
            и отдаёт на обработку функции on_segment_receive
            """
            while True:
                # Ждём следующего прихода сообщения, потом обрабатываем его
                # print('wait for receive')
                s: bytes = self.recv_f()
                s: gbn_segment = gbn_segment.from_bytes(s)
                if not s.check_checksum():
                    # print('checksum ERROR')
                    continue
                with self.lock:
                    on_segment_receive(s)
        
        self.timeout_thread = None

        # отдельный поток, занимающийся получением UDP пакетов
        self.receive_holder_thread = threading.Thread(target=receive_holder_f, name='RDT holder', daemon=False)
        self.receive_holder_thread.start()


    def recv(self):
        """
        извлекает из очереди получения новый сегмент
        если очередь пуста, но другая сторона не сообщила о конце передачи - ждёт
        если очередь пуста, и другая сторона сообщила о конце передачи - возвращает None
        """
        with self.lock:
            empty = lambda: len(self.recv_queue) == 0
            end = lambda: empty() and self.closed
            if empty() and not end():
                # print('wait')
                self.segment_received.wait()
            if end():
                return None
            data = self.recv_queue[0]
            self.recv_queue = self.recv_queue[1:]
        return data
    

    def send(self, data):
        """
        кладёт в очередь отправки новый сегмент
        (возможно сразу же отправляя его если можно)
        """
        with self.lock:
            
            n = (self.send_number+len(self.send_queue)) % 256  # номер нового сегмента

            # print(f'send {n}')
            if data is not None:
                s = gbn_segment(0, n, data)
            else:
                s = gbn_segment(2, n, b'')
            self.send_queue.append(s.to_bytes())
            self._send_new()


    def _send_new(self):
        """
        отправляет все ещё не отправленные сегменты из self.send_queue
        (но чтобы отправленных было не более N)
        ставит таймер если его не было
        """
        if len(self.send_queue) == 0:
            self._cancel_timeout()
            return
        new_sended = min(len(self.send_queue), self.N)  # столько отправленных пакетов будет после завершения этой функции
        # print(f'send_f new {self.send_number + self.sended} to {self.send_number + new_sended}')
        for s in self.send_queue[self.sended:new_sended]:
            self.send_f(s)
        self.sended = new_sended
        if self.timeout_thread is None:
            self._set_timeout()
    
    def _send_again(self):
        """
        переотправляет все отправленные, но неподтверждённые сегменты
        """
        # print(f'send_f again {self.send_number} to {self.send_number + self.sended}')
        for s in self.send_queue[:self.sended]:
            self.send_f(s)

    def _send_ack(self, segment_number):
        """
        отправляет ACK с данным номером
        """
        s = gbn_segment(1, segment_number, b'')
        self.send_f(s.to_bytes())

    def _on_timeout(self):
        """
        действие по таймауту: вызов _send_all + перезапуск таймаута
        """
        with self.lock:
            # print('TIMEOUT')
            self._send_again()
            self._set_timeout(cancel=False)

    def _set_timeout(self, cancel=True):
        """
        ставит таймаут: через время self.timeout вызовется функция _on_timeout
        можно настроить, удалять ли прошлый таймаут при замене (cancel)
        """
        if cancel:
            self._cancel_timeout()
        self.timeout_thread = threading.Timer(self.timeout, lambda: self._on_timeout())
        self.timeout_thread.start()

    def _cancel_timeout(self):
        """
        убирает таймаут, если он был
        """
        if self.timeout_thread is not None:
            self.timeout_thread.cancel()
            self.timeout_thread = None

    def _run_callback(self, name, *args):
        """
        запускает callback с данным имененем и данными аргументами,
        если такой callback вообще существует
        """
        callback = self.callbacks.get(name)
        # print(self.callbacks.keys(), name)
        
        if callback is not None:
            callback(self, *args)
