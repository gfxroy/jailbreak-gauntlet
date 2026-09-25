"""Output filter: withhold responses that contain the secret in any known form."""

from __future__ import annotations

from typing import ClassVar

from app.defenses.base import Defense, GuardContext, GuardResult, Handler
from app.defenses.leak_detection import SecretDetector


class OutputFilter(Defense):
    """Scans the model's reply for the secret: plain, separated, reversed, leetspeak,
    ROT13, base64, hex and NATO-phonetic variants."""

    name: ClassVar[str] = "output_filter"
    label: ClassVar[str] = "Output Filter"
    stage = "output"

    async def __call__(self, ctx: GuardContext, call_next: Handler) -> GuardResult:
        result = await call_next(ctx)
        if result.blocked:
            return result
        variants = SecretDetector(ctx.secret).find_variants(result.text)
        if variants:
            kinds = ", ".join(variants)
            return self.block(
                ctx,
                f"secret detected in output ({kinds})",
                f"🛡️ Output filter: the guard's reply contained the password ({kinds}) and was withheld.",
            )
        ctx.log(self.name, "pass")
        return result
