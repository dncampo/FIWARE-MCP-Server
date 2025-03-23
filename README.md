# FIWARE MCP Server

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

```bash
mcp install server.py

# Custom name
mcp install server.py --name "FIWARE MCP Server"

# Environment variables, if any
mcp install server.py -v API_KEY=abc123 -v DB_URL=postgres://...
mcp install server.py -f .env
```

## Usage

Start the MCP server:
```bash
python server.py
# or
mcp run server.py
```

The server will start on `127.0.0.1:5001` by default.

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
- Host address
- Port number
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