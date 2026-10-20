"""Acquisition reproductible des archives officielles LEGI, sans import métier.

SHA-256 identifie les octets acquis ; ce n'est pas une signature de l'éditeur.
Une métadonnée par archive permet des acquisitions parallèles sans manifeste
global concurrent. Le traitement du XML reste indépendant de cet adaptateur.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


INDEX_URL = "https://echanges.dila.gouv.fr/OPENDATA/LEGI/"
ATTRIBUTION = (
    "Source : DILA — Légifrance, base LEGI. "
    "Réutilisation sous Licence Ouverte / Open Licence 2.0."
)
LICENCE_URL = "https://www.data.gouv.fr/pages/legal/licences/etalab-2.0"
_NAME = re.compile(
    r"(?:(?P<stock>Freemium_legi_global)|(?P<delta>LEGI))_"
    r"(?P<timestamp>\d{8}-\d{6})\.tar\.gz\Z"
)
_CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)\Z")
_USER_AGENT = "Beaume-LEGI-corpus/1.0 (public legal corpus acquisition)"
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class Archive:
    """Une publication identifiée par son horodatage complet, pas son jour."""
    name: str
    url: str
    kind: str
    timestamp: str

    def __post_init__(self) -> None:
        match = _NAME.fullmatch(self.name)
        if match is None:
            raise ValueError(f"Nom d'archive DILA non reconnu : {self.name!r}")
        datetime.strptime(self.timestamp, "%Y%m%d-%H%M%S")
        expected_kind = "stock" if match.group("stock") else "delta"
        if self.kind != expected_kind or self.timestamp != match.group("timestamp"):
            raise ValueError("Métadonnées d'archive incohérentes avec son nom")
        if self.url != urljoin(INDEX_URL, self.name):
            raise ValueError("L'archive doit provenir du répertoire officiel LEGI")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.names: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href is not None and _NAME.fullmatch(href):
            self.names.add(href)


def discover(index_html: str) -> list[Archive]:
    """Dernier stock puis deltas strictement postérieurs, triés par horodatage.

    Les publications multiples d'un même jour restent distinctes. Un index vide
    ou inattendu échoue explicitement au lieu de produire un corpus vide.
    """
    parser = _Links()
    parser.feed(index_html)
    archives = []
    for name in parser.names:
        match = _NAME.fullmatch(name)
        assert match is not None
        archives.append(Archive(
            name=name,
            url=urljoin(INDEX_URL, name),
            kind="stock" if match.group("stock") else "delta",
            timestamp=match.group("timestamp"),
        ))
    stocks = [archive for archive in archives if archive.kind == "stock"]
    if not stocks:
        raise ValueError("Aucun stock LEGI reconnu dans l'index officiel")
    stock = max(stocks, key=lambda archive: (archive.timestamp, archive.name))
    deltas = sorted(
        (archive for archive in archives
         if archive.kind == "delta" and archive.timestamp > stock.timestamp),
        key=lambda archive: (archive.timestamp, archive.name),
    )
    return [stock, *deltas]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_response_origin(response: Any) -> None:
    parsed = urlparse(response.geturl())
    if parsed.scheme != "https" or parsed.hostname != "echanges.dila.gouv.fr":
        raise ValueError("Redirection hors du domaine DILA HTTPS")


def _request(url: str, *, timeout: float, headers: dict[str, str] | None = None,
             method: str = "GET") -> Any:
    request_headers = {"User-Agent": _USER_AGENT, "Accept-Encoding": "identity"}
    request_headers.update(headers or {})
    response = urlopen(Request(url, headers=request_headers, method=method), timeout=timeout)
    try:
        _check_response_origin(response)
    except Exception:
        response.close()
        raise
    return response


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_index(raw_dir: Path, *, timeout: float = 60.0) -> str:
    """Acquérir et sauvegarder un instantané exploitable de l'index DILA."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    with _request(INDEX_URL, timeout=timeout) as response:
        content = response.read(4 * 1024 * 1024 + 1)
        if len(content) > 4 * 1024 * 1024:
            raise ValueError("Index DILA anormalement volumineux")
        encoding = response.headers.get_content_charset() or "utf-8"
        text = content.decode(encoding)
        discover(text)
        metadata = {
            "url": INDEX_URL, "downloaded_at": _utc_now(),
            "bytes": len(content), "sha256": sha256(content).hexdigest(),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
        }
    path = raw_dir / "index_legi.html"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    _atomic_json(raw_dir / "index_legi.metadata.json", metadata)
    return text


def _validator(metadata: dict[str, Any]) -> str | None:
    etag = metadata.get("etag")
    # Un ETag faible n'est pas recevable pour If-Range (RFC 9110).
    if isinstance(etag, str) and etag and not etag.startswith("W/"):
        return etag
    modified = metadata.get("last_modified")
    return modified if isinstance(modified, str) and modified else None


