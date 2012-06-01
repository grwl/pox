#!/bin/sh -x

sudo ovs-vsctl del-br mitm0
script -c 'while true ; do python pox.py --no-cli mitmer nm.test ; done'
