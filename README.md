# FIWARE MCP Server
![](https://badge.mcpx.dev?type=server 'MCP Server')
![](https://badge.mcpx.dev?type=dev 'MCP Dev')

A FastMCP server implementation for interacting with FIWARE Context Broker using natural language queries and NGSI-LD operations.

## Features

- Natural language to NGSI-LD query translation using OpenAI's fine-tuned models
- Comprehensive set of tools for Context Broker interaction:
  - Get Context Broker version
  - Get all entities
  - Query entities
  - Get entity types
  - Publish/update entities
  - Get entity by ID
  - Magic query (natural language to NGSI-LD)


## Prerequisites

- Python 3.8+
- OpenAI API key
- FIWARE Context Broker instance

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd FIWARE-MCP-Server
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Claude Desktop integration

```bash
mcp install server.py

# Custom name
mcp install server.py --name "FIWARE MCP Server"
```

## Usage

Start the MCP server:
```bash
python server.py
# or
mcp run server.py
```

The server will start on `127.0.0.1:5001` by default.

3. Available tools:
- `CB_version`: Get the Context Broker version
- `get_all_entities`: Get all entities from the Context Broker
- `query_CB`: Query entities in the Context Broker
- `get_entity_types`: Get all entity types
- `publish_to_CB`: Create or update entities
- `get_entity_by_id`: Get a specific entity by ID
- `magic_query_context_broker`: Convert natural language to NGSI-LD queries

## Configuration

The server can be configured through environment variables and command-line arguments:

- `OPENAI_API_KEY`: OpenAI API key (required)
- Default Context Broker address: `localhost:1026`
- Default server address: `127.0.0.1:5001`

## Logging

Logs are stored in the `logs` directory with timestamped filenames. The logging system captures:
- Server startup and shutdown
- API calls to the Context Broker
- Success and failure of operations
- Error conditions with detailed messages

## Project Structure

```
FIWARE-MCP-Server/
├── server.py                          # Main server implementation
├── curl_utils.py                      # Curl command parsing utilities
├── instructions.txt                   # Instructions for the fine-tuned model
├── claude_desktop_configuration.json  # Example config file to integreate the server into Claude Desktop
├── logs/                              # Log files directory
├── .env                               # Environment variables
└── README.md                          # This file
```

## Error Handling

The server includes error handling for:
- OpenAI API errors
- Context Broker connection issues
- Invalid queries and requests

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache License 2.0. 