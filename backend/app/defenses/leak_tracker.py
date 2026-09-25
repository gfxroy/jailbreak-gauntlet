"""Conversation-level leak tracking: stop slow, letter-by-letter exfiltration."""

from __future__ import annotations

import math
from typing import ClassVar

from app.defenses.base import Defense, GuardContext, GuardResult, Handler
from app.defenses.leak_detection import SecretDetector


class LeakTracker(Defense):
    """Remembers which positions of the secret earlier replies disclosed.

    Per-message filters can't see that five innocent-looking replies together spell
    the password. This layer keeps the union of disclosed positions in session state
    and blocks any reply that would push cumulative disclosure over ``max_fraction``.
    """

    name: ClassVar[str] = "leak_tracker"
    label: ClassVar[str] = "Leak Tracker"
    stage = "output"

    def __init__(self, max_fraction: float = 0.6) -> None:
        self.max_fraction = max_fraction

    async def __call__(self, ctx: GuardContext, call_next: Handler) -> GuardResult:
        result = await call_next(ctx)
        if result.blocked:
            return result
        revealed = set(ctx.state.get("revealed", []))
        report = SecretDetector(ctx.secret).scan(result.text)
        # Prefer explicit "letters 4-5 are CA" statements; otherwise fall back to every
        # position an emphasized fragment could correspond to (conservative).
        new = (
            SecretDetector.positional_letters(ctx.secret, result.text) or report.revealed_positions
        )
        combined = revealed | new
        budget = math.floor(len(ctx.secret) * self.max_fraction)
        if len(combined) > budget:
            return self.block(
                ctx,
                f"cumulative disclosure {len(combined)}/{len(ctx.secret)} letters exceeds budget",
                "🛡️ Leak tracker: this reply would reveal too much of the password "
                "across the conversation.",
            )
        ctx.state["revealed"] = sorted(combined)
        ctx.log(self.name, "pass", f"{len(combined)}/{len(ctx.secret)} letters disclosed")
        return result
