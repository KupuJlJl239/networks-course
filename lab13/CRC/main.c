#include <stdio.h>
#include <inttypes.h>
#include <assert.h>
#include <stdlib.h>



/*
Вычисляет сумму CRC-32 от массива данных
*/
uint32_t CRC_32(const uint8_t* data, size_t size){

    // текущая контрольная сумма 
    uint32_t res = 0;

    for(size_t byte_n = 0; byte_n < size; ++byte_n){
        uint8_t byte = data[byte_n];
        for(int bit_n = 7; bit_n >=0; --bit_n){

            uint8_t old_bit = (res >> 15) & 1;   // старший бит res
            uint8_t new_bit = (byte >> bit_n) & 1;  // новый бит res

            res = (res << 1) | new_bit;     // сдвигаем результат на один бит
            if(old_bit){
                res = res ^ 0x1EDC6F41;
            }
        }  
    }

    return res;
}




int main(){
    uint8_t buf[21];

    int i = 1;
    while(1){
        int l = fread(buf, 1, 20, stdin);
        if(l <= 0)
            break;
        buf[l] = 0;

        // номер бита с ошибкой
        int r = rand() % (8*l);     

        // считаем настоящую контрольную сумму
        uint32_t good_checksum = CRC_32(buf, l);

        // меняем один бит
        buf[r / 8] ^= (1 << (r % 8));

        // сумма пакета с изменённым одним битом
        uint32_t bad_checksum = CRC_32(buf, l);


        if(good_checksum != bad_checksum)
            printf("пакет %d: ОК\n", i);
        else
            printf("пакет %d: ОШИБКА НЕ РАСПОЗНАНА\n", i);

        ++i;
    }
}