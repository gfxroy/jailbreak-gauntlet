from app.services import research
from scripts.seed import run


def test_seed_generates_labeled_synthetic_data(settings):
    run(players=5, days=3, seed=1, reset=True, settings=settings)
    from app.db import make_engine

    engine = make_engine(settings.database_url)
    summary = research.summary(engine)
    assert summary["totals"]["attempts"] > 0
    assert summary["totals"]["synthetic_attempts"] == summary["totals"]["attempts"]
    assert all(
        e["synthetic"] and e["nickname"].startswith("synth_") for e in research.leaderboard(engine)
    )
    assert research.summary(engine, include_synthetic=False)["totals"]["attempts"] == 0
    # reset removes previous synthetic rows
    run(players=2, days=1, seed=2, reset=True, settings=settings)
    assert research.summary(engine)["totals"]["sessions"] <= 2
