#!/bin/sh

src=$1
gcc $src -o $src.out
shift
./$src.out $@