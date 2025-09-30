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


echo "Installing recommended GPU driver..."
INSTALL_OUTPUT=$(ubuntu-drivers install --gpgpu 2>&1 || true)

echo "$INSTALL_OUTPUT"

VERSION=$(echo "$INSTALL_OUTPUT" | grep -oP 'nvidia-headless-no-dkms-\K[0-9]+(?=-server)' | head -n1)

if [[ -z "$VERSION" ]]; then
  echo "Could not extract NVIDIA driver version from output. Please install the driver manually."
  exit 1
fi

echo "Installing matching nvidia-utils-$VERSION-server package..."
apt update
apt install -y "nvidia-utils-${VERSION}-server"

nvidia-smi || echo "nvidia-smi failed. A reboot may be required first."