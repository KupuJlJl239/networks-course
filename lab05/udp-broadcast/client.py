import socket
import sys

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.bind(("0.0.0.0", int(sys.argv[1])))
while True:
    data, addr = sock.recvfrom(1024)
    print(data.decode("utf-8"))