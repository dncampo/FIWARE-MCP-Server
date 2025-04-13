import re
import json
import logging
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger('CB-assistant')

def parse_curl_command(curl_command: str) -> dict:
    """
    Parse a curl command string into its components.

    Args:
        curl_command: String containing the curl command

    Returns:
        Dictionary containing the parsed components:
        - method: HTTP method (GET, POST, etc.)
        - url: Target URL
        - headers: Dictionary of headers
        - data: Request body data
        - params: Query parameters
    """
    try:
        # Initialize result dictionary
        result = {
            'method': 'GET',  # Default method
            'url': '',
            'headers': {},
            'data': None,
            'params': {}
        }

        # Extract method if specified
        method_match = re.search(r'-X\s+(\w+)', curl_command)
        if method_match:
            result['method'] = method_match.group(1).upper()

        # Extract URL
        url_match = re.search(r"'(https?://[^']+)'", curl_command)
        if not url_match:
            url_match = re.search(r'"(https?://[^"]+)"', curl_command)
        if not url_match:
            url_match = re.search(r'https?://\S+', curl_command)

        if url_match:
            url = url_match.group(0)
            result['url'] = url

            # Parse query parameters from URL
            parsed_url = urlparse(url)
            if parsed_url.query:
                result['params'] = parse_qs(parsed_url.query)

        # Extract headers
        header_matches = re.finditer(r"-H\s+'([^']+)'", curl_command)
        for match in header_matches:
            header = match.group(1)
            key, value = header.split(':', 1)
            result['headers'][key.strip()] = value.strip()

        # Extract data/body
        data_match = re.search(r"--data-raw\s+'([^']+)'", curl_command)
        if not data_match:
            data_match = re.search(r"-d\s+'([^']+)'", curl_command)

        if data_match:
            data = data_match.group(1)
            try:
                # Try to parse as JSON
                result['data'] = json.loads(data)
            except json.JSONDecodeError:
                # If not JSON, keep as string
                result['data'] = data

        logger.debug(f"Parsed curl command: {result}")
        return result

    except Exception as e:
        logger.error(f"Error parsing curl command: {str(e)}")
        raise

def prepare_request_from_curl(curl_command: str, address: str = "localhost", port: int = 1026, custom_headers: object={}) -> tuple:
    """
    Convert a curl command to Python request parameters.

    Args:
        curl_command: String containing the curl command
        address: Context Broker address
        port: Context Broker port
        custom_headers: Dictionary of custom headers to be added to the request
    Returns:
        Tuple containing:
        - broker_url: The target URL
        - headers: Dictionary of headers
        - method: HTTP method
        - data: Request body data
        - params: Query parameters
    """
    try:
        logger.debug(f"Preparing request from received curl command: {curl_command}")

        # Remove single quotes from the curl command
        curl_command_no_quotes = curl_command.replace("'", "")

        # Parse the curl command
        parsed = parse_curl_command(curl_command_no_quotes)

        # Extract base URL from the parsed command or use default
        if parsed['url']:
            broker_url = parsed['url']
        else:
            broker_url = f"http://{address}:{port}/ngsi-ld/v1/entities"

        # Ensure Content-Type header is set for POST/PATCH requests
        if parsed['method'] in ['POST', 'PATCH'] and 'Content-Type' not in parsed['headers']:
            parsed['headers']['Content-Type'] = 'application/ld+json'

        # Ensure Accept header is set
        if 'Accept' not in parsed['headers']:
            parsed['headers']['Accept'] = 'application/ld+json'

        # Add custom headers
        if custom_headers:
            parsed['headers'].update(custom_headers)

        logger.debug(f"Prepared request parameters: {parsed}")
        return (
            broker_url,
            parsed['headers'],
            parsed['method'],
            parsed['data'],
            parsed['params']
        )

    except Exception as e:
        logger.error(f"Error preparing request from curl: {str(e)}")
        raise 