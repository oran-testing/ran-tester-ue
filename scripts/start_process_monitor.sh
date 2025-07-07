#!/bin/bash

stop_orphaned_processes() {
  while docker ps -q --filter ancestor=ghcr.io/oran-testing/controller | grep -q .; do
    echo "HERE"
    sleep 1
  done
  container_names=$(docker ps | awk '/rtue|jammer|sniffer|grafana/{print $1}')
  if ! [ -z $container_names ]; then
    docker kill $container_names
  fi
}

while true; do
  stop_orphaned_processes
done
