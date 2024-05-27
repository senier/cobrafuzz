#!/bin/bash

mkdir -p seeds
n=0
for line in $(wget -q -O- https://raw.githubusercontent.com/dateutil/dateutil/master/tests/test_parser.py | sed -n -e 's/^\s*("\([^"]*\).*$/\1/p');
do
    echo $line > seeds/$n.dat
    n=$[n+1]
done
