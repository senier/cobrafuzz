#!/bin/bash

mkdir -p seeds
n=0
for line in $(wget -q -O- https://github.com/kjd/idna/raw/master/tests/IdnaTestV2.txt | sed -n -e 's/^\([^;]*\);.*$/\1/p');
do
    echo $line > seeds/$n.dat
    n=$[n+1]
done
