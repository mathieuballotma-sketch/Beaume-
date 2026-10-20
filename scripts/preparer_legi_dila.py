#!/usr/bin/env python3
"""Acquisition LEGI reproductible, isolée du dépôt de production.

Les fichiers DILA sont indexés par chemin : une suppression peut être un
déplacement et ne doit jamais supprimer aveuglément toutes les occurrences ID.
Les numéros et dates sont conservés tels que publiés ; aucune règle temporelle
de production n'est inventée ici.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import sys
import tarfile
import time
from urllib.request import Request, urlopen

from beaume.adapters.dila_xml import DilaParser, DilaXMLInvalide
from beaume.adapters.source_dila_legi import Archive, discover, download_archive, fetch_index

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT / "data/vector/legi_dila_v2"
BASE_URL = "https://echanges.dila.gouv.fr/OPENDATA/LEGI/"
DTD_URL = "https://echanges.dila.gouv.fr/OPENDATA/DTD_LEGIFRANCE/DTD_LEGIFRANCE_20181017.7z"
SCHEMA_VERSION = 1
MAX_MEMBER_BYTES = 64 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare_dtd(output: Path, manifest: dict) -> Path:
    """Acquire the official definition once and freeze every effective DTD file."""
    directory = output / "dtd"
    directory.mkdir(exist_ok=True)
    archive = directory / "DTD_LEGIFRANCE_20181017.7z"
    if not archive.exists():
        with urlopen(Request(DTD_URL, headers={"User-Agent": "Beaume-LEGI/1.0"}), timeout=120) as response:
            if not response.geturl().startswith("https://echanges.dila.gouv.fr/"):
                raise ValueError("Redirection DTD hors DILA")
            data = response.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("Archive DTD anormalement volumineuse")
            expected = response.headers.get("Content-Length")
            if expected and int(expected) != len(data):
                raise ValueError("Archive DTD incomplète")
        temporary = archive.with_suffix(".part")
        temporary.write_bytes(data)
        temporary.replace(archive)
    candidates = list(directory.glob("**/legi/legi_article.dtd"))
    if not candidates:
        listing = subprocess.run(["/usr/bin/tar", "-tf", str(archive)], check=True, capture_output=True, text=True)
        for name in listing.stdout.splitlines():
            canonical_path(name)
        subprocess.run(["/usr/bin/tar", "-xf", str(archive), "-C", str(directory)], check=True, capture_output=True)
        candidates = list(directory.glob("**/legi/legi_article.dtd"))
    if len(candidates) != 1:
        raise ValueError("DTD LEGI absente ou ambiguë après extraction")
    legi = candidates[0].parent
    source = {"url": DTD_URL, "archive_sha256": sha256(archive),
              "fichiers": {p.name: sha256(p) for p in sorted(legi.iterdir()) if p.suffix in {".dtd", ".ent"}}}
    if manifest.get("dtd") and manifest["dtd"] != source:
        raise ValueError("Les DTD ont changé depuis le manifeste figé")
    manifest["dtd"] = source
    write_json(output / "manifest.json", manifest)
    # Fail before downloading gigabytes if DTD compilation itself is impossible.
    DilaParser(legi)
    return legi


def canonical_path(name: str) -> str:
    """Remove only the dated package prefix; never resolve archive paths on disk."""
    if "\\" in name:
        raise ValueError("Chemin archive avec antislash")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Chemin archive non relatif")
    parts = list(path.parts)
    if parts and re.fullmatch(r"\d{8}-\d{6}", parts[0]):
        parts.pop(0)
    while parts and parts[0] == ".":
        parts.pop(0)
    return "/".join(parts)


def open_database(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA temp_store=MEMORY")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS archives(
        name TEXT PRIMARY KEY, timestamp TEXT NOT NULL, sha256 TEXT NOT NULL,
        bytes INTEGER NOT NULL, applied_at TEXT NOT NULL, counts_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS documents(
        path TEXT PRIMARY KEY, root TEXT NOT NULL, document_id TEXT,
        archive TEXT NOT NULL, source_sha256 TEXT NOT NULL, dtd_valid INTEGER,
        dtd_errors_json TEXT NOT NULL, warnings_json TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS documents_id ON documents(document_id);
      CREATE TABLE IF NOT EXISTS articles_source(
        path TEXT PRIMARY KEY REFERENCES documents(path) ON DELETE CASCADE,
        article_id TEXT NOT NULL, code TEXT, texte_id TEXT, nature TEXT,
        titre TEXT, numero TEXT, date_debut TEXT, date_fin TEXT, statut TEXT,
        texte TEXT NOT NULL, contenu_xml TEXT, nota TEXT,
        versions_json TEXT NOT NULL, liens_json TEXT NOT NULL, contexte_json TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS articles_source_id ON articles_source(article_id);
      CREATE TABLE IF NOT EXISTS textes_source(
        path TEXT PRIMARY KEY REFERENCES documents(path) ON DELETE CASCADE,
        document_id TEXT, cid TEXT, nature TEXT, titre TEXT, metadata_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS anomalies(
        archive TEXT NOT NULL, path TEXT NOT NULL, type TEXT NOT NULL, detail TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS suppressions(
        archive TEXT NOT NULL, path TEXT NOT NULL, dossier INTEGER NOT NULL, deleted INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS familles(
        article_id TEXT PRIMARY KEY, famille_id TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS conflits_articles_source(
        article_id TEXT PRIMARY KEY, ambiguite_derniere_archive INTEGER NOT NULL,
        champs_divergents_json TEXT NOT NULL);
      CREATE VIEW IF NOT EXISTS versions_articles AS
      SELECT a.article_id,a.code,a.numero,a.date_debut,a.date_fin,a.statut,a.texte,
             a.texte_id,a.nature,a.titre,a.contenu_xml,a.nota,a.versions_json,
             a.liens_json,a.contexte_json,d.archive AS source_archive,
             d.path AS source_path,d.source_sha256,d.dtd_valid,d.dtd_errors_json,d.warnings_json,
             f.famille_id AS article_famille_id
      FROM articles_source a JOIN documents d ON a.path=d.path
      LEFT JOIN familles f ON a.article_id=f.article_id
      WHERE a.path=(SELECT b.path FROM articles_source b JOIN documents e ON b.path=e.path
                    WHERE b.article_id=a.article_id ORDER BY e.archive DESC,b.path ASC LIMIT 1);
      CREATE VIEW IF NOT EXISTS codes_metadata AS
      SELECT t.cid AS code,t.document_id,t.titre,d.archive AS source_archive,
             t.path AS source_path,t.metadata_json
      FROM textes_source t JOIN documents d ON t.path=d.path
      WHERE d.root='TEXTE_VERSION' AND t.nature='CODE' AND t.cid LIKE 'LEGITEXT%';
      CREATE VIEW IF NOT EXISTS versions_articles_sans_conflit_source AS
      SELECT v.* FROM versions_articles v
      WHERE EXISTS(SELECT 1 FROM metadata WHERE key='audit_conflits_source')
      AND NOT EXISTS(SELECT 1 FROM conflits_articles_source c WHERE c.article_id=v.article_id);
    """)
    existing = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
    if existing and existing[0] != str(SCHEMA_VERSION):
        raise ValueError("Version de schéma inconnue ; choisir un autre répertoire de sortie")
    db.execute("INSERT OR IGNORE INTO metadata VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
    db.commit()
    return db


def stream_members(path: Path):
    """Stream tar safely, including the gzip trailer/CRC, without filesystem extraction."""
    with gzip.open(path, "rb") as gz:
        with tarfile.open(fileobj=gz, mode="r|") as archive:
            for member in archive:
                # Python 3.12 retains TarInfo objects even in streaming mode.
                # extractfile(member) needs no previous members or name lookup.
                archive.members.clear()
                if not member.isfile():
                    continue
                canonical = canonical_path(member.name)
                if member.size > MAX_MEMBER_BYTES:
                    raise ValueError(f"Membre trop volumineux : {canonical} ({member.size})")
                yield canonical, archive.extractfile(member)
        # tar readers may stop at zero blocks before reaching the gzip trailer.
        while gz.read(1024 * 1024):
            pass


def deletion_lists(path: Path) -> list[tuple[str, bool]]:
    results = []
    manifests_seen = set()
    for name, stream in stream_members(path):
        if not (name.endswith("liste_suppression_legi.dat") or
                name.endswith("liste_suppression_legi_dossier.dat")):
            continue
        folder = name.endswith("_dossier.dat")
        manifests_seen.add(folder)
        for line in stream.read().decode("utf-8-sig").splitlines():
            line = line.strip()
            if not line:
                continue
            if folder:
                if not line.endswith(" D"):
                    raise ValueError(f"Suppression dossier non reconnue : {line}")
                line = line[:-2].rstrip()
            clean = canonical_path(line)
            if not clean.startswith("legi/"):
                raise ValueError(f"Suppression hors racine legi : {clean}")
            if not folder and not clean.endswith(".xml"):
                clean += ".xml"
            results.append((clean, folder))
        # The subsequent ingestion pass still validates the full gzip CRC.
        if manifests_seen == {False, True}:
            break
    return results


def apply_deletions(db: sqlite3.Connection, archive: str, deletions) -> int:
    removed = 0
    for path, folder in deletions:
        if folder:
            # Lexicographic prefix range avoids SQL LIKE wildcard semantics.
            prefix = path.rstrip("/") + "/"
            cursor = db.execute("DELETE FROM documents WHERE path>=? AND path<?", (prefix, prefix + "\uffff"))
        else:
            cursor = db.execute("DELETE FROM documents WHERE path=?", (path,))
        count = cursor.rowcount
        db.execute("INSERT INTO suppressions VALUES(?,?,?,?)", (archive, path, int(folder), count))
        removed += count
    return removed


def store_document(db: sqlite3.Connection, name: str, archive: str, data: bytes, obj: dict) -> None:
    root = obj["root"]
    ident = obj.get("article_id") if root == "ARTICLE" else obj.get("id")
    if not ident:
        ident = PurePosixPath(name).stem
    if root == "ARTICLE" and not re.fullmatch(r"LEGIARTI\d{12}", ident):
        raise ValueError(f"Identifiant ARTICLE LEGI invalide : {ident}")
    db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET "
               "root=excluded.root,document_id=excluded.document_id,archive=excluded.archive,"
               "source_sha256=excluded.source_sha256,dtd_valid=excluded.dtd_valid,dtd_errors_json=excluded.dtd_errors_json,warnings_json=excluded.warnings_json",
               (name, root, ident, archive, hashlib.sha256(data).hexdigest(), obj.get("dtd_valid"), json_text(obj.get("dtd_errors", [])), json_text(obj.get("fragment_errors", []))))
    if root == "ARTICLE":
        keys = ("article_id", "code", "texte_id", "nature", "titre", "numero", "date_debut", "date_fin", "statut", "texte", "contenu_xml", "nota")
        values = [obj.get(key) for key in keys]
        values[9] = values[9] or ""
        db.execute("INSERT OR REPLACE INTO articles_source VALUES(" + ",".join(["?"] * 16) + ")",
                   [name, *values, json_text(obj.get("versions", [])), json_text(obj.get("liens", [])), json_text(obj.get("contexte", {}))])
    elif root in {"TEXTE_VERSION", "TEXTELR", "SECTION_TA"}:
        db.execute("INSERT OR REPLACE INTO textes_source VALUES(?,?,?,?,?,?)",
                   (name, ident, obj.get("cid"), obj.get("nature"), obj.get("titre"), json_text(obj)))


