#!/bin/sh

cd $(dirname -- "$0";)

pwd

ulimit -n 4096

./micromamba/root/envs/beambci/bin/python MainProgram.py

echo "\nPress ENTER to close this window."

read junk
