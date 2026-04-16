from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock


@dataclass
class UsageSnapshot:
    day: str
    tokens_used: int


class AnalyticsStore:
    def __init__(self, db_path: str = "/tmp/rag_analytics.db", json_path: str = "/tmp/rag_qa_logs.json") -> None:
        self._db_path = Path(db_path)
        self._json_path = Path(json_path)
        self._lock = Lock()
        self._init_db()
        self._init_json_store()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS question_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    user_agent TEXT,
                    question TEXT NOT NULL,
                    answer_preview TEXT,
                    out_of_scope INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_usage (
                    day TEXT PRIMARY KEY,
                    tokens_used INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_json_store(self) -> None:
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._json_path.exists():
            self._json_path.write_text("[]", encoding="utf-8")

    def log_question(
        self,
        client_ip: str,
        user_agent: str | None,
        question: str,
        answer_preview: str,
        out_of_scope: bool,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        dt = datetime.now(UTC)
        log_entry = {
            "timestamp": now,
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
            "client_ip": client_ip,
            "user_agent": user_agent or "",
            "question": question,
            "answer": answer_preview,
            "out_of_scope": bool(out_of_scope),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO question_logs (
                        created_at, client_ip, user_agent, question, answer_preview, out_of_scope
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (now, client_ip, user_agent, question, answer_preview, int(out_of_scope)),
                )
                conn.commit()

            self._append_json_entry(log_entry)

    _JSON_MAX_ENTRIES = 5000
    _JSON_MAX_BYTES = 50 * 1024 * 1024  # 50 MB hard cap

    def _append_json_entry(self, entry: dict[str, str | bool]) -> None:
        try:
            # Rotate file if it exceeds size cap before loading into memory
            if self._json_path.exists() and self._json_path.stat().st_size > self._JSON_MAX_BYTES:
                backup = self._json_path.with_suffix(".json.bak")
                self._json_path.rename(backup)
                existing: list = []
            else:
                try:
                    existing = json.loads(self._json_path.read_text(encoding="utf-8"))
                    if not isinstance(existing, list):
                        existing = []
                except (FileNotFoundError, json.JSONDecodeError):
                    existing = []

            existing.append(entry)
            # Keep only the most recent entries to bound memory and disk usage
            if len(existing) > self._JSON_MAX_ENTRIES:
                existing = existing[-self._JSON_MAX_ENTRIES:]

            self._json_path.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed to append analytics entry: %s", e)

    def get_json_logs(self, limit: int = 200) -> list[dict[str, str | bool]]:
        with self._lock:
            try:
                payload = json.loads(self._json_path.read_text(encoding="utf-8"))
                if not isinstance(payload, list):
                    return []
            except (FileNotFoundError, json.JSONDecodeError):
                return []

        if limit <= 0:
            return payload

        return payload[-limit:]

    def get_recent_questions(self, limit: int = 100) -> list[dict[str, str | int]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT created_at, client_ip, question, answer_preview, out_of_scope
                    FROM question_logs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        return [
            {
                "ts": str(row[0]),
                "client_ip": str(row[1]),
                "question": str(row[2]),
                "answer_preview": str(row[3] or ""),
                "out_of_scope": int(row[4]),
            }
            for row in rows
        ]

    def get_today_usage(self) -> UsageSnapshot:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT tokens_used FROM daily_usage WHERE day = ?",
                    (today,),
                ).fetchone()

                if not row:
                    conn.execute(
                        "INSERT INTO daily_usage (day, tokens_used) VALUES (?, 0)",
                        (today,),
                    )
                    conn.commit()
                    return UsageSnapshot(day=today, tokens_used=0)

        return UsageSnapshot(day=today, tokens_used=int(row[0]))

    def increment_today_usage(self, tokens: int) -> UsageSnapshot:
        snapshot = self.get_today_usage()
        updated = snapshot.tokens_used + max(tokens, 0)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE daily_usage SET tokens_used = ? WHERE day = ?",
                    (updated, snapshot.day),
                )
                conn.commit()
        return UsageSnapshot(day=snapshot.day, tokens_used=updated)
