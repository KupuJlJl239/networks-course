
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
Находит в http запросе имя файла и копирует его в буфер buf, заканчивая символом 0 (чтобы получилась C-строка)
[Функция написана ужасно!]
*/
int find_file_name(const char* http_request, size_t request_size, char* buf, size_t buf_size){
    int start = 0;
    while(http_request[start] != ' '){
        ++start;
        if(start+1 > request_size)
            return -1;
    }
    start += 1;
    int end = start;
    while(http_request[end] != ' '){
        ++end;
        if(end > request_size)
            return -1;
    }
    if(end-start+1 > buf_size)
        return -1;

    memcpy(buf, http_request + start, end-start);
    buf[end-start] = 0;
    return end-start;
}


/*
Функция принисает путь к файлу, указатель на буфер и размер буфера.
Записывает в буфер MIME-тип файла в виде C-строки [если не хватило места, записывает сколько влезло].
Возвращает число байт, необходимых для записи полного результата [включая нулевой байт в конце].
MIME-тип нужен при отправке файла по http, он указывается в поле 'Content-type'

Например:
Content-type: text/plain
Content-type: application/pdf
...

В этой функции вызывается подпроцесс с утилитой file, вывод которой перенаправляется в pipe,
из которого затем читается в буфер.
*/
int get_file_type(const char* path, char* buf, size_t buf_size){

    // массив двух файловых дескрипторов: 0 - чтение, 1 - запись в pipe
    int pipefds[2]; 
    pipe(pipefds);

    // запускаем подпроцесс
    int child_pid = fork();
    if(child_pid == 0){ // процесс-ребёнок
        // закрываем чтение из pipe
        close(pipefds[0]);   

        // переключаем стандартный вывод на вывод в pipe               
        dup2(pipefds[1], STDOUT_FILENO);   

        // запускаем утилиту file 
        execl("/bin/file", "file", "-b", "--mime-type", path, NULL);  

        // если это выполнилось, то в execl произошла ошибка  
        printf("pid=%d: execl - ERROR (%s)\n", getpid(), strerror(errno));
        return -1;
    }
    // закрываем запись в pipe
    close(pipefds[1]); 

    // ждём пока подпроцесс не завершится 
    printf("pid=%d: waiting for 'file' command finishes...\n", getpid());
    int child_status;
    wait(&child_status);    

    // читаем результат file и возвращаем необходимое для записи полного ответа количество байт
    int file_type_size = read(pipefds[0], buf, buf_size)-1;
    buf[file_type_size] = 0;
    return file_type_size+1;
}


int process_request(int connfd){

    /*
    1 - читаем пришедшие данные в буфер
    2 - анализируем http сообщение и находим в нём имя файла
    3 - открываем файл
    4 - получаем размер файла, проверяем что это обычный файл
    5 - получаем тип файла командой file
    6 - пишем ответное сообщение
    */

    printf("pid=%d start: reading request...\n", getpid());


    // 1 - читаем пришедшие данные в буфер

    char http_request[1501];
    int msg_length = read(connfd, http_request, 1500);
    if(msg_length == 0){
        printf("pid=%d finish: read zero bytes, closing connection.\n", getpid());
        close(connfd);
        return -1;
    }
    http_request[msg_length] = 0;   // завершаем прочитанное нулевым символом, чтобы получилась корректная C-строка
    printf("pid=%d: receive following http message\n----------\n%s----------\n", getpid(), http_request);


    // 2 - анализируем http сообщение и находим в нём имя файла

    char file_name[101];    
    file_name[0] = '.';     // в начале имени ставим '.', чтобы путь был относительно текущей директории
    int file_name_size = find_file_name(http_request, msg_length, file_name+1, 100) + 1;
    if(file_name_size < 0){
        printf("pid=%d finish: can't extract file name from request, closing connection.\n", getpid());
        close(connfd);
        return -1;
    }
    printf("pid=%d: file_name = '%s'\n", getpid(), file_name);


    // 3 - открываем файл

    int fd = open(file_name, O_RDONLY);
    if(fd < 0){
        dprintf(connfd, "HTTP/1.0 404 Not Found\r\n\r\n");
        close(connfd);
        printf("pid=%d finish: open file '%s' - ERROR (%s). Closing connection.\n", getpid(), file_name, strerror(errno));
        return -1;
    }


    // 4 - получаем размер файла, проверяем что это обычный файл

    struct stat f_stat;
    fstat(fd, &f_stat);
    if(!S_ISREG(f_stat.st_mode)){
        dprintf(connfd, "HTTP/1.0 404 Not Found\r\n\r\n");
        close(connfd);
        printf("pid=%d finish: file '%s' is not a regular file\n", getpid(), file_name);
        return -1;
    }
    size_t file_size = f_stat.st_size;
    printf("pid=%d: file_size = %ld\n", getpid(), file_size);


    // 5 - получаем тип файла командой file
    char file_type[100];
    get_file_type(file_name, file_type, 100);

    printf("pid=%d: file mime type = '%s'\n", getpid(), file_type);


    // 6 - пишем ответное сообщение
    dprintf(connfd, "HTTP/1.0 200 OK\r\n"); 
    dprintf(connfd, "Content-type: %s;charset=UTF-8\r\n", file_type);
    dprintf(connfd, "Content-Length: %ld\r\n\r\n", file_size);

    sendfile(connfd, fd, 0, file_size);

    close(fd);
    close(connfd);

    printf("pid=%d finish: response - success!!!\n", getpid());
    return 0;
}

