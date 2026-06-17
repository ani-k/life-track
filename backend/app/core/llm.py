"""
LLM abstraction layer built on LiteLLM.

Provider routing:
  LLMClient(settings)                          → cloud (litellm_model)
  LLMClient.for_ollama(settings)               → local Ollama
  LLMClient.for_provider("local", settings)    → convenience dispatcher

Structured output strategy:
  OpenAI/Azure  → response_format=json_object (native JSON mode)
  Others        → schema injected into user message; Pydantic validates

Tool calling strategy:
  OpenAI/Azure  → native tools param (chat_with_tools)
  Others        → raise NotImplementedError (caller uses chat_structured fallback)
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Literal, TypeVar

from litellm import acompletion
from pydantic import BaseModel

from app.core.config import Settings, get_settings

log = logging.getLogger(__name__)
M = TypeVar("M", bound=BaseModel)
Provider = Literal["cloud", "local"]


class LLMResponse:
    def __init__(self, content: str, tokens_used: int, model: str) -> None:
        self.content = content
        self.tokens_used = tokens_used
        self.model = model

    def __repr__(self) -> str:
        return f"<LLMResponse model={self.model} tokens={self.tokens_used}>"


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.litellm_model
        self._temperature = settings.litellm_temperature
        self._max_tokens = settings.litellm_max_tokens
        self._max_retries = settings.litellm_max_retries
        self._extra: dict = {}
        # Resolve API Base
        api_base = settings.openai_api_base or settings.litellm_api_base
        if api_base:
            self._extra["api_base"] = api_base
            
        # Resolve API Key
        api_key = settings.openai_api_key or settings.litellm_api_key
        if api_key:
            self._extra["api_key"] = api_key

        # Если задан сторонний api_base (прокси) и у модели нет явного префикса провайдера,
        # автоматически префиксируем её как openai/... чтобы LiteLLM понимал протокол.
        if api_base and not any(self._model.startswith(p) for p in ("openai/", "ollama/", "anthropic/", "azure/", "gpt-")):
            self._model = f"openai/{self._model}"

    # ── Provider factories ────────────────────────────────────────────

    @classmethod
    def for_ollama(cls, settings: Settings, model: str | None = None) -> "LLMClient":
        instance = cls.__new__(cls)
        instance._model = f"ollama/{model or settings.ollama_model}"
        instance._temperature = settings.litellm_temperature
        instance._max_tokens = settings.litellm_max_tokens
        instance._max_retries = settings.litellm_max_retries
        instance._extra = {}
        if settings.ollama_base_url != "http://localhost:11434":
            instance._extra["api_base"] = settings.ollama_base_url
        return instance

    @classmethod
    def for_provider(
        cls, provider: Provider, settings: Settings, model: str | None = None
    ) -> "LLMClient":
        if provider == "local":
            return cls.for_ollama(settings, model=model)
        return cls(settings)

    # ── Capability detection ──────────────────────────────────────────

    def _supports_json_mode(self) -> bool:
        return any(self._model.startswith(p) for p in ("gpt-", "openai/", "azure/"))

    def _supports_tool_calling(self) -> bool:
        """Same providers that support JSON mode support native tool calling."""
        return self._supports_json_mode()

    # ── Internals ─────────────────────────────────────────────────────

    def _build_kwargs(self, **overrides: object) -> dict:
        return {
            "model": self._model,
            "temperature": overrides.pop("temperature", self._temperature),
            "max_tokens": overrides.pop("max_tokens", self._max_tokens),
            "num_retries": overrides.pop("num_retries", self._max_retries),
            **self._extra,
            **overrides,
        }

    @staticmethod
    def _extract_tokens(response: object) -> int:
        try:
            return response.usage.total_tokens  # type: ignore[union-attr]
        except AttributeError:
            return 0

    # ── Public API ────────────────────────────────────────────────────

    async def chat(self, messages: list[dict], **overrides: object) -> LLMResponse:
        kwargs = self._build_kwargs(**overrides)
        response = await acompletion(messages=messages, **kwargs)
        content: str = response.choices[0].message.content or ""
        return LLMResponse(content, self._extract_tokens(response), self._model)

    async def chat_structured(
        self, messages: list[dict], schema: type[M], **overrides: object
    ) -> M:
        """Structured output — OpenAI JSON mode OR schema-injected prompting."""
        if self._supports_json_mode():
            kwargs = self._build_kwargs(
                response_format={"type": "json_object"}, **overrides
            )
            response = await acompletion(messages=messages, **kwargs)
            raw = response.choices[0].message.content or "{}"
        else:
            schema_block = (
                "\n\n---\nRespond with ONLY a valid JSON object matching this schema "
                "(no markdown, no explanation):\n"
                + json.dumps(schema.model_json_schema(), indent=2)
            )
            patched = list(messages)
            last = patched[-1]
            patched[-1] = {**last, "content": last["content"] + schema_block}
            kwargs = self._build_kwargs(**overrides)
            response = await acompletion(messages=patched, **kwargs)
            raw = response.choices[0].message.content or "{}"

        log.debug("LLM structured tokens=%d schema=%s", self._extract_tokens(response), schema.__name__)
        return schema.model_validate_json(raw)

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> tuple[str, list[dict], list[object], int]:
        """
        Native tool calling — OpenAI/Azure only.

        Returns (text_reply, parsed_calls, raw_tool_calls_for_history, tokens_used).
        parsed_calls: [{"name": str, "arguments": dict, "call_id": str}]
        raw_tool_calls_for_history: kept for the follow-up message round.

        Raises NotImplementedError for non-OpenAI providers — caller should
        fall back to chat_structured with OrchestratorOutput.
        """
        if not self._supports_tool_calling():
            raise NotImplementedError(
                f"Native tool calling not supported for {self._model!r}. "
                "Use chat_structured with OrchestratorOutput instead."
            )

        kwargs = self._build_kwargs(tools=tools, tool_choice="auto")
        response = await acompletion(messages=messages, **kwargs)
        msg = response.choices[0].message
        tokens = self._extract_tokens(response)

        parsed: list[dict] = []
        raw: list[object] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                parsed.append({
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                    "call_id": tc.id,
                })
                raw.append(tc)

        log.debug(
            "LLM tools — model=%s calls=%d tokens=%d", self._model, len(parsed), tokens
        )
        return msg.content or "", parsed, raw, tokens

    async def stream(self, messages: list[dict], **overrides: object) -> AsyncIterator[str]:
        kwargs = self._build_kwargs(stream=True, **overrides)
        response = await acompletion(messages=messages, **kwargs)
        async for chunk in response:
            delta: str | None = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── Singleton ─────────────────────────────────────────────────────────────────

_client: LLMClient | None = None


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    global _client
    if settings is not None:
        return LLMClient(settings)
    if _client is None:
        _client = LLMClient(get_settings())
    return _client
