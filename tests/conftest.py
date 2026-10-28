"""HTTP access independent of the production broker wrapper for live assertions."""
import json
import os

import httpx
import pytest

from examples.demo import CONTEXT_URL


@pytest.fixture
def raw_broker():
    if os.getenv('FIWARE_INTEGRATION') != '1':
        pytest.skip('Set FIWARE_INTEGRATION=1 with Compose broker running')
    headers = json.loads(os.getenv('NGSI_LD_HEADERS', '{}'))
    headers['Accept'] = 'application/ld+json'
    def add_context(request):
        if request.headers.get('Content-Type') != 'application/ld+json':
            request.headers['Link'] = f'<{CONTEXT_URL}>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
    with httpx.Client(base_url=os.getenv('NGSI_LD_BROKER_URL', 'http://localhost:1026').rstrip('/') + '/',
                      headers=headers, timeout=10, trust_env=False, follow_redirects=False,
                      event_hooks={'request': [add_context]}) as client:
        yield client
