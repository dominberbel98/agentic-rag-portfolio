#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def fetch_remote_items(url: str, admin_key: str) -> list[dict]:
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Key", admin_key)

    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    items = payload.get("items", [])
    return items if isinstance(items, list) else []


def unique_key(item: dict) -> str:
    ts = str(item.get("timestamp") or item.get("ts") or item.get("created_at") or "")
    q = str(item.get("question") or "")
    a = str(item.get("answer") or item.get("answer_preview") or "")
    return f"{ts}|{q}|{a}"


def merge_items(local_items: list[dict], remote_items: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}

    for it in local_items:
        by_key[unique_key(it)] = it

    for it in remote_items:
        normalized = {
            "timestamp": it.get("timestamp") or it.get("ts") or it.get("created_at") or "",
            "date": it.get("date") or "",
            "time": it.get("time") or "",
            "question": it.get("question") or "",
            "answer": it.get("answer") or it.get("answer_preview") or "",
            "out_of_scope": bool(it.get("out_of_scope", False)),
            "client_ip": it.get("client_ip") or "",
            "user_agent": it.get("user_agent") or "",
        }
        by_key[unique_key(normalized)] = normalized

    merged = list(by_key.values())
    merged.sort(key=lambda x: str(x.get("timestamp", "")))
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync remote Q&A logs to local preguntas.json")
    parser.add_argument(
        "--url",
        default="https://api.domingoberbel.com/api/admin/questions-json",
        help="Admin endpoint URL",
    )
    parser.add_argument(
        "--output",
        default="preguntas.json",
        help="Local JSON file path",
    )
    parser.add_argument(
        "--admin-key",
        default=os.getenv("ADMIN_READ_KEY", ""),
        help="Admin API key (defaults to ADMIN_READ_KEY env var)",
    )
    args = parser.parse_args()

    if not args.admin_key:
        print("ERROR: Missing admin key. Set ADMIN_READ_KEY or pass --admin-key.", file=sys.stderr)
        return 1

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        remote_items = fetch_remote_items(args.url, args.admin_key)
    except urllib.error.URLError as exc:
        print(f"ERROR: failed to fetch remote items: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON from endpoint: {exc}", file=sys.stderr)
        return 3

    local_items = load_json_list(output_path)
    merged = merge_items(local_items, remote_items)

    output_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: wrote {len(merged)} entries to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
