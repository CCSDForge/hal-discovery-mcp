"""
Fixtures partagées pour mocker les appels HTTP sortants (aiohttp/httpx) sans
dépendre de l'API HAL réelle ni de bibliothèques de mock HTTP supplémentaires.

`fake_aiohttp` patche `aiohttp.ClientSession` pour tout le module appelant
`async with aiohttp.ClientSession(...) as session:` puis `session.get(...)`.
`fake_httpx` fait de même pour `httpx.AsyncClient`.
"""

import json

import pytest


class FakeAiohttpResponse:
    def __init__(
        self,
        status=200,
        json_data=None,
        text_data=None,
        url="http://example.test/",
        json_exc=None,
    ):
        self.status = status
        self.url = url
        self.headers = {}
        self._json_data = {} if json_data is None else json_data
        self._text_data = text_data if text_data is not None else json.dumps(self._json_data)
        self._json_exc = json_exc

    async def json(self, content_type=None):
        if self._json_exc is not None:
            raise self._json_exc
        return self._json_data

    async def text(self):
        return self._text_data

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP error {self.status}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeAiohttpSession:
    def __init__(self, response, raise_on_enter=None):
        self.response = response
        self.calls = []
        self._raise_on_enter = raise_on_enter

    def get(self, url, params=None, **kwargs):
        self.calls.append({"url": url, "params": params})
        return self.response

    async def __aenter__(self):
        if self._raise_on_enter is not None:
            raise self._raise_on_enter
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeHttpxResponse:
    def __init__(self, status_code=200, json_data=None, url="http://example.test/"):
        self.status_code = status_code
        self.url = url
        self._json_data = {} if json_data is None else json_data

    def json(self):
        return self._json_data


class FakeHttpxAsyncClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def get(self, url, params=None, **kwargs):
        self.calls.append({"url": url, "params": params})
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def fake_aiohttp(monkeypatch):
    """
    Factory `make(raise_on_enter=None, **response_kwargs)` : patche
    `aiohttp.ClientSession` et renvoie la session fake créée (utile pour
    inspecter `session.calls`, la liste des `{"url", "params"}` envoyés).

    `raise_on_enter` : exception levée à l'entrée du `async with`, pour
    simuler une panne réseau (ex. `aiohttp.ClientError`).
    `**response_kwargs` : voir `FakeAiohttpResponse`.
    """

    def make(raise_on_enter=None, **response_kwargs):
        response = None if raise_on_enter is not None else FakeAiohttpResponse(**response_kwargs)
        session = FakeAiohttpSession(response, raise_on_enter=raise_on_enter)
        monkeypatch.setattr("aiohttp.ClientSession", lambda *a, **kw: session)
        return session

    return make


@pytest.fixture
def fake_httpx(monkeypatch):
    """
    Factory `make(**response_kwargs)` : patche `httpx.AsyncClient` et
    renvoie le client fake créé (utile pour inspecter `client.calls`).
    """

    def make(**response_kwargs):
        response = FakeHttpxResponse(**response_kwargs)
        client = FakeHttpxAsyncClient(response)
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: client)
        return client

    return make
