from pathlib import Path

from scripts.export_static_data import OUT, render


def test_static_data_is_up_to_date():
    assert Path(OUT).read_text(encoding="utf-8") == render(), (
        "frontend/src/engine/data.json is stale: run `python -m scripts.export_static_data`"
    )
