import socket
import sys

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((sys.argv[1], int(sys.argv[2])))

args = ' '.join(sys.argv[3:])
s.send(args.encode())

data = b'0'
while(len(data) > 0):
    data = s.recv(1500)
    sys.stdout.buffer.write(data)