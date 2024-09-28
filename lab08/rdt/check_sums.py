

# Я не стал инвертировать биты контрольной суммы, ибо зачем
def make_checksum(bytes: bytes):
    res = 0
    for i in range((len(bytes)+1)//2):
        res += int.from_bytes(bytes[2*i:2*i+2], 'little')
    return res % (256*256)


def check_checksum(bytes: bytes, sum: int):
    return make_checksum(bytes) == sum



if __name__ == '__main__':
    with open('check_sums.py', 'rb') as f:
        data = f.read()

    bad_data = data[0:21] + data[22:]

    good_tests = [b'a', b'0', b'gh', b'abhfiduas', b'dbyhuds', data]
    bad_tests = [b'b', b'1', b'gj', b'abhiduas', b'dbyhudsa', bad_data]

    for i, (good, bad) in enumerate(zip(good_tests, bad_tests)):
        print(f'Test {i+1} passed!')
        assert check_checksum(good, make_checksum(good))
        assert not check_checksum(bad, make_checksum(good))

    print('\nAll tests passed!')