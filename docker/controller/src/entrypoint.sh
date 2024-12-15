#!/bin/bash

kill_ue_containers() {
	UE_IMG_IDS=$(docker ps | awk '/srsran\/ue/{print $1}')
	for IMG in $UE_IMG_IDS; do
		docker kill $IMG
	done
}

trap kill_ue_containers SIGTERM
trap kill_ue_containers SIGINT

poetry run python3 main.py --config $CONFIG --docker 1
