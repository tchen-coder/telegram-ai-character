import asyncio
import logging
import inspect
from typing import Optional

from openai import AsyncOpenAI

from app.config import get_settings

try:
    from xai_sdk import Client as XAIClient
    from xai_sdk.chat import system
    from xai_sdk.chat import user
except ImportError as exc:
    XAIClient = None
    system = None
    user = None
    XAI_SDK_IMPORT_ERROR = exc
else:
    XAI_SDK_IMPORT_ERROR = None

logger = logging.getLogger(__name__)


class GenerationLayer:
    """生成层：调用通用 LLM 接口生成回复内容"""

    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None
        self.grok_client = None
        self.grok_http_client: Optional[AsyncOpenAI] = None

    async def init(self):
        settings = get_settings()
        if settings.llm_provider == "grok":
            if XAIClient is None:
                raise RuntimeError(
                    "LLM_PROVIDER=grok requires the official xai-sdk. "
                    "Use Python 3.10+ and reinstall dependencies before starting the app."
                ) from XAI_SDK_IMPORT_ERROR

            if settings.llm_base_url:
                logger.info(
                    "LLM_PROVIDER=grok is using the official xai-sdk; "
                    "LLM_BASE_URL=%s will be ignored.",
                    settings.llm_base_url,
                )

            self.client = None
            self.grok_client = XAIClient(
                api_key=settings.resolved_llm_api_key,
                timeout=60.0,
            )
            self.grok_http_client = AsyncOpenAI(
                api_key=settings.resolved_llm_api_key,
                base_url="https://api.x.ai/v1",
                timeout=60.0,
            )
            return

        client_kwargs = {"api_key": settings.resolved_llm_api_key}
        if settings.resolved_llm_base_url:
            client_kwargs["base_url"] = settings.resolved_llm_base_url
        self.client = AsyncOpenAI(**client_kwargs)
        self.grok_client = None
        self.grok_http_client = None

    async def close(self):
        if self.client is not None:
            await self.client.close()
            self.client = None
        if self.grok_http_client is not None:
            await self.grok_http_client.close()
            self.grok_http_client = None
        if self.grok_client is not None:
            close = getattr(self.grok_client, "close", None)
            if close is not None:
                maybe_awaitable = close()
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
            self.grok_client = None

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """调用模型生成回复"""
        settings = get_settings()
        if settings.llm_provider == "grok":
            if self.grok_client is None:
                await self.init()
            try:
                return await self._generate_with_grok_sdk(system_prompt, user_prompt)
            except Exception as exc:
                if not self._should_fallback_to_grok_http(exc):
                    raise
                logger.warning(
                    "Grok xai-sdk request failed, falling back to xAI HTTP API: %s",
                    exc,
                )
                return await self._generate_with_grok_http(system_prompt, user_prompt)

        if self.client is None:
            await self.init()

        response = await self.client.chat.completions.create(
            model=settings.resolved_llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned empty content")
        return content

    async def _generate_with_grok_sdk(
        self, system_prompt: str, user_prompt: str
    ) -> str:
        return await asyncio.to_thread(
            self._sample_grok_response,
            system_prompt,
            user_prompt,
        )

    def _sample_grok_response(self, system_prompt: str, user_prompt: str) -> str:
        settings = get_settings()
        chat = self.grok_client.chat.create(model=settings.resolved_llm_model)
        chat.append(system(system_prompt))
        chat.append(user(user_prompt))

        response = chat.sample()
        content = getattr(response, "content", None)
        if content:
            return content.strip()
        raise ValueError("Grok SDK response did not contain content")

    async def _generate_with_grok_http(
        self, system_prompt: str, user_prompt: str
    ) -> str:
        settings = get_settings()
        response = await self.grok_http_client.chat.completions.create(
            model=settings.resolved_llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )

        content = response.choices[0].message.content
        if content:
            return content.strip()
        raise ValueError("Grok HTTP response did not contain output text")

    def _should_fallback_to_grok_http(self, exc: Exception) -> bool:
        exc_text = str(exc)
        exc_type = type(exc)
        exc_module = getattr(exc_type, "__module__", "")
        exc_name = getattr(exc_type, "__name__", "")
        return (
            exc_module.startswith("grpc")
            or "http2 header with status: 403" in exc_text
            or "StatusCode.PERMISSION_DENIED" in exc_text
            or "StatusCode.UNAVAILABLE" in exc_text
            or exc_name in {"_InactiveRpcError", "AioRpcError"}
        )


generation_layer = GenerationLayer()
