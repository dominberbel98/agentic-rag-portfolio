from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class GuardDecision:
    allowed: bool
    message: str | None = None


class RequestGuards:
    def __init__(
        self,
        per_minute_limit: int,
        daily_token_limit: int,
    ) -> None:
        self._per_minute_limit = per_minute_limit
        self._daily_token_limit = daily_token_limit
        self._requests_by_ip: dict[str, deque[float]] = defaultdict(deque)

    def enforce_rate_limit(self, client_ip: str) -> GuardDecision:
        now = datetime.now(UTC).timestamp()
        window_start = now - 60.0
        bucket = self._requests_by_ip[client_ip]
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self._per_minute_limit:
            return GuardDecision(
                allowed=False,
                message="Rate limit alcanzado. Prueba de nuevo en 1 minuto.",
            )

        bucket.append(now)
        return GuardDecision(allowed=True)

    def enforce_token_budget(self, used_today: int, estimated_new_tokens: int) -> GuardDecision:
        if used_today + estimated_new_tokens > self._daily_token_limit:
            return GuardDecision(
                allowed=False,
                message="Limite diario de tokens alcanzado. Intenta mas tarde.",
            )
        return GuardDecision(allowed=True)