def ingest_archive(db: sqlite3.Connection, entry: dict, raw_dir: Path, parser: DilaParser, output: Path) -> dict:
    name = entry["name"]
    previous = db.execute("SELECT sha256,counts_json FROM archives WHERE name=?", (name,)).fetchone()
    if previous:
        if previous[0] != entry["sha256"]:
            raise ValueError(f"Archive déjà appliquée avec une empreinte différente : {name}")
        return json.loads(previous[1])
    path = raw_dir / name
    # Do not trust a previously saved manifest if local bytes were changed.
    if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
        raise ValueError(f"Empreinte archive incorrecte : {name}")
    counts: Counter = Counter()
    roots: Counter = Counter()
    parser_hash = sha256(PROJECT / "beaume/adapters/dila_xml.py")
    collector_hash = sha256(Path(__file__))
    compatible_archives = {
        row[0] for row in db.execute("SELECT name,counts_json FROM archives")
        if json.loads(row[1]).get("parseur_sha256") == parser_hash
    }
    start = time.monotonic()
    with db:
        # The exclusion view stays closed until conflicts are audited again.
        db.execute("DELETE FROM metadata WHERE key='audit_conflits_source'")
        if entry["kind"] == "delta":
            deletions = deletion_lists(path)
            counts["suppressions_recues"] = len(deletions)
            counts["documents_supprimes"] = apply_deletions(db, name, deletions)
        for member, stream in stream_members(path):
            if not member.endswith(".xml"):
                continue
            data = stream.read()
            try:
                if entry["kind"] == "delta":
                    existing = db.execute("SELECT root,source_sha256,archive FROM documents WHERE path=?", (member,)).fetchone()
                    if (existing and existing[2] in compatible_archives
                            and existing[1] == hashlib.sha256(data).hexdigest()):
                        db.execute("UPDATE documents SET archive=? WHERE path=?", (name, member))
                        roots[existing[0]] += 1
                        counts["xml_lus"] += 1
                        counts["xml_inchanges_reutilises"] += 1
                        continue
                obj = parser.parse(data)
                store_document(db, member, name, data, obj)
                roots[obj["root"]] += 1
                if obj.get("dtd_valid") is False:
                    counts["dtd_non_conformes"] += 1
            except (DilaXMLInvalide, ValueError) as exc:
                counts["xml_rejetes"] += 1
                # A rejected replacement must not expose an obsolete document
                # at the same path as if it had survived the new publication.
                db.execute("DELETE FROM documents WHERE path=?", (member,))
                digest = hashlib.sha256(data).hexdigest()
                quarantine = output / "quarantine"
                quarantine.mkdir(exist_ok=True)
                (quarantine / f"{digest}.xml").write_bytes(data)
                db.execute("INSERT INTO anomalies VALUES(?,?,?,?)", (name, member, type(exc).__name__, str(exc)[:4000]))
            counts["xml_lus"] += 1
            if counts["xml_lus"] % 50000 == 0:
                print(f"  {name}: {counts['xml_lus']:,} XML lus", flush=True)
        counts["secondes"] = round(time.monotonic() - start, 2)
        result = dict(counts, racines=dict(roots),
                      parseur_sha256=parser_hash, collecteur_sha256=collector_hash)
        db.execute("INSERT INTO archives VALUES(?,?,?,?,?,?)", (name, entry["timestamp"], entry["sha256"], entry["bytes"], utc_now(), json_text(result)))
    print(f"Appliqué {name}: {counts['xml_lus']:,} XML, {counts['xml_rejetes']} rejetés, {counts['secondes']} s", flush=True)
    return result


