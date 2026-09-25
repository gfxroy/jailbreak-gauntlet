"""Aggregations for the research dashboard, the leaderboard and dataset export."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets as secrets_mod
from collections import Counter, defaultdict
from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.classifier import Technique
from app.levels import LEVELS
from app.models import Attempt, GameSession, LevelProgress, Outcome

BYPASS = {Outcome.LEAKED, Outcome.PARTIAL_LEAK}
# Per-process salt so exported session hashes can't be linked to session ids.
_SALT = secrets_mod.token_hex(16)


def _attempts(db: Session, include_synthetic: bool) -> list[Attempt]:
    query = select(Attempt).order_by(col(Attempt.created_at))
    if not include_synthetic:
        query = query.where(Attempt.synthetic == False)  # noqa: E712
    return list(db.exec(query).all())


def summary(engine: Engine, *, include_synthetic: bool = True) -> dict[str, Any]:
    with Session(engine) as db:
        attempts = _attempts(db, include_synthetic)
        prog_query = select(LevelProgress, GameSession).where(
            LevelProgress.session_id == GameSession.id
        )
        if not include_synthetic:
            prog_query = prog_query.where(GameSession.synthetic == False)  # noqa: E712
        progress = db.exec(prog_query).all()

    synthetic_count = sum(a.synthetic for a in attempts)
    per_level: list[dict[str, Any]] = []
    by_level: dict[int, list[Attempt]] = defaultdict(list)
    for a in attempts:
        by_level[a.level].append(a)
    players: dict[int, int] = Counter(p.level for p, _ in progress if p.attempts > 0)
    solves: dict[int, int] = Counter(p.level for p, _ in progress if p.solved)

    for spec in LEVELS:
        rows = by_level.get(spec.id, [])
        n = len(rows)
        outcomes = Counter(a.outcome.value for a in rows)
        caught = Counter(a.caught_by for a in rows if a.caught_by)
        per_level.append(
            {
                "level": spec.id,
                "name": spec.name,
                "attempts": n,
                "players": players.get(spec.id, 0),
                "solves": solves.get(spec.id, 0),
                "solve_rate": _rate(solves.get(spec.id, 0), players.get(spec.id, 0)),
                "bypass_rate": _rate(sum(a.outcome in BYPASS for a in rows), n),
                "block_rate": _rate(
                    outcomes.get("blocked", 0) + outcomes.get("rate_limited", 0), n
                ),
                "model_leak_rate": _rate(sum(a.model_leaked for a in rows), n),
                "outcomes": dict(outcomes),
                "caught_by": dict(caught),
            }
        )

    # Technique x level: how often did attempts using a technique get information out?
    tech_level: dict[tuple[str, int], list[Attempt]] = defaultdict(list)
    tech_layer: Counter[tuple[str, str]] = Counter()
    tech_totals: Counter[str] = Counter()
    for a in attempts:
        for t in a.techniques:
            tech_level[(t, a.level)].append(a)
            tech_totals[t] += 1
            if a.caught_by:
                tech_layer[(t, a.caught_by)] += 1
    techniques = [t.value for t in Technique if tech_totals[t.value]]
    heatmap = [
        {
            "technique": t,
            "level": lvl.id,
            "attempts": len(tech_level[(t, lvl.id)]),
            "bypass_rate": _rate(
                sum(a.outcome in BYPASS for a in tech_level[(t, lvl.id)]),
                len(tech_level[(t, lvl.id)]),
            ),
        }
        for t in techniques
        for lvl in LEVELS
    ]
    layers = sorted({layer for _, layer in tech_layer})
    caught_matrix = [
        {"technique": t, "layer": layer, "count": tech_layer[(t, layer)]}
        for t in techniques
        for layer in layers
    ]

    daily: dict[str, Counter[str]] = defaultdict(Counter)
    for a in attempts:
        daily[a.created_at.date().isoformat()][a.outcome.value] += 1
    timeseries = [{"date": day, **dict(counts)} for day, counts in sorted(daily.items())]

    return {
        "totals": {
            "attempts": len(attempts),
            "synthetic_attempts": synthetic_count,
            "sessions": len({a.session_id for a in attempts}),
            "solves": sum(solves.values()),
            "bypass_rate": _rate(sum(a.outcome in BYPASS for a in attempts), len(attempts)),
        },
        "levels": per_level,
        "techniques": techniques,
        "technique_counts": {t: tech_totals[t] for t in techniques},
        "heatmap": heatmap,
        "layers": layers,
        "caught_matrix": caught_matrix,
        "timeseries": timeseries,
    }


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def leaderboard(
    engine: Engine, *, include_synthetic: bool = True, limit: int = 50
) -> list[dict[str, Any]]:
    with Session(engine) as db:
        query = select(GameSession, LevelProgress).where(LevelProgress.session_id == GameSession.id)
        if not include_synthetic:
            query = query.where(GameSession.synthetic == False)  # noqa: E712
        rows = db.exec(query).all()
    agg: dict[str, dict[str, Any]] = {}
    for game, prog in rows:
        entry = agg.setdefault(
            game.id,
            {
                "nickname": game.nickname,
                "levels_solved": 0,
                "attempts": 0,
                "synthetic": game.synthetic,
                "last_solve": None,
            },
        )
        entry["attempts"] += prog.attempts
        if prog.solved:
            entry["levels_solved"] += 1
            if prog.solved_at and (
                entry["last_solve"] is None or prog.solved_at > entry["last_solve"]
            ):
                entry["last_solve"] = prog.solved_at
    ranked = sorted(
        (e for e in agg.values() if e["levels_solved"] > 0),
        key=lambda e: (-e["levels_solved"], e["attempts"], e["last_solve"]),
    )
    out = []
    for i, e in enumerate(ranked[:limit], start=1):
        last = e["last_solve"]
        out.append({**e, "rank": i, "last_solve": last.isoformat() if last else None})
    return out


_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("[URL]", re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)),
    # API keys / tokens: long unbroken runs of key-ish characters, and known prefixes.
    ("[KEY]", re.compile(r"\b(?:sk|pk|rk|ghp|gho|xox[abp]|AIza|hf)[-_A-Za-z0-9]{12,}")),
    ("[KEY]", re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")),
    ("[IP]", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("[CARD]", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("[PHONE]", re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")),
)


def redact_pii(text: str) -> str:
    """Scrub common personal data and credentials from free text (best effort)."""
    for placeholder, pattern in _PII_PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


def _redact(text: str, secret: str) -> str:
    variants = {secret, secret[::-1], base64.b64encode(secret.encode()).decode()}
    for v in variants:
        text = re.sub(re.escape(v), "[REDACTED]", text, flags=re.IGNORECASE)
    spaced = r"[^A-Za-z]{1,3}".join(map(re.escape, secret))
    return re.sub(spaced, "[REDACTED]", text, flags=re.IGNORECASE)


def export_jsonl(engine: Engine, *, include_synthetic: bool = True) -> Iterator[str]:
    """Yield one JSON object per attempt.

    Safe to publish: level secrets (in several encodings), emails, URLs, IPs, phone and
    card numbers and credential-like strings are redacted; session ids are replaced by a
    salted hash; nicknames and latencies are omitted. Client IPs are never stored at all.
    """
    with Session(engine) as db:
        secrets = {g.id: g.secrets for g in db.exec(select(GameSession)).all()}
        attempts = _attempts(db, include_synthetic)
    for a in attempts:
        secret = secrets.get(a.session_id, {}).get(str(a.level), "")
        prompt = _redact(a.prompt, secret) if secret else a.prompt
        response = _redact(a.response, secret) if secret else a.response
        record = {
            "id": a.id,
            "session": hashlib.sha256((_SALT + a.session_id).encode()).hexdigest()[:12],
            "level": a.level,
            "prompt": redact_pii(prompt),
            "response": redact_pii(response),
            "outcome": a.outcome.value,
            "caught_by": a.caught_by,
            "block_reason": redact_pii(a.block_reason) if a.block_reason else None,
            "model_leaked": a.model_leaked,
            "techniques": a.techniques,
            "provider": a.provider,
            "synthetic": a.synthetic,
            "created_at": a.created_at.isoformat(),
        }
        yield json.dumps(record, ensure_ascii=False) + "\n"
