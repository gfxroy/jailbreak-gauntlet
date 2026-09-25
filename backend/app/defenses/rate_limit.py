"""Sliding-window rate limiting."""

from __future__ import annotations

from typing import ClassVar

from app.defenses.base import Defense, GuardContext, GuardResult, Handler


class RateLimit(Defense):
    """Caps requests per window. Slows automated fuzzing and brute-force search."""

    name: ClassVar[str] = "rate_limit"
    label: ClassVar[str] = "Rate Limit"
    stage = "input"

    def __init__(self, max_requests: int = 6, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, ctx: GuardContext, call_next: Handler) -> GuardResult:
        cutoff = ctx.now - self.window_seconds
        recent = [t for t in ctx.state.get("rl", []) if t > cutoff]
        if len(recent) >= self.max_requests:
            retry = int(recent[0] + self.window_seconds - ctx.now) + 1
            ctx.state["rl"] = recent
            return self.block(
                ctx,
                f"{len(recent)} requests in {self.window_seconds:.0f}s",
                f"🛡️ Rate limit: slow down. Try again in {retry}s.",
            )
        ctx.state["rl"] = [*recent, ctx.now]
        ctx.log(self.name, "pass")
        return await call_next(ctx)