def calculate_families(db: sqlite3.Connection) -> dict:
    """Components of explicit DILA VERSIONS links, never of equal article numbers."""
    parents: dict[str, str] = {}
    def find(x):
        parents.setdefault(x, x)
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parents[max(a, b)] = min(a, b)
    missing = set()
    external = set()
    other = set()
    ids = {row[0] for row in db.execute("SELECT DISTINCT article_id FROM articles_source")}
    for ident, links_json in db.execute("SELECT article_id,versions_json FROM versions_articles"):
        find(ident)
        for link in json.loads(links_json):
            target = link.get("article_id")
            if target in ids:
                union(ident, target)
            elif target and target.startswith("LEGIARTI"):
                missing.add(target)
            elif target and target.startswith("JORFARTI"):
                external.add(target)
            elif target:
                other.add(target)
    with db:
        db.execute("DELETE FROM familles")
        db.executemany("INSERT INTO familles VALUES(?,?)", ((ident, find(ident)) for ident in sorted(ids)))
    return {"familles_calculees_liens_versions": len({find(ident) for ident in ids}),
            "references_versions_legi_absentes": len(missing),
            "references_versions_jorf_externes": len(external),
            "references_versions_autres": len(other),
            "exemples_references_legi_absentes": sorted(missing)[:30]}


