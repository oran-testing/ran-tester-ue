#!/bin/bash

# Virtual Interface Cleanup Script
echo "Cleaning up virtual interfaces..."

# Remove IP addresses if they exist
sudo ip addr del 192.168.1.1/24 dev vgnb0 2>/dev/null || true
sudo ip addr del 192.168.1.2/24 dev vru0 2>/dev/null || true

# Bring interfaces down
sudo ip link set vgnb0 down 2>/dev/null || true
sudo ip link set vru0 down 2>/dev/null || true

# Delete the veth pair
sudo ip link del vru0 2>/dev/null || true
sudo ip link del vgnb0 2>/dev/null || true

echo "Cleanup complete!"

# Verify cleanup
echo "Remaining virtual interfaces:"
ip link show | grep -E "(vru0|vgnb0)" || echo "No virtual interfaces found - cleanup successful!"
