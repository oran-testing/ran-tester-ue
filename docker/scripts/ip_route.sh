#!/bin/bash

# Check if the script is run as root
if [ "$(id -u)" -ne 0 ]; then
	echo "Script must be run as root"
	exit 1
fi

# Get container IDs for containers using the rtu/ue image
#container_ids=$(sudo docker ps -a --filter "ancestor=rtu/ue" --format "{{.ID}}")
container_ids=$(sudo docker ps --filter "name=rtue" --format "{{.ID}}")

echo "Container IDs: $container_ids"

# Loop through each container ID
INDEX=1
for id in $container_ids; do
	echo "Executing in container: $id"
	INDEX+=1

	# Get the IP address of tun_rtue interface inside the container
	IP=$(sudo docker exec $id /bin/bash -c "ifconfig tun_rtue | grep 'inet ' | awk '{print \$2}'")
	GW=$(echo $IP | awk -F'.' '{OFS="."; $4=1; print $1,$2,$3,$4}')
	IPERF_IDX=$(echo $IP | awk -F'.' '{print $3}')

	# Check if the IP was correctly extracted
	if [ -z "$IP" ]; then
		echo "Error: IP address not found for container $id"
		continue
	fi

	echo "Extracted IP: $GW"

	# Check if the route already exists
	existing_route=$(sudo docker exec $id /bin/bash -c "ip route show 10.53.0.0/16" | wc -l)

	if [ "$existing_route" -gt 0 ]; then
		echo "Route 10.53.0.0/16 already exists in container $id. Skipping route addition."
	else
		# Add routing information to the container
		sudo docker exec $id /bin/bash -c "ip ro add 10.53.0.0/16 via $IP dev tun_rtue"
		echo "Route added to container $id"
	fi

	# Run iperf3 test in the background (parallel execution)
	echo "Starting iperf3 test in container $id"
	sudo docker exec $id /bin/bash -c "iperf3 -c 10.53.1.1 -i 1 -t 86400 -u -b 10M -p 520$IPERF_IDX &"

	echo "Started iperf3 test in container $id"
done

# Wait for all background processes (iperf3 tests) to complete
wait

echo "All iperf3 tests are finished."
