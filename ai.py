import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from sanitize_json_newlines import sanitize_json_newlines

# provider_id -> display label, backend kind, default model, optional base_url for chat APIs
PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "gemini_flash": {
        "label": "Google Gemini (Flash)",
        "kind": "gemini",
        "default_model": "gemini-2.0-flash",
    },
    "gemini_pro": {
        "label": "Google Gemini (Pro)",
        "kind": "gemini",
        "default_model": "gemini-1.5-pro",
    },
    "openai": {
        "label": "OpenAI (Chat API)",
        "kind": "openai_compatible",
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1/chat/completions",
    },
    "groq": {
        "label": "Groq (OpenAI-compatible)",
        "kind": "openai_compatible",
        "default_model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
    },
    # Same request format as OpenAI; paste key from https://openrouter.ai/keys
    "openrouter": {
        "label": "OpenRouter (OpenAI-compatible)",
        "kind": "openai_compatible",
        "default_model": "openai/gpt-4o-mini",
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "extra_headers": {
            "HTTP-Referer": "https://github.com/",
            "X-Title": "Quiz helper",
        },
    },
}

GEMINI_BASE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def list_provider_ids():
    return list(PROVIDER_PRESETS.keys())


def provider_label(provider_id: str) -> str:
    return PROVIDER_PRESETS.get(provider_id, {}).get("label", provider_id)


def is_quota_or_rate_limit_error(message: Optional[str]) -> bool:
    """True if the error is likely throttling / quota (skip extra API calls)."""
    if not message:
        return False
    m = message.lower()
    return (
        "429" in m
        or "rate limit" in m
        or "too many requests" in m
        or "resource exhausted" in m
    )


def _effective_model(provider_id: str, model_override: str) -> str:
    preset = PROVIDER_PRESETS.get(provider_id) or PROVIDER_PRESETS["gemini_flash"]
    trimmed = (model_override or "").strip()
    return trimmed or preset["default_model"]


def _extract_gemini_text(result: Dict) -> str:
    try:
        parts = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])
        )
        chunks = []
        for p in parts:
            if isinstance(p, dict) and "text" in p:
                chunks.append(p["text"])
        return "".join(chunks).strip()
    except (IndexError, TypeError, KeyError):
        return ""


def _friendly_http_error(kind: str, status_code: int, body: str) -> str:
    message = ""
    if body:
        try:
            data = json.loads(body)
            err = data.get("error")
            if isinstance(err, dict):
                message = (err.get("message") or "") or ""
            elif isinstance(err, str):
                message = err
        except json.JSONDecodeError:
            message = body.strip()

    snippet = (message[:400] + ("…" if len(message) > 400 else "")) if message else "(no detail)"

    if status_code == 429:
        return (
            "Rate limited (429): the provider is throttling requests for this key or model.\n"
            "Try: turn off “Two-step prompting” (one request per F8), wait 1–2 minutes, "
            "switch model (e.g. Gemini Pro), or use Groq/OpenAI.\n\n"
            f"Detail: {snippet}"
        )
    return f"{kind} HTTP {status_code}: {snippet}"


