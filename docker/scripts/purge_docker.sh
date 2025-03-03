#!/bin/bash

if [ $EUID -ne 0 ]; then
  echo "This script must be run as root"
  exit 1
fi

echo "WARNING: This will completely wipe Docker, removing all:"
echo "- Containers (running & stopped)"
echo "- Images (local & pulled)"
echo "- Volumes (data storage)"
echo "- Networks (custom ones)"
echo "- Build cache"
echo ""
read -p "Are you sure you want to proceed? (y/N): " confirm

if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborting cleanup."
  exit 1
fi

echo "Stopping all running containers..."
docker stop $(docker ps -aq) 2>/dev/null

echo "Removing all containers..."
docker rm -f $(docker ps -aq) 2>/dev/null

echo "Removing all images..."
docker rmi -f $(docker images -aq) 2>/dev/null

echo "Removing all volumes..."
docker volume rm $(docker volume ls -q) 2>/dev/null

echo "Pruning unused Docker objects..."
docker system prune -a --volumes -f

echo "Removing all build cache..."
docker builder prune -a -f

echo "Removing all networks (except default ones)..."
docker network prune -f

echo "Docker purge completed!"
