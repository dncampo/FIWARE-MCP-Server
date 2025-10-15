# FIWARE MCP Server

[![smithery badge](https://smithery.ai/badge/@dncampo/FIWARE-MCP-Server)](https://smithery.ai/server/@dncampo/FIWARE-MCP-Server)
![](https://badge.mcpx.dev?type=server 'MCP Server')
![](https://badge.mcpx.dev?type=dev 'MCP Dev')

This is a first implementation of a FIWARE Model Context Protocol (MCP) Server that provides a bridge between the Context Broker and other services. The server implements basic operations for interacting with a FIWARE Context Broker.

## Objectives

- Create a basic MCP server implementation for FIWARE
- Provide simple tools for Context Broker interaction
- Demonstrate basic intent CRUD operations with the Context Broker
- Serve as a foundation for more complex MCP implementations

## Features

- Context Broker version checking
- Query capabilities for the Context Broker
- Entity publishing and updating

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- Access to a FIWARE Context Broker instance

## Installation

### Installing via Smithery

To install FIWARE MCP Server for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@dncampo/FIWARE-MCP-Server):

```bash
npx -y @smithery/cli install @dncampo/FIWARE-MCP-Server --client claude
```

### Manual Installation
1. Clone this repository:
```bash
git clone <repository-url>
cd FIWARE_MCP_01
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Claude Desktop integration

Claude Desktop should launch the server via STDIO. Do not use “mcp install” or “mcp run” with this server.

Example configuration (adjust paths for your environment):
```json
{
  "mcpServers": {
    "CB-assistant": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "requests>=2.31.0",
        "--with",
        "fastmcp>=0.3.0",
        "python",
        "PATH\\TO\\FIWARE-MCP-Server\\server.py"
      ]
    }
  }
}
```

Alternative if dependencies are installed with pip:
```json
{
  "mcpServers": {
    "CB-assistant": {
      "command": "python",
      "args": [
        "PATH\\TO\\FIWARE-MCP-Server\\server.py"
      ]
    }
  }
}
```

## Usage

By default, running the script starts the server in STDIO mode. Use `--http` to start an HTTP server.

- STDIO (default):
```bash
python server.py
```

- HTTP mode:
```bash
python server.py --http
```

- HTTP host/port (optional):
```bash
python server.py --http --host 127.0.0.1 --port 5001
```

When running with `--http`, the server binds to the provided host/port and uses stateless HTTP sessions for compatibility with streamable HTTP clients.

### Redirecting with ngrok (HTTP mode)

To use LLMs via external APIs (for example the OpenAI Responses API) you may need to expose your local MCP server to the Internet. Use ngrok to create a public HTTPS tunnel to the server when running in HTTP mode.

1. Sign up at https://ngrok.com and install the ngrok client for your OS.
2. Add your ngrok auth token to the client (follow ngrok's OS-specific setup). For example:
   - ngrok (v3) config command: ngrok config add-authtoken <YOUR_AUTH_TOKEN>
3. Start your MCP server in HTTP mode (if not already running). Example:
   - python server.py --http --host 127.0.0.1 --port 5001
4. Start an ngrok tunnel that forwards to your HTTP server:
   - ngrok http http://127.0.0.1:5001
   (replace host/port if you configured them differently)
5. Once ngrok is running it will display one or more public forwarding URLs. The MCP endpoint will be reachable at:
   - {PUBLIC_URL}/mcp

Note: Keep your auth token secure. The public URL stays active while ngrok is running and will cease to be reachable when you stop the tunnel.

### Available Tools

1. **CB_version**
   - Checks the version of the Context Broker
   - Default parameters: address="localhost", port=1026
   - Returns: JSON string with version information

2. **query_CB**
   - Queries the Context Broker
   - Parameters:
     - address (default: "localhost")
     - port (default: 1026)
     - query (default: "")
   - Returns: JSON string with query results

3. **publish_to_CB**
   - Publishes or updates entities in the Context Broker
   - Parameters:
     - address (default: "localhost")
     - port (default: 1026)
     - entity_data (required: dictionary with entity information)
   - Returns: JSON string with operation status

### Example Usage

```python
# Example entity data
entity_data = {
    "id": "urn:ngsi-ld:TemperatureSensor:001",
    "type": "TemperatureSensor",
    "temperature": {
        "type": "Property",
        "value": 25.5
    },
    "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
}

# Publish to Context Broker
result = publish_to_CB(entity_data=entity_data)
```

## Configuration

The server can be configured by modifying the following parameters in `server.py`:
- Host address (HTTP mode only)
- Port number (HTTP mode only)
- Timeout settings

## Error Handling

The server includes comprehensive error handling for:
- Network connectivity issues
- Invalid responses from the Context Broker
- Malformed entity data
- Server shutdown

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the Apache License 2.0.