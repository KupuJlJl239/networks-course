#!/bin/sh

src=$1
gcc $src -o $src.out -lpcap > /dev/null 2> /dev/null
shift
./$src.out $@