def _download_once(archive: Archive, part: Path, partial_metadata: Path,
                   *, timeout: float) -> dict[str, Any]:
    previous = _read_json(partial_metadata)
    offset = part.stat().st_size if part.exists() else 0
    validator = _validator(previous)
    resume = bool(offset and validator and previous.get("url") == archive.url)
    headers: dict[str, str] = {}
    if resume:
        headers.update({"Range": f"bytes={offset}-", "If-Range": validator})
    with _request(archive.url, timeout=timeout, headers=headers) as response:
        status = response.status
        length_header = response.headers.get("Content-Length")
        response_length = int(length_header) if length_header is not None else None
        metadata: dict[str, Any] = {
            **archive.to_dict(), "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
        }
        if status == 206:
            content_range = _CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
            if not resume or content_range is None:
                raise ValueError("Réponse partielle sans reprise demandée ou plage valable")
            start, end, total = map(int, content_range.groups())
            if start != offset or end < start or end >= total:
                raise ValueError("Plage HTTP incompatible avec le fichier partiel")
            if response_length is not None and response_length != end - start + 1:
                raise ValueError("Content-Length et Content-Range incompatibles")
            for key in ("etag", "last_modified"):
                if previous.get(key) and metadata.get(key) and previous[key] != metadata[key]:
                    raise ValueError("Le validateur de l'archive a changé pendant la reprise")
            mode, expected_total = "ab", total
        elif status == 200:
            # Range ignoré, ou ressource modifiée : écraser le partiel, pas concaténer.
            mode, expected_total = "wb", response_length
        else:
            raise ValueError(f"Statut HTTP inattendu : {status}")
        metadata["expected_bytes"] = expected_total
        received = 0
        with part.open(mode) as stream:
            # En mode wb, tronquer AVANT de publier le nouveau validateur. Un
            # arrêt brutal entre ces deux opérations ne doit jamais associer
            # les octets d'une ancienne ressource au validateur de la nouvelle.
            _atomic_json(partial_metadata, metadata)
            for chunk in iter(lambda: response.read(_CHUNK), b""):
                stream.write(chunk)
                received += len(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if response_length is not None and received != response_length:
            raise OSError(f"Réponse HTTP incomplète : {received} / {response_length} octets")
        actual_total = part.stat().st_size
        if expected_total is not None and actual_total != expected_total:
            raise OSError(f"Archive incomplète : {actual_total} / {expected_total} octets")
        return metadata


def download_archive(archive: Archive, raw_dir: Path, *, timeout: float = 120.0,
                     retries: int = 3) -> dict[str, Any]:
    """Acquérir une archive avec reprise validée et publication atomique.

    Une archive déjà publiée est relue et comparée à sa métadonnée SHA-256. Un
    fichier sans métadonnée (ex. acquisition curl préalable) est accepté seulement
    après comparaison de sa taille avec un HEAD officiel. Un partiel sans
    validateur est retéléchargé, jamais concaténé à l'aveugle. Appeler une seule
    fois simultanément pour chaque archive. La vérification gzip/tar se fait
    ensuite dans l'importeur, distinctement du transport HTTP.
    """
    if retries < 1:
        raise ValueError("retries doit être positif")
    archive.__post_init__()
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / archive.name
    sidecar = raw_dir / (archive.name + ".metadata.json")
    if target.exists():
        metadata = _read_json(sidecar)
        digest = _hash_file(target)
        if metadata:
            if (metadata.get("url") != archive.url
                    or metadata.get("sha256") != digest
                    or metadata.get("bytes") != target.stat().st_size):
                raise ValueError(f"Archive locale modifiée ou métadonnée invalide : {target}")
            return metadata
        with _request(archive.url, timeout=timeout, method="HEAD") as response:
            expected = response.headers.get("Content-Length")
            if expected is None or int(expected) != target.stat().st_size:
                raise ValueError(f"Taille de l'archive locale non vérifiée : {target}")
            metadata = {
                **archive.to_dict(), "bytes": target.stat().st_size, "sha256": digest,
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "downloaded_at": _utc_now(),
                "verification": "existing_file_size_checked_against_official_HEAD",
            }
        _atomic_json(sidecar, metadata)
        return metadata
    part = raw_dir / (archive.name + ".part")
    partial_metadata = raw_dir / (archive.name + ".part.json")
    for attempt in range(retries):
        try:
            metadata = _download_once(archive, part, partial_metadata, timeout=timeout)
            break
        except (OSError, URLError, IncompleteRead) as error:
            # Un partiel complet peut provoquer 416 après une interruption tardive.
            # Au prochain essai, repartir de zéro plutôt que valider sans preuve.
            if isinstance(error, HTTPError) and error.code == 416:
                partial_metadata.unlink(missing_ok=True)
            if attempt + 1 == retries:
                raise RuntimeError(
                    f"Échec après {retries} tentatives : {archive.name}"
                ) from error
            time.sleep(min(2 ** attempt, 4))
    metadata.pop("expected_bytes", None)
    metadata.update({
        "bytes": part.stat().st_size, "sha256": _hash_file(part),
        "downloaded_at": _utc_now(), "verification": "HTTP_transfer_length_and_local_SHA256",
    })
    part.replace(target)
    _atomic_json(sidecar, metadata)
    partial_metadata.unlink(missing_ok=True)
    return metadata
