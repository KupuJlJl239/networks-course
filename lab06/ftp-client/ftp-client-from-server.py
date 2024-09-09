from ftplib import FTP
import sys



def process_request(ftp: FTP):
    inp = input().split()
    
    try:
        match inp[0]:
            case 'ls': 
                ftp.dir()
            
            case 'upload':      
                with open(inp[1], 'rb') as fp:
                    ftp.storbinary(f'STOR {inp[2]}', fp)

            case 'download': 
                with open(inp[2], 'wb') as fp:
                    ftp.retrbinary(f'RETR {inp[1]}', fp.write)

            case 'cd': 
                print(ftp.cwd(inp[1]))

            case 'cwd': 
                print(ftp.pwd())

            case 'rm':
                ftp.delete(inp[1])

            case 'mkdir':
                ftp.mkd(inp[1])

            case 'exit':
                return False

            case _:
                print(f'неизвестное действие {inp[0]}')

    except Exception as e:
         print(e)

    return True

def print_help():
    print('Команды:')
    print('ls - выводит список всего в текущем каталоге')
    print('upload <local_file> <server_file> - загружает файл на сервер')
    print('download <server_file> <local_file> - загружает файл с сервера')
    print('cd <server_path> - переходит в другой каталог')
    print('cwd - выводит текущий каталог')
    print('rm <server_path> - удаляет файл с сервера')
    print('mkdir <server_path> - создаёт новый каталог')
    print('exit - завершает программу')


def main():
    host = 'ftp.dlptest.com'
    user = 'dlpuser'
    passwd = 'rNrKYTX9g7z3RgJRmxWuGHbeu'

    ftp = FTP() 
    ftp.connect(host)
    ftp.login(user, passwd)

    print('Успешное подключение')
    print_help()

    while(process_request(ftp)):
        pass
        

main()



