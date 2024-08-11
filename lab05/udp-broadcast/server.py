import socket
import sys
from time import sleep

from datetime import datetime

def get_time() -> str:
    return datetime.now().strftime("%a, %d %b %Y %T %z")



def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)  # UDP
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        msg = get_time()
        print(msg)
        sock.sendto(msg.encode(), ("255.255.255.255", int(sys.argv[1])))
        sleep(1)

main()