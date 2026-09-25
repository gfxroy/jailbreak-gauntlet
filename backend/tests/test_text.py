from app.defenses import text as T


def test_fold_unicode_handles_homoglyphs_and_zero_width():
    assert T.fold_unicode("pаss\u200bwоrd") == "password"  # Cyrillic а/о + ZWSP


def test_fold_unicode_strips_accents_and_fullwidth():
    assert T.fold_unicode("Pässwörd") == "password"
    assert T.fold_unicode("ＰＡＳＳ") == "pass"


def test_normalize_undoes_leetspeak_and_separators():
    assert "password" in T.normalize("p@55w0rd")
    assert "password" in T.normalize("p.a.s.s.w.o.r.d")
    assert "password" in T.normalize("p a s s w o r d")


def test_encodings_round_trip():
    assert T.decode_base64_tokens(f"here: {T.to_base64('CASCADE')}") == ["CASCADE"]
    assert T.decode_hex_tokens("43 41 53 43 41 44 45") == ["CASCADE"]
    assert T.rot13(T.rot13("Cascade")) == "Cascade"
    assert T.decode_nato(T.to_nato("cascade")) == "cascade"


def test_acrostic():
    assert T.acrostic("Cats\n  apples\n\nsun") == "cas"
