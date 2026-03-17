import asyncio
from unittest.mock import Mock

from app.generation import GenerationLayer
from app.telegram_request import ConfigurableHTTPXRequest


class DummySettings:
    llm_provider = "grok"
    llm_api_key = None
    xai_api_key = "test-key"
    llm_base_url = "https://api.x.ai/v1"
    llm_model = "grok-4-1-fast-reasoning"
    llm_temperature = 0.7
    llm_max_tokens = 256
    telegram_proxy = None

    @property
    def resolved_llm_api_key(self) -> str:
        return self.xai_api_key

    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model


def test_httpx_request_disables_env_proxy_without_explicit_proxy() -> None:
    request = ConfigurableHTTPXRequest(connection_pool_size=1)
    client = request._build_client()
    try:
        assert client._trust_env is False
    finally:
        asyncio.run(client.aclose())


def test_grok_requires_official_xai_sdk(monkeypatch) -> None:
    monkeypatch.setattr("app.generation.get_settings", lambda: DummySettings())
    monkeypatch.setattr("app.generation.XAIClient", None)

    layer = GenerationLayer()

    try:
        asyncio.run(layer.init())
    except RuntimeError as exc:
        assert "official xai-sdk" in str(exc)
    else:
        raise AssertionError("Expected Grok init to require xai-sdk")


def test_grok_generate_uses_sdk_only(monkeypatch) -> None:
    monkeypatch.setattr("app.generation.get_settings", lambda: DummySettings())

    fake_chat = Mock()
    fake_response = type("FakeResponse", (), {"content": " hello "})()
    fake_client = type("FakeClient", (), {"chat": type("FakeChatAPI", (), {})()})()

    fake_client.chat.create = lambda **_: fake_chat
    fake_chat.sample = Mock(return_value=fake_response)

    monkeypatch.setattr("app.generation.XAIClient", lambda **_: fake_client)
    monkeypatch.setattr("app.generation.system", lambda content: ("system", content))
    monkeypatch.setattr("app.generation.user", lambda content: ("user", content))

    layer = GenerationLayer()
    result = asyncio.run(layer.generate("sys", "usr"))

    assert result == "hello"
    assert fake_chat.append.call_count == 2
