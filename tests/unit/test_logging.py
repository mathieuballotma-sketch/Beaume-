from beaume.utils.logging import get_logger


def test_logger_writes():
    log = get_logger("test_unit")
    log.info("message de test")
    log_file = log.handlers[0].baseFilename
    with open(log_file, encoding="utf-8") as f:
        content = f.read()
    assert "message de test" in content
