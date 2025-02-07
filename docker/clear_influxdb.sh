#!/bin/bash

if [ $EUID -ne 0 ]; then
	echo "Script must be run as root"
	exit 1
fi

source .env

EPOCH=$(date -d '7 days ago' --utc +'%Y-%m-%dT00:00:00Z')
NOW=$(date --utc +'%Y-%m-%dT23:59:59Z')

INFLUX_PS=$(docker ps --filter="ancestor=influxdb:2.7" -q | head -n 1)

docker exec -it $INFLUX_PS bash -c "influx delete \
	--bucket $DOCKER_INFLUXDB_INIT_BUCKET \
	--start \"$EPOCH\" \
	--stop \"$NOW\" \
  --token=$DOCKER_INFLUXDB_INIT_ADMIN_TOKEN \
  --org=$DOCKER_INFLUXDB_INIT_ORG"
