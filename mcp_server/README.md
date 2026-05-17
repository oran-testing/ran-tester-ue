# MCP Server for RAN Tester UE Controller

Model Context Protocol (MCP) server that enables AI agents to control the RAN Tester UE system by supplying JSON configurations that are automatically converted to the appropriate format (YAML/TOML/CONF).

## Architecture

```
AI Agent (Claude Desktop, Cursor, etc.)
         │
         │ MCP Protocol (stdio)
         │
┌────────▼────────┐
│   MCP Server    │
│                 │
│  • Validates    │
│  • Converts     │
│  • Proxies      │
└────────┬────────┘
         │ HTTP (port 1343)
         │
┌────────▼────────┐
│   Controller    │
│                 │
│  • Docker Mgmt  │
│  • Components   │
└─────────────────┘
```

## Quick Start

### Prerequisites

- Docker Engine and Docker Compose
- RAN Tester UE system configured and running
- Python 3.11+ (for local development)

### Running with Docker Compose

```bash
# Start the full system including MCP server
docker compose up -d

# Or start only the MCP server (requires controller running)
docker compose up -d mcp-server

# View logs
docker compose logs -f mcp-server
```

### Environment Variables

Set these in your `.env` file:

```bash
# Required - Must match a token in the controller's api_auth configuration
MCP_CONTROLLER_TOKEN=testing_token

# Optional - Log level (DEBUG, INFO, WARNING, ERROR)
MCP_LOG_LEVEL=INFO
```

## Using with Opencode (Recommended)

Opencode uses `opencode.json` configuration files. Create one in your project root or at `~/.config/opencode/opencode.json`:

