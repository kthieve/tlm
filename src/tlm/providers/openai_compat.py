"""OpenAI-compatible /v1/chat/completions (httpx)."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "chutes": "https://llm.chutes.ai/v1",
    "nano-gpt": "https://nano-gpt.com/api/v1",
}

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "openrouter": "openai/gpt-4o-mini",
    "chutes": "meta-llama/Llama-3.3-70B-Instruct",
    "nano-gpt": "gpt-4o-mini",
}


def _count_tokens_heuristic(text: str) -> int:
    return max(1, len(text) // 4)


def count_tokens_text(text: str) -> int:
    try:
        import tiktoken  # type: ignore[import-not-found]

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return _count_tokens_heuristic(text)


@dataclass
class OpenAICompatProvider:
    id: str
    base_url: str
    api_key: str
    model: str
    timeout: float = 120.0
    temperature: float = 0.7

    def _url(self) -> str:
        b = self.base_url.rstrip("/")
        return f"{b}/chat/completions"

    def _headers(self) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.id == "openrouter":
            h["HTTP-Referer"] = "https://github.com/tlm-cli/tlm"
            h["X-Title"] = "tlm"
        return h

    def _messages(self, prompt: str, *, system: str | None) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        if system:
            out.append({"role": "system", "content": system})
        out.append({"role": "user", "content": prompt})
        return out

    def _payload_messages(self, messages: list[dict[str, str]], *, system: str | None) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        if system:
            out.append({"role": "system", "content": system})
        out.extend(messages)
        return out

    def count_tokens(self, text: str) -> int:
        return count_tokens_text(text)

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._payload_messages(messages, system=system),
            "temperature": self.temperature,
            "stream": False,
        }
        data = self._request_json(body)
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"unexpected API response: {data!r}") from e

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        return self.chat([{"role": "user", "content": prompt}], system=system)

    def stream(self, prompt: str, *, system: str | None = None) -> Iterator[str]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(prompt, system=system),
            "temperature": self.temperature,
            "stream": True,
        }
        yield from self._stream_sse(body)

    def _request_json(self, body: dict[str, Any]) -> dict[str, Any]:
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    r = client.post(self._url(), headers=self._headers(), json=body)
                    if r.status_code == 429 and attempt < 3:
                        time.sleep(0.5 * (2**attempt))
                        continue
                    if r.status_code in (401, 403):
                        raise RuntimeError("API authentication failed (check API key).") from None
                    r.raise_for_status()
                    return r.json()
            except httpx.HTTPStatusError as e:
                txt = e.response.text[:500] if e.response is not None else ""
                raise RuntimeError(f"HTTP {e.response.status_code if e.response else '?'}: {txt}") from e
            except httpx.RequestError as e:
                last_err = e
                if attempt < 3:
                    time.sleep(0.3 * (2**attempt))
                    continue
                raise RuntimeError(f"network error: {e}") from e
        if last_err is not None:
            raise RuntimeError(f"request failed: {last_err}")
        raise RuntimeError("rate limited (429) after retries")

    def _stream_sse(self, body: dict[str, Any]) -> Iterator[str]:
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", self._url(), headers=self._headers(), json=body) as r:
                if r.status_code in (401, 403):
                    raise RuntimeError("API authentication failed (check API key).")
                r.raise_for_status()
                for line in r.iter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    if not line:
                        continue
                    if line.startswith("data: "):
                        payload = line[6:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                            delta = chunk["choices"][0].get("delta") or {}
                            piece = delta.get("content")
                            if piece:
                                yield piece
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            continue
