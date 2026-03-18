from __future__ import annotations

import httpx


class CaptchaService:
    def __init__(self, secret_key: str | None) -> None:
        self._secret_key = secret_key

    def validate(self, token: str | None, remote_ip: str) -> bool:
        if not self._secret_key:
            return True
        if not token:
            return False

        response = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": self._secret_key,
                "response": token,
                "remoteip": remote_ip,
            },
            timeout=10.0,
        )
        if response.status_code != 200:
            return False

        payload = response.json()
        return bool(payload.get("success"))
