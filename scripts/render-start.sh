#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8000}"
AUTH_DIR="${CHATMOCK_AUTH_DIR:-/tmp/chatmock-accounts}"
mkdir -p "$AUTH_DIR"

build_auth_files_from_env() {
  local -a files=()

  if [[ -n "${CHATGPT_LOCAL_AUTH_FILES:-}" ]]; then
    return 0
  fi

  if [[ -n "${CHATMOCK_AUTH_JSONS_BASE64:-}" ]]; then
    IFS=',' read -r -a b64_items <<< "${CHATMOCK_AUTH_JSONS_BASE64}"
    local idx=1
    for item in "${b64_items[@]}"; do
      [[ -z "$item" ]] && continue
      local acc
      acc="$(printf "acc%02d" "$idx")"
      mkdir -p "$AUTH_DIR/$acc"
      printf "%s" "$item" | base64 -d > "$AUTH_DIR/$acc/auth.json"
      files+=("$AUTH_DIR/$acc/auth.json")
      idx=$((idx + 1))
    done
  fi

  for i in $(seq 1 20); do
    local json_var="CHATMOCK_AUTH_JSON_${i}"
    local b64_var="CHATMOCK_AUTH_B64_${i}"
    local json_val="${!json_var:-}"
    local b64_val="${!b64_var:-}"
    local acc
    acc="$(printf "acc%02d" "$i")"

    if [[ -n "$json_val" ]]; then
      mkdir -p "$AUTH_DIR/$acc"
      printf "%s" "$json_val" > "$AUTH_DIR/$acc/auth.json"
      files+=("$AUTH_DIR/$acc/auth.json")
      continue
    fi

    if [[ -n "$b64_val" ]]; then
      mkdir -p "$AUTH_DIR/$acc"
      printf "%s" "$b64_val" | base64 -d > "$AUTH_DIR/$acc/auth.json"
      files+=("$AUTH_DIR/$acc/auth.json")
    fi
  done

  if [[ ${#files[@]} -gt 0 ]]; then
    CHATGPT_LOCAL_AUTH_FILES="$(IFS=,; echo "${files[*]}")"
    export CHATGPT_LOCAL_AUTH_FILES
  fi
}

build_auth_files_from_env

if [[ -z "${CHATGPT_LOCAL_AUTH_FILES:-}" ]]; then
  echo "[render-start] CHATGPT_LOCAL_AUTH_FILES is empty."
  echo "[render-start] Set CHATMOCK_AUTH_JSONS_BASE64 or CHATMOCK_AUTH_JSON_1..N in Render env vars."
fi

export CHATGPT_LOCAL_ROUTING_STRATEGY="${CHATGPT_LOCAL_ROUTING_STRATEGY:-round-robin}"
export CHATGPT_LOCAL_REQUEST_RETRY="${CHATGPT_LOCAL_REQUEST_RETRY:-0}"
export CHATGPT_LOCAL_MAX_RETRY_INTERVAL="${CHATGPT_LOCAL_MAX_RETRY_INTERVAL:-5}"

exec python chatmock.py serve --host 0.0.0.0 --port "$PORT"
