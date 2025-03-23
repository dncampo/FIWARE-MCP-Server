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

# Create an MCP server with increased timeout
mcp = FastMCP(
    name="CB-assistant",
    host="127.0.0.1",
    port=5001,
    # Add this to make the server more resilient
    timeout=15  # Increase timeout to 15 seconds
)

# Define our tool
@mcp.tool()
def count_r(word: str) -> int:
    """Count the number of 'r' letters in a given word."""
    try:
        # Add robust error handling
        if not isinstance(word, str):
            return 0
        return word.lower().count("r")
    except Exception as e:
        # Return 0 on any error
        return 0
    
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