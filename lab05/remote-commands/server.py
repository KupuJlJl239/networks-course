import socket
import sys
import os





def process_request(conn: socket.socket):
    cmd = conn.recv(1500)
    pid = os.fork()
    if pid == 0:
        os.dup2(conn.fileno(), 1)
        os.system(cmd)
        exit(0)
        # os.execl('/bin/sh', *args)

    os.wait()
    conn.close()


def run_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', int(sys.argv[1])))
    s.listen(1)

    while(1):
        conn, addr = s.accept()
        process_request(conn)

run_server()