"""Secret passwords. One is drawn at random per level per session, server-side only."""

from __future__ import annotations

import secrets
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SecretWord:
    word: str
    description: str
    rhyme: str


WORDS: tuple[SecretWord, ...] = (
    SecretWord("CASCADE", "a small waterfall tumbling over rocks", "lemonade"),
    SecretWord("LANTERN", "a portable light you carry by a handle", "pattern"),
    SecretWord("MARIGOLD", "a bright orange garden flower", "fairy gold"),
    SecretWord("HORIZON", "the line where the sky meets the land", "surprisin'"),
    SecretWord("VELVET", "a soft, plush fabric", "held it"),
    SecretWord("THUNDER", "the rumble that follows lightning", "wonder"),
    SecretWord("SAPPHIRE", "a precious blue gemstone", "campfire"),
    SecretWord("COMPASS", "a tool whose needle always points north", "rumpus"),
    SecretWord("ORCHARD", "a field planted with fruit trees", "tortured"),
    SecretWord("PHOENIX", "a mythical bird reborn from its ashes", "genie tricks"),
    SecretWord("SPARROW", "a small brown songbird", "narrow"),
    SecretWord("WHISPER", "a very quiet way of speaking", "crisper"),
    SecretWord("CRIMSON", "a deep, rich shade of red", "Grimm's son"),
    SecretWord("LABYRINTH", "a maze with a minotaur at its heart", "hyacinth"),
    SecretWord("MOONBEAM", "a ray of light from the night sky's satellite", "daydream"),
    SecretWord("TORNADO", "a violently spinning column of wind", "avocado"),
    SecretWord("AVALANCHE", "snow rushing down a mountainside", "a ranch"),
    SecretWord("GLACIER", "a slow-moving river of ice", "racier"),
    SecretWord("NEBULA", "a vast cloud of cosmic dust and gas", "Petula"),
    SecretWord("FALCON", "a fast bird of prey", "balcon(y)"),
)

_BY_WORD = {w.word: w for w in WORDS}


def lookup(word: str) -> SecretWord | None:
    return _BY_WORD.get(word.upper())


def draw_secrets(levels: int, *, rng: secrets.SystemRandom | None = None) -> dict[int, str]:
    """Pick a distinct random word for each level (1-indexed)."""
    chooser = rng or secrets.SystemRandom()
    picks = chooser.sample(WORDS, k=levels)
    return {i + 1: w.word for i, w in enumerate(picks)}
