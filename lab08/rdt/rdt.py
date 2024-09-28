
import threading
# import time



class rdt_segment:
    def __init__(self, segment_type: int, segment_number: int, data: bytes):
        self.segment_type = segment_type
        self.segment_number = segment_number
        self.data = data

    def from_bytes(bytes: bytes):
        return rdt_segment(int(bytes[0]), int(bytes[1]), bytes[2:])
    
    def to_bytes(self):
        return self.segment_type.to_bytes(1, 'little') + self.segment_number.to_bytes(1, 'little') + self.data


    def to_str(self):
        return f'type={self.segment_type}, number={self.segment_number}, data={self.data}'



class rdt_socket:
    """ Принимает сообщения и отправляет ACK-и """
    def __init__(self, send_f, recv_f, timeout):
        self.send_f = send_f
        self.recv_f = recv_f
        self.next_number = 0
        self.timeout = timeout

        self.lock = threading.RLock()
        self.segment_received = threading.Condition(self.lock)
        # self.segment_sended = threading.Condition(self.lock)

        self.recv_queue = []
        self.send_queue = []    # сегменты которые не отправлены или не гарантированно получены

        self.recv_number = 0    # следующий номер который мы ожидаем получить
        self.send_number = 0    # номер первого сегмента в self.send_queue 

        self.closed = False  # правда ли что другая сторона больше ничего не отправляет


        # Обрабатывает получение одного сегмента
        def on_segment_recieve(s: rdt_segment):
            print(f'receive {s.to_str()}')

            if s.segment_type == 0: # сегмент с данными
                if s.segment_number == self.recv_number: # сегмент который мы ждали добавляем в очередь и оповещаем об этом
                    self.recv_queue.append(s.data)
                    self.segment_received.notify_all()
                    self.recv_number = 1 - self.recv_number
                    print('notify')
                self.__send_ack(s.segment_number)   # в любом случае шлём ACK

            elif s.segment_type == 1: # ACK сегмент 
                # номер подтверждения такой же как у отправленного => считаем его доставленным (удаляем из очереди)
                # снимаем таймаут на этот сегмент
                # сдвигаем номер на один и отправляем следующий сегмент
                if s.segment_number == self.send_number:    
                    
                    self.timeout_thread.cancel()
                    self.send_number = 1 - self.send_number
                    self.send_queue = self.send_queue[1:]
                    if len(self.send_queue) > 0:
                        self.__send_top()


            elif s.segment_type == 2: # закрытие соединения (другая сторона больше не будет отправлять)
                self.__send_ack(s.segment_number)   # в любом случае шлём ACK
                if s.segment_number == self.recv_number: # сегмент тот который мы ждали
                    # в этом случае просто завершаем слушающий поток
                    self.closed = True
                    self.segment_received.notify_all()
                    print('notify')
                    # exit(0)
                
   
        # Обрабатывает все получения сегментов в отдельном потоке
        def receive_holder_f():
            while(1):
                # Ждём следующего прихода сообщения, потом обрабатываем его
                s: bytes = self.recv_f()
                s: rdt_segment = rdt_segment.from_bytes(s)
                with self.lock:
                    on_segment_recieve(s)

        self.timeout_thread = None
        self.receive_holder_thread = threading.Thread(target=receive_holder_f, name='RDT holder', daemon=True)
        self.receive_holder_thread.start()


    def recv(self):
        with self.lock:
            empty = lambda: len(self.recv_queue) == 0
            end = lambda: empty() and self.closed
            if empty() and not end():
                # self.segment_received.wait_for(lambda: not empty() or end())
                print('recv wait')
                self.segment_received.wait()
            if end():
                print('recv end')
                # self.receive_holder_thread.join()
                print('recv join and return none')
                return None
            data = self.recv_queue[0]
            self.recv_queue = self.recv_queue[1:]
        return data
    

    def send(self, data):
        with self.lock:
            self.send_queue.append(data)
            # print('send:')
            # for d in self.send_queue:
            #     print(f'    {d}')
            if len(self.send_queue) == 1:
                self.__send_top()


    def __send_top(self):
        with self.lock:
            data = self.send_queue[0]
            if data == None: 
                s = rdt_segment(2, self.send_number, b'')
            else:
                s = rdt_segment(0, self.send_number, self.send_queue[0])
            self.timeout_thread = threading.Timer(self.timeout, lambda: self.__send_top())
            self.timeout_thread.start()
            print(f'send {s.to_str()}')
            self.send_f(s.to_bytes())

    def __send_ack(self, segment_number):
        with self.lock:
            s = rdt_segment(1, segment_number, b'')
            print(f'send ack {s.to_str()}')
            self.send_f(s.to_bytes())