import httpx
from telegram.request import HTTPXRequest


class ConfigurableHTTPXRequest(HTTPXRequest):
    """仅使用显式配置的 Telegram 代理，避免系统代理污染 Bot 连接。"""

    def _build_client(self) -> httpx.AsyncClient:
        client_kwargs = dict(self._client_kwargs)
        has_explicit_proxy = bool(client_kwargs.get("proxies"))
        if not has_explicit_proxy:
            client_kwargs.pop("proxies", None)
        client_kwargs["trust_env"] = False
        return httpx.AsyncClient(**client_kwargs)
