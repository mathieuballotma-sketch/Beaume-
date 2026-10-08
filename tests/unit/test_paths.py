from beaume.config import paths


def test_root_exists():
    assert paths.ROOT.exists()


def test_ensure_dirs_creates_all():
    paths.ensure_dirs()
    for d in paths.ALL_DATA_DIRS:
        assert d.exists(), f"{d} manquant"


def test_logs_inside_data():
    assert paths.LOGS.parent == paths.DATA
