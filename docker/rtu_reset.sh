#!/bin/bash

if [ $EUID -ne 0 ]; then
	echo "Script must be run as root"
	exit 1
fi

UE_PS=$(docker ps -q -a --filter="ancestor=rtu/ue")
JAMMER_PS=$(docker ps -q -a --filter="ancestor=rtu/jammer")
UU_PS=$(docker ps -q -a --filter="ancestor=rtu/uuagent")

if [ -z "$UE_PS" ] && [ -z "$JAMMER_PS" ] && [ -z "$UU_PS" ]; then
	exit 0
fi

docker kill $UE_PS $JAMMER_PS $UU_PS

docker rm $UE_PS $JAMMER_PS $UU_PS
