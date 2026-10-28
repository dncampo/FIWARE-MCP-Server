"""Wait up to 60 seconds for the configured demonstration broker."""
import os
import time

import httpx

url = os.getenv('NGSI_LD_BROKER_URL', 'http://localhost:1026').rstrip('/')
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            response = client.get(url + '/ngsi-ld/v1/types', params={'limit': 1})
            if response.is_success:
                print('Broker is ready')
                break
    except httpx.RequestError:
        pass
    time.sleep(1)
else:
    raise SystemExit('Broker did not become ready within 60 seconds; inspect docker compose logs orion mongo')
