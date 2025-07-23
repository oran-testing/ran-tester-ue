#!/bin/bash

if [ $EUID -ne 0 ]; then
  echo "This script must be run as root"
  exit 1
fi

read -p "This installation requires a reboot. Are you sure you want to proceed? (y/N): " confirm

if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborting installation."
  exit 0
fi

ubuntu-drivers install --gpgpu
apt install nvidia-utils-570-server
nvidia-smi
