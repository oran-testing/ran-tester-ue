#!/bin/bash

# Push a prach_cfg measurement into InfluxDB with values matching
# the gNB configuration in configs/srsran/gnb_uhd.yaml.

if [ "$EUID" -ne 0 ]; then
    echo "Script must be run as root"
    exit 1
fi

source ../.env

# InfluxDB v2 line protocol for prach_cfg
# Fields derived from gnb_uhd.yaml and cell_config.h defaults:
#   config_idx      = 1  (prach.prach_config_index)
#   root_seq_idx    = 1
#   zero_corr_zone  = 0
#   freq_offset     = 8
#   num_ra_preambles= 1

TIMESTAMP=$(date +%s%9N)

LINE="prach_cfg,sni5gect_data_id=test config_idx=1i,root_seq_idx=1i,zero_corr_zone=0i,freq_offset=8i,num_ra_preambles=1i ${TIMESTAMP}"

echo "Writing: $LINE"

RESP=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST \
    "http://localhost:${DOCKER_INFLUXDB_INIT_PORT}/api/v2/write?org=${DOCKER_INFLUXDB_INIT_ORG}&bucket=${DOCKER_INFLUXDB_INIT_BUCKET}&precision=ns" \
    -H "Authorization: Token ${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN}" \
    -H "Content-Type: text/plain" \
    --data-binary "$LINE")

if [ "$RESP" = "204" ]; then
    echo "Success (HTTP $RESP)"
else
    echo "Failed (HTTP $RESP)"
    exit 1
fi
