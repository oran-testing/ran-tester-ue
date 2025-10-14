#!/usr/bin/env bash
set -eux

# Check if NVIDIA driver is installed and working
if ! command -v nvidia-smi &>/dev/null || ! nvidia-smi &>/dev/null; then
  echo "ERROR: NVIDIA driver not detected."
  echo "Please install the driver first by running:"
  echo "  sudo ./scripts/nvidia_driver_setup.sh"
  exit 1
fi

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
| sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/libnvidia-container.list \
| sed 's#deb #deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] #' \
| sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2 nvidia-container-toolkit

sudo systemctl restart docker

echo "NVIDIA Container Toolkit installed successfully."
