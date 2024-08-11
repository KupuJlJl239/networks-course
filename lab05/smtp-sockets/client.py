import socket
from datetime import datetime

# server = 'emx.mail.ru'
# server = 'mail.spbu.ru'
server = 'mx.yandex.ru'

# Команды серверу
mail_from = 'st094571@student.spbu.ru'
rcpt_to = 'kirill141103@yandex.ru'

# Поля в заголовке письма
from_msg = f'Kirill On SPBu <{mail_from}>'
to_msg = f'Kirill On Yandex <{rcpt_to}>'
subject = f'HW5 in networks course'

# Содержание письма
message = f'Добрый вечер!\nНе желаете ли прийти ко мне в гости и выпить чаю?'




s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((server, 25))

print(f'C: \\* установил соединение с сервером {server} *\\')
print(f"S: {s.recv(1500)}")


msg = b'HELO client-python\r\n'
s.send(msg)
print(f"C: {msg}")
print(f"S: {s.recv(1500)}")

msg = f'MAIL FROM:<{mail_from}>\r\n'.encode()
s.send(msg)
print(f"C: {msg}")
print(f"S: {s.recv(1500)}")

msg = f'RCPT TO:<{rcpt_to}>\r\n'.encode()
s.send(msg)
print(f"C: {msg}")
print(f"S: {s.recv(1500)}")

msg = b'DATA\r\n'
s.send(msg)
print(f"C: {msg}")
print(f"S: {s.recv(1500)}")

print(f'C: \\* отправляет письмо *\\')
s.send(f'From: {from_msg}\r\n'.encode())
s.send(f'To: {to_msg}\r\n'.encode())
s.send(f'Subject: {subject}\r\n\r\n'.encode())
s.send(message.encode())
s.send(b'\r\n.\r\n')

print(f"S: {s.recv(1500)}")


msg = b'QUIT\r\n'
s.send(msg)
print(f"C: {msg}")
print(f"S: {s.recv(1500)}")