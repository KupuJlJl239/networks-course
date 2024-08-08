
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



//////////////////////////////////////
///   Функции для работы с сетью   ///
//////////////////////////////////////


/*
Получает адрес хоста + порта по их строковым представлениям 
В случае неудачи возвращает NULL
В случае успеха результат должен быть освобождён с помощью freeaddrinfo
*/
struct addrinfo* my_getaddrinfo(char* host, char* service){
    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;          /* Только IPv4 */
    hints.ai_socktype = SOCK_STREAM;    /* Только TCP */

    struct addrinfo *res;
    int err = getaddrinfo(host, "http", &hints, &res);
    if (err != 0) {
        fprintf(stderr, "getaddrinfo(host=%s, tcp_port=80): %s\n", host, gai_strerror(err));   
        return NULL;
    }
    return res;
}


/* 
Соединяется по tcp с данным хостом на данном порту. Возвращает fd сокета или -1 при неудаче.
*/
int tcp_connect(char* host, char* port){
    struct addrinfo *res = my_getaddrinfo(host, port);
    if(res == NULL)
        return -1;

    int serverfd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (serverfd == -1){
        fprintf(stderr, "socket: %s\n", strerror(errno));
        freeaddrinfo(res);
        return -1;
    }

    int err = connect(serverfd, res->ai_addr, res->ai_addrlen);
    freeaddrinfo(res);
    if(err == -1){
        fprintf(stderr, "connect: %s\n", strerror(errno));
        return -1;
    }

    return serverfd;
}


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


// Создаёт сокет и привязывает его к порту port
int create_socket(int port){
    int listenfd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if(listenfd != 0) printf("listening socket creation - success\n");
    else { 
        printf("listening socket creation - ERROR (%s)\n", strerror(errno));
        exit(-1);
    }

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
    return listenfd;
}



///////////////////////////////////////////////////
///   Функции для работы с забаненными хостами  ///
///////////////////////////////////////////////////


struct in_addr get_ip(struct addrinfo* a){
    printf("getip\n");
    struct sockaddr_in* h = a->ai_addr;
    return h->sin_addr;
}


// Список забаненных хостов
struct banned_host{
    struct banned_host* next;
    struct in_addr ip;    // адрес хоста
};

// Проверяет, есть ли забаненный хост в списке (1 - есть, 0 - нет)
int is_banned(struct in_addr ip, struct banned_host* hosts){
    struct banned_host* h = hosts;
    printf("is_banned start\n");
    while(h != NULL){
        if(memcmp(&ip, &(h->ip), sizeof(struct sockaddr)) == 0)
            return 1;
        printf("is_banned\n");
        h = h->next;
    }
    return 0;
}

// Освобождает список адресов
void free_banned_hosts(struct banned_host* hosts){
    struct banned_host* h = hosts;
    while(h != NULL){
        struct banned_host* next = h->next;
        free(h);
        h = next;
    }
}


// Добавляет в начало списка новый адрес, возвращает указатель на новое начало
struct banned_host* add_host(struct in_addr ip, struct banned_host* hosts){
    struct banned_host* new_host = malloc(sizeof(struct banned_host));
    new_host->next = hosts;
    new_host->ip = ip;
    return new_host;
}

/*
Загружает список из файла. 
Формат файла: каждое имя хоста заканчивается переносом строки
*/
struct banned_host* load_banned_hosts(const char* file_path){
    struct stat st;
    stat(file_path, &st);
    size_t file_size = st.st_size;
    
    char* file_data = malloc(file_size);
    int fd = open(file_path, O_RDONLY);
    read(fd, file_data, file_size);
    close(fd);

    struct banned_host* hosts = NULL;

    char* host_name_start = file_data;
    char* ch = file_data;
    while(ch < file_data + file_size){
        if(*ch == '\n'){
            *ch = 0;
            printf("%s: ", host_name_start);
            struct addrinfo* a = my_getaddrinfo(host_name_start, "http");
            if(a != NULL){
                hosts = add_host(get_ip(a), hosts);
                freeaddrinfo(a);
                printf("OK\n");
            }
            else{
                printf("Can't resolve address\n");
            }
            host_name_start = ch + 1;
        }
        ch += 1;
    }
    
    free(file_data);
    printf("end\n");
    return hosts;
}


////////////////////////////////////////
///   Функции для работы с строками  ///
////////////////////////////////////////

// Извлекает символы от start до end в строкку dst
void extract_substring(char* dst, const char* start, const char* end){
    int len = end - start;
    memcpy(dst, start, len);
    dst[len] = 0;
}

// Извлекает из заголовка http метод и uri
void parse_http_request_header(char* method, char* uri, const char* http_request){
    char* method_end = strstr(http_request, " ");
    char* uri_start = method_end + 1;
    char* uri_end = strstr(uri_start, " ");

    extract_substring(method, http_request, method_end);
    extract_substring(uri, uri_start, uri_end);
}

// Извлекает из uri имя хоста и имя файла на хосте
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


// Заменяет все '/' на '\' в строке [чтобы файл можно было сохранить]
void change_file(char* file){
    char* symbol = file;
    while(*symbol != 0){
        if(*symbol == '/')
            *symbol = '\\';
        symbol += 1;
    }
}



///////////////////////////////////
///   Основная линия программы  ///
///////////////////////////////////


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



// Извлекает номер порта из аргументов командной строки (проверяя их корректность)
int get_port(int argc, char** argv){
    if(argc != 2){
        printf("expected 1 argument (port number), got %d arguments\n", argc-1);
        exit(-1);
    }
    return atoi(argv[1]);
}


int main(int argc, char** argv){
    struct banned_host* hosts = load_banned_hosts("banned_hosts.txt");
    struct banned_host* h = hosts;
    while(h != NULL){
        printf("%p\n", h);
        h = h->next;
    }
    struct sockaddr* a = my_getaddrinfo("www.google.com", "http")->ai_addr;
    get_ip(a);
    if(a == NULL){
        printf("END\n");
        return -1;
    }
    printf("%d\n", is_banned(get_ip(a), hosts));
    // printf("%d\n", is_banned(*(my_getaddrinfo("vk.com", "http")->ai_addr), hosts));
    free_banned_hosts(hosts);

    // int port = get_port(argc, argv);
    // int listenfd = create_socket(port);
    // listen(listenfd, 10); 
    // while(1)
    // {
    //     printf("waiting for incoming connections...\n");
    //     int connfd = accept(listenfd, (struct sockaddr*)NULL, NULL);
    //     if(connfd >= 0) 
    //         printf("connection accepted (connfd=%d)\n", connfd);
    //     else { 
    //         printf("connection accept - ERROR (%s)\n", strerror(errno));
    //         continue;
    //     }
    //     process_request(connfd); 
    //     close(connfd);
    // }
}