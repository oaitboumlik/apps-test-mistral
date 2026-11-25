from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from api.routers.api.v1 import chat as chat_module
from fastapi.testclient import TestClient
from utils.mistral import MistralNotConfiguredError

from conftest import build_app


def _reply(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = build_app()

    def fake_client() -> object:
        class Chat:
            async def complete_async(self, **kwargs: object) -> SimpleNamespace:
                assert kwargs["model"] == chat_module.CHAT_MODEL
                assert isinstance(kwargs["messages"], list)
                return _reply("Hello there.")

        return SimpleNamespace(chat=Chat())

    monkeypatch.setattr(chat_module, "caller_mistral_client", fake_client)
    return TestClient(app)


def test_chat_replies_with_the_model_response(client: TestClient) -> None:
    res = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert res.status_code == 200
    assert res.json() == {"content": "Hello there."}


@pytest.mark.parametrize(
    "body",
    [
        {"messages": []},
        {"messages": [{"role": "bogus", "content": "hi"}]},
        {"messages": [{"role": "user", "content": ""}]},
        {},
    ],
)
def test_chat_refuses_an_invalid_body(client: TestClient, body: dict) -> None:
    res = client.post("/api/v1/chat", json=body)

    assert res.status_code == 422


def test_chat_maps_a_missing_credential_to_a_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_client() -> object:
        raise MistralNotConfiguredError("no credential")

    monkeypatch.setattr(chat_module, "caller_mistral_client", no_client)
    res = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert res.status_code == 503
