"""
Fixture partagée pour mocker les appels HTTP sortants sans dépendre de l'API
HAL réelle ni de bibliothèques de mock HTTP supplémentaires.

Tous les appels passent par `hal_api.client.hal_get`, qui utilise
`httpx.AsyncClient` : `fake_httpx` le remplace par un client fake.
"""

import json

import pytest


class FakeHttpxResponse:
    def __init__(
        self,
        status_code=200,
        json_data=None,
        text_data=None,
        headers=None,
        url="http://example.test/",
    ):
        self.status_code = status_code
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = text_data if text_data is not None else json.dumps({} if json_data is None else json_data)

    def json(self):
        return json.loads(self.text)


class FakeHttpxAsyncClient:
    def __init__(self, responses, raise_on_get=None):
        self.responses = responses
        self.calls = []
        self._raise_on_get = raise_on_get

    async def get(self, url, params=None, **kwargs):
        self.calls.append({"url": url, "params": params})
        if self._raise_on_get is not None:
            raise self._raise_on_get
        # Une réponse par appel si plusieurs sont fournies, sinon toujours la même.
        index = min(len(self.calls), len(self.responses)) - 1
        return self.responses[index]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def fake_httpx(monkeypatch):
    """
    Factory `make(raise_on_get=None, responses=None, **response_kwargs)` :
    patche `httpx.AsyncClient` et renvoie le client fake créé (utile pour
    inspecter `client.calls`, la liste des `{"url", "params"}` envoyés).

    `raise_on_get` : exception levée par `get`, pour simuler une panne réseau.
    `responses` : liste de dicts de kwargs, une réponse par appel successif.
    `**response_kwargs` : voir `FakeHttpxResponse` (réponse unique).
    """

    def make(raise_on_get=None, responses=None, **response_kwargs):
        responses = [FakeHttpxResponse(**kw) for kw in (responses or [response_kwargs])]
        client = FakeHttpxAsyncClient(responses, raise_on_get=raise_on_get)
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: client)
        return client

    return make