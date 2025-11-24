from fastmcp import FastMCP
import time
import signal
import sys
import requests
import json
import logging
import argparse
from typing import Optional
from pysmartdatamodels import pysmartdatamodels as sdm

from helpers import process_headers

# --- Logging to STDERR only ---
logger = logging.getLogger("cb-assistant")
logger.setLevel(logging.INFO)
logger.handlers.clear()
_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.INFO)
logger.addHandler(_stderr_handler)
logger.propagate = False


# Parse CLI args early so we can configure MCP instance accordingly
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--http", action="store_true", help="Run MCP server over HTTP transport")
_parser.add_argument("--host", default="127.0.0.1", help="HTTP host (only for --http)")
_parser.add_argument("--port", type=int, default=5001, help="HTTP port (only for --http)")
_args, _ = _parser.parse_known_args()
_IS_HTTP = _args.http
_HOST = _args.host
_PORT = _args.port

# Handle SIGINT (Ctrl+C) gracefully
def signal_handler(sig, frame):
    logger.info("Shutting down server gracefully...")  # was print
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# This MCP server provides tools for interacting with a FIWARE Context Broker
mcp = FastMCP(
    name="CB-assistant",
    stateless_http=_IS_HTTP,  # only enable when running in HTTP mode
)

# This tool gets the Context Broker version
@mcp.tool(exclude_args=["sessionId","toolCallId","action","chatInput"])
def CB_version(address: str="https://up-broker.fox.dea.k8s.fiware.org", port: int=443,
    sessionId: Optional[str] = None,
    action: Optional[str] = None,
    chatInput: Optional[str] = None,
    toolCallId: Optional[str] = None
               ) -> str:
    """Return the version of the CB."""
    try:
        url = f"{address}:{port}/version"
        logger.info("Executing GET request to: %s", url)
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        result = response.json()
        logger.info("Request successful. Status: %s, Response: %s", response.status_code, json.dumps(result))
        return json.dumps(result)
    except requests.exceptions.RequestException as e:
        logger.error("Request failed. Error: %s", str(e))
        return json.dumps({"error": str(e)})


# This tool gets all entities from the Context Broker
# - You can add extra headers to the request if needed
# - Like adding a personalized context to the request
# - The default headers are "Accept: application/json" and "Content-Type: application/json"
# - This tool returns a JSON object with the entities and a count of the total number of entities in NGSILD-Results-Count
@mcp.tool(exclude_args=["sessionId","toolCallId","action","chatInput"])
def get_all_entities(address: str="https://up-broker.fox.dea.k8s.fiware.org", port: int=443,  limit=1000, extra_headers: str="",
    sessionId: Optional[str] = None,
    action: Optional[str] = None,
    chatInput: Optional[str] = None,
    toolCallId: Optional[str] = None) -> str:
    """Get all entities from the Context Broker."""
    try:
        url = f"{address}:{port}/ngsi-ld/v1/entities?limit={limit}"
        params = {
            "local": "true",
            "count": "true"
        }
        headers = {
            "Accept": "application/json",
            "Link": '<https://raw.githubusercontent.com/jason-fox/csv-to-json/refs/heads/cote-divoire/data-models/demo-context-fr.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"',
            "Demo": "Demo"
        }

        # Add any extra headers if provided
        if extra_headers:
            try:
                headers = process_headers(headers, extra_headers)
            except ValueError as exc:
                return json.dumps({"error": str(exc)})

        logger.info("Executing GET request to: %s with params: %s, headers: %s", url, params, headers)
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        result = response.json()
        logger.info("Request successful. Status: %s, Response count: %s", response.status_code, len(result) if isinstance(result, list) else "N/A")
        return json.dumps(result)
    except requests.exceptions.RequestException as e:
        logger.error("Request failed. Error: %s", str(e))
        return json.dumps({"error": str(e)})



