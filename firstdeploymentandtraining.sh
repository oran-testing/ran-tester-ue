#!/bin/bash
if [ $EUID -ne 0 ]; then
	echo "script must be run as root"
	exit 1
fi

# Build the image locally if you want (optional, comment if pulling from GHCR)
# docker build -t llm_image ./llm_worker

docker build --no-cache -f llm_worker/Dockerfile.alpine -t ghcr.io/oran-testing/llm-worker llm_worker 
docker run -d --gpus all --name llm_worker ghcr.io/oran-testing/llm-worker tail -f /dev/null


# Run commands inside the running container
#docker exec -it llm_worker python3 generatedataset.py
#docker exec -it llm_worker python3 finetune.py
sudo docker commit llm_worker llm_worker:finetuned

sudo docker compose --profile components build

sudo docker compose --profile components pull 
sudo docker compose --profile system pull
sudo docker compose --profile system up