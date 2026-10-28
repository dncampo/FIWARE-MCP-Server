"""Bounded NGSI-LD HTTP requests. Modified for the MCP modernization."""
import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field


class Result(BaseModel):
    ok: bool
    status: int | None = None
    data: Any = None
    error: dict[str, Any] | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    pagination: dict[str, Any] | None = None


def failure(kind: str, message: str, status: int | None = None, data: Any = None) -> Result:
    return Result(ok=False, status=status, data=data, error={"kind": kind, "message": message})


def absolute_uri(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s]+$", value))


@dataclass
class Config:
    url: str = 'http://localhost:1026'
    timeout: float = 10
    headers: dict[str, str] = field(default_factory=dict)
    writes: bool = False
    context_urls: tuple[str, ...] = ()
    default_context: str | None = None
    max_bytes: int = 2_000_000

    def __post_init__(self):
        u = urlsplit(self.url)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError('NGSI_LD_BROKER_URL must be an HTTP(S) base URL without credentials, query or fragment')
        if not math.isfinite(self.timeout) or self.timeout <= 0 or self.max_bytes < 1:
            raise ValueError('Timeout and response byte limit must be positive')
        self.url = self.url.rstrip('/')
        self.headers = dict(httpx.Headers(self.headers))
        if any(k in self.headers for k in ('host', 'content-length', 'transfer-encoding', 'connection', 'link', 'content-type', 'accept')):
            raise ValueError('Configure context and representation separately; reserved HTTP headers are not allowed')
        for context in self.context_urls + ((self.default_context,) if self.default_context else ()):
            u = urlsplit(context)
            if u.scheme not in ('http', 'https') or not u.hostname or any(c in context for c in '<>\r\n"'):
                raise ValueError('Context URLs must be valid HTTP(S) URLs')

    @classmethod
    def from_env(cls):
        return cls(url=os.getenv('NGSI_LD_BROKER_URL', 'http://localhost:1026'),
                   timeout=float(os.getenv('NGSI_LD_TIMEOUT', '10')),
                   headers=json.loads(os.getenv('NGSI_LD_HEADERS', '{}')),
                   writes=os.getenv('NGSI_LD_ENABLE_WRITES', '').lower() == 'true',
                   context_urls=tuple(json.loads(os.getenv('NGSI_LD_CONTEXT_URLS', '[]'))),
                   default_context=os.getenv('NGSI_LD_CONTEXT_URL') or None,
                   max_bytes=int(os.getenv('NGSI_LD_MAX_RESPONSE_BYTES', '2000000')))


