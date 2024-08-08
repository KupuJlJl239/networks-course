
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
#include <assert.h>

/*
чтобы intellisense не ругался (и без этого дефайна работает)
__USE_XOPEN2K включает в <netdb.h> определение структуры struct addrinfo
*/ 
#ifndef __USE_XOPEN2K
    #define __USE_XOPEN2K
#endif
#include <netdb.h>



/* 
Читает из файла, пока файл не закончится либо пока буфер не заполнится
Возвращает число прочитанных байт
*/
int read_all(int file, char* buf, int buf_size){
    int len = 0;
    while(1){
        int seg_len = read(file, buf + len, buf_size - len);
        if(seg_len <= 0)
            return len;
        len += seg_len;
        if(len >= buf_size)
            return len;  
    }
}



int tcp_connect(char* host, char* port){
    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;          /* Только IPv4 */
    hints.ai_socktype = SOCK_STREAM;    /* Только TCP */

    struct addrinfo *res;
    int err = getaddrinfo(host, "http", &hints, &res);
    if (err != 0) {
        fprintf(stderr, "getaddrinfo(host=%s, tcp_port=80): %s\n", host, gai_strerror(err));
        return -1;
    }

    int serverfd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (serverfd == -1){
        fprintf(stderr, "socket: %s\n", strerror(errno));
        return -1;
    }

    err = connect(serverfd, res->ai_addr, res->ai_addrlen);
    freeaddrinfo(res);
    if(err == -1){
        fprintf(stderr, "connect: %s\n", strerror(errno));
        return -1;
    }

    return serverfd;
}


void extract_substring(char* dst, const char* start, const char* end){
    int len = end - start;
    memcpy(dst, start, len);
    dst[len] = 0;
}


void parse_http_request_header(char* method, char* uri, const char* http_request){
    char* method_end = strstr(http_request, " ");
    char* uri_start = method_end + 1;
    char* uri_end = strstr(uri_start, " ");

    extract_substring(method, http_request, method_end);
    extract_substring(uri, uri_start, uri_end);
}


void parse_uri(char* host, char* file, const char* uri){
    char* uri_end = uri + strlen(uri);
    char* host_start = uri + 1;     // первый символ uri всегда '/', пропускаем его
    char* host_end = strstr(host_start, "/");
    if(host_end == NULL){
        // uri == /{хост}

        host_end = uri_end;
        extract_substring(host, host_start, host_end);
        memcpy(file, "/", 2);
        return;
    }

    // uri == /{хост}/{файл}
    extract_substring(host, host_start, host_end);
    extract_substring(file, host_end, uri_end);
}


// Заменяет все '/' на '\' в строке
void change_file(char* file){
    char* symbol = file;
    while(*symbol != 0){
        if(*symbol == '/')
            *symbol = '\\';
        symbol += 1;
    }
}


