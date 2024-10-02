import socket
import struct
import sys
import time

    

def main(host, max_hops, timeout, packets=3):
    icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)    # , socket.IPPROTO_ICMP
    icmp_socket.settimeout(timeout)
    
    for ttl in range(1, max_hops):
        icmp_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)
        header = struct.pack('>BBHHH', 8, 0, 0, ttl, ttl)
        for _ in range(packets):
            icmp_socket.sendto(header, (host, 1))

            try:
                t0 = time.time()
                data, addr = icmp_socket.recvfrom(1024)
                rtt = time.time() - t0
            except TimeoutError:
                print(f'{ttl}\t***')
                continue

            ip_addr = addr[0]
            try:
                hostname, _, _ = socket.gethostbyaddr(ip_addr)
                hostname = f'{ip_addr} ({hostname})'
            except Exception:
                hostname = ip_addr

            type, code = struct.unpack('>BB', data[20:20+2])
            print(f'{ttl}\t{hostname}\t{round(rtt*1e6)} ms')
        if type == 0:
            break
        

main(host=sys.argv[1], max_hops=30, timeout=2.0, packets=int(sys.argv[2]))

