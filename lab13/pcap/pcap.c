#include <stdio.h>
#include <pcap.h>
#include <stdio.h>

int main(int argc, char *argv[])
{
    char *dev, errbuf[PCAP_ERRBUF_SIZE];

    dev = pcap_lookupdev(errbuf);
    if (dev == NULL) 
    {
        fprintf(stderr, "Couldn't find default device: %s\n", errbuf);
        return(2);
    }
    printf("Device: %s\n", dev);


    pcap_t *handle;
    struct pcap_pkthdr header;


    handle = pcap_open_live(dev, BUFSIZ, 1, 1000, errbuf);
    size_t total_traffic = 0;
    printf("\033[0K\r%d байтов передано", total_traffic);

    while(1){
        // const uint8_t* packet = pcap_next(handle, &header);
        // const struct sniff_ethernet *ethernet = packet;
        pcap_next(handle, &header);
        total_traffic += header.len;
        printf("\033[0K\r%d байтов передано", total_traffic);
    }
    
    pcap_close(handle);
    return(0);
}