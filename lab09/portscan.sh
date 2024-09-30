#!/bin/bash



ip=$1
startport=$2
endport=$3

port=$startport

# Чтобы скрипт можно было прервать нажав ctrl-C
trap "echo 'interrupted'; exit" INT

# Перебираем все порты в указанном диапазоне
while ((port<=$endport))
do
    # echo "$port"

    # На каждый порт отправляем пустое сообщение: "echo > /dev/tcp/$ip/$port"
    # Весь вывод перенаправляем в /dev/null: "> /dev/null 2>&1"
    # В случае успеха выполнится также команда после "&&", то есть 'echo "$port"'
    # Таким образом на каждую успешную отправку выведется порт
    (echo > /dev/tcp/$ip/$port) > /dev/null 2>&1 && echo "$port open"

    port=$(( $port + 1 ))

done
