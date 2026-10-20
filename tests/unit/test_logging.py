from beaume.utils.logging import get_logger


def test_logger_writes():
    log = get_logger("test_unit")
    log.info("message de test")
    log_file = log.handlers[0].baseFilename
    with open(log_file, encoding="utf-8") as f:
        content = f.read()
    assert "message de test" in content


def test_entree_cli_ne_journalise_pas_le_chemin_du_dossier_client(tmp_path, caplog):
    from scripts.analyser_dossier import main

    chemin_client = tmp_path / "dossier-client-confidentiel" / "absent"

    assert main(str(chemin_client), None) == 1

    assert str(chemin_client.resolve()) not in caplog.text
    assert "Dossier introuvable" in caplog.text
