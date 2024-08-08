#!/bin/sh

src=$1
gcc $src -o $src.out -Wformat-overflow=0 -ggdb
shift
./$src.out $@