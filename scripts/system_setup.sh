#!/bin/bash

if [ $EUID -ne 0 ]; then
	echo "This script must be run as root"
	exit 1
fi

SCRIPT_PATH=$(realpath $0)
SCRIPT_DIR=$(dirname $SCRIPT_PATH)
PROJECT_ROOT_DIR=$(realpath $SCRIPT_DIR/..)

echo "Configuring with project root: $PROJECT_ROOT_DIR"

read -p "Are you sure you want to proceed? (y/N): " confirm

if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborting cleanup."
  exit 0
fi

echo "Updating DOCKER_SYSTEM_DIRECTORY to ${PROJECT_ROOT_DIR}"
sed -i "s|DOCKER_SYSTEM_DIRECTORY=.*|DOCKER_SYSTEM_DIRECTORY=${PROJECT_ROOT_DIR}|g" $PROJECT_ROOT_DIR/.env

if ! command -v docker &>/dev/null; then
  echo "Docker is not installed. Installing now..."

  # Update package list
  apt update

  # Install Docker (Debian/Ubuntu)
  apt install -y docker.io

  # Enable Docker service
  systemctl start docker
  systemctl enable docker

  echo "Docker installation completed."
else
  echo "Docker is already installed!"
  docker --version
fi

if ! command -v uhd_images_downloader &>/dev/null; then
	echo "UHD is not installed. Installing now..."
	apt update
	apt install -y uhd-host

	echo "UHD utils are installed."
fi

uhd_images_downloader -i $PROJECT_ROOT_DIR/.uhd_images
