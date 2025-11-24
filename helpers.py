import json
from typing import Dict, List, Union, Any


HeaderInput = Union[str, Dict[str, Any], List[Dict[str, Any]]]


def process_headers(base_headers: Dict[str, str], extra_headers: HeaderInput) -> Dict[str, str]:
    """
    Merge user-provided headers into the provided base headers, accepting either:
      * a JSON string (object or array of objects)
      * a Python dict
      * a list/array of dicts

    Parameters
    ----------
    base_headers: Dict[str, str]
        Default headers to be used for the request.
    extra_headers: Union[str, dict, list]
        Additional headers. If a string, it must be valid JSON that decodes into a
        dict or a list of dicts. Lists/arrays must contain JSON objects.

    Returns
    -------
    dict
        New dictionary containing the merged headers.

    Raises
    ------
    ValueError
        If `extra_headers` cannot be decoded or does not conform to the supported formats.
    """
    parsed_headers: Union[Dict[str, Any], List[Dict[str, Any]]] = {}

    if isinstance(extra_headers, str):
        extra_headers = extra_headers.strip()
        if not extra_headers:
            return base_headers
        try:
            parsed_headers = json.loads(extra_headers)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid extra_headers format. Must be valid JSON string") from exc
    elif isinstance(extra_headers, dict):
        parsed_headers = extra_headers
    elif isinstance(extra_headers, list):
        parsed_headers = extra_headers
    elif extra_headers:
        raise ValueError("extra_headers must be a JSON string, dict, or list of dicts")
    else:
        return base_headers

    merged_headers: Dict[str, str] = base_headers.copy()

    if isinstance(parsed_headers, dict):
        merged_headers.update(_normalize_header_dict(parsed_headers))
    elif isinstance(parsed_headers, list):
        if not parsed_headers:
            return merged_headers
        for item in parsed_headers:
            if not isinstance(item, dict):
                raise ValueError("Each element of extra_headers array must be a JSON object")
            merged_headers.update(_normalize_header_dict(item))
    else:
        raise ValueError("extra_headers must decode to a JSON object or array of objects")

    return merged_headers


def _normalize_header_dict(headers: Dict[str, Any]) -> Dict[str, str]:
    """
    Ensure header keys/values are strings for compatibility with `requests`.
    """
    normalized: Dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str):
            raise ValueError("Header names must be strings")
        normalized[key] = str(value)
    return normalized

