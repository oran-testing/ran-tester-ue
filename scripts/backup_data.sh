#!/bin/bash

if [ $EUID -ne 0 ]; then
	echo "Script must be runs root"
	exit 1
fi

if [ $# -lt 2 ]; then
	echo "Usage: backup <since> <output filepath>"
	exit 1
fi

source ../.env

set -x

INFLUX_PS=$(docker ps --filter="ancestor=influxdb:2.7" -q | head -n 1)
docker exec -it $INFLUX_PS bash -c "influx query 'from(bucket: \"$DOCKER_INFLUXDB_INIT_BUCKET\") \
	|> range(start: $1)' --token $DOCKER_INFLUXDB_INIT_ADMIN_TOKEN --org $DOCKER_INFLUXDB_INIT_ORG --raw > /tmp/host/$2 "