def audit_source_quality(db: sqlite3.Connection, output: Path) -> dict:
    """Describe source defects without repairing or legally validating them."""
    from lxml import etree

    fields = ("numero", "statut", "date_debut", "date_fin", "nature", "texte_id", "titre", "texte")
    missing = {field: f"NULLIF(TRIM({field}),'') IS NULL" for field in fields}
    required = " OR ".join(missing[field] for field in fields[:4])
    aggregations = [f"COALESCE(SUM({missing[field]}),0)" for field in fields]
    row = db.execute("SELECT COUNT(*)," + ",".join(aggregations) +
                     f",COALESCE(SUM({required}),0),"
                     "COALESCE(SUM(nature='CODE' AND code IS NULL),0),"
                     "COALESCE(SUM(substr(source_path,-length(article_id)-4)!=article_id||'.xml'),0) "
                     "FROM versions_articles").fetchone()
    by_root: Counter = Counter()
    by_error: Counter = Counter()
    incomplete_context = []
    examples = []
    editor_rows = 0
    editor_rows_with_text = 0
    xml_parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    for path, root, ident, errors_json in db.execute(
            "SELECT path,root,document_id,dtd_errors_json FROM documents WHERE dtd_valid=0"):
        errors = json.loads(errors_json)
        by_root[root] += 1
        categories = {code for message in errors for code in re.findall(r"\bDTD_[A-Z_]+\b", message)}
        for category in categories or {"AUTRE"}:
            by_error[f"{root}:{category}"] += 1
        if any("Element TEXTE does not carry attribute" in message for message in errors):
            incomplete_context.append({"document_id": ident, "root": root, "source_path": path})
        if len(examples) < 20:
            examples.append({"document_id": ident, "root": root, "source_path": path, "diagnostics": errors[:3]})
        if root == "ARTICLE":
            content = db.execute("SELECT contenu_xml FROM articles_source WHERE path=?", (path,)).fetchone()
            if content and content[0] and "_delete=" in content[0]:
                fragment = etree.fromstring(content[0].encode("utf-8"), parser=xml_parser)
                for node in fragment.xpath("//*[@_delete]"):
                    if node.get("_delete", "").lower() == "true":
                        editor_rows += 1
                        if "".join(node.itertext()).strip():
                            editor_rows_with_text += 1
    result = {"generated_at": utc_now(), "statut": "A_AUDITER", "validation_juridique": False,
              "versions_examinees": row[0], "champs_vides_ou_absents": dict(zip(fields, row[1:9])),
              "versions_champs_requis_vides_ou_absents": row[9],
              "versions_nature_code_sans_id_code": row[10], "identifiants_divergents_du_nom_fichier": row[11],
              "documents_non_conformes_dtd_par_racine": dict(by_root),
              "classes_erreurs_dtd_par_document": dict(by_error),
              "contextes_sans_attributs_requis": incomplete_context,
              "exemples_diagnostics_dtd": examples,
              "elements_editeur_delete_true": editor_rows,
              "elements_editeur_delete_true_avec_texte": editor_rows_with_text,
              "limites": ["Les comptes portent sur le corpus présent après les mises à jour, pas sur la somme historique des imports.",
                          "Une valeur vide peut être présente telle quelle dans le XML officiel. Elle est signalée, jamais inventée.",
                          "Une non-conformité DTD peut concerner le XHTML ou des métadonnées réellement absentes. Elle n'est pas automatiquement attribuée à l'ancienneté de la DTD.",
                          "Ces contrôles techniques ne remplacent pas des annotations de pertinence et une validation juridique."]}
    write_json(output / "reports/qualite_sources.json", result)
    lines = ["# Qualité des sources DILA", "", "Statut : **à auditer**. Validation juridique : **non**.", "",
             f"Versions examinées : {row[0]:,}.", "", "## Champs vides ou absents", "",
             "| Champ | Versions |", "|---|---:|"]
    lines += [f"| {field} | {count:,} |" for field, count in result["champs_vides_ou_absents"].items()]
    lines += ["", f"Au moins un champ numéro/statut/date vide : {row[9]:,} versions.",
              f"Identifiant divergent du nom de fichier : {row[11]:,}.", "", "## Conformité DTD", ""]
    lines += [f"- {root} : {count:,} documents non conformes." for root, count in sorted(by_root.items())]
    lines += ["", f"Contextes sans attributs requis : {len(incomplete_context):,} documents.",
              f"Éléments `_delete=true` : {editor_rows}, dont {editor_rows_with_text} contenant du texte non blanc.",
              "", "Les détails et chemins sources figurent dans `qualite_sources.json`.", "", "## Limites", ""]
    lines += ["- " + item for item in result["limites"]]
    (output / "reports/QUALITE_SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def audit_source_conflicts(db: sqlite3.Connection, output: Path) -> dict:
    """Inspect competing copies; publication order is not a legal conclusion."""
    fields = ("code", "numero", "date_debut", "date_fin", "statut", "texte_sha256")
    changed: Counter = Counter()
    duplicates = divergent = latest_ties = 0
    flagged = []
    target = output / "reports/conflits_sources.jsonl"
    temporary = target.with_suffix(".jsonl.tmp")
    query = ("SELECT a.article_id,a.code,a.numero,a.date_debut,a.date_fin,a.statut,a.texte,d.archive,a.path "
             "FROM articles_source a JOIN documents d ON a.path=d.path "
             "WHERE a.article_id IN (SELECT article_id FROM articles_source GROUP BY article_id HAVING COUNT(*)>1) "
             "ORDER BY a.article_id,d.archive,a.path")
    current_id = None
    copies = []

    with temporary.open("w", encoding="utf-8") as stream:
        def record(ident, rows):
            nonlocal duplicates, divergent, latest_ties
            duplicates += 1
            different = [key for key in fields if len({row[key] for row in rows}) > 1]
            if not different:
                return
            divergent += 1
            changed.update(different)
            latest = max(row["source_archive"] for row in rows)
            recent = [row for row in rows if row["source_archive"] == latest]
            ambiguous = len({tuple(row[key] for key in fields) for row in recent}) > 1
            latest_ties += int(ambiguous)
            flagged.append((ident, int(ambiguous), json_text(different)))
            stream.write(json_text({"article_id": ident, "champs_divergents": different,
                                    "ambiguite_dans_archive_la_plus_recente": ambiguous,
                                    "copies": rows}) + "\n")
        for ident, code, number, start, end, status, text, archive, path in db.execute(query):
            if current_id is not None and current_id != ident:
                record(current_id, copies)
                copies = []
            current_id = ident
            copies.append({"code": code, "numero": number, "date_debut": start, "date_fin": end,
                           "statut": status, "texte_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                           "source_archive": archive, "source_path": path})
        if current_id is not None:
            record(current_id, copies)
    temporary.replace(target)
    archive_signature = hashlib.sha256(json_text(db.execute("SELECT name,sha256 FROM archives ORDER BY name").fetchall()).encode("utf-8")).hexdigest()
    with db:
        db.execute("DELETE FROM conflits_articles_source")
        db.executemany("INSERT INTO conflits_articles_source VALUES(?,?,?)", flagged)
        db.execute("INSERT OR REPLACE INTO metadata VALUES('audit_conflits_source',?)", (archive_signature,))
    result = {"generated_at": utc_now(), "identifiants_plusieurs_chemins": duplicates,
              "identifiants_divergents": divergent,
              "identifiants_ambigus_dans_archive_la_plus_recente": latest_ties,
              "identifiants_divergents_avec_derniere_valeur_unique": divergent - latest_ties,
              "champs_compares": list(fields), "champs_divergents": dict(changed), "details": target.name,
              "signature_archives": archive_signature,
              "vue_exclusion": "versions_articles_sans_conflit_source",
              "limite": "Une copie plus récente peut être une correction ou un changement de contexte ; l'ordre de publication ne prouve pas l'applicabilité juridique. Les égalités de priorité divergentes nécessitent une revue avant entraînement."}
    write_json(output / "reports/audit_conflits_sources.json", result)
    lines = ["# Copies sources divergentes", "",
             f"- Identifiants présents sur plusieurs chemins : {duplicates:,}.",
             f"- Identifiants aux valeurs divergentes : {divergent:,}.",
             f"- Dont plusieurs valeurs dans la dernière archive : {latest_ties:,}.",
             f"- Dont dernière valeur unique sur les champs comparés : {divergent - latest_ties:,}.", "",
             "Les chemins, archives, valeurs et empreintes de texte sont conservés dans `conflits_sources.jsonl`.", "",
             "## Exclusion automatique", "",
             "La vue `versions_articles_sans_conflit_source` exclut tous les identifiants divergents, sans supprimer les sources.",
             "Elle reste vide tant que l'audit n'a pas été exécuté. Un nouvel import la ferme jusqu'au prochain audit.",
             "Elle ne vérifie pas à elle seule les champs vides, les dates, la pertinence juridique ou les exemples d'entraînement.", "",
             result["limite"]]
    (output / "reports/CONFLITS_SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def coverage_report(db: sqlite3.Connection, manifest: dict, output: Path) -> dict:
    print("Rapport : regroupement des liens de versions", flush=True)
    family = calculate_families(db)
    scalar = lambda sql: db.execute(sql).fetchone()[0]
    print("Rapport : qualité des champs sources", flush=True)
    quality = audit_source_quality(db, output)
    versions = quality["versions_examinees"]
    print("Rapport : statuts et catalogue des codes", flush=True)
    statuses = dict(db.execute("SELECT COALESCE(NULLIF(statut,''),'MANQUANT'),COUNT(*) FROM versions_articles GROUP BY COALESCE(NULLIF(statut,''),'MANQUANT')"))
    codes = [dict(zip(("code", "titre", "versions"), row)) for row in db.execute(
        "SELECT code,MAX(titre),COUNT(*) FROM versions_articles WHERE code IS NOT NULL GROUP BY code ORDER BY COUNT(*) DESC")]
    catalogue = {}
    for code, title, source in db.execute("SELECT code,titre,source_archive FROM codes_metadata ORDER BY source_archive,source_path"):
        if title:
            catalogue[code] = (title, source)
    for code in codes:
        if code["code"] in catalogue:
            code["titre"], code["source_titre"] = catalogue[code["code"]]
        else:
            code["source_titre"] = "CONTEXTE_ARTICLE"
    anomalies = dict(db.execute("SELECT type,COUNT(*) FROM anomalies GROUP BY type"))
    date_issues = 0
    date_samples = []
    for ident, debut, fin in db.execute("SELECT article_id,date_debut,date_fin FROM versions_articles"):
        try:
            if any(not isinstance(value, str) or len(value) != 10
                   or value[4] != "-" or value[7] != "-" for value in (debut, fin)):
                raise ValueError("format")
            d, f = date.fromisoformat(debut), date.fromisoformat(fin)
            if d > f:
                raise ValueError("ordre")
        except (ValueError, TypeError):
            date_issues += 1
            if len(date_samples) < 30:
                date_samples.append({"article_id": ident, "date_debut": debut, "date_fin": fin})
    applied_rows = dict(db.execute("SELECT name,sha256 FROM archives"))
    expected_rows = {entry["name"]: entry.get("sha256") for entry in manifest["archives"]}
    missing_archives = sorted(expected_rows.keys() - applied_rows.keys())
    extra_archives = sorted(applied_rows.keys() - expected_rows.keys())
    mismatched = sorted(name for name, digest in expected_rows.items()
                        if digest and name in applied_rows and applied_rows[name] != digest)
    applied = len(applied_rows)
    expected = len(manifest["archives"])
    rejected = scalar("SELECT COUNT(*) FROM anomalies")
    empty_eli = scalar("SELECT COUNT(*) FROM anomalies WHERE path LIKE 'legi/global/eli/%/versions.xml' AND detail LIKE 'Document is empty,%'")
    rejected_content = rejected - empty_eli
    xml_counts: Counter = Counter()
    dtd_counts: Counter = Counter()
    fragment_warnings = 0
    for root, valid, warning, count in db.execute(
            "SELECT root,dtd_valid,warnings_json!='[]',COUNT(*) FROM documents GROUP BY root,dtd_valid,warnings_json!='[]'"):
        xml_counts[root] += count
        dtd_counts[str(valid)] += count
        if warning:
            fragment_warnings += count
    dtd = dict(dtd_counts)
    print("Rapport : contrôle d'intégrité SQLite et couverture", flush=True)
    integrity = scalar("PRAGMA quick_check")
    missing_required = quality["versions_champs_requis_vides_ou_absents"]
    # Read full bodies only for IDs present at several source paths.
    conflict_audit = audit_source_conflicts(db, output)
    conflicts = conflict_audit["identifiants_divergents"]
    print("Rapport : bilan des dates et rattachements", flush=True)
    summary = db.execute("SELECT "
                         "COALESCE(SUM(code IS NOT NULL),0),COALESCE(SUM(code IS NULL),0),"
                         "COALESCE(SUM(date_debut='2999-01-01'),0),COALESCE(SUM(date_fin='2999-01-01'),0),"
                         "COALESCE(SUM(date_debut='2222-02-22' OR date_fin='2222-02-22'),0),"
                         "COALESCE(SUM(date_debut=date_fin),0),"
                         "COALESCE(SUM(code IS NULL AND NULLIF(TRIM(nature),'') IS NOT NULL AND nature!='CODE'),0) "
                         "FROM versions_articles").fetchone()
    complete = not missing_archives and not extra_archives and not mismatched and integrity == "ok"
    report = {"generated_at": utc_now(), "statut_collecte": "COMPLETE" if complete else "INCOMPLETE",
              "statut_qualite": "A_AUDITER",
              "statut_parsing_contenu": "COMPLET" if rejected_content == 0 else "PARTIEL",
              "autorisation_import_production": False, "pret_entrainement_supervise": False,
              "dernier_lot_source": manifest["archives"][-1]["name"], "archives_attendues": expected,
              "archives_appliquees": applied, "versions_articles_distinctes": versions,
              "archives_manquantes": missing_archives, "archives_inattendues": extra_archives,
              "archives_empreinte_incorrecte": mismatched,
              **family, "distribution_statuts": statuses, "codes": codes,
              "versions_code": summary[0], "versions_sans_code_identifie": summary[1],
              "versions_hors_code": summary[1],
              "versions_non_codifiees_identifiees": summary[6],
              "versions_texte_vide": quality["champs_vides_ou_absents"]["texte"],
              "champs_requis_manquants": missing_required, "dates_anormales": date_issues,
              "exemples_dates_anormales": date_samples, "identifiants_plusieurs_chemins": conflict_audit["identifiants_plusieurs_chemins"],
              "date_debut_2999": summary[2], "date_fin_2999": summary[3],
              "dates_2222": summary[4], "intervalles_nuls": summary[5],
              "documents_fragments_avertis": fragment_warnings,
              "identifiants_contenus_divergents": conflicts, "racines_xml_stock_present": xml_counts,
              "validation_dtd_documents": dtd, "erreurs_quarantaine": anomalies,
              "alias_eli_vides": empty_eli, "rejets_contenu_hors_alias_eli_vides": rejected_content,
              "suppressions_recues": scalar("SELECT COUNT(*) FROM suppressions"),
              "documents_supprimes": scalar("SELECT COALESCE(SUM(deleted),0) FROM suppressions"),
              "sqlite_quick_check": integrity,
              "licence": manifest["licence"], "attribution": manifest["attribution"],
              "limites": ["Couverture mesurée sur les archives DILA listées, pas preuve d'exhaustivité juridique nationale.",
                          "Les familles sont des composantes des liens VERSIONS officiels ; elles ne garantissent pas la continuité d'une règle juridique. Des renumérotations peuvent aussi relier des textes identiques entre familles.",
                          "Les alias ELI (racines ID/VERSIONS ou fichiers vides) ne sont pas des versions d'articles ; les alias vides sont conservés et comptés séparément des rejets de contenu.",
                          "Les dates et statuts sources sont conservés ; leur applicabilité dépend du dossier et des dispositions transitoires.",
                          "Les textes non codifiés restent présents avec code NULL ; texte_id identifie leur texte parent.",
                          "Aucun exemple synthétique ni annotation de pertinence ne devient fiable par cette collecte.",
                          "Une non-conformité à la DTD publiée de 2018 n'implique pas un XML illisible ; examiner les diagnostics."]}
    report["audit_qualite_sources"] = quality
    report["audit_conflits_sources"] = conflict_audit
    write_json(output / "reports/couverture.json", report)
    lines = ["# Couverture du corpus LEGI DILA", "", f"Collecte : **{report['statut_collecte']}**. Import production : **non autorisé**.", "",
             f"- Archives appliquées : {applied}/{expected}", f"- Dernier lot : {report['dernier_lot_source']}",
             f"- Versions d'articles distinctes (LEGIARTI) : {versions:,}",
             f"- Familles calculées via les liens VERSIONS : {family['familles_calculees_liens_versions']:,}",
             f"- Versions rattachées à un code : {report['versions_code']:,}",
             f"- Versions sans identifiant de code (textes non codifiés ou contexte incomplet) : {report['versions_sans_code_identifie']:,}",
             f"- Codes distincts : {len(codes)}", f"- XML rejetés : {rejected}",
             f"- Dont alias ELI vides : {empty_eli}", f"- Rejets de contenu hors alias ELI vides : {rejected_content}",
             f"- Dates anormales : {date_issues}", f"- Identifiants aux contenus divergents : {conflicts}",
             f"- Contrôle SQLite : {integrity}", "", "## Statuts", "", "| Statut | Versions |", "|---|---:|"]
    lines += [f"| {status} | {count:,} |" for status, count in sorted(statuses.items())]
    lines += ["", "## Codes", "", "| Code DILA | Titre | Versions |", "|---|---|---:|"]
    lines += [f"| {code['code']} | {(code['titre'] or 'Titre manquant').replace('|', '/')} | {code['versions']:,} |" for code in codes]
    lines += ["", "## Contrôles et limites", ""] + ["- " + item for item in report["limites"]]
    lines += ["", "Les détails par code, les erreurs DTD, suppressions et sources figurent dans `couverture.json` et dans SQLite.", "",
              "L'audit des champs vides et des écarts DTD figure dans `QUALITE_SOURCES.md` et `qualite_sources.json`.", "",
              "Les copies divergentes sont détaillées dans `conflits_sources.jsonl` et `audit_conflits_sources.json`.", "",
              "## Attribution", "", manifest["attribution"], "", "Licence : Licence Ouverte / Open Licence 2.0.", "",
              "## Avant un entraînement", "", "1. Résoudre les anomalies bloquantes et figer les empreintes du corpus.",
              "2. Définir un périmètre juridique et des jeux d'évaluation indépendants, avec versions et dates.",
              "3. Construire des exemples annotés distincts pour retrieval et extraction JSON ; les textes seuls ne suffisent pas.",
              "4. Dédupliquer les textes y compris entre familles/renumérotations, puis séparer avant génération de paraphrases/chunks.",
              "5. Comparer aux baselines sur le corpus complet ; conserver les cas négatifs et les articles multiples.",
              "6. Faire contrôler la pertinence juridique avant de revendiquer une fiabilité métier."]
    (output / "reports/COUVERTURE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def prepare_manifest(output: Path, refresh: bool = False) -> dict:
    path = output / "manifest.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if path.exists():
        raise ValueError("Manifeste déjà figé : utiliser un nouveau répertoire pour une nouvelle photographie")
    raw = output / "raw"
    html = fetch_index(raw) if refresh or not (raw / "index_legi.html").exists() else (raw / "index_legi.html").read_text(encoding="utf-8")
    archives = discover(html)
    if not archives:
        raise ValueError("Aucune archive stock trouvée")
    manifest = {"schema_version": SCHEMA_VERSION, "created_at": utc_now(), "source": BASE_URL,
                "index_sha256": sha256(raw / "index_legi.html"), "licence": "Licence Ouverte / Open Licence 2.0",
                "licence_url": "https://www.data.gouv.fr/pages/legal/licences/etalab-2.0",
                "attribution": "Source : DILA — Légifrance, base LEGI, " + BASE_URL + "; photographie arrêtée au lot " + archives[-1].name + ". Textes consolidés reproduits et texte dérivé de leurs XML officiels.",
                "archives": [{"name": a.name, "url": a.url, "kind": a.kind, "timestamp": a.timestamp} for a in archives]}
    write_json(path, manifest)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sortie", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--etape", choices=("tout", "telecharger", "parser", "rapport", "qualite", "conflits"), default="tout")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    output = args.sortie.expanduser().resolve()
    # Guard the known production paths even if a bad CLI argument is pasted.
    if output == PROJECT or output == PROJECT / "data/vector":
        ap.error("Choisir un sous-répertoire dédié, jamais le répertoire de production")
    for folder in ("raw", "reports", "quarantine", "tmp"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    manifest = prepare_manifest(output)
    dtd_dir = prepare_dtd(output, manifest) if args.etape in {"tout", "parser"} else None
    if args.etape in {"tout", "telecharger"}:
        if not 1 <= args.workers <= 8:
            ap.error("--workers doit être compris entre 1 et 8")
        entries = manifest["archives"]
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(download_archive, Archive(e["name"], e["url"], e["kind"], e["timestamp"]), output / "raw"): e for e in entries}
            for index, future in enumerate(as_completed(futures), 1):
                entry = futures[future]
                entry.update(future.result())
                write_json(output / "manifest.json", manifest)
                print(f"Acquis {index}/{len(entries)} : {entry['name']} ({entry['bytes']:,} octets)", flush=True)
    db = open_database(output / "legi_dila.sqlite")
    try:
        if args.etape in {"tout", "parser"}:
            parser = DilaParser(dtd_dir)
            for entry in manifest["archives"]:
                if "sha256" not in entry:
                    raise ValueError(f"Archive pas encore acquise : {entry['name']}")
                ingest_archive(db, entry, output / "raw", parser, output)
        if args.etape in {"tout", "parser", "rapport"}:
            report = coverage_report(db, manifest, output)
            print(json_text({k: report[k] for k in ("statut_collecte", "archives_appliquees", "versions_articles_distinctes", "distribution_statuts")}), flush=True)
        if args.etape == "qualite":
            quality = audit_source_quality(db, output)
            coverage = output / "reports/couverture.json"
            if coverage.exists():
                report = json.loads(coverage.read_text(encoding="utf-8"))
                report["audit_qualite_sources"] = quality
                report["champs_requis_manquants"] = quality["versions_champs_requis_vides_ou_absents"]
                write_json(coverage, report)
            print(json_text({"versions_examinees": quality["versions_examinees"], "statut": quality["statut"]}), flush=True)
        if args.etape == "conflits":
            conflict_audit = audit_source_conflicts(db, output)
            coverage = output / "reports/couverture.json"
            if coverage.exists():
                report = json.loads(coverage.read_text(encoding="utf-8"))
                report["audit_conflits_sources"] = conflict_audit
                write_json(coverage, report)
            print(json_text(conflict_audit), flush=True)
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, tarfile.TarError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(f"ÉCHEC : {type(error).__name__} : {error}", file=sys.stderr)
        raise SystemExit(1)
