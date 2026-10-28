"""Regression checks for strict, repeatable fixture loading."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from examples.demo import entities, populate


class FixtureClient:
    def __init__(self, status, *, mismatch=False):
        self.status = status
        self.mismatch = mismatch
        self.stored = {entity['id']: entity for entity in entities()}
        self.reads = 0

    async def call_tool(self, name, arguments):
        if name == 'create_entity':
            data = {'ok': self.status == 201, 'status': self.status}
        else:
            self.reads += 1
            entity = deepcopy(self.stored[arguments['entity_id']])
            if self.mismatch:
                entity['name']['value'] = 'unexpected existing entity'
            data = {'ok': True, 'status': 200, 'data': entity}
        return SimpleNamespace(is_error=False, structured_content=data)


@pytest.mark.parametrize('status', [201, 409])
def test_loader_verifies_each_created_or_existing_entity(status):
    client = FixtureClient(status)
    counts = asyncio.run(populate(client))
    assert counts == {'inserted': 9 if status == 201 else 0,
                      'existing': 9 if status == 409 else 0, 'verified': 9}
    assert client.reads == 9


@pytest.mark.parametrize('status', [400, 500])
def test_loader_does_not_ignore_broker_failure(status):
    with pytest.raises(RuntimeError):
        asyncio.run(populate(FixtureClient(status)))


def test_loader_rejects_conflicting_existing_entity():
    with pytest.raises(RuntimeError, match='expected.*Building 1'):
        asyncio.run(populate(FixtureClient(409, mismatch=True)))
