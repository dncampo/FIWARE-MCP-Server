from mcp.server.fastmcp import FastMCP
import time
import signal
import sys
import requests
import json

# Handle SIGINT (Ctrl+C) gracefully
def signal_handler(sig, frame):
    print("Shutting down server gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# This MCP server provides tools for interacting with a FIWARE Context Broker
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
        url = f"http://{address}:{port}/version"
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": str(e)})


# This tool gets all entities from the Context Broker
# - You can add extra headers to the request if needed
# - Like adding a personalized context to the request
# - The default headers are "Accept: application/json" and "Content-Type: application/json"
# - This tool returns a JSON object with the entities and a count of the total number of entities in NGSILD-Results-Count
@mcp.tool()
def get_all_entities(address: str="localhost", port: int=1026,  limit=1000, extra_headers: str="") -> str:
    """Get all entities from the Context Broker."""
    try:
        url = f"http://{address}:{port}/ngsi-ld/v1/entities?limit={limit}"
        params = {
            "local": "true",
            "count": "true"
        }
        headers = {
            "Accept": "application/json"
        }

        # Add any extra headers if provided
        if extra_headers:
            try:
                extra_headers_dict = json.loads(extra_headers)
                headers.update(extra_headers_dict)
            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid extra_headers format. Must be valid JSON string"})

        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
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
def get_entity_types(address: str="localhost", port: int=1026, limit=1000, extra_headers: str="") -> str:
    """Get entity types from the Context Broker."""
    try:
        url = f"http://{address}:{port}/ngsi-ld/v1/types?limit={limit}"
        headers = {
            "Accept": "application/json"
        }

        # Add any extra headers if provided
        if extra_headers:
            try:
                extra_headers_dict = json.loads(extra_headers)
                headers.update(extra_headers_dict)
            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid extra_headers format. Must be valid JSON string"})

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": str(e)})


# This tool creates or updates entities in the Context Broker
@mcp.tool()
def publish_to_CB(address: str="localhost", port: int=1026, entity_data: dict=None) -> str:
    """Publish an entity to the CB."""
    broker_url = f"http://{address}:{port}/ngsi-ld/v1/entities"  # Default URL, adjust if needed
    headers = {
        "Content-Type": "application/ld+json"
    }
    try:
        response = requests.post(broker_url, json=entity_data, headers=headers)

        if response.status_code == 201:
            print(f"Success! Entity created. Status code: {response.status_code}")
        elif response.status_code == 409:
            print(f"Entity already exists. Status code: {response.status_code}")

            # Update the entity if it already exists
            entity_id = entity_data["id"]
            update_url = f"{broker_url}/{entity_id}/attrs"

            # Remove id, type and context for update
            update_data = entity_data.copy()
            update_data.pop("id", None)
            update_data.pop("type", None)
            update_data.pop("@context", None)

            update_response = requests.patch(update_url, json=update_data, headers=headers)
            print(f"Update attempt result: {update_response.status_code}")
        else:
            print(f"Error creating entity. Status code: {response.status_code}")
            print(f"Response content: {response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")

    print("\nEntity data sent:")
    print(json.dumps(entity_data, indent=2))
    return json.dumps({"status": "completed"})


if __name__ == "__main__":
    try:
        print("Starting MCP server 'CB-assistant' on 127.0.0.1:5001")
        # Use this approach to keep the server running
        mcp.run()
    except Exception as e:
        print(f"Error: {e}")
        # Sleep before exiting to give time for error logs
        time.sleep(3)