class Broker:
    def __init__(self, config: Config, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.transport = transport

    def validate_context(self, context: Any):
        allowed = self.config.context_urls + ((self.config.default_context,) if self.config.default_context else ())
        def check(value):
            if isinstance(value, str):
                if value not in allowed:
                    raise ValueError('Remote context URL must be explicitly configured in NGSI_LD_CONTEXT_URLS')
            elif isinstance(value, list):
                for item in value:
                    check(item)
            elif isinstance(value, dict):
                for key, item in value.items():
                    if key in ('@context', '@import'):
                        check(item)
                    elif isinstance(item, dict):
                        # Term @id IRIs identify data; only nested contexts cause retrieval.
                        for nested_key, nested_value in item.items():
                            if nested_key == '@context':
                                check(nested_value)
            else:
                raise ValueError('Context must be a configured URL, object or array')
        check(context)

    def request(self, method: str, path: str, *, params=None, body=None, context_url=None, representation='normalized') -> Result:
        try:
            if context_url:
                self.validate_context(context_url)
            context_url = context_url or self.config.default_context
            headers = dict(self.config.headers)
            headers['Accept'] = 'application/ld+json'
            if context_url:
                headers['Link'] = f'<{context_url}>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
            if body is not None:
                def check_document(value):
                    if isinstance(value, dict):
                        for key, item in value.items():
                            if key in ('@context', '@import'):
                                self.validate_context(item)
                            else:
                                check_document(item)
                    elif isinstance(value, list):
                        for item in value:
                            check_document(item)
                check_document(body)
                if '@context' in body:
                    self.validate_context(body['@context'])
                    headers.pop('Link', None)
                headers['Content-Type'] = 'application/ld+json' if '@context' in body else 'application/json'
            params = dict(params or {})
            if representation == 'keyValues':
                params['options'] = 'keyValues'
            # Paths are constructed internally; never accept a caller URL or follow redirects.
            with httpx.Client(timeout=self.config.timeout, follow_redirects=False, trust_env=False, transport=self.transport) as client:
                with client.stream(method, self.config.url + path, params=params, json=body, headers=headers) as response:
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > self.config.max_bytes:
                            return failure('response_too_large', 'Response exceeded configured byte limit; narrow the query', response.status_code)
                        chunks.append(chunk)
                    raw = b''.join(chunks)
                    try:
                        data = json.loads(raw) if raw else None
                    except (ValueError, UnicodeDecodeError):
                        data = raw.decode('utf-8', errors='replace')
                        if response.is_success:
                            return failure('invalid_response', 'Broker returned non-JSON success response', response.status_code, data)
                    safe_headers = {k: v for k, v in response.headers.items() if k in ('content-type', 'link', 'location', 'ngsild-results-count', 'retry-after')}
                    ok = response.is_success and response.status_code != 207
                    return Result(ok=ok, status=response.status_code, data=data, headers=safe_headers,
                                  error=None if ok else {'kind': 'partial_update' if response.status_code == 207 else 'broker_error',
                                                         'message': f'Broker returned HTTP {response.status_code}'})
        except ValueError as exc:
            return failure('validation', str(exc))
        except httpx.TimeoutException:
            return failure('timeout', 'Broker request timed out; a write may have been applied. Read before retrying.')
        except httpx.RequestError:
            return failure('connection', 'Could not connect to the configured broker')

    def page(self, path: str, limit: int, offset: int, **kwargs) -> Result:
        if not 1 <= limit <= 100 or offset < 0:
            return failure('validation', 'limit must be 1..100 and offset must be nonnegative')
        params = dict(kwargs.pop('params', {}) or {}, limit=limit, offset=offset, count='true')
        result = self.request('GET', path, params=params, **kwargs)
        if result.ok:
            # NGSI-LD type discovery can return EntityTypeList (including an
            # empty Orion-LD broker), rather than the detailed metadata array.
            if path == '/ngsi-ld/v1/types' and isinstance(result.data, dict) and isinstance(result.data.get('typeList'), list):
                result.data = result.data['typeList']
            if not isinstance(result.data, list):
                return failure('invalid_response', 'Expected a JSON array from collection endpoint', result.status, result.data)
            try:
                total = int(result.headers['ngsild-results-count'])
            except (KeyError, ValueError):
                total = None
            count = len(result.data)
            more = offset + count < total if total is not None else (True if 'rel="next"' in result.headers.get('link', '') else (None if count >= limit else False))
            result.pagination = dict(limit=limit, offset=offset, returned=count, total=total, has_more=more,
                                     incomplete=more is not False, next_offset=offset + count if more is not False and count else None)
        return result


def validate_attributes(body: dict[str, Any]):
    for name, values in body.items():
        if name == '@context':
            continue
        if name in ('id', 'type'):
            raise ValueError('Attribute updates must not contain id or type')
        values = values if isinstance(values, list) else [values]
        if not values:
            raise ValueError(f'{name}: attribute instance list cannot be empty')
        for value in values:
            if not isinstance(value, dict) or value.get('type') not in ('Property', 'Relationship', 'GeoProperty'):
                raise ValueError(f'{name}: expected normalized Property, Relationship or GeoProperty')
            key = 'object' if value['type'] == 'Relationship' else 'value'
            if key not in value:
                raise ValueError(f'{name}: missing {key}')
            if key == 'object' and (not isinstance(value[key], str) or not absolute_uri(value[key])):
                raise ValueError(f'{name}: Relationship object must be an absolute URI')
            if value['type'] == 'GeoProperty':
                geo = value['value']
                if not isinstance(geo, dict) or 'type' not in geo or 'coordinates' not in geo:
                    raise ValueError(f'{name}: expected GeoJSON geometry')
