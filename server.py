"""FIWARE MCP tools. Modified to use the official MCP Python SDK v2."""
import argparse
import json
import logging
from typing import Any, Literal
from urllib.parse import quote

from mcp.server import MCPServer

from broker import Broker, Config, Result, absolute_uri, failure, validate_attributes


def build_server(config: Config | None = None, *, transport=None) -> MCPServer:
    broker = Broker(config or Config.from_env(), transport)
    mcp = MCPServer('CB-assistant', instructions='Discover types and attributes before querying. Check ok and pagination in every result. Writes require explicit server configuration.')

    @mcp.tool(annotations={'readOnlyHint': True, 'openWorldHint': True})
    def get_broker_info() -> Result:
        """Check connectivity with a bounded standard /types request. Returns its status,
        configured endpoint, write policy and an optional /version probe. A missing
        vendor version endpoint does not mean NGSI-LD is unavailable. No capabilities
        are inferred beyond the requests actually made. Use before discovery.
        """
        result = broker.page('/ngsi-ld/v1/types', 1, 0)
        version = broker.request('GET', '/version')
        result.data = {'endpoint': broker.config.url, 'writes_enabled': broker.config.writes,
                       'types_probe': {'status': result.status, 'ok': result.ok},
                       'version_probe': version.model_dump()}
        result.pagination = None
        return result

    @mcp.tool(annotations={'readOnlyHint': True, 'openWorldHint': True})
    def get_types(limit: int = 20, offset: int = 0, context_url: str | None = None) -> Result:
        """Discover currently stored entity types and broker metadata, not a schema registry.
        Returns one /types?details=true page, including type identifiers and counts
        where supported. limit: 1..100; offset: nonnegative. Follow pagination.next_offset
        while incomplete. An empty array is a successful empty broker. context_url must
        be an explicitly configured context URL. Example: limit=10, offset=0.
        """
        return broker.page('/ngsi-ld/v1/types', limit, offset, params={'details': 'true'}, context_url=context_url)

    @mcp.tool(annotations={'readOnlyHint': True, 'openWorldHint': True})
    def get_attributes(entity_type: str, sample_limit: int = 5, context_url: str | None = None) -> Result:
        """Discover observed attributes for a type (compact term or full IRI).
        Returns /types/{type} metadata plus a bounded normalized entity sample showing
        actual Property, Relationship and GeoProperty structures. sample_limit: 1..20.
        This describes stored observations, never a complete model schema. Sample
        failures are reported separately. Example: entity_type='Room', sample_limit=2.
        """
        if not entity_type or not 1 <= sample_limit <= 20:
            return failure('validation', 'entity_type is required and sample_limit must be 1..20')
        result = broker.request('GET', '/ngsi-ld/v1/types/' + quote(entity_type, safe=''), context_url=context_url)
        if result.ok:
            sample = broker.page('/ngsi-ld/v1/entities', sample_limit, 0, params={'type': entity_type}, context_url=context_url)
            result.data = {'type_metadata': result.data, 'observed_entities': sample.model_dump(),
                           'complete_schema': False}
        return result

    @mcp.tool(annotations={'readOnlyHint': True, 'openWorldHint': True})
    def get_entity(entity_id: str, attrs: list[str] | None = None, context_url: str | None = None,
                   representation: Literal['normalized', 'keyValues'] = 'normalized') -> Result:
        """Read an entity by absolute URI, e.g. urn:ngsi-ld:Room:001. A missing entity
        returns ok=false with broker HTTP 404. Optional attrs selects attribute terms
        or IRIs. normalized preserves attribute types and Relationship objects;
        keyValues simplifies values. Context URLs must be configured by the operator.
        Returns broker JSON-LD and relevant response headers without re-expansion.
        """
        if not absolute_uri(entity_id):
            return failure('validation', 'entity_id must be an absolute URI')
        if attrs is not None and (not attrs or any(not a or ',' in a for a in attrs)):
            return failure('validation', 'attrs must contain nonempty terms or IRIs without commas')
        return broker.request('GET', '/ngsi-ld/v1/entities/' + quote(entity_id, safe=''),
                              params={'attrs': ','.join(attrs)} if attrs else {}, context_url=context_url, representation=representation)

    @mcp.tool(annotations={'readOnlyHint': True, 'openWorldHint': True})
    def query_entities(type: str | None = None, attrs: list[str] | None = None, q: str | None = None,
                       id: list[str] | None = None, idPattern: str | None = None,
                       georel: str | None = None, geometry: Literal['Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon'] | None = None,
                       coordinates: list[Any] | None = None, limit: int = 20, offset: int = 0,
                       context_url: str | None = None, representation: Literal['normalized', 'keyValues'] = 'normalized') -> Result:
        """Query one bounded NGSI-LD entity page. type is a type term/IRI (comma-separated
        types allowed). attrs must be a JSON array of attribute terms/IRIs, e.g.
        ['temperature'], not a comma-separated string. id is an array of absolute
        entity URIs. q is standard NGSI-LD text: 'temperature>20' or 'name=="Room 1"';
        combine with ';' (AND) or '|' (OR). q attribute paths use compact terms,
        resolved by the request's JSON-LD context, not bare full IRIs. Property
        predicates target their values directly; do not append .value merely
        because the entity representation contains a value member.
        Supply an operator-configured context_url or configure NGSI_LD_CONTEXT_URL;
        the server sends it as a Link header. Without that context, custom terms
        may resolve differently and match nothing. Full IRIs are valid for type
        and attrs. idPattern is a broker regex. No query is repaired or expanded
        by this server. Empty data with ok=true means no matches under the supplied
        type/context/filter; verify those before concluding no entities exist.
        Geo filters require georel, geometry and coordinates together, e.g. georel=
        'near;maxDistance==1000', geometry='Point', coordinates=[-3.7,40.4]. They use
        the default location GeoProperty. limit: 1..100; offset: nonnegative. Returns
        entities, count if supplied, and pagination; incomplete=true requires another
        page. Unknown has_more is null. Example: type='Sensor', q='temperature>20'.
        Broker validates q, regex and full geometry semantics; errors retain status.
        """
        params = {k: v for k, v in {'type': type, 'q': q, 'idPattern': idPattern, 'georel': georel, 'geometry': geometry}.items() if v is not None}
        if any(v == '' for v in params.values()):
            return failure('validation', 'Query strings must not be empty')
        for name, values in (('attrs', attrs), ('id', id)):
            if values is not None:
                if not values or any(not v or ',' in v for v in values):
                    return failure('validation', f'{name} must be a nonempty list without commas in items')
                if name == 'id' and any(not absolute_uri(v) for v in values):
                    return failure('validation', 'id entries must be absolute URIs')
                params[name] = ','.join(values)
        if any(v is not None for v in (georel, geometry, coordinates)):
            if any(v is None for v in (georel, geometry, coordinates)) or not coordinates:
                return failure('validation', 'georel, geometry and nonempty coordinates must be supplied together')
            try:
                params['coordinates'] = json.dumps(coordinates, allow_nan=False, separators=(',', ':'))
            except ValueError:
                return failure('validation', 'coordinates must be finite JSON numbers')
        return broker.page('/ngsi-ld/v1/entities', limit, offset, params=params, context_url=context_url, representation=representation)

    @mcp.tool(annotations={'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': False, 'openWorldHint': True})
    def create_entity(entity: dict[str, Any], context_url: str | None = None) -> Result:
        """Create exactly one normalized NGSI-LD entity; writes must be enabled.
        Requires id (absolute URI), type (term/IRI), and normalized attributes such as
        {'type':'Property','value':21} or {'type':'Relationship','object':'urn:room:1'}.
        Supply inline @context or a configured context_url for compact terms. Example:
        {'id':'urn:ngsi-ld:Sensor:9','type':'Sensor','temperature':{'type':'Property',
        'value':21},'@context':{'Sensor':'https://example.org/Sensor',
        'temperature':'https://example.org/temperature'}}. Returns broker status and
        Location; duplicates remain HTTP 409 and are never automatically updated.
        """
        if not broker.config.writes:
            return failure('read_only', 'Enable NGSI_LD_ENABLE_WRITES=true to create entities')
        try:
            if not isinstance(entity.get('id'), str) or not absolute_uri(entity['id']):
                raise ValueError('Entity id must be an absolute URI')
            if not isinstance(entity.get('type'), str) or not entity['type'].strip():
                raise ValueError('Entity type must be a nonempty term or IRI')
            validate_attributes({k: v for k, v in entity.items() if k not in ('id', 'type')})
        except ValueError as exc:
            return failure('validation', str(exc))
        return broker.request('POST', '/ngsi-ld/v1/entities', body=entity, context_url=context_url)

    @mcp.tool(annotations={'readOnlyHint': False, 'destructiveHint': True, 'idempotentHint': True, 'openWorldHint': True})
    def update_entity(entity_id: str, attributes: dict[str, Any], context_url: str | None = None) -> Result:
        """Update existing attributes using PATCH /entities/{id}/attrs; never creates
        an entity or appends missing attributes. Writes must be enabled. entity_id is
        an absolute URI. attributes contains normalized Property/Relationship/
        GeoProperty objects; no entity id/type. Inline @context is allowed. Example:
        entity_id='urn:ngsi-ld:Sensor:9', attributes={'temperature':{'type':'Property',
        'value':22}} with configured context_url. Replaces supplied attribute values;
        datasetId may identify an attribute instance. Broker validates remaining
        semantics. HTTP 207 is ok=false with partial results: some changes may have
        applied. HTTP 404 and all broker diagnostics are preserved. Read to verify.
        """
        if not broker.config.writes:
            return failure('read_only', 'Enable NGSI_LD_ENABLE_WRITES=true to update entities')
        try:
            if not absolute_uri(entity_id):
                raise ValueError('entity_id must be an absolute URI')
            if not attributes or set(attributes) == {'@context'}:
                raise ValueError('At least one attribute is required')
            validate_attributes(attributes)
        except ValueError as exc:
            return failure('validation', str(exc))
        return broker.request('PATCH', '/ngsi-ld/v1/entities/' + quote(entity_id, safe='') + '/attrs', body=attributes, context_url=context_url)

    return mcp


def main():
    parser = argparse.ArgumentParser(description='FIWARE NGSI-LD MCP server')
    parser.add_argument('--http', action='store_true', help='Use Streamable HTTP instead of STDIO')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    mcp = build_server()
    if args.http:
        mcp.run(transport='streamable-http', host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == '__main__':
    main()