# This tool gets all entity types from the Context Broker
# - You can add extra headers to the request if needed
# - Like adding a personalized context to the request
# - The default headers are "Accept: application/json"
@mcp.tool(exclude_args=["sessionId","toolCallId","action","chatInput"])
def get_entity_types(address: str="https://up-broker.fox.dea.k8s.fiware.org", port: int=443, limit=100, extra_headers: str="",
    sessionId: Optional[str] = None,
    action: Optional[str] = None,
    chatInput: Optional[str] = None,
    toolCallId: Optional[str] = None) -> str:
    """Get entity types from the Context Broker."""
    try:
        url = f"{address}:{port}/ngsi-ld/v1/types?limit={limit}"
        headers = {
            "Accept": "application/json",
            "Link": '<https://raw.githubusercontent.com/jason-fox/csv-to-json/refs/heads/cote-divoire/data-models/demo-context-fr.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"',
            "Demo": "Demo"
        }

        # Add any extra headers if provided
        if extra_headers:
            try:
                headers = process_headers(headers, extra_headers)
            except ValueError as exc:
                return json.dumps({"error": str(exc)})

        logger.info("Executing GET request to: %s with headers: %s", url, headers)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()
        logger.info("Request successful. Status: %s, Response: %s", response.status_code, json.dumps(result))
        return json.dumps(result)
    except requests.exceptions.RequestException as e:
        logger.error("Request failed. Error: %s", str(e))
        return json.dumps({"error": str(e)})



# This tool allows to execute any query to the Context Broker
# - You should provide the full or partial URL of the query
# - For example, to get the entity of type "Building" whose name is "Building 1" you should provide the following URL:
# 'GET http://localhost:1026/ngsi-ld/v1/entities/Building/name/Building%201' or 'GET /ngsi-ld/v1/entities/Building/name/Building%201'
# you need to provide the proper parameter for the GET request
@mcp.tool(exclude_args=["sessionId","toolCallId","action","chatInput"])
def execute_query(params: str, address: str="https://up-broker.fox.dea.k8s.fiware.org", port: int=443, limit=10, extra_headers: str="",
    sessionId: Optional[str] = None,
    action: Optional[str] = None,
    chatInput: Optional[str] = None,
    toolCallId: Optional[str] = None) -> str:
        """
        This tools just passes the query to the Context Broker and returns the response
        You should provide the full or partial VALID query to the Context Broker
        you need to provide the proper parameter for the GET request.
        For example, to get the entity of type "Building" whose name is "Building 1" you should provide the following URL:
        'GET https://up-broker.fox.dea.k8s.fiware.org:443/ngsi-ld/v1/entities/Building/name/Building%201' or 'GET /ngsi-ld/v1/entities/Building/name/Building%201'
        """
        base_url = f"{address}:{port}"

        # Normalize params without printing anything to stdout
        if isinstance(params, str) and params.strip().startswith("GET"):
            params = params.strip()[3:]
        if isinstance(params, str) and params.strip().startswith("https://up-broker.fox.dea.k8s.fiware.org:443/"):
            params = params.strip()[len("https://up-broker.fox.dea.k8s.fiware.org:443/"):]
        params = params.lstrip("/").replace(" ", "")

        # Check if params start with "/" (possibly with leading spaces), and strip spaces and the first slash
        if isinstance(params, str):
            params = params.lstrip()
            if params.startswith("/"):
                params = params[1:]

        full_url = f"{base_url}/{params}"

        headers = {
            "Accept": "application/ld+json, application/json;q=0.9, */*;q=0.1",
            "Link": '<https://raw.githubusercontent.com/jason-fox/csv-to-json/refs/heads/cote-divoire/data-models/demo-context-fr.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"',
            "Demo": "Demo"
        }

        # Add any extra headers if provided
        if extra_headers:
            try:
                headers = process_headers(headers, extra_headers)
            except ValueError as exc:
                return json.dumps({"error": str(exc)})

        try:
            logger.info("Executing GET request to: %s with headers: %s", full_url, headers)
            resp = requests.get(full_url, headers=headers)

            # Try JSON; fall back to text
            try:
                body = resp.json()
            except ValueError:
                body = {"raw_response": resp.text}

            # Return ONLY JSON to stdout
            result = {
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": body,
            }

            # Raise for non-2xx after capturing body, but still return JSON error
            resp.raise_for_status()
            logger.info("Request successful. Status: %s, Response body: %s", resp.status_code, json.dumps(body)[:500] if isinstance(body, dict) else str(body)[:500])
            return json.dumps(result)

        except requests.exceptions.RequestException as e:
            logger.error("Request failed. Error: %s, URL: %s", str(e), full_url)
            # Still return valid JSON
            return json.dumps({"error": str(e), "url": full_url})


