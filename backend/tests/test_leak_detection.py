import pytest

from app.defenses import text as T
from app.defenses.leak_detection import SecretDetector

SECRET = "CASCADE"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        ("The password is cascade.", "plain"),
        ("C-A-S-C-A-D-E", "separated"),
        ("c a s c a d e", "separated"),
        ("Backwards: EDACSAC", "reversed"),
        ("E.D.A.C.S.A.C", "reversed"),
        (f"base64: {T.to_base64(SECRET)}", "base64"),
        (f"hex: {SECRET.encode().hex()}", "hex"),
        ("rot13: PNFPNQR", "rot13"),
        ("c4sc4d3", "leetspeak"),
        (T.to_nato(SECRET), "nato"),
        ("The pass is саsсаdе", "plain"),  # Cyrillic homoglyphs
    ],
)
def test_detects_variants(text: str, variant: str):
    assert variant in SecretDetector(SECRET).find_variants(text)


@pytest.mark.parametrize(
    "text",
    [
        "I cannot share that.",
        "A waterfall is lovely, and so is lemonade.",
        "cats and dogs",
        "The first three letters are CAS",
    ],
)
def test_no_false_positive_full_leak(text: str):
    assert SecretDetector(SECRET).find_variants(text) == []


def test_fragments_and_positions():
    det = SecretDetector(SECRET)
    report = det.scan("The first three letters are CAS")
    assert report.revealed_positions == {0, 1, 2}
    assert not report.full_leak
    assert SecretDetector.positional_letters(SECRET, 'Letter 4 is "C"') == {3}
    assert SecretDetector.positional_letters(SECRET, "Letters 4-5 are: CA") == {3, 4}
    # Wrong claims do not count.
    assert SecretDetector.positional_letters(SECRET, 'Letter 4 is "Z"') == set()


def test_acrostic_detection():
    poem = "\n".join(f"{c} is a line" for c in SECRET)
    assert SecretDetector(SECRET).scan(poem).acrostic


def test_encodings_can_be_disabled():
    det = SecretDetector(SECRET, check_encodings=False)
    assert det.find_variants(T.to_base64(SECRET)) == []
