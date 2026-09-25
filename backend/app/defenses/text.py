"""Text normalization and encoding helpers shared by filters, detectors and the mock model.

Attackers routinely hide payloads with look-alike characters, zero-width joiners,
leetspeak or separators ("p.a.s.s.w.o.r.d"). Filters that match on raw strings are
trivially bypassed, so every filter in this project matches against normalized text.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import re
import unicodedata

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)

# Common Cyrillic / Greek homoglyphs that NFKC does not fold to ASCII.
HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",
        "ј": "j", "ѕ": "s", "ԁ": "d", "ɡ": "g", "ո": "n", "ν": "v", "ο": "o", "α": "a",
        "ρ": "p", "τ": "t", "κ": "k", "ι": "i", "Α": "a", "Β": "b", "Ε": "e", "Η": "h",
        "Ι": "i", "Κ": "k", "Μ": "m", "Ν": "n", "Ο": "o", "Ρ": "p", "Τ": "t", "Χ": "x",
        "А": "a", "В": "b", "Е": "e", "К": "k", "М": "m", "Н": "h", "О": "o", "Р": "p",
        "С": "c", "Т": "t", "Х": "x",
    }
)  # fmt: skip

LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "@": "a", "$": "s",
     "!": "i", "|": "l", "+": "t"}
)  # fmt: skip

NATO = {
    "alfa": "a", "alpha": "a", "bravo": "b", "charlie": "c", "delta": "d", "echo": "e",
    "foxtrot": "f", "golf": "g", "hotel": "h", "india": "i", "juliett": "j", "juliet": "j",
    "kilo": "k", "lima": "l", "mike": "m", "november": "n", "oscar": "o", "papa": "p",
    "quebec": "q", "romeo": "r", "sierra": "s", "tango": "t", "uniform": "u", "victor": "v",
    "whiskey": "w", "whisky": "w", "xray": "x", "x-ray": "x", "yankee": "y", "zulu": "z",
}  # fmt: skip
NATO_BY_LETTER = {v: k.capitalize() for k, v in reversed(list(NATO.items())) if "-" not in k}

_SEPARATED_RUN = re.compile(r"\b(?:[a-z][\s\.\-_*,·|/]{1,3}){2,}[a-z]\b")
_BASE64_TOKEN = re.compile(r"[A-Za-z0-9+/]{8,}={0,2}")
_HEX_TOKEN = re.compile(r"\b(?:[0-9a-fA-F]{2}[\s:]?){3,}\b")


def fold_unicode(text: str) -> str:
    """NFKC-normalize, drop zero-width characters, fold homoglyphs and lowercase."""
    text = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH).translate(HOMOGLYPHS)
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    return stripped.lower()


def collapse_separated_letters(text: str) -> str:
    """Join runs of single letters split by separators: ``p.a.s.s`` -> ``pass``."""
    return _SEPARATED_RUN.sub(lambda m: re.sub(r"[^a-z]", "", m.group(0)), text)


def normalize(text: str) -> str:
    """Canonical form used by keyword filters (folding + separator collapse + de-leet)."""
    folded = collapse_separated_letters(fold_unicode(text))
    return collapse_separated_letters(folded.translate(LEET))


def letters_only(text: str) -> str:
    return re.sub(r"[^a-z]", "", fold_unicode(text))


def rot13(text: str) -> str:
    return codecs.encode(text, "rot13")


def to_base64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def decode_base64_tokens(text: str) -> list[str]:
    """Best-effort decode of every base64-looking token in ``text``."""
    decoded: list[str] = []
    for token in _BASE64_TOKEN.findall(text):
        padded = token + "=" * (-len(token) % 4)
        try:
            raw = base64.b64decode(padded, validate=True)
            decoded.append(raw.decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
    return decoded


def decode_hex_tokens(text: str) -> list[str]:
    decoded: list[str] = []
    for token in _HEX_TOKEN.findall(text):
        compact = re.sub(r"[\s:]", "", token)
        try:
            decoded.append(bytes.fromhex(compact).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
    return decoded


def decode_nato(text: str) -> str:
    """Translate NATO phonetic words to letters, leaving other words intact."""
    words = re.findall(r"[a-z\-]+", text.lower())
    return "".join(NATO.get(w, " ") for w in words)


def to_nato(word: str) -> str:
    return " ".join(NATO_BY_LETTER.get(c, c) for c in word.lower())


def acrostic(text: str) -> str:
    """First letter of every non-empty line."""
    letters = []
    for line in text.splitlines():
        m = re.search(r"[A-Za-z]", line)
        if m:
            letters.append(m.group(0).lower())
    return "".join(letters)


def folded_leet(text: str) -> str:
    return fold_unicode(text).translate(LEET)
