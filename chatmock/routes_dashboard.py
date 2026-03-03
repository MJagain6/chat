from __future__ import annotations

import datetime
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, make_response, request, send_from_directory

from .utils import (
    get_chatgpt_auth_records,
    get_max_retry_interval_seconds,
    get_request_retry_limit,
)


dashboard_bp = Blueprint("dashboard", __name__)

_DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"


def _model_ids(expose_variants: bool) -> List[str]:
    model_groups = [
        ("gpt-5", ["high", "medium", "low", "minimal"]),
        ("gpt-5.1", ["high", "medium", "low"]),
        ("gpt-5.2", ["xhigh", "high", "medium", "low"]),
        ("gpt-5.3-codex", ["xhigh", "high", "medium", "low"]),
        ("gpt-5-codex", ["high", "medium", "low"]),
        ("gpt-5.2-codex", ["xhigh", "high", "medium", "low"]),
        ("gpt-5.1-codex", ["high", "medium", "low"]),
        ("gpt-5.1-codex-max", ["xhigh", "high", "medium", "low"]),
        ("gpt-5.1-codex-mini", []),
        ("codex-mini", []),
    ]
    out: List[str] = []
    for base, efforts in model_groups:
        out.append(base)
        if expose_variants:
            out.extend([f"{base}-{effort}" for effort in efforts])
    return out


def _default_log_path() -> str:
    explicit = (os.getenv("CHATMOCK_DASHBOARD_LOG_PATH") or "").strip()
    if explicit:
        return explicit
    env_log = (os.getenv("CHATGPT_LOCAL_LOG_PATH") or "").strip()
    if env_log:
        return env_log
    return str(Path.cwd() / "chatmock.log")


def _read_log_tail(path: str, lines: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.readlines()
        return "".join(data[-lines:])
    except Exception as exc:
        return f"failed to read log: {exc}"


def _service_status() -> Dict[str, Any]:
    service_name = (os.getenv("CHATMOCK_SERVICE_NAME") or "").strip()
    if not service_name:
        return {"name": "", "status": "running", "raw": "running in foreground/no service configured"}
    try:
        completed = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        status = (completed.stdout or completed.stderr or "unknown").strip()
        if not status:
            status = "unknown"
        return {"name": service_name, "status": status, "raw": status}
    except Exception as exc:
        return {"name": service_name, "status": "error", "raw": str(exc)}


@dashboard_bp.get("/dashboard")
@dashboard_bp.get("/dashboard/")
def dashboard_index():
    return send_from_directory(_DASHBOARD_DIR, "index.html")


@dashboard_bp.get("/dashboard/app.js")
def dashboard_js():
    return send_from_directory(_DASHBOARD_DIR, "app.js")


@dashboard_bp.get("/dashboard/styles.css")
def dashboard_css():
    return send_from_directory(_DASHBOARD_DIR, "styles.css")


@dashboard_bp.get("/api/health")
def dashboard_health():
    records = get_chatgpt_auth_records()
    models = _model_ids(bool(current_app.config.get("EXPOSE_REASONING_MODELS")))
    payload = {
        "now": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "service": _service_status(),
        "listening": True,
        "models": {"count": len(models), "ids": models, "error": ""},
        "accounts": {"count": len(records)},
        "routing": {
            "strategy": (os.getenv("CHATGPT_LOCAL_ROUTING_STRATEGY") or "round-robin"),
            "request_retry": get_request_retry_limit(),
            "max_retry_interval": get_max_retry_interval_seconds(),
        },
    }
    return jsonify(payload)


@dashboard_bp.get("/api/accounts")
def dashboard_accounts():
    records = get_chatgpt_auth_records()
    return jsonify({"count": len(records), "accounts": records})


@dashboard_bp.get("/api/models")
def dashboard_models():
    ids = _model_ids(bool(current_app.config.get("EXPOSE_REASONING_MODELS")))
    return jsonify({"count": len(ids), "ids": ids})


@dashboard_bp.get("/api/config")
def dashboard_config():
    local = {
        "CHATGPT_LOCAL_HOME": os.getenv("CHATGPT_LOCAL_HOME", ""),
        "CHATGPT_LOCAL_AUTH_FILES": os.getenv("CHATGPT_LOCAL_AUTH_FILES", ""),
        "CHATGPT_LOCAL_ROUTING_STRATEGY": os.getenv("CHATGPT_LOCAL_ROUTING_STRATEGY", "round-robin"),
        "CHATGPT_LOCAL_REQUEST_RETRY": str(get_request_retry_limit()),
        "CHATGPT_LOCAL_MAX_RETRY_INTERVAL": str(get_max_retry_interval_seconds()),
        "CHATGPT_LOCAL_REASONING_EFFORT": str(current_app.config.get("REASONING_EFFORT", "medium")),
        "CHATGPT_LOCAL_REASONING_SUMMARY": str(current_app.config.get("REASONING_SUMMARY", "auto")),
        "CHATGPT_LOCAL_REASONING_COMPAT": str(current_app.config.get("REASONING_COMPAT", "think-tags")),
    }
    return jsonify(
        {
            "localPath": ".env / runtime env",
            "activePath": "runtime",
            "localConfig": json.dumps(local, ensure_ascii=False, indent=2),
            "activeConfig": json.dumps(local, ensure_ascii=False, indent=2),
        }
    )


@dashboard_bp.get("/api/logs")
def dashboard_logs():
    raw_lines = request.args.get("lines", "180")
    try:
        lines = int(raw_lines)
    except Exception:
        lines = 180
    lines = max(20, min(lines, 1000))
    log_path = _default_log_path()
    text = _read_log_tail(log_path, lines)
    return jsonify({"lines": lines, "logPath": log_path, "text": text})


@dashboard_bp.post("/api/actions/sync")
def dashboard_action_sync():
    health = dashboard_health().get_json()
    return jsonify({"ok": True, "stdout": "sync not required for ChatMock", "stderr": "", "health": health})


@dashboard_bp.post("/api/actions/service")
def dashboard_action_service():
    action = str((request.get_json(silent=True) or {}).get("action") or "").strip().lower()
    if action not in ("start", "stop", "restart"):
        return make_response(jsonify({"error": "action must be one of start|stop|restart"}), 400)

    service_name = (os.getenv("CHATMOCK_SERVICE_NAME") or "").strip()
    if not service_name:
        return make_response(
            jsonify(
                {
                    "ok": False,
                    "error": "CHATMOCK_SERVICE_NAME is not set; service action unavailable.",
                }
            ),
            400,
        )

    try:
        completed = subprocess.run(
            ["systemctl", action, service_name],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        health = dashboard_health().get_json()
        return jsonify(
            {
                "ok": completed.returncode == 0,
                "action": action,
                "manager": "systemd",
                "service": service_name,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "health": health,
            }
        )
    except Exception as exc:
        return make_response(jsonify({"ok": False, "error": str(exc)}), 500)
