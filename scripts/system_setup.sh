#!/bin/bash

SCRIPT_PATH=$(realpath $0)
SCRIPT_DIR=$(dirname $SCRIPT_PATH)
PROJECT_ROOT_DIR=$(realpath $SCRIPT_DIR/..)

echo "Configuring with project root: $PROJECT_ROOT_DIR"

read -p "Are you sure you want to proceed? (y/N): " confirm

if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborting cleanup."
  exit 0
fi

sed -i "s|<rtusystem-dir>|${PROJECT_ROOT_DIR}|g" $PROJECT_ROOT_DIR/.env

if ! command -v docker &>/dev/null; then
  echo "Docker is not installed. Installing now..."

  # Update package list
  sudo apt update

  # Install Docker (Debian/Ubuntu)
  sudo apt install -y docker.io

  # Enable Docker service
  sudo systemctl start docker
  sudo systemctl enable docker

  echo "Docker installation completed."
else
  echo "Docker is already installed!"
  docker --version
fi