**Project-level config** (`/home/charles/ran-tester-ue/opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ran_tester_ue": {
      "type": "local",
      "command": ["sudo", "docker", "compose", "-f", "/home/charles/ran-tester-ue/docker-compose.yml", "run", "--rm", "mcp-server"],
      "environment": {
        "MCP_CONTROLLER_TOKEN": "testing_token"
      },
      "enabled": true
    }
  }
}
```

**Important:** The MCP server name in the config (`ran_tester_ue`) becomes the prefix for tool names. In opencode, the tools will be named:
- `ran_tester_ue_list_components`
- `ran_tester_ue_start_component`
- `ran_tester_ue_stop_component`
- etc.

### How the Agent Discovers Tool Information

When opencode starts, it:

1. **Connects to the MCP server** using the command specified in `opencode.json`
2. **Calls `list_tools()`** which returns all available tools with their descriptions and input schemas
3. **The agent reads the tool descriptions** to understand what each tool does
4. **The agent calls `get_usage_guide`** (first tool listed) which returns a comprehensive guide including:
   - All available tools and their parameters
   - Component types and their purposes
   - RF hardware options
   - 5G frequency bands and concepts
   - Validation rules
   - Example workflows

This means **the agent self-documents** - it gets all the information it needs directly from the MCP server at startup, no external documentation required.

### Using the Tools in Opencode

Once configured, simply run `opencode` in the project directory. The agent will automatically have access to the MCP tools. You can prompt it:

```
use ran_tester_ue to list all running components
```

Or ask it to do something specific:

```
use ran_tester_ue to start a sniffer component at 3.5GHz with 20MHz bandwidth using zmq
```

The agent will automatically call `get_usage_guide` first to learn how to operate the system, then use the appropriate tools.

### Using with Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ran-tester-ue": {
      "command": "docker",
      "args": [
        "compose",
        "-f",
        "$HOME/ran-tester-ue/docker-compose.yml",
        "run",
        "--rm",
        "mcp-server"
      ],
      "env": {
        "MCP_CONTROLLER_TOKEN": "testing_token"
      }
    }
  }
}
```

Alternatively, run the MCP server directly with Python:

```json
{
  "mcpServers": {
    "ran-tester-ue": {
      "command": "python",
      "args": ["$HOME/ran-tester-ue/mcp_server/main.py"],
      "env": {
        "CONTROLLER_URL": "http://localhost:1343",
        "CONTROLLER_TOKEN": "testing_token",
        "CONFIGS_DIR": "$HOME/ran-tester-ue/configs"
      }
    }
  }
}
```

### Cursor IDE

Add to Cursor MCP settings:

```json
{
  "mcpServers": {
    "ran-tester-ue": {
      "command": "docker",
      "args": ["compose", "-f", "$HOME/ran-tester-ue/docker-compose.yml", "run", "--rm", "mcp-server"]
    }
  }
}
```

### VS Code with MCP Extension

```json
{
  "mcp": {
    "servers": {
      "ran-tester-ue": {
        "command": "docker",
        "args": ["compose", "-f", "$HOME/ran-tester-ue/docker-compose.yml", "run", "--rm", "mcp-server"]
      }
    }
  }
}
```

## Available Tools

### list_components

List all running RAN tester components.

**Input:** None

**Example:**
```
"List all running components"
```

### start_component

Start a component with JSON configuration. The MCP server automatically validates and converts the JSON to the appropriate format.

**Input:**
- `component_type`: One of `rtue`, `sniffer`, `sni5gect`, `jammer`, `ssb_spoofer`, `uuagent`
- `config_json`: Component configuration as JSON object
- `rf_config`: RF hardware configuration with `type` field (`b200`, `zmq`, or `none`)

**Example - Start RTUE:**
```json
{
  "component_type": "rtue",
  "config_json": {
    "id": "test_ue_1",
    "rf_srate": 23040000,
    "rf_tx_gain": 60,
    "rf_rx_gain": 40,
    "rat_nr_bands": 3,
    "rat_nr_nof_prb": 106,
    "usim_imsi": "001010123456789",
    "nas_apn": "internet"
  },
  "rf_config": {
    "type": "b200"
  }
}
```

**Example - Start Sniffer:**
```json
{
  "component_type": "sniffer",
  "config_json": {
    "id": "downlink_sniffer",
    "file_path": "/tmp/capture.pcap",
    "sample_rate": 23040000,
    "frequency": 1842500000,
    "nid_1": 0,
    "ssb_numerology": 0
  },
  "rf_config": {
    "type": "b200"
  }
}
```

**Example - Start Jammer:**
```json
{
  "component_type": "jammer",
  "config_json": {
    "id": "test_jammer",
    "center_frequency": 2400000000,
    "bandwidth": 10000000,
    "amplitude": 0.5,
    "sampling_freq": 30720000,
    "tx_gain": 50,
    "device_args": "type=b200"
  },
  "rf_config": {
    "type": "b200"
  }
}
```

### stop_component

Stop a running component.

**Input:**
- `component_id`: ID of the component to stop

**Example:**
```json
{
  "component_id": "test_ue_1"
}
```

### get_component_logs

Retrieve logs from a component.

**Input:**
- `component_id`: ID of the component
- `component_type`: Type of the component

**Example:**
```json
{
  "component_id": "test_ue_1",
  "component_type": "rtue"
}
```

### get_component_health

Check health status of a component.

**Input:**
- `component_id`: ID of the component

**Example:**
```json
{
  "component_id": "test_ue_1"
}
```

### get_component_schema

Get JSON schema for a component type to understand required fields.

**Input:**
- `component_type`: Component type

**Example:**
```json
{
  "component_type": "rtue"
}
```

### validate_config

Validate a JSON configuration without starting the component.

**Input:**
- `component_type`: Component type
- `config_json`: Configuration to validate

**Example:**
```json
{
  "component_type": "rtue",
  "config_json": {
    "id": "test_ue",
    "rf_srate": 23040000,
    "rf_tx_gain": 60
  }
}
```

### list_available_configs

List all available configuration templates.

**Input:** None

## Configuration Formats

The MCP server automatically converts JSON to the appropriate format based on component type:

| Component Type | Output Format | Description |
|----------------|---------------|-------------|
| `rtue` | `.conf` (INI) | ConfigParser format with sections |
| `uuagent` | `.conf` (INI) | Same as rtue |
| `sniffer` | `.toml` | TOML with sniffer and pdcch sections |
| `sni5gect` | `.yaml` | YAML format |
| `jammer` | `.yaml` | YAML format |
| `ssb_spoofer` | `.yaml` | YAML format |

### RTUE Configuration Example

**JSON Input:**
```json
{
  "id": "test_ue",
  "rf_srate": 23040000,
  "rf_tx_gain": 60,
  "rf_rx_gain": 40,
  "rat_nr_bands": 3,
  "rat_nr_nof_prb": 106,
  "usim_imsi": "001010123456789",
  "nas_apn": "internet"
}
```

**Converted to .conf:**
```ini
[rf]
srate = 23040000
tx_gain = 60
rx_gain = 40

[rat.nr]
bands = 3
nof_prb = 106

[usim]
imsi = 001010123456789

[nas]
apn = internet
```

### Sniffer Configuration Example

**JSON Input:**
```json
{
  "id": "sniffer_1",
  "sample_rate": 23040000,
  "frequency": 1842500000,
  "file_path": "/tmp/capture.pcap",
  "nid_1": 0,
  "ssb_numerology": 0,
  "pdcch_num_prbs": 48
}
```

**Converted to .toml:**
```toml
[sniffer]
sample_rate = 23040000
frequency = 1842500000
file_path = "/tmp/capture.pcap"
nid_1 = 0
ssb_numerology = 0

[[pdcch]]
num_prbs = 48
```

## Validation Rules

### RTUE
- `rf_tx_gain`: 0-90 dB
- `rf_rx_gain`: 0-90 dB
- `rf_srate`: Must be > 0
- `rat_nr_nof_prb`: Must be > 0
- `usim_imsi`: Must be 15 digits

### Sniffer
- `sample_rate`: Must be > 0
- `frequency`: Must be in FR1 (410e6-7.125e9) or FR2 (24.25e9-52.6e9)
- `ssb_numerology`: 0-4
- `pdcch_coreset_duration`: 1, 2, or 3

### Jammer
- `center_frequency`: Must be in FR1 or FR2
- `bandwidth`: Must be > 0
- `amplitude`: 0-1
- `tx_gain`: 0-90 dB
- `sampling_freq`: Must be >= 2x bandwidth

### Device Constraints (B200/B210)
- Max frequency: 6 GHz
- Max sample rate: 61.44 MHz
- Cannot operate in FR2

## Agent Instructions

When using this MCP server with an AI agent, provide the following context:

### System Prompt for Agents

```
You have access to the RAN Tester UE MCP server which allows you to control a 5G RAN testing system.