# This tool creates or updates entities in the Context Broker
@mcp.tool(exclude_args=["sessionId","toolCallId","action","chatInput"])
def publish_to_CB(address: str="https://up-broker.fox.dea.k8s.fiware.org", port: int=443, entity_data: dict=None,
    sessionId: Optional[str] = None,
    action: Optional[str] = None,
    chatInput: Optional[str] = None,
    toolCallId: Optional[str] = None) -> str:  # type: ignore
    """Publish an entity to the CB."""
    broker_url = f"{address}:{port}/ngsi-ld/v1/entities"
    headers = {
        "Content-Type": "application/ld+json",
        "Link": '<https://raw.githubusercontent.com/jason-fox/csv-to-json/refs/heads/cote-divoire/data-models/demo-context-fr.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"',
        "Demo": "Demo"
    }
    try:
        logger.info("Executing POST request to: %s with entity_data: %s", broker_url, json.dumps(entity_data, indent=2))
        response = requests.post(broker_url, json=entity_data, headers=headers)

        if response.status_code == 201:
            logger.info("Request successful. Entity created. Status code: %s, Response: %s", response.status_code, response.text[:500])
        elif response.status_code == 409:
            logger.info("Entity already exists. Status code: %s, Response: %s", response.status_code, response.text[:500])

            # Update the entity if it already exists
            entity_id = entity_data["id"]
            update_url = f"{broker_url}/{entity_id}/attrs"

            # Remove id, type and context for update
            update_data = entity_data.copy()
            update_data.pop("id", None)
            update_data.pop("type", None)
            update_data.pop("@context", None)

            logger.info("Executing PATCH request to: %s with update_data: %s", update_url, json.dumps(update_data, indent=2))
            update_response = requests.patch(update_url, json=update_data, headers=headers)
            logger.info("Update request successful. Status: %s, Response: %s", update_response.status_code, update_response.text[:500])
        else:
            logger.error("Request failed. Error creating entity. Status code: %s, Response content: %s", response.status_code, response.text)
    except Exception as e:
        logger.exception("Request failed. An error occurred: %s", e)

    logger.info("Entity data sent: %s", json.dumps(entity_data, indent=2))
    return json.dumps({"status": "completed"})


# This tool creates or updates entities in the Context Broker
@mcp.tool(exclude_args=["sessionId","toolCallId","action","chatInput"])
def fetch_SDM_data(datamodel: str = "Animal", subject: str = "dataModel.Agrifood",
    sessionId: Optional[str] = None,
    action: Optional[str] = None,
    chatInput: Optional[str] = None,
    toolCallId: Optional[str] = None) -> str:
    """Fetch data from the SDM.
    From a URL of a SDM or a SDM ID, fetch the data of the SDM using the pysmartdatamodels library.
    The response is a JSON object with the data of the SDM, where you can get the data of the SDM in a human readable format
    useful for LLMs to understand the data of the SDM.
    You need to provide the datamodel and the subject of the SDM.
    For example, to fetch data from the SDM of the entity of type "WeatherForcast", you should provide the following:
    'datamodel: WeatherForcast, subject: datamode.Weather'
    In "JSON_schema_data" you will get the JSON schema of the SDM.
    """
    try:
        response = sdm.list_datamodel_metadata(datamodel, subject)
        logger.info("retrieved SDM metadata: %s", json.dumps(response, indent=2))
        schema_url = response['jsonSchemaUrl']
        logger.info("Executing GET request to: %s", schema_url)
        schema_response = requests.get(schema_url)
        schema_response.raise_for_status()
        schema_data = schema_response.json()
        logger.info("Request successful. Status: %s, Schema data retrieved", schema_response.status_code)
        response['JSON_schema_data'] = json.dumps(schema_data)
        logger.info("JSON schema data: %s", response['JSON_schema_data'])
        return json.dumps(response)
    except requests.exceptions.RequestException as e:
        logger.error("Request failed. Error fetching schema: %s", str(e))
        return json.dumps({"error": str(e)})
    except Exception as e:
        logger.error("Error: %s", str(e))
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    try:
        if _IS_HTTP:
            logger.info("Starting MCP server 'CB-assistant' on %s:%s (HTTP)", _HOST, _PORT)
            mcp.run(
                transport="sse",
                host=_HOST,
                port=_PORT,
            )
        else:
            logger.info("Starting MCP server 'CB-assistant' (STDIO)")
            mcp.run(
                transport="stdio",
            )

    except Exception as e:
        logger.exception("Error: %s", e)
        time.sleep(3)