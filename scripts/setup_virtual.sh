# clean up any leftovers 
sudo ip link del vru0 2>/dev/null || true
sudo ip link del vgnb0 2>/dev/null || true

# make the virtual cable
sudo ip link add vru0 type veth peer name vgnb0

# bring them up
sudo ip link set vru0 up
sudo ip link set vgnb0 up

# jumbo MTU on both ends
sudo ip link set vru0 mtu 9000
sudo ip link set vgnb0 mtu 9000

# setup addresses
sudo ip link set dev vru0 address ac:b4:80:13:48:48
sudo ip link set dev vgnb0 address 90:e3:ba:00:12:22