int process_request(int clientfd){
    char http_request[1501];
    int msg_length = read(clientfd, http_request, 1500);
    if(msg_length == 0){
        printf("finish: read zero bytes, closing connection.\n");
        close(clientfd);
        return -1;
    }
    http_request[msg_length] = 0;   // завершаем прочитанное нулевым символом, чтобы получилась корректная C-строка
    printf("http request from client\n----------\n%s----------\n", http_request);

    /*
    Нужно извлечь:
        - имя файла в кеше
        - имя хоста
        - имя файла на сервере

    Имеем: http запрос с URL адресом вида {хост}/{файл}

    Http запрос: {метод} URI HTTP/1.0
    URI = /{хост}/{файл}

    Пути в кеше имеют вид: server-cache/{URL, где все '/' заменены на '\'}
    */


    char method[100];
    char uri[100];
    parse_http_request_header(method, uri, http_request);
    printf("method = '%s'\n", method);
    printf("URI = '%s'\n", uri);

    char host[100];
    char file[100];
    parse_uri(host, file, uri);    
    printf("host = '%s'\n", host);
    printf("file = '%s'\n", file);


    char cache_dir[100] = "server-cache";   // директория с кешем сервера
    char cache_host_dir[100];               // директория с кешем для данного хоста
    char cache_file_dir[100];               // директория с кешем для данного файла на хосте
    char cache_last_modified_file[100];     // файл с последним изменением файла
    char cache_etag_file[100];              // файл с etag-ом файла
    char cache_data_file[100];              // файл с данными файла

    sprintf(cache_host_dir, "%s/%s", cache_dir, host);
    sprintf(cache_file_dir, "%s/%s", cache_host_dir, file);
    change_file(cache_file_dir + strlen(cache_host_dir) + 1);
    sprintf(cache_last_modified_file, "%s/%s", cache_file_dir, "last-modified");
    sprintf(cache_etag_file, "%s/%s", cache_file_dir, "etag");
    sprintf(cache_data_file, "%s/%s", cache_file_dir, "data");

    printf("cache_dir = '%s'\n", cache_dir);
    printf("cache_host_dir = '%s'\n", cache_host_dir);
    printf("cache_file_dir = '%s'\n", cache_file_dir);


    if(access(cache_dir, F_OK) != 0){
        printf("not cached\n");
        if(mkdir(cache_dir, S_IRWXU) != 0)
            printf("mkdir %s: ERROR (%s)\n", cache_dir, strerror(errno));
        if(mkdir(cache_host_dir, S_IRWXU) != 0)
            printf("mkdir %s: ERROR (%s)\n", cache_dir, strerror(errno));
        if(mkdir(cache_file_dir, S_IRWXU) != 0)
            printf("mkdir %s: ERROR (%s)\n", cache_dir, strerror(errno));
    }
    else{
        printf("cached\n");
    }


    int serverfd = tcp_connect(host, "http");
    if(serverfd < 0){
        dprintf(clientfd, "HTTP/1.0 404 Not Found\r\n\r\n");
        return -1;
    }


    // Пишем http-запрос указанного файла
    dprintf(serverfd, "GET %s HTTP/1.0\r\nConnection: close\r\n\r\n", file); 

    char http_answer[1501];
    msg_length = 0;
    while(1){
        int seg_length = read(serverfd, http_answer + msg_length, 1500 - msg_length);
        if(seg_length <= 0)
            break;
        msg_length += seg_length;
        if(msg_length >= 1500)
            break;  
    }
    http_answer[msg_length] = 0;   // завершаем прочитанное нулевым символом, чтобы получилась корректная C-строка
    printf("http answer from server\n----------\n%s----------\n", http_answer);



    char* code_start = strstr(http_answer, " ") + 1;
    if(memcmp(code_start, "200", 3) != 0){
        fprintf(stderr, "status code is not 200\n");
        dprintf(clientfd, "HTTP/1.0 404 Not Found\r\n\r\n");
        return -1;
    }
    
    // Находим начало данных с помощью функции strstr, находящей подстроку в строке
    char* data = strstr(http_answer, "\r\n\r\n");
    if(data == NULL){
        printf("can't find end of http header ('\\r\\n\\r\\n') in answer\n");
        return -1;
    }
    data += 4;

    // Выводим данные
    printf("длины пересылаемых кусков: \n");
    dprintf(clientfd, "HTTP/1.0 200 OK\r\n\r\n");

    write(clientfd, data, msg_length - (data - http_answer));
    printf("%d\n", msg_length - (data - http_answer));

    msg_length -= (data - http_answer);
    while(1){
        msg_length = read(serverfd, http_answer, 1500);
        if(msg_length <= 0)
            break;

        write(clientfd, http_answer, msg_length);
        printf("%d\n", msg_length);
    }
    printf("отправка клиенту окончена.\n");


}



int main(int argc, char** argv){
    if(argc != 2){
        printf("expected 1 argument (port number), got %d arguments\n", argc-1);
        exit(-1);
    }
    int port = atoi(argv[1]);

    // 1 - создаём сокет, который потом сделаем слушающим входящие соединения
    int listenfd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if(listenfd != 0) printf("listening socket creation - success\n");
    else { 
        printf("listening socket creation - ERROR (%s)\n", strerror(errno));
        exit(-1);
    }

    // 2 - устанавливаем его IP адрес и порт
    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);                // преобразование в big-endian, для использования в заголовке TCP
    addr.sin_addr.s_addr = htonl(INADDR_ANY);   // преобразование в big-endian, для использования в заголовке IP
    int err = bind(listenfd, (struct sockaddr*)&addr, (socklen_t)sizeof(addr));

    if(err == 0) printf("binding listening socket - success\n");
    else { 
        printf("binding listening socket - ERROR (%s)\n", strerror(errno));
        exit(-1);
    }

    // 3 - делаем сокет слушающим
    listen(listenfd, 10); 

    // 4 - обрабатываем входящие запросы
    while(1)
    {
        // 4.1 - ждём очередное входящие соединение и принимаем его
        printf("waiting for incoming connections...\n");
        int connfd = accept(listenfd, (struct sockaddr*)NULL, NULL);
        if(connfd >= 0) printf("connection accepted (connfd=%d)\n", connfd);
        else { 
            printf("connection accept - ERROR (%s)\n", strerror(errno));
            continue;
        }

        // 4.3 - обрабатываем пришедший запрос в этом же потоке
        process_request(connfd); 

        close(connfd);
    }
}