// максимальное число дочерних процессов
int MAX_CHILD_PROC_COUNT;

// счётчик числа дочерних процессов
int CHILD_PROC_COUNT = 0;


/*
Обработчик сигнала SIGCHLD.
Процесс получает этот сигнал, когда изменяется состояние его процессов-детей,
в частности когда те завершаются.
В этом обработчике вызывается функция wait, чтобы полностью очищать систему от завершившихся процессов.

Если число процессов максимальное, то wait будет вызван в main, иначе тут, в этом обработчике.
*/
void SIGCHLD_handler(int signum)
{   
    assert(CHILD_PROC_COUNT <= MAX_CHILD_PROC_COUNT);

    /*
    Если число процессов предельное, то wait будет вызван в main
    Иначе вызываем wait тут, чтобы не было зомби-процессов
    */ 
    if(CHILD_PROC_COUNT == MAX_CHILD_PROC_COUNT){
        printf("SIGCHLD_handler in main(pid=%d): CHILD_PROC_COUNT == MAX_CHILD_PROC_COUNT (== %d), skipping wait\n", getpid(), MAX_CHILD_PROC_COUNT);
        return;
    }

    pid_t child_pid = wait(NULL);
    if(child_pid > 0){
        CHILD_PROC_COUNT -= 1;
        printf("SIGCHLD_handler in main(pid=%d): wait - child with pid=%d finished, now CHILD_PROC_COUNT=%d\n", getpid(), child_pid, CHILD_PROC_COUNT);
    }        
    else 
        printf("SIGCHLD_handler in main(pid=%d): wait - ERROR (%s)\n", getpid(), strerror(errno));
}


int main(int argc, char** argv){

    /*
    0 - проверяем корректность аргументов
    1 - создаём сокет, который потом сделаем слушающим входящие соединения (socket)
    2 - устанавливаем его IP адрес и порт (bind)
    3 - делаем сокет слушающим (listen)
    4 - обрабатываем входящие запросы 
        4.1 - ждём очередное входящие соединение и принимаем его (accept)
        4.2 - если количество процессов предельное, то также ждём завершения какого-то
        4.3 - делаем fork, обрабатываем пришедший запрос в другом потоке (fork)
    */

    // 0 - проверяем корректность аргументов
    if(argc != 3){
        printf("main(pid=%d): expected 2 arguments (port number, concurrency level), got %d arguments\n", getpid(), argc-1);
        exit(-1);
    }
    int port = atoi(argv[1]);
    MAX_CHILD_PROC_COUNT = atoi(argv[2]);
    if(MAX_CHILD_PROC_COUNT < 1){
        printf("main(pid=%d): concurrency level must be integer and greater that 0.\n", getpid());
        exit(-1);
    }


    // 1 - создаём сокет, который потом сделаем слушающим входящие соединения
    int listenfd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if(listenfd != 0) printf("main(pid=%d): listening socket creation - success\n", getpid());
    else { 
        printf("main(pid=%d): listening socket creation - ERROR (%s)\n", getpid(), strerror(errno));
        exit(-1);
    }


    // 2 - устанавливаем его IP адрес и порт
    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);                // преобразование в big-endian, для использования в заголовке TCP
    addr.sin_addr.s_addr = htonl(INADDR_ANY);   // преобразование в big-endian, для использования в заголовке IP
    int err = bind(listenfd, (struct sockaddr*)&addr, (socklen_t)sizeof(addr));

    if(err == 0) printf("main(pid=%d): binding listening socket - success\n", getpid());
    else { 
        printf("main(pid=%d): binding listening socket - ERROR (%s)\n", getpid(), strerror(errno));
        exit(-1);
    }


    // 3 - делаем сокет слушающим
    listen(listenfd, 10); 


    // 4 - обрабатываем входящие запросы
    signal(SIGCHLD, SIGCHLD_handler);   // устанавливаем обработчик сигнала SIGCHLD, чтобы не было зомби-процессов
    while(1)
    {
        // 4.1 - ждём очередное входящие соединение и принимаем его
        printf("main(pid=%d): waiting for incoming connections...\n", getpid());
        int connfd = accept(listenfd, (struct sockaddr*)NULL, NULL);
        if(connfd >= 0) printf("main(pid=%d): connection accepted (connfd=%d)\n", getpid(), connfd);
        else { 
            printf("main(pid=%d): connection accept - ERROR (%s)\n", getpid(), strerror(errno));
            continue;
        }

        // 4.2 - если количество процессов предельное, то также ждём завершения какого-то
        if(CHILD_PROC_COUNT == MAX_CHILD_PROC_COUNT){
            while(1){
                pid_t child_pid = wait(NULL);
                if(child_pid > 0){
                    CHILD_PROC_COUNT -= 1;
                    printf("main(pid=%d): wait - child with pid=%d finished, now CHILD_PROC_COUNT=%d\n", getpid(), child_pid, CHILD_PROC_COUNT);
                    break;
                }        
                else 
                    printf("main(pid=%d): wait - ERROR (%s)\n", getpid(), strerror(errno));
            }
        }

        // 4.3 - делаем fork, обрабатываем пришедший запрос в другом потоке
        CHILD_PROC_COUNT += 1;
        int child_pid = fork();
        if(child_pid == 0){
            exit(process_request(connfd));
        }
        close(connfd);
        printf("main(pid=%d): processing request in child process (pid=%d)\n", getpid(), child_pid);

        // 4.3 - обрабатываем пришедший запрос в этом же потоке
        // process_request(connfd);
        
    }
}