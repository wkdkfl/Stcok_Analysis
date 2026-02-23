"""
Report Generator — LLM API wrapper for OpenAI, Anthropic, and Ollama.
"""

import ssl
import os
import requests
import httpx
from typing import Dict, List, Optional
from src.report.prompt_builder import build_analysis_prompt

# ── SSL workaround for corporate proxy / firewall ─────────
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass
os.environ["PYTHONHTTPSVERIFY"] = "0"


# ── Provider → Model options ─────────────────────────────────
PROVIDER_MODELS: Dict[str, List[str]] = {
    "OpenAI": ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano", "o3-mini", "gpt-5", "gpt-5-mini"],
    "Anthropic": ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"],
    "Ollama": ["llama3", "mistral", "gemma2", "phi3"],
}

PROVIDER_LIST = list(PROVIDER_MODELS.keys())


def generate_report(
    results: dict,
    provider: str,
    api_key: str,
    model: str,
    language: str = "ko",
    max_tokens: int = 2500,
    temperature: float = 0.4,
) -> str:
    """
    Generate an AI investment report from analysis results.

    Parameters
    ----------
    results : dict — output of run_analysis()
    provider : "OpenAI" | "Anthropic" | "Ollama"
    api_key : API key (empty string for Ollama)
    model : model name
    language : "ko" | "en"
    max_tokens : max response tokens
    temperature : sampling temperature

    Returns
    -------
    str — Markdown formatted report

    Raises
    ------
    ValueError — on configuration errors
    RuntimeError — on API call failures
    """
    system_prompt, user_prompt = build_analysis_prompt(results, language)

    if provider == "OpenAI":
        if not api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다. .env 파일 또는 사이드바에서 입력하세요.")
        return _call_openai(system_prompt, user_prompt, api_key, model, max_tokens, temperature)

    elif provider == "Anthropic":
        if not api_key:
            raise ValueError("Anthropic API 키가 설정되지 않았습니다. .env 파일 또는 사이드바에서 입력하세요.")
        return _call_anthropic(system_prompt, user_prompt, api_key, model, max_tokens, temperature)

    elif provider == "Ollama":
        return _call_ollama(system_prompt, user_prompt, model, max_tokens, temperature)

    else:
        raise ValueError(f"지원하지 않는 Provider: {provider}")


# ═══════════════════════════════════════════════════════════
# OpenAI
# ═══════════════════════════════════════════════════════════

def _call_openai(
    system: str, user: str, api_key: str, model: str,
    max_tokens: int, temperature: float,
) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "openai 패키지가 설치되지 않았습니다.\n"
            "터미널에서 `pip install openai` 를 실행하세요."
        )

    try:
        client = OpenAI(
            api_key=api_key,
            http_client=httpx.Client(verify=False),
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        err = str(e)
        if "invalid_api_key" in err or "Incorrect API key" in err:
            raise RuntimeError("OpenAI API 키가 유효하지 않습니다. 키를 확인해주세요.")
        if "model_not_found" in err:
            raise RuntimeError(f"모델 '{model}'을 찾을 수 없습니다. 모델명을 확인하세요.")
        if "insufficient_quota" in err or "exceeded" in err.lower():
            raise RuntimeError(
                "OpenAI API 사용량 한도 초과입니다.\n\n"
                "**해결 방법:**\n"
                "1. https://platform.openai.com/settings/organization/billing 에서 결제 수단을 등록하세요\n"
                "2. ChatGPT 유료 구독과 API 크레딧은 별도입니다 — API용 크레딧을 충전해야 합니다\n"
                "3. 최소 $5 크레딧을 추가하면 사용 가능합니다"
            )
        raise RuntimeError(f"OpenAI API 호출 실패: {err}")


# ═══════════════════════════════════════════════════════════
# Anthropic
# ═══════════════════════════════════════════════════════════

def _call_anthropic(
    system: str, user: str, api_key: str, model: str,
    max_tokens: int, temperature: float,
) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[
                {"role": "user", "content": user},
            ],
        )
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        return "\n".join(text_parts).strip()
    except ImportError:
        # SDK not available — use raw HTTP fallback
        return _call_anthropic_raw(system, user, api_key, model, max_tokens, temperature)
    except Exception as e:
        err = str(e)
        if "authentication_error" in err or "invalid x-api-key" in err:
            raise RuntimeError("Anthropic API 키가 유효하지 않습니다. 키를 확인해주세요.")
        if "model_not_found" in err or "not_found_error" in err:
            raise RuntimeError(f"모델 '{model}'을 찾을 수 없습니다. 모델명을 확인하세요.")
        raise RuntimeError(f"Anthropic API 호출 실패: {err}")


def _call_anthropic_raw(
    system: str, user: str, api_key: str, model: str,
    max_tokens: int, temperature: float,
) -> str:
    """Fallback: call Anthropic Messages API directly via requests (no SDK needed)."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120, verify=False)
        data = resp.json()

        if resp.status_code == 401:
            raise RuntimeError("Anthropic API 키가 유효하지 않습니다. 키를 확인해주세요.")
        if resp.status_code == 404:
            raise RuntimeError(f"모델 '{model}'을 찾을 수 없습니다. 모델명을 확인하세요.")
        if resp.status_code != 200:
            msg = data.get("error", {}).get("message", resp.text)
            raise RuntimeError(f"Anthropic API 오류 ({resp.status_code}): {msg}")

        # Parse response
        content = data.get("content", [])
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        return "\n".join(texts).strip()
    except requests.exceptions.Timeout:
        raise RuntimeError("Anthropic API 응답 시간 초과 (120초).")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Anthropic HTTP 호출 실패: {e}")


# ═══════════════════════════════════════════════════════════
# Ollama (local)
# ═══════════════════════════════════════════════════════════

def _call_ollama(
    system: str, user: str, model: str,
    max_tokens: int, temperature: float,
    base_url: str = "",
) -> str:
    import os
    url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    endpoint = f"{url}/api/chat"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        resp = requests.post(endpoint, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Ollama 서버에 연결할 수 없습니다 ({url}).\n"
            "Ollama가 실행 중인지 확인하세요: `ollama serve`"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama 응답 시간 초과 (120초). 더 작은 모델을 사용해보세요.")
    except Exception as e:
        raise RuntimeError(f"Ollama 호출 실패: {e}")
