"""Tests d'import LEGI indépendants du réseau et du corpus de production."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest

from scripts.preparer_legi_dila import (
    apply_deletions, audit_source_conflicts, audit_source_quality, canonical_path, coverage_report, deletion_lists,
    ingest_archive, open_database, store_document, stream_members,
)
from beaume.adapters.source_dila_legi import discover
from beaume.adapters import source_dila_legi as acquisition


def make_archive(path: Path, members: dict[str, bytes]):
    with tarfile.open(path, "w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    data = path.read_bytes()
    return {"name": path.name, "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "kind": "delta", "timestamp": "20261019-211152"}


def article(ident="LEGIARTI000000000001", numero="L1", text="Texte officiel", **kwargs):
    return {"root": "ARTICLE", "article_id": ident, "code": "LEGITEXT000000000001",
            "numero": numero, "date_debut": "2020-01-01", "date_fin": "2999-01-01",
            "statut": "VIGUEUR", "texte": text, "dtd_valid": True, **kwargs}


@pytest.fixture
def database(tmp_path):
    db = open_database(tmp_path / "corpus.sqlite")
    yield db
    db.close()


def test_manifest_selects_latest_stock_and_all_later_deltas():
    names = ["Freemium_legi_global_20250713-140000.tar.gz", "Freemium_legi_global_20240101-120000.tar.gz",
             "LEGI_20250712-220000.tar.gz", "LEGI_20250713-205013.tar.gz",
             "LEGI_20261015-205000.tar.gz", "LEGI_20261015-215000.tar.gz"]
    result = discover("".join(f'<a href="{name}">{name}</a>' for name in names))
    assert [r.name for r in result] == [names[0], *names[3:]]


def test_paths_are_normalized_without_filesystem_extraction():
    assert canonical_path("20261019-211152/legi/a.xml") == "legi/a.xml"
    for path in ("../outside.xml", "/etc/passwd", "legi/../../outside.xml", "legi\\bad.xml"):
        with pytest.raises(ValueError):
            canonical_path(path)


def test_deletions_apply_by_path_and_preserve_other_id_occurrence(database):
    a = article()
    for path in ("legi/ancien/a.xml", "legi/autre/a.xml"):
        store_document(database, path, "LEGI_20261018-200000.tar.gz", b"XML", a)
    count = apply_deletions(database, "delta", [("legi/ancien/a.xml", False)])
    assert count == 1
    assert database.execute("SELECT path FROM articles_source").fetchall() == [("legi/autre/a.xml",)]
    assert database.execute("SELECT COUNT(*) FROM versions_articles").fetchone()[0] == 1


def test_directory_delete_uses_prefix_without_like_wildcards(database):
    for path in ("legi/code_A/a.xml", "legi/codeXA/a.xml", "legi/code_AA/a.xml"):
        store_document(database, path, "stock", b"XML", article())
    assert apply_deletions(database, "delta", [("legi/code_A", True)]) == 1
    assert database.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2


def test_deletion_files_have_no_xml_extension_and_directory_marker(tmp_path):
    path = tmp_path / "delta.tar.gz"
    make_archive(path, {"20261019-211152/liste_suppression_legi.dat": b"legi/old/LEGIARTI000000000001\n",
                        "20261019-211152/liste_suppression_legi_dossier.dat": b"legi/old_folder D\n"})
    assert deletion_lists(path) == [("legi/old/LEGIARTI000000000001.xml", False), ("legi/old_folder", True)]


def test_newer_occurrence_wins_without_merging_numbers(database):
    store_document(database, "legi/old/a.xml", "Freemium_legi_global_20250713-140000.tar.gz", b"a", article(numero="L1"))
    store_document(database, "legi/new/a.xml", "LEGI_20261019-211152.tar.gz", b"b", article(numero="L2"))
    assert database.execute("SELECT numero FROM versions_articles").fetchone() == ("L2",)


def test_ingestion_moves_article_and_is_idempotent(database, tmp_path):
    ident = "LEGIARTI000000000001"
    old = f"legi/vigueur/{ident}.xml"
    store_document(database, old, "stock", b"old", article(ident))
    database.commit()
    path = tmp_path / "LEGI_20261019-211152.tar.gz"
    entry = make_archive(path, {"20261019-211152/liste_suppression_legi.dat": f"{old[:-4]}\n".encode(),
                               f"20261019-211152/legi/abroge/{ident}.xml": b"new"})
    class Parser:
        def parse(self, data):
            return article(ident, statut="ABROGE")
    result = ingest_archive(database, entry, tmp_path, Parser(), tmp_path)
    assert result["documents_supprimes"] == 1
    assert database.execute("SELECT statut FROM versions_articles").fetchone() == ("ABROGE",)
    ingest_archive(database, entry, tmp_path, Parser(), tmp_path)
    assert database.execute("SELECT COUNT(*) FROM archives").fetchone()[0] == 1


def test_corrupt_gzip_trailer_is_not_accepted(tmp_path):
    path = tmp_path / "bad.tar.gz"
    make_archive(path, {"legi/a.xml": b"test"})
    data = bytearray(path.read_bytes())
    data[-8] ^= 255
    path.write_bytes(data)
    with pytest.raises((gzip.BadGzipFile, EOFError, tarfile.ReadError)):
        for _, stream in stream_members(path):
            stream.read()


def test_families_use_explicit_links_and_keep_renumbering(database, tmp_path):
    ids = [f"LEGIARTI{i:012d}" for i in range(1, 4)]
    for i, ident in enumerate(ids):
        # First two explicitly linked despite different numbers; third same number, unrelated.
        links = [{"article_id": ids[0]}, {"article_id": ids[1]}] if i < 2 else []
        store_document(database, f"legi/{ident}.xml", "stock", b"XML", article(ident, numero="L1" if i != 1 else "L2", versions=links))
    (tmp_path / "reports").mkdir()
    manifest = {"archives": [{"name": "stock"}], "licence": "LO2", "attribution": "DILA"}
    report = coverage_report(database, manifest, tmp_path)
    assert report["versions_articles_distinctes"] == 3
    assert report["familles_calculees_liens_versions"] == 2
    assert report["statut_collecte"] == "INCOMPLETE"
    assert report["autorisation_import_production"] is False
    assert report["pret_entrainement_supervise"] is False
    assert json.loads((tmp_path / "reports/couverture.json").read_text())["distribution_statuts"] == {"VIGUEUR": 3}


def test_xml_failure_is_quarantined_and_excluded(database, tmp_path):
    from beaume.adapters.dila_xml import DilaXMLInvalide
    path = tmp_path / "LEGI_20261019-211152.tar.gz"
    entry = make_archive(path, {"legi/bad.xml": b"<bad>"})
    class Parser:
        def parse(self, data):
            raise DilaXMLInvalide("malformed")
    result = ingest_archive(database, entry, tmp_path, Parser(), tmp_path)
    assert result["xml_rejetes"] == 1
    assert len(list((tmp_path / "quarantine").glob("*.xml"))) == 1
    assert database.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0


def test_rejected_replacement_does_not_leave_an_obsolete_version(database, tmp_path):
    from beaume.adapters.dila_xml import DilaXMLInvalide
    member = "legi/a.xml"
    store_document(database, member, "stock", b"old", article())
    database.commit()
    path = tmp_path / "LEGI_20261019-211152.tar.gz"
    entry = make_archive(path, {member: b"<broken>"})
    class Parser:
        def parse(self, data):
            raise DilaXMLInvalide("malformed")
    ingest_archive(database, entry, tmp_path, Parser(), tmp_path)
    assert database.execute("SELECT COUNT(*) FROM versions_articles").fetchone()[0] == 0


def test_missing_jorf_reference_is_not_a_missing_legi_version(database, tmp_path):
    store_document(database, "legi/a.xml", "stock", b"xml", article(versions=[
        {"article_id": "JORFARTI000000000001"}, {"article_id": "LEGIARTI000000000099"}]))
    (tmp_path / "reports").mkdir()
    report = coverage_report(database, {"archives": [{"name": "stock"}], "licence": "LO2", "attribution": "DILA"}, tmp_path)
    assert report["references_versions_legi_absentes"] == 1
    assert report["references_versions_jorf_externes"] == 1


def test_article_id_is_checked_independently_of_dtd(database):
    with pytest.raises(ValueError, match="Identifiant ARTICLE"):
        store_document(database, "legi/a.xml", "stock", b"xml", article(ident="L1233-3"))


def test_code_catalogue_uses_version_title_instead_of_empty_structure(database):
    store_document(database, "legi/texte/struct/code.xml", "stock", b"struct", {
        "root": "TEXTELR", "id": "LEGITEXT000000000001", "cid": "LEGITEXT000000000001", "nature": "CODE", "titre": ""})
    store_document(database, "legi/texte/version/code.xml", "stock", b"version", {
        "root": "TEXTE_VERSION", "id": "LEGITEXT000000000001", "cid": "LEGITEXT000000000001", "nature": "CODE", "titre": "Code exemple"})
    assert database.execute("SELECT code,titre FROM codes_metadata").fetchall() == [("LEGITEXT000000000001", "Code exemple")]


@pytest.mark.parametrize("content,has_text", [(" ", 0), ("Texte à revoir", 1)])
def test_quality_audit_reports_missing_metadata_and_editor_markers_without_repair(database, tmp_path, content, has_text):
    ident = "LEGIARTI000000000001"
    store_document(database, f"legi/{ident}.xml", "stock", b"source", article(
        ident, statut="", dtd_valid=False,
        dtd_errors=["DTD_MISSING_ATTRIBUTE: Element TEXTE does not carry attribute cid"],
        contenu_xml=f'<CONTENU><table><tr _delete="true"><td>{content}</td></tr></table></CONTENU>'))
    (tmp_path / "reports").mkdir()
    result = audit_source_quality(database, tmp_path)
    assert result["champs_vides_ou_absents"]["statut"] == 1
    assert result["versions_champs_requis_vides_ou_absents"] == 1
    assert result["identifiants_divergents_du_nom_fichier"] == 0
    assert len(result["contextes_sans_attributs_requis"]) == 1
    assert result["documents_non_conformes_dtd_par_racine"] == {"ARTICLE": 1}
    assert result["elements_editeur_delete_true"] == 1
    assert result["elements_editeur_delete_true_avec_texte"] == has_text
    assert result["validation_juridique"] is False
    assert database.execute("SELECT statut FROM articles_source").fetchone()[0] == ""


def test_empty_eli_alias_does_not_count_as_rejected_legal_content(database, tmp_path):
    database.execute("INSERT INTO archives VALUES(?,?,?,?,?,?)", ("stock", "20250713-140000", "hash", 1, "date", "{}"))
    database.execute("INSERT INTO anomalies VALUES(?,?,?,?)", ("stock", "legi/global/eli/decret/2000/1/1/texte/versions.xml", "DilaXMLInvalide", "Document is empty, line 1, column 1"))
    (tmp_path / "reports").mkdir()
    report = coverage_report(database, {"archives": [{"name": "stock", "sha256": "hash"}], "licence": "LO2", "attribution": "DILA"}, tmp_path)
    assert report["statut_collecte"] == "COMPLETE"
    assert report["alias_eli_vides"] == 1
    assert report["statut_parsing_contenu"] == "COMPLET"
    assert report["autorisation_import_production"] is False


def test_coverage_checks_archive_identity_and_digest_not_just_count(database, tmp_path):
    database.execute("INSERT INTO archives VALUES(?,?,?,?,?,?)", ("stock", "20250713-140000", "wrong", 1, "date", "{}"))
    (tmp_path / "reports").mkdir()
    report = coverage_report(database, {"archives": [{"name": "stock", "sha256": "expected"}], "licence": "LO2", "attribution": "DILA"}, tmp_path)
    assert report["statut_collecte"] == "INCOMPLETE"
    assert report["archives_empreinte_incorrecte"] == ["stock"]


@pytest.mark.parametrize("start,end,expected", [
    ("2020-02-30", "2999-01-01", 1),
    ("20200101", "2999-01-01", 1),
    ("2022-01-01", "2021-12-31", 1),
    ("2020-02-29", "2999-01-01", 0),
])
def test_report_checks_strict_calendar_dates_without_rewriting_them(database, tmp_path, start, end, expected):
    store_document(database, "legi/a.xml", "stock", b"XML", article(date_debut=start, date_fin=end))
    (tmp_path / "reports").mkdir()
    result = coverage_report(database, {"archives": [{"name": "stock"}], "licence": "LO2", "attribution": "DILA"}, tmp_path)
    assert result["dates_anormales"] == expected
    assert database.execute("SELECT date_debut FROM articles_source").fetchone()[0] == start


def test_conflicting_copies_are_counted_on_source_rows(database, tmp_path):
    store_document(database, "legi/old/a.xml", "stock", b"old", article(text="Version ancienne"))
    store_document(database, "legi/new/a.xml", "LEGI_20261019-211152.tar.gz", b"new", article(text="Version nouvelle"))
    (tmp_path / "reports").mkdir()
    result = coverage_report(database, {"archives": [{"name": "stock"}], "licence": "LO2", "attribution": "DILA"}, tmp_path)
    assert result["identifiants_contenus_divergents"] == 1
    assert result["versions_articles_distinctes"] == 1


@pytest.mark.parametrize("same_archive", [False, True])
def test_conflict_audit_distinguishes_old_copies_from_latest_ties(database, tmp_path, same_archive):
    latest = "LEGI_20261019-211152.tar.gz"
    old = latest if same_archive else "Freemium_legi_global_20250713-140000.tar.gz"
    store_document(database, "legi/old/a.xml", old, b"old", article(text="Version ancienne"))
    store_document(database, "legi/new/a.xml", latest, b"new", article(text="Version nouvelle"))
    (tmp_path / "reports").mkdir()
    result = audit_source_conflicts(database, tmp_path)
    assert result["identifiants_plusieurs_chemins"] == 1
    assert result["identifiants_divergents"] == 1
    assert result["identifiants_ambigus_dans_archive_la_plus_recente"] == int(same_archive)
    record = json.loads((tmp_path / "reports/conflits_sources.jsonl").read_text())
    assert record["champs_divergents"] == ["texte_sha256"]
    assert len(record["copies"]) == 2


def test_identical_copies_are_not_reported_as_conflicting(database, tmp_path):
    for path in ("legi/a.xml", "legi/b.xml"):
        store_document(database, path, "stock", b"same", article())
    (tmp_path / "reports").mkdir()
    result = audit_source_conflicts(database, tmp_path)
    assert result["identifiants_plusieurs_chemins"] == 1
    assert result["identifiants_divergents"] == 0
    assert (tmp_path / "reports/conflits_sources.jsonl").read_text() == ""


def test_exclusion_view_requires_current_audit_and_never_changes_raw_sources(database, tmp_path):
    store_document(database, "legi/a.xml", "stock", b"a", article(text="Ancien"))
    store_document(database, "legi/b.xml", "stock", b"b", article(text="Nouveau"))
    store_document(database, "legi/c.xml", "stock", b"c", article(ident="LEGIARTI000000000002"))
    database.commit()
    assert database.execute("SELECT COUNT(*) FROM versions_articles_sans_conflit_source").fetchone()[0] == 0
    (tmp_path / "reports").mkdir()
    audit_source_conflicts(database, tmp_path)
    assert database.execute("SELECT article_id FROM versions_articles_sans_conflit_source").fetchall() == [("LEGIARTI000000000002",)]
    assert database.execute("SELECT COUNT(*) FROM articles_source").fetchone()[0] == 3
    path = tmp_path / "LEGI_20261019-211152.tar.gz"
    entry = make_archive(path, {})
    class Parser:
        def parse(self, data):
            return article()
    ingest_archive(database, entry, tmp_path, Parser(), tmp_path)
    assert database.execute("SELECT COUNT(*) FROM versions_articles_sans_conflit_source").fetchone()[0] == 0


@pytest.mark.parametrize("compatible", [True, False])
def test_unchanged_xml_reuse_requires_same_parser(database, tmp_path, compatible):
    from scripts.preparer_legi_dila import json_text
    class Parser:
        calls = 0
        def parse(self, data):
            self.calls += 1
            return article()
    parser = Parser()
    first = make_archive(tmp_path / "LEGI_20261018-211152.tar.gz", {"legi/a.xml": b"same XML"})
    ingest_archive(database, first, tmp_path, parser, tmp_path)
    if not compatible:
        database.execute("UPDATE archives SET counts_json=? WHERE name=?", (json_text({"parseur_sha256": "other"}), first["name"]))
        database.commit()
    second = make_archive(tmp_path / "LEGI_20261019-211152.tar.gz", {"legi/a.xml": b"same XML"})
    result = ingest_archive(database, second, tmp_path, parser, tmp_path)
    assert parser.calls == (1 if compatible else 2)
    assert result.get("xml_inchanges_reutilises", 0) == int(compatible)
    assert database.execute("SELECT archive FROM documents").fetchone()[0] == second["name"]


def test_corrupt_archive_rolls_back_all_its_documents(database, tmp_path):
    path = tmp_path / "LEGI_20261019-211152.tar.gz"
    make_archive(path, {"legi/a.xml": b"XML"})
    data = bytearray(path.read_bytes())
    data[-8] ^= 255
    path.write_bytes(data)
    entry = {"name": path.name, "timestamp": "20261019-211152", "kind": "stock", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    class Parser:
        def parse(self, data):
            return article()
    with pytest.raises((gzip.BadGzipFile, EOFError, tarfile.ReadError)):
        ingest_archive(database, entry, tmp_path, Parser(), tmp_path)
    assert database.execute("SELECT COUNT(*) FROM archives").fetchone()[0] == 0
    assert database.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0


class HTTPResponse(io.BytesIO):
    def __init__(self, data, status, headers):
        super().__init__(data)
        self.status, self.headers = status, headers


@pytest.fixture
def publication():
    name = "LEGI_20261019-211152.tar.gz"
    return acquisition.Archive(name, acquisition.INDEX_URL + name, "delta", "20261019-211152")


def prepare_partial(tmp_path, archive, validated=True):
    part = tmp_path / (archive.name + ".part")
    part.write_bytes(b"abc")
    if validated:
        (tmp_path / (archive.name + ".part.json")).write_text(json.dumps({"url": archive.url, "etag": '"v1"', "expected_bytes": 6}))
    return part


def test_download_resumes_206_and_reuses_verified_file(tmp_path, monkeypatch, publication):
    part = prepare_partial(tmp_path, publication)
    calls = []
    def request(url, **kwargs):
        calls.append(kwargs)
        return HTTPResponse(b"def", 206, {"Content-Length": "3", "Content-Range": "bytes 3-5/6", "ETag": '"v1"'})
    monkeypatch.setattr(acquisition, "_request", request)
    metadata = acquisition.download_archive(publication, tmp_path, retries=1)
    assert (tmp_path / publication.name).read_bytes() == b"abcdef"
    assert metadata["sha256"] == hashlib.sha256(b"abcdef").hexdigest()
    assert calls[0]["headers"] == {"Range": "bytes=3-", "If-Range": '"v1"'}
    assert not part.exists()
    assert json.loads((tmp_path / (publication.name + ".metadata.json")).read_text()) == metadata
    def forbidden(*args, **kwargs):
        pytest.fail("Verified local archive must not require network")
    monkeypatch.setattr(acquisition, "_request", forbidden)
    assert acquisition.download_archive(publication, tmp_path) == metadata


def test_download_200_truncates_before_publishing_new_validator(tmp_path, monkeypatch, publication):
    part = prepare_partial(tmp_path, publication)
    before_metadata = []
    original = acquisition._atomic_json
    def atomic(path, value):
        if path.name.endswith(".part.json"):
            before_metadata.append(part.read_bytes())
        original(path, value)
    monkeypatch.setattr(acquisition, "_atomic_json", atomic)
    monkeypatch.setattr(acquisition, "_request", lambda *a, **kw: HTTPResponse(b"new", 200, {"Content-Length": "3", "ETag": '"v2"'}))
    metadata = acquisition.download_archive(publication, tmp_path, retries=1)
    assert (tmp_path / publication.name).read_bytes() == b"new"
    assert metadata["etag"] == '"v2"'
    assert before_metadata == [b""]


def test_partial_without_validator_starts_over(tmp_path, monkeypatch, publication):
    prepare_partial(tmp_path, publication, validated=False)
    calls = []
    def request(*a, **kwargs):
        calls.append(kwargs)
        return HTTPResponse(b"new", 200, {"Content-Length": "3"})
    monkeypatch.setattr(acquisition, "_request", request)
    acquisition.download_archive(publication, tmp_path, retries=1)
    assert calls[0]["headers"] == {}
    assert (tmp_path / publication.name).read_bytes() == b"new"


@pytest.mark.parametrize("headers", [
    {"Content-Length": "3", "Content-Range": "bytes 2-4/6", "ETag": '"v1"'},
    {"Content-Length": "2", "Content-Range": "bytes 3-5/6", "ETag": '"v1"'},
    {"Content-Length": "3", "Content-Range": "bytes 3-5/6", "ETag": '"v2"'},
    {"Content-Length": "3", "ETag": '"v1"'},
])
def test_invalid_206_does_not_change_partial(tmp_path, monkeypatch, publication, headers):
    part = prepare_partial(tmp_path, publication)
    monkeypatch.setattr(acquisition, "_request", lambda *a, **kw: HTTPResponse(b"def", 206, headers))
    with pytest.raises(ValueError):
        acquisition.download_archive(publication, tmp_path, retries=1)
    assert part.read_bytes() == b"abc"
    assert not (tmp_path / publication.name).exists()


def test_incomplete_transfer_is_not_published(tmp_path, monkeypatch, publication):
    monkeypatch.setattr(acquisition, "_request", lambda *a, **kw: HTTPResponse(b"abc", 200, {"Content-Length": "6", "ETag": '"v1"'}))
    with pytest.raises(RuntimeError):
        acquisition.download_archive(publication, tmp_path, retries=1)
    assert not (tmp_path / publication.name).exists()


def test_modified_local_archive_is_rejected(tmp_path, monkeypatch, publication):
    (tmp_path / publication.name).write_bytes(b"modified")
    (tmp_path / (publication.name + ".metadata.json")).write_text(json.dumps({**publication.to_dict(), "bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}))
    with pytest.raises(ValueError, match="Archive locale modifiée"):
        acquisition.download_archive(publication, tmp_path)


@pytest.mark.parametrize("html", ["", "<html>Unavailable</html>", '<a href="LEGI_20261019-211152.tar.gz">delta</a>', '<a href="../Freemium_legi_global_20250713-140000.tar.gz">bad</a>'])
def test_index_without_stock_is_rejected(html):
    with pytest.raises(ValueError, match="Aucun stock"):
        discover(html)


@pytest.mark.parametrize("etag,modified,expected", [('"strong"', None, '"strong"'), ('W/"weak"', None, None), ('W/"weak"', "Mon, 19 Oct 2026 00:00:00 GMT", "Mon, 19 Oct 2026 00:00:00 GMT")])
def test_weak_etag_is_not_used_for_if_range(etag, modified, expected):
    assert acquisition._validator({"etag": etag, "last_modified": modified}) == expected
