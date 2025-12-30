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


class InsufficientBalanceError(RuntimeError):
    """Raised when LLM API returns 402 Insufficient Balance."""
    pass


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


def chat_completion_text(cfg: LLMConfig, *, messages: list[dict[str, Any]], max_tokens: int = 8000) -> str:
    """Returns assistant text content. Raises Exception on error.
    
    Args:
        cfg: LLM configuration
        messages: Chat messages
        max_tokens: Maximum tokens for the response (default 8000, compatible with most APIs including DeepSeek's 8192 limit)
    """

    url = _chat_completions_url(cfg)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    payload = {
        "model": cfg.model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,  # Prevent truncation of long responses
    }

    # Optional logging for debugging long-running LLM calls.
    do_log = (os.getenv("QT_TEST_AI_LOG_REQUESTS") or "").strip() in {"1","true","yes"}
    if do_log:
        try:
            import datetime
            print(f"[LLM] request {datetime.datetime.now().isoformat()} url={url} model={cfg.model} messages={len(messages)} max_tokens={max_tokens}")
        except Exception:
            pass

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=cfg.timeout_s)
    if resp.status_code == 402:
        err = f"LLM请求失败: url={url} HTTP 402 Insufficient Balance (余额不足)"
        if do_log:
            print(f"[LLM] error: {err}")
        raise InsufficientBalanceError(err)

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


def parse_json_from_text(text: str):
    """
    Robustly extract and parse JSON from LLM output.
    Handles markdown code blocks and extra text before/after JSON.
    Returns python object or raises ValueError/JSONDecodeError on failure.
    """
    t = (text or "").strip()

    # Remove markdown code blocks - handle multiple formats
    # Pattern: ```json ... ``` or ``` ... ```
    import re
    code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)```', t, re.IGNORECASE)
    if code_block_match:
        t = code_block_match.group(1).strip()
    else:
        # Fallback: simple removal
        if t.startswith("```json"):
            t = t[7:]
        elif t.startswith("```"):
            t = t[3:]
        if t.endswith("```"):
            t = t[:-3]
        t = t.strip()

    # Find the first { or [ and extract balanced JSON
    start_idx = -1
    open_char = None
    close_char = None

    for i, c in enumerate(t):
        if c == '{':
            start_idx = i
            open_char, close_char = '{', '}'
            break
        elif c == '[':
            start_idx = i
            open_char, close_char = '[', ']'
            break

    if start_idx == -1:
        raise ValueError("No JSON object or array found in LLM response")

    depth = 0
    in_string = False
    escape_next = False
    end_idx = start_idx

    for i in range(start_idx, len(t)):
        c = t[i]

        if escape_next:
            escape_next = False
            continue

        if c == '\\':
            escape_next = True
            continue

        if c == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    json_str = t[start_idx:end_idx]
    
    # If extraction yielded empty or incomplete JSON (truncated response), try repair
    if not json_str or json_str == open_char or len(json_str) < 10:
        # Attempt to extract whatever JSON we have and indicate truncation
        remaining = t[start_idx:] if start_idx >= 0 else t
        raise ValueError(f"JSON appears truncated (no closing bracket found). depth={depth}, partial content length={len(remaining)}")
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Try to provide more context about where the error is
        error_context = json_str[max(0, e.pos - 50):e.pos + 50] if hasattr(e, 'pos') else json_str[:200]
        raise ValueError(f"JSON parse failed at position {getattr(e, 'pos', '?')}: {e.msg}. Context: {repr(error_context)}")


def chat_completion_json(cfg: LLMConfig, *, messages: list[dict[str, Any]], max_retries: int = 3, expect_type: type | tuple[type, ...] | None = None, max_tokens: int = 8000) -> Any:
    """
    Call the chat completion and attempt to parse a JSON object/array from the response.
    Retries up to `max_retries` times, appending a repair hint when parsing fails.
    Returns parsed Python object.
    
    Args:
        cfg: LLM configuration
        messages: Chat messages
        max_retries: Maximum number of retry attempts
        expect_type: Expected type of the parsed JSON (dict, list, or tuple of types)
        max_tokens: Maximum tokens for the response (default 8000, compatible with DeepSeek)
    """
    if max_retries < 1:
        max_retries = 1

    last_text = ""
    for attempt in range(1, max_retries + 1):
        last_text = chat_completion_text(cfg, messages=messages, max_tokens=max_tokens)
        try:
            parsed = parse_json_from_text(last_text)
            if expect_type and not isinstance(parsed, expect_type):
                raise ValueError(f"Parsed JSON is {type(parsed)}, expected {expect_type}")
            return parsed
        except Exception as e:
            # If final attempt, raise detailed error
            if attempt == max_retries:
                raise RuntimeError(f"Failed to obtain valid JSON after {max_retries} attempts: {e}\nLast response preview: {last_text[:2000]}")

            # Prepare repair hint: ask model to return only the JSON
            repair_msg = {
                "role": "user",
                "content": (
                    "上一次回复无法解析为合法 JSON。请只返回一个合法的 JSON 对象或数组，不要包含代码块标记或额外说明。"
                    " 如果上一次回复包含 JSON 片段，请修正并仅返回修正后的完整 JSON。\n\n上一次回复：\n" + last_text
                ),
            }
            # Append repair hint to original messages for next attempt
            messages = list(messages) + [repair_msg]

def generate_tests_with_llm(cfg: LLMConfig, *, prompt: str, system_prompt: str | None = None) -> str:
    """
    Generate test code using LLM.
    
    Args:
        cfg: LLM configuration
        prompt: The prompt for test generation
        system_prompt: Optional system prompt override
        
    Returns:
        Generated test code (extracted from code blocks if present)
    """
    import re
    
    if not system_prompt:
        system_prompt = (
            "你是一个精通Qt和C++的测试工程师。"
            "生成的代码应该是有效的Qt Test框架代码，完整且可以直接编译。"
            "请在```cpp和```之间返回代码。"
        )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    response = chat_completion_text(cfg, messages=messages)
    
    # Extract C++ code block if present
    code_blocks = re.findall(r'```(?:cpp|c\+\+)?\n(.*?)\n```', response, re.DOTALL)
    if code_blocks:
        return code_blocks[0].strip()
    
    return response.strip()