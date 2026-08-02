"""Model backends. Stdlib only — no pip installs needed.

Supported providers:
  anthropic   — needs ANTHROPIC_API_KEY
  openrouter  — needs OPENROUTER_API_KEY
  ollama      — needs a local Ollama server (OLLAMA_HOST, default http://localhost:11434)
  mock        — no network; simulates a model with controllable sloppiness (see mock.py)
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

RETRIES = 3
TIMEOUT = 180


class ProviderError(RuntimeError):
    pass


def _post_json(url: str, headers: dict, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            if e.code in (429, 500, 502, 503, 529) and attempt < RETRIES - 1:
                time.sleep(2 ** (attempt + 1))
                last_err = ProviderError(f"HTTP {e.code}: {detail}")
                continue
            raise ProviderError(f"HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < RETRIES - 1:
                time.sleep(2 ** (attempt + 1))
                last_err = e
                continue
            raise ProviderError(str(e)) from e
    raise ProviderError(str(last_err))


def _require_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise ProviderError(f"{name} is not set. `export {name}=...` and retry.")
    return val


def call_anthropic(model: str, system: str, user: str) -> str:
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": _require_env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
        {
            "model": model,
            "max_tokens": 1024,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
    )
    return "".join(b.get("text", "") for b in data.get("content", []))


def call_openrouter(model: str, system: str, user: str) -> str:
    data = _post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        {"Authorization": f"Bearer {_require_env('OPENROUTER_API_KEY')}"},
        {
            "model": model,
            "temperature": 0,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as e:
        raise ProviderError(f"Unexpected OpenRouter response: {json.dumps(data)[:400]}") from e


def call_ollama(model: str, system: str, user: str) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    data = _post_json(
        f"{host}/api/chat",
        {},
        {
            "model": model,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 8192},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    return data.get("message", {}).get("content", "")


CALLERS = {
    "anthropic": call_anthropic,
    "openrouter": call_openrouter,
    "ollama": call_ollama,
}
