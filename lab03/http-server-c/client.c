#include <stdio.h>
#include <errno.h>

#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/sendfile.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <string.h>

/*
чтобы intellisense не ругался (и без этого дефайна работает)
__USE_XOPEN2K включает в <netdb.h> определение структуры struct addrinfo
*/ 
#ifndef __USE_XOPEN2K
    #define __USE_XOPEN2K
#endif
#include <netdb.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

int main(int argc, char** argv){
    if(argc != 1+3){
        printf("expected 3 arguments (server_host, server_port, filename), got %d arguments\n", argc-1);
        exit(-1);
    }

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;          /* Только IPv4 */
    hints.ai_socktype = SOCK_STREAM;    /* Только TCP */

    /*
    Ссылка на первый узел связного списка, возвращаемого функцией getaddrinfo.
    В этом списке содержатся все возможные адреса, подходящие под указанные 
    в аргументах критерии.
    */ 
    struct addrinfo *res;

    /*
    Ищем запрашиваемый адрес (переводим строки в двоичные адреса и порты, при необходимости
    используем DNS).
    Первый аргумент - имя хоста, второй - имя порта, третий - остальные критерии поиска
    (тип протокола), четвёртый - возвращаемый результат поиска.
    */
    int err = getaddrinfo(argv[1], argv[2], &hints, &res);
    if (err != 0) {
        fprintf(stderr, "getaddrinfo: %s\n", gai_strerror(err));
        exit(-1);
    }

    /*
    Создаём сокет нужного типа
    */
    int connfd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (connfd == -1){
        fprintf(stderr, "socket: %s\n", strerror(errno));
        exit(-1);
    }

    /*
    Пытаемся соединиться с первым адресом из списка
    */
    err = connect(connfd, res->ai_addr, res->ai_addrlen);
    if(err == -1){
        fprintf(stderr, "connect: %s\n", strerror(errno));
        exit(-1);
    }

    // Освобождаем список
    freeaddrinfo(res);

    // Пишем http-запрос указанного файла
    dprintf(connfd, "GET %s HTTP/1.0\r\n\r\n", argv[3]); 


    /*
    Читаем из сокета, пока не наберётся 1500 символов или не будет разорвано соединение.

    Получаем ответ. Он должен быть не более 1500 символов (иначе обрежется),
    а также это должно быть ровно одно http сообщение (иначе следующие сообщения будут 
    распознаны как продолжение данных первого).
    */ 
    char http_answer[1501];
    int msg_length = 0;
    while(1){
        int seg_length = read(connfd, http_answer + msg_length, 1500 - msg_length);
        if(seg_length <= 0)
            break;
        msg_length += seg_length;
        if(msg_length >= 1500)
            break;
        
    }
    http_answer[msg_length] = 0;   // завершаем прочитанное нулевым символом, чтобы получилась корректная C-строка
    

    // Находим начало данных с помощью функции strstr, находящей подстроку в строке
    char* data = strstr(http_answer, "\r\n\r\n");
    if(data == NULL){
        printf("can't find end of http header ('\\r\\n\\r\\n') in answer\n");
        printf("http answer\n----------\n%s----------\n", http_answer);
        return -1;
    }
    data += 4;

    // Выводим данные
    // printf("http answer\n----------\n%s----------\n", http_answer);
    printf("%s", data);
}