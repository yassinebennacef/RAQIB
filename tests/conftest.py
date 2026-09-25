import pytest

from raqib import config as C


@pytest.fixture(scope="session")
def built():
    """Make sure the artifacts exist (runs the ~20 s build once if they do not)."""
    needed = [C.ARTIFACTS / "metrics.json", C.ARTIFACTS / "test_scored.parquet",
              C.ARTIFACTS / "replay_default.json", C.MODELS_DIR / "thresholds.json"]
    if not all(p.exists() for p in needed):
        from raqib import build
        build.main()
    return True