Available component types:
- rtue: RAN Tester UE (simulates a 5G user equipment)
- sniffer: Packet sniffer (captures and analyzes 5G traffic)
- sni5gect: Security testing framework (tests RAN security)
- jammer: Jamming simulation (simulates RF jamming attacks)
- ssb_spoofer: SSB spoofing (spoofs synchronization signals)
- uuagent: UU interface agent

RF hardware types:
- b200: USRP B200/B210 software-defined radio
- zmq: ZeroMQ for simulation/testing
- none: No RF hardware

Key frequency bands:
- n1: 2100 MHz
- n3: 1800 MHz  
- n28: 700 MHz
- n41: 2.5 GHz
- n78: 3.5 GHz
- n79: 4.9 GHz

Sample rate guidelines:
- 15.36 MHz: 10 MHz bandwidth (50 PRB)
- 23.04 MHz: 20 MHz bandwidth (106 PRB)
- 30.72 MHz: 20 MHz bandwidth (106 PRB)
- 61.44 MHz: 100 MHz bandwidth (273 PRB)

Always validate configurations before starting components. Use get_component_schema to understand required fields.
```

### Example Agent Workflows

**Workflow 1: Basic RAN Testing Setup**
```
User: "Set up a basic RAN testing environment with a UE and sniffer on band 3"

Agent should:
1. Call get_component_schema for "rtue" and "sniffer"
2. Call start_component for rtue with band 3 configuration
3. Call start_component for sniffer tuned to band 3 frequency
4. Call list_components to verify both are running
```

**Workflow 2: Security Test**
```
User: "Run a jamming attack test at 2.4GHz"

Agent should:
1. Call get_component_schema for "jammer"
2. Call validate_config to check the configuration
3. Call start_component with jammer config at 2.4GHz
4. Call get_component_health to verify it's running
5. When done, call stop_component
```

**Workflow 3: Configuration Debugging**
```
User: "Why won't my sniffer start?"

Agent should:
1. Call list_components to see what's running
2. Call get_component_logs for the sniffer
3. Call get_component_health to check status
4. Analyze errors and suggest fixes
```

## Troubleshooting

### MCP Server Cannot Connect to Controller

```bash
# Check controller is running
docker ps | grep controller

# Check network connectivity
docker exec mcp-server ping controller

# Check logs
docker compose logs -f mcp-server
docker compose logs -f controller
```

### Configuration Validation Fails

```bash
# Test with known-good config
curl -X POST http://localhost:1343/start_from_json \
  -H "Authorization: Bearer testing_token" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test",
    "type": "rtue",
    "config_json": {
      "rf_srate": 23040000,
      "rf_tx_gain": 60,
      "rf_rx_gain": 40,
      "rat_nr_bands": 3,
      "rat_nr_nof_prb": 106,
      "usim_imsi": "001010123456789",
      "nas_apn": "internet"
    },
    "rf": {"type": "b200"}
  }'
```

### Component Starts but Immediately Fails

```bash
# Check container status
docker ps -a | grep <component_id>

# Check container logs
docker logs <component_id>

# Get component logs via MCP
# Call get_component_logs with the component ID
```

### Debug Mode

Enable debug logging by setting in `.env`:
```bash
MCP_LOG_LEVEL=DEBUG
```

Then restart:
```bash
docker compose restart mcp-server
```

## Development

### Local Development

```bash
cd mcp_server
pip install -r requirements.txt

# Run the server
python main.py
```

### Building Docker Image

```bash
docker build -t ran-tester-ue-mcp ./mcp_server
```

### Running Tests

```bash
cd mcp_server
python -m pytest tests/
```

## File Structure

```
mcp_server/
├── main.py              # MCP server entry point
├── adapter.py           # Controller API client
├── converter.py         # JSON-to-config converter
├── tools.py             # MCP tool definitions
├── resources.py         # MCP resource definitions
├── schemas/             # JSON schemas
│   ├── rtue.json
│   ├── sniffer.json
│   ├── jammer.json
│   └── sni5gect.json
├── templates/           # Config templates (future)
├── Dockerfile
├── requirements.txt
└── README.md
```

## API Reference

The MCP server interfaces with the controller's enhanced API:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/list` | GET | List running components |
| `/start` | POST | Start component (config\_str) |
| `/start_from_json` | POST | Start component (JSON config) |
| `/stop` | POST | Stop component |
| `/logs` | POST | Get component logs |
| `/health` | POST | Check component health |
| `/schemas/{type}` | GET | Get JSON schema |

## Security

- Bearer token authentication required
- Token must match controller's `api_auth` configuration
- MCP server runs in isolated Docker network
- Config directory mounted read-only

## License

TBD
