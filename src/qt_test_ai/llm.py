from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str | None
    model: str
    timeout_s: float = 30.0


def load_llm_config_from_env() -> LLMConfig | None:
    """OpenAI-compatible config.

    Env:
      - QT_TEST_AI_LLM_BASE_URL (e.g. https://api.openai.com)
      - QT_TEST_AI_LLM_API_KEY  (optional for some local gateways)
      - QT_TEST_AI_LLM_MODEL    (e.g. gpt-4o-mini)
      - QT_TEST_AI_LLM_TIMEOUT_S (optional)
    """

    base_url = (os.getenv("QT_TEST_AI_LLM_BASE_URL") or "").strip()
    model = (os.getenv("QT_TEST_AI_LLM_MODEL") or "").strip()
    api_key = (os.getenv("QT_TEST_AI_LLM_API_KEY") or "").strip() or None
    timeout_raw = (os.getenv("QT_TEST_AI_LLM_TIMEOUT_S") or "").strip()

    if not base_url or not model:
        return None

    timeout_s = 30.0
    if timeout_raw:
        try:
            timeout_s = float(timeout_raw)
        except Exception:
            timeout_s = 30.0

    return LLMConfig(base_url=base_url, api_key=api_key, model=model, timeout_s=timeout_s)


def load_llm_system_prompt_from_env() -> str | None:
        """Optional override for system prompt.

        Env:
            - QT_TEST_AI_LLM_SYSTEM_PROMPT
        """

        p = (os.getenv("QT_TEST_AI_LLM_SYSTEM_PROMPT") or "").strip()
        return p or None


def _chat_completions_url(cfg: LLMConfig) -> str:
    base = cfg.base_url.rstrip("/")
    # 兼容用户把 BASE_URL 配成 ".../v1"（避免拼成 /v1/v1/...）
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def chat_completion_text(cfg: LLMConfig, *, messages: list[dict[str, Any]]) -> str:
    """Returns assistant text content. Raises Exception on error."""

    url = _chat_completions_url(cfg)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    payload = {
        "model": cfg.model,
        "messages": messages,
        "temperature": 0.2,
    }

    # Optional logging for debugging long-running LLM calls.
    do_log = (os.getenv("QT_TEST_AI_LOG_REQUESTS") or "").strip() in {"1","true","yes"}
    if do_log:
        try:
            import datetime
            print(f"[LLM] request {datetime.datetime.now().isoformat()} url={url} model={cfg.model} messages={len(messages)}")
        except Exception:
            pass

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=cfg.timeout_s)
    if resp.status_code >= 400:
        err = f"LLM请求失败: url={url} HTTP {resp.status_code} {resp.text[:500]}"
        if do_log:
            print(f"[LLM] error: {err}")
        raise RuntimeError(err)

    data = resp.json()
    if do_log:
        try:
            import datetime
            print(f"[LLM] response {datetime.datetime.now().isoformat()} keys={list(data.keys())}")
        except Exception:
            pass
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LLM返回缺少choices")

    msg = (choices[0].get("message") or {})
    content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM返回content为空")
    return content.strip()
