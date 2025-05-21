#!/bin/bash

read -p "GitHub Username: " GHCR_USER
read -s -p "GitHub Token: " GHCR_TOKEN
echo

echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
