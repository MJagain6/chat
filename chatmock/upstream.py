from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

import requests
from flask import Response, current_app, jsonify, make_response

from .config import CHATGPT_RESPONSES_URL
from .http import build_cors_headers
from .session import ensure_session_id
from flask import request as flask_request
from .utils import (
    get_effective_chatgpt_auth_candidates,
    get_max_retry_interval_seconds,
    get_request_retry_limit,
    get_retryable_statuses,
    mark_chatgpt_auth_result,
)


def _log_json(prefix: str, payload: Any) -> None:
    try:
        print(f"{prefix}\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    except Exception:
        try:
            print(f"{prefix}\n{payload}")
        except Exception:
            pass


def normalize_model_name(name: str | None, debug_model: str | None = None) -> str:
    if isinstance(debug_model, str) and debug_model.strip():
        return debug_model.strip()
    if not isinstance(name, str) or not name.strip():
        return "gpt-5"
    base = name.split(":", 1)[0].strip()
    for sep in ("-", "_"):
        lowered = base.lower()
        for effort in ("minimal", "low", "medium", "high", "xhigh"):
            suffix = f"{sep}{effort}"
            if lowered.endswith(suffix):
                base = base[: -len(suffix)]
                break
    mapping = {
        "gpt5": "gpt-5",
        "gpt-5-latest": "gpt-5",
        "gpt-5": "gpt-5",
        "gpt-5.1": "gpt-5.1",
        "gpt5.2": "gpt-5.2",
        "gpt-5.2": "gpt-5.2",
        "gpt-5.2-latest": "gpt-5.2",
        "gpt5.3-codex": "gpt-5.3-codex",
        "gpt-5.3-codex": "gpt-5.3-codex",
        "gpt-5.3-codex-latest": "gpt-5.3-codex",
        "gpt5.2-codex": "gpt-5.2-codex",
        "gpt-5.2-codex": "gpt-5.2-codex",
        "gpt-5.2-codex-latest": "gpt-5.2-codex",
        "gpt5-codex": "gpt-5-codex",
        "gpt-5-codex": "gpt-5-codex",
        "gpt-5-codex-latest": "gpt-5-codex",
        "gpt-5.1-codex": "gpt-5.1-codex",
        "gpt-5.1-codex-max": "gpt-5.1-codex-max",
        "codex": "codex-mini-latest",
        "codex-mini": "codex-mini-latest",
        "codex-mini-latest": "codex-mini-latest",
        "gpt-5.1-codex-mini": "gpt-5.1-codex-mini",
    }
    return mapping.get(base, base)


def start_upstream_request(
    model: str,
    input_items: List[Dict[str, Any]],
    *,
    instructions: str | None = None,
    tools: List[Dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    parallel_tool_calls: bool = False,
    reasoning_param: Dict[str, Any] | None = None,
):
    auth_candidates = get_effective_chatgpt_auth_candidates(ensure_fresh=True)
    if not auth_candidates:
        resp = make_response(
            jsonify(
                {
                    "error": {
                        "message": (
                            "Missing ChatGPT credentials. Run 'python3 chatmock.py login' first, "
                            "or configure CHATGPT_LOCAL_AUTH_FILES/auth_pool.json for multi-account mode."
                        ),
                    }
                }
            ),
            401,
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp

    include: List[str] = []
    if isinstance(reasoning_param, dict):
        include.append("reasoning.encrypted_content")

    client_session_id = None
    try:
        client_session_id = (
            flask_request.headers.get("X-Session-Id")
            or flask_request.headers.get("session_id")
            or None
        )
    except Exception:
        client_session_id = None
    session_id = ensure_session_id(instructions, input_items, client_session_id)

    responses_payload = {
        "model": model,
        "instructions": instructions if isinstance(instructions, str) and instructions.strip() else instructions,
        "input": input_items,
        "tools": tools or [],
        "tool_choice": tool_choice if tool_choice in ("auto", "none") or isinstance(tool_choice, dict) else "auto",
        "parallel_tool_calls": bool(parallel_tool_calls),
        "store": False,
        "stream": True,
        "prompt_cache_key": session_id,
    }
    if include:
        responses_payload["include"] = include

    if reasoning_param is not None:
        responses_payload["reasoning"] = reasoning_param

    verbose = False
    try:
        verbose = bool(current_app.config.get("VERBOSE"))
    except Exception:
        verbose = False
    if verbose:
        _log_json("OUTBOUND >> ChatGPT Responses API payload", responses_payload)

    retryable_statuses = get_retryable_statuses()
    request_retry_limit = get_request_retry_limit()
    max_retry_interval = get_max_retry_interval_seconds()
    last_error_resp = None
    last_exception = None
    last_upstream = None

    for round_idx in range(request_retry_limit + 1):
        if round_idx > 0:
            sleep_secs = min(max_retry_interval, 2 ** (round_idx - 1))
            if verbose:
                print(f"Retry round {round_idx}/{request_retry_limit} after {sleep_secs}s")
            time.sleep(sleep_secs)

        round_candidates = get_effective_chatgpt_auth_candidates(ensure_fresh=True)
        if not round_candidates:
            break

        for idx, candidate in enumerate(round_candidates):
            access_token = candidate.get("access_token")
            account_id = candidate.get("account_id")
            label = candidate.get("label") or f"candidate-{idx + 1}"
            if not access_token or not account_id:
                continue

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "chatgpt-account-id": account_id,
                "OpenAI-Beta": "responses=experimental",
                "session_id": session_id,
            }

            try:
                upstream = requests.post(
                    CHATGPT_RESPONSES_URL,
                    headers=headers,
                    json=responses_payload,
                    stream=True,
                    timeout=600,
                )
            except requests.RequestException as e:
                last_exception = e
                mark_chatgpt_auth_result(label, success=False, error_message=str(e))
                if verbose:
                    print(f"Upstream request failed for {label}: {e}")
                continue

            last_upstream = upstream
            status = int(upstream.status_code or 0)
            should_retry = status in retryable_statuses
            has_more_candidates = idx < len(round_candidates) - 1
            has_more_rounds = round_idx < request_retry_limit
            if should_retry:
                mark_chatgpt_auth_result(label, success=False, status_code=status)
                if has_more_candidates or has_more_rounds:
                    if verbose:
                        print(
                            f"Upstream status {status} for {label}; "
                            "retrying with next account."
                        )
                    try:
                        upstream.close()
                    except Exception:
                        pass
                    continue
                return upstream, None

            mark_chatgpt_auth_result(label, success=True, status_code=status)
            return upstream, None

    if last_upstream is not None:
        return last_upstream, None

    if last_exception is not None:
        last_error_resp = make_response(
            jsonify({"error": {"message": f"Upstream ChatGPT request failed: {last_exception}"}}),
            502,
        )
    else:
        last_error_resp = make_response(
            jsonify({"error": {"message": "No valid ChatGPT account is available."}}),
            401,
        )
    for k, v in build_cors_headers().items():
        last_error_resp.headers.setdefault(k, v)
    return None, last_error_resp
