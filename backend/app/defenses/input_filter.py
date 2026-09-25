"""Input filter: block known-bad prompts before they reach the model."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import ClassVar

from app.defenses import text as T
from app.defenses.base import Defense, GuardContext, GuardResult, Handler

DEFAULT_RULES: tuple[tuple[str, str], ...] = (
    ("mentions the password", r"pass\s*(word|phrase|code)|\bpwd?\b"),
    ("mentions the secret", r"\bsecrets?\b"),
    ("instruction override", r"ignore\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier)?"
     r"\s*(instructions|rules|prompts?)|disregard\s+(all|your|the|previous)|forget\s+your"),
    ("system prompt extraction", r"system\s*prompt|(your|the)\s+instructions"),
    ("jailbreak keyword", r"jailbreak|developer\s+mode|\bdan\b|do\s+anything\s+now"),
    ("disclosure verb", r"\b(reveal|leak|divulge|disclose)\b"),
)  # fmt: skip


class InputFilter(Defense):
    """Regex blocklist evaluated on *normalized* input.

    Normalization folds homoglyphs, strips zero-width characters, undoes leetspeak and
    collapses separated letters, so ``p.4.s.s.w.0.r.d`` and ``pаsswоrd`` (Cyrillic) are
    caught. Blocklists still cannot enumerate every synonym or paraphrase.
    """

    name: ClassVar[str] = "input_filter"
    label: ClassVar[str] = "Input Filter"
    stage = "input"

    def __init__(self, rules: Sequence[tuple[str, str]] = DEFAULT_RULES) -> None:
        self.rules = [(label, re.compile(pattern, re.IGNORECASE)) for label, pattern in rules]

    def check(self, text: str) -> str | None:
        """Return the label of the first matching rule, or ``None``."""
        views = {T.fold_unicode(text), T.normalize(text)}
        for label, pattern in self.rules:
            if any(pattern.search(v) for v in views):
                return label
        return None

    async def __call__(self, ctx: GuardContext, call_next: Handler) -> GuardResult:
        if hit := self.check(ctx.user_input):
            return self.block(ctx, hit, f"🛡️ Input filter: your message was rejected ({hit}).")
        ctx.log(self.name, "pass")
        return await call_next(ctx)