def _post_gemini(
    api_key: str,
    model: str,
    prompt_text: str,
) -> Tuple[Optional[Dict], Optional[str]]:
    if not api_key:
        return None, "API key is missing."

    url = GEMINI_BASE.format(model=model)

    for attempt in range(2):
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                params={"key": api_key},
                json={
                    "contents": [
                        {"parts": [{"text": prompt_text}]},
                    ]
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json(), None
        except requests.HTTPError as e:
            code = e.response.status_code if e.response else 0
            body = e.response.text if e.response is not None else ""
            print(f"Gemini HTTP error: {code} {e.response.reason if e.response else ''}")
            if body:
                print(f"Gemini error body: {body}")
            err_msg = _friendly_http_error("Gemini", code, body)
            if code == 429 and attempt == 0:
                time.sleep(2.5)
                continue
            return None, err_msg
        except requests.RequestException as e:
            print(f"Gemini request error: {e}")
            return None, f"Network error: {e}"

    return None, "Gemini: too many requests after retry."


def _post_openai_compatible(
    api_key: str,
    base_url: str,
    model: str,
    prompt_text: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    if not api_key:
        return None, "API key is missing."

    for attempt in range(2):
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            if extra_headers:
                headers.update(extra_headers)
            response = requests.post(
                base_url,
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt_text}],
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json(), None
        except requests.HTTPError as e:
            code = e.response.status_code if e.response else 0
            body = e.response.text if e.response is not None else ""
            print(f"Chat API HTTP error: {code} {e.response.reason if e.response else ''}")
            if body:
                print(f"Chat API error body: {body}")
            err_msg = _friendly_http_error("Chat API", code, body)
            if code == 429 and attempt == 0:
                time.sleep(2.5)
                continue
            return None, err_msg
        except requests.RequestException as e:
            print(f"Chat API request error: {e}")
            return None, f"Network error: {e}"

    return None, "Chat API: too many requests after retry."


def _extract_chat_text(result: Dict) -> str:
    try:
        return (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
    except (IndexError, TypeError, AttributeError):
        return ""


def _completion_request(
    provider_id: str,
    api_key: str,
    model: str,
    prompt_text: str,
) -> Tuple[Optional[str], Optional[str]]:
    preset = PROVIDER_PRESETS.get(provider_id) or PROVIDER_PRESETS["gemini_flash"]
    kind = preset["kind"]

    if kind == "gemini":
        raw, err = _post_gemini(api_key, model, prompt_text)
        if err:
            return None, err
        return _extract_gemini_text(raw), None

    if kind == "openai_compatible":
        base_url = preset.get("base_url", "https://api.openai.com/v1/chat/completions")
        extra = preset.get("extra_headers") if isinstance(preset.get("extra_headers"), dict) else None
        raw, err = _post_openai_compatible(api_key, base_url, model, prompt_text, extra_headers=extra)
        if err:
            return None, err
        return _extract_chat_text(raw), None

    return None, f"Unknown provider kind: {kind}"


def build_prompt_generator_user_text(question: str, options: List[str]) -> str:
    opts = "\n".join(f"- {opt}" for opt in options)
    return f"""You are a prompt engineer designed to enhance AI answering accuracy.

Given a single multiple-choice question, analyze it and return a custom prompt that helps another AI answer correctly. Your output must help the answering model think logically, avoid common traps, and apply the right reasoning strategy.

Your output must include:

1. **Question Type** (e.g. factual, logic, riddle, math, IQ pattern, geography, history, etc.)
2. **Knowledge Domain** (e.g. mathematics, language, computer science, general knowledge, logic, etc.)
3. **Instructional Prompt**: A concise and effective instruction tailored to the question type and domain.
4. **Filtered Options**: After careful analysis, eliminate up to 2 obviously wrong options (never more than 2). Return the remaining options in a list as "filtered_options".

Respond in the following JSON format:

{{
  "question_type": "...",
  "domain": "...",
  "instructional_prompt": "...",
  "filtered_options": ["...", "...", ...]
}}

Question: {question}
Options:
{opts}
"""


def _parse_json_object_from_text(content: str) -> Optional[Dict]:
    json_matches = re.findall(r"\{[\s\S]*\}", content)
    for json_str in json_matches:
        try:
            sanitized = sanitize_json_newlines(json_str)
            return json.loads(sanitized)
        except Exception as e:
            print("JSON parsing error:", e)
    return None


def generate_prompt(
    question: str, options: List[str], ctx: Dict[str, Any]
) -> Tuple[Optional[dict], Optional[str]]:
    provider_id = ctx.get("provider_id") or "gemini_flash"
    api_key = (ctx.get("api_key") or "").strip()
    model = _effective_model(provider_id, ctx.get("model") or "")
    prompt_text = build_prompt_generator_user_text(question, options)

    try:
        content, api_err = _completion_request(
            provider_id, api_key, model, prompt_text
        )
        if api_err:
            return None, api_err
        if not (content or "").strip():
            return None, "Empty response from the prompt-generator API call."

        parsed = _parse_json_object_from_text(content)
        if parsed:
            return parsed, None

        print("No valid JSON object found in prompt generator response. Raw:")
        print(content[:2000])
        return {
            "question_type": "general",
            "domain": "general knowledge",
            "instructional_prompt": (
                "Carefully analyze the question and select the most accurate answer "
                "from the given options."
            ),
        }, None
    except Exception as e:
        print(f"Prompt Generator Error: {e}")
        return None, str(e)


def build_answer_user_text(question: str, options: List[str], enhanced_prompt) -> str:
    opts = "\n".join(f"- {opt}" for opt in options)
    if enhanced_prompt:
        instruct = enhanced_prompt.get("instructional_prompt", "")
        qt = enhanced_prompt.get("question_type", "")
        dom = enhanced_prompt.get("domain", "")
        filtered = enhanced_prompt.get("filtered_options")
        extra = ""
        if isinstance(filtered, list) and filtered:
            extra = (
                "\nFiltered options (focus on these if listed):\n"
                + "\n".join(f"- {x}" for x in filtered)
            )
        return f"""{instruct}

Question Type: {qt}
Domain: {dom}
{extra}

Question: {question}
Options:
{opts}

Debate, test, and deduct between the remaining options. Based on the above analysis,
provide ONLY the correct answer from the given options (no explanation, just the answer text)."""

    return f"""You are a multiple choice question solver. Reply ONLY with the option text that is the correct answer (no explanation).

Question: {question}
Options:
{opts}
"""


def get_ai_answer(
    question: str,
    options: List[str],
    enhanced_prompt,
    ctx: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str]]:
    provider_id = ctx.get("provider_id") or "gemini_flash"
    api_key = (ctx.get("api_key") or "").strip()
    model = _effective_model(provider_id, ctx.get("model") or "")
    prompt = build_answer_user_text(question, options, enhanced_prompt)

    try:
        answer, api_err = _completion_request(provider_id, api_key, model, prompt)
        if api_err:
            return None, api_err
        if not answer:
            return None, "Model returned an empty answer."

        lower = answer.lower()
        for option in options:
            if option.lower() in lower:
                return option, None
        lines = answer.split("\n")
        first = lines[0].strip() if lines else ""
        return (first or None), None
    except Exception as e:
        print(f"Answering AI Error: {e}")
        return None, str(e)
