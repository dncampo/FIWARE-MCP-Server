from mcp.server.fastmcp import FastMCP
import time
import signal
import sys
import requests
import json
import logging
import os
from datetime import datetime
from curl_utils import prepare_request_from_curl
import openai
import httpx

#workaround for openai proxy error
#https://community.openai.com/t/bypassing-proxy-settings-with-openais-python-sdk/1026752
#https://github.com/openai/openai-python/issues/1026
class CustomHTTPClient(httpx.Client):
    def __init__(self, *args, **kwargs):
        kwargs.pop("proxies", None)  # Remove the 'proxies' argument if present
        super().__init__(*args, **kwargs)

# Configure logging
def setup_logging():
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Create a logger
    logger = logging.getLogger('CB-assistant')
    logger.setLevel(logging.DEBUG)

    # Create handlers
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_handler = logging.FileHandler(f'logs/cb_assistant_{current_time}.log')
    console_handler = logging.StreamHandler()

    # Create formatters and add it to handlers
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(log_format)
    console_handler.setFormatter(log_format)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Initialize logger
logger = setup_logging()

# Handle SIGINT (Ctrl+C) gracefully
def signal_handler(sig, frame):
    logger.info("Shutting down server gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# This MCP server provides tools for interacting with a FIWARE Context Broker
logger.info("Initializing MCP server 'CB-assistant'")
mcp = FastMCP(
    name="CB-assistant",
    host="127.0.0.1",
    port=5001,
    # Add this to make the server more resilient
    timeout=15  # Increase timeout to 15 seconds
)

# This tool gets the Context Broker version
@mcp.tool()
def CB_version(address: str="localhost", port: int=1026) -> str:
    """Return the version of the CB."""
    try:
        logger.debug(f"Getting CB version from {address}:{port}")
        url = f"http://{address}:{port}/version"
        response = requests.get(url)
        response.raise_for_status()
        logger.info(f"Successfully retrieved CB version from {address}:{port}")
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting CB version: {str(e)}")
        return json.dumps({"error": str(e)})


# This tool gets all entities from the Context Broker
# - You can add extra headers to the request if needed
# - Like adding a personalized context to the request
# - The default headers are "Accept: application/json" and "Content-Type: application/json"
# - This tool returns a JSON object with the entities and a count of the total number of entities in NGSILD-Results-Count
@mcp.tool()
def get_all_entities(address: str="localhost", port: int=1026,  limit=1000, custom_headers: object = {
            "Link": "<http://context/user-context.jsonld>",
            "rel": "http://www.w3.org/ns/json-ld#context",
            "type": "application/ld+json"
            }) -> str:
    """Get all entities from the Context Broker."""
    try:
        logger.debug(f"Getting all entities from {address}:{port} with limit {limit}")
        url = f"http://{address}:{port}/ngsi-ld/v1/entities?limit={limit}"
        params = {
            "local": "true",
            "count": "true",
            "format": "simplified"
        }
        headers = {
            "Accept": "application/json"
        }

        # Add any extra headers if provided
        if custom_headers:
            headers.update(custom_headers)

        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        logger.info(f"Successfully retrieved {response.headers.get('NGSILD-Results-Count', 'unknown')} entities")
        logger.info(f"Payload size: {response.headers.get('Content-Length', 'unknown')} bytes")
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting entities: {str(e)}")
        return json.dumps({"error": str(e)})


# This tool queries entities in the Context Broker
# - You can add a query to the request if needed
@mcp.tool()
def query_CB(address: str="localhost", port: int=1026, query: str="") -> str:
    """Query the CB."""
    try:
        url = f"http://{address}:{port}/query"
        response = requests.get(url, params={"query": query})
        response.raise_for_status()  # Raise an exception for bad status codes
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": str(e)})


# This tool gets all entity types from the Context Broker
# - You can add extra headers to the request if needed
# - Like adding a personalized context to the request
# - The default headers are "Accept: application/json"
@mcp.tool()
def get_entity_types(address: str="localhost", port: int=1026, limit=1000, custom_headers: object = {
            "Link": "<http://context/user-context.jsonld>",
            "rel": "http://www.w3.org/ns/json-ld#context",
            "type": "application/ld+json"
            }) -> str:
    """Get entity types from the Context Broker."""
    try:
        url = f"http://{address}:{port}/ngsi-ld/v1/types?limit={limit}"
        headers = {
            "Accept": "application/json"
        }

        # Add any extra headers if provided
        if custom_headers:
            headers.update(custom_headers)

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": str(e)})


# This tool creates or updates entities in the Context Broker
@mcp.tool()
def publish_to_CB(address: str="localhost", port: int=1026, entity_data: dict=None, custom_headers = {
            "Link": "<http://context/user-context.jsonld>",
            "rel": "http://www.w3.org/ns/json-ld#context",
            "type": "application/ld+json"
            }) -> str:
    """Publish an entity to the CB."""

    logger.debug(f"Attempting to publish entity to {address}:{port}")
    broker_url = f"http://{address}:{port}/ngsi-ld/v1/entities"
    headers = {
        "Content-Type": "application/ld+json"
    }
    # Add any extra headers if provided
    if custom_headers:
        headers.update(custom_headers)

    logger.debug(f"Entity data: {entity_data}")
    logger.debug(f"Headers: {headers}")

    try:
        response = requests.post(broker_url, json=entity_data, headers=headers)

        if response.status_code == 201:
            logger.info(f"Successfully created entity. Status code: {response.status_code}")
        elif response.status_code == 409:
            logger.info(f"Entity already exists. Attempting update. Status code: {response.status_code}")

            entity_id = entity_data["id"]
            update_url = f"{broker_url}/{entity_id}/attrs"

            # Remove id, type and context for update
            update_data = entity_data.copy()
            update_data.pop("id", None)
            update_data.pop("type", None)
            update_data.pop("@context", None)

            update_response = requests.patch(update_url, json=update_data, headers=headers)
            logger.info(f"Update attempt result: {update_response.status_code}")
        else:
            logger.error(f"Error creating entity. Status code: {response.status_code}")
            logger.error(f"Response content: {response.text}")
    except Exception as e:
        logger.error(f"An error occurred while publishing entity: {e}")

    logger.debug("Entity data sent:")
    logger.debug(json.dumps(entity_data, indent=2))
    return json.dumps({"status": response.status_code})


# This tool gets an entity by ID from the Context Broker
@mcp.tool()
def get_entity_by_id(address: str="localhost", port: int=1026, entity_id: str="") -> str:
    """Get an entity by ID from the Context Broker."""
    try:
        url = f"http://{address}:{port}/ngsi-ld/v1/entities/{entity_id}"
        response = requests.get(url)
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": str(e)})


# This tool asks an LLM to generate a valid NGSI-LD query from a natural language query
@mcp.tool()
def magic_query_context_broker(query: str="", address: str="localhost", port: int=1026, custom_headers: object = {
            "Link": "<http://context/user-context.jsonld>",
            "rel": "http://www.w3.org/ns/json-ld#context",
            "type": "application/ld+json"
            }) -> str:
    """
    If none of the other tools fits to interact with the context broker, this should be used to ask
    to an LLM to generate a valid NGSI-LD query from a natural language query.

    Args:
        query: The natural language query to process
        address: Context Broker address
        port: Context Broker port
        custom_headers: Dictionary of custom headers to be added to the request
    Returns:
        JSON string with the original query, the generated NGSI-LD query and the query results
    """
    try:
        # Load instructions from external file
        filepath = os.path.join(os.path.dirname(__file__), "instructions.txt")
        logger.debug(f"Loading instructions from {filepath}")
        with open(filepath, "r") as file:
            INSTRUCTIONS_FOR_FTGPT4o_mini_FIWARE = file.read()

        # Prepare the request to the OpenAI API
        filepath = os.path.join(os.path.dirname(__file__), ".env")
        logger.debug(f"Loading OpenAI API key from {filepath}")
        env_vars = {}
        with open(filepath, "r") as file:
            for line in file:
                if line.startswith('#') or not line.strip():
                    continue
                key, value = line.strip().split('=', 1)
                env_vars[key] = value
        openai_client = openai.OpenAI(http_client=CustomHTTPClient(), api_key=env_vars['OPENAI_API_KEY'])

        # Call the fine-tuned model which returns a curl command to run in the CB
        response = openai_client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:ging-upm:fiware-translator-v3-01:BKPTbGe6",
            messages=[
                {"role": "system", "content": INSTRUCTIONS_FOR_FTGPT4o_mini_FIWARE},
                {"role": "user", "content": query}
            ]
        )
        logger.debug(f"created chat with OpenAI")

        # Extract the NGSI-LD query from the model response
        ngsi_query = response.choices[0].message.content
        logger.debug(f"Generated NGSI-LD query from fine tuned OpenAI model: {ngsi_query}")

        # Call helper method to prepare the request parameters
        broker_url, headers, method, data, params = prepare_request_from_curl(ngsi_query, address, port, custom_headers)

        # Execute the query against the Context Broker
        if method == 'GET':
            cb_response = requests.get(broker_url, headers=headers, params=params)
        elif method == 'POST':
            cb_response = requests.post(broker_url, headers=headers, json=data, params=params)
        elif method == 'PATCH':
            cb_response = requests.patch(broker_url, headers=headers, json=data, params=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        cb_response.raise_for_status()

        return json.dumps({
            "original_query": query,
            "ngsi_query": ngsi_query,
            "results": cb_response.json()
        })

    except FileNotFoundError:
        logger.error("Instructions file not found")
        return json.dumps({"error": "Instructions file not found"})
    except openai.OpenAIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return json.dumps({"error": f"OpenAI API error: {str(e)}"})
    except requests.exceptions.RequestException as e:
        logger.error(f"Context Broker request error: {str(e)}")
        return json.dumps({"error": f"Context Broker request error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return json.dumps({"error": f"Unexpected error: {str(e)}"})


if __name__ == "__main__":
    try:
        logger.info("Starting MCP server 'CB-assistant' on 127.0.0.1:5001")
        mcp.run()
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        time.sleep(3)
