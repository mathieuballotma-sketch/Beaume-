"""Lecture stricte des documents LEGI avec validation DTD locale distincte.

Un LEGIARTI désigne une version ; les rapprochements reposent sur les liens
officiels VERSIONS, jamais sur le seul numéro. Dates et numéros restent bruts.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from lxml import etree


class DilaXMLInvalide(ValueError):
    """XML malformé ou accès à une DTD/entité non autorisée."""


_DTDS = {
    "ARTICLE": "legi_article.dtd", "TEXTELR": "legi_texte_struct.dtd",
    "TEXTE_VERSION": "legi_texte_version.dtd", "SECTION_TA": "legi_section_ta.dtd",
}
_BLOCKS = frozenset({
    "p", "div", "li", "ul", "ol", "blockquote", "h1", "h2", "h3",
    "h4", "h5", "h6", "table", "tableau", "tr", "caption", "thead",
    "tbody", "tfoot", "ent", "notes", "not", "pre",
})
_ROOT = re.compile(rb"<(?![!?/])([A-Za-z_][\w:.-]*)(?:\s|/?>)")
_DOCTYPE = re.compile(rb"<!DOCTYPE\s+[^>]*>", re.IGNORECASE)
_INTERNAL_DTD = re.compile(rb"<!DOCTYPE[^>]*\[|<!ENTITY\s", re.IGNORECASE)
_XML_DECL = re.compile(rb"^\s*<\?xml[^?]*\?>", re.IGNORECASE)
_NAMED_ENTITY = re.compile(rb"&(?!amp;|lt;|gt;|quot;|apos;)[A-Za-z][A-Za-z0-9]+;")


def _tag(element: etree._Element) -> str:
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


def _text(element: etree._Element | None) -> str:
    """Conserve mixed content et tails, sépare paragraphes/lignes/cellules."""
    if element is None:
        return ""
    parts: list[str] = []

    def walk(node: etree._Element) -> None:
        if not isinstance(node.tag, str):
            return
        name = _tag(node).lower()
        if name in _BLOCKS or name == "br":
            parts.append("\n")
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)
        if name in {"td", "th"}:
            parts.append("\t")
        if name in _BLOCKS:
            parts.append("\n")

    walk(element)
    lines = []
    for line in "".join(parts).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        cells = [re.sub(r"[^\S\t]+", " ", cell).strip() for cell in line.split("\t")]
        line = "\t".join(cells).strip("\t ")
        if line:
            lines.append(line)
    return "\n".join(lines)


def _at(root: etree._Element, path: str) -> str:
    return _text(root.find(path))


def _node_dict(node: etree._Element) -> dict[str, Any]:
    result: dict[str, Any] = {"tag": _tag(node), "attrs": dict(node.attrib)}
    if node.text and node.text.strip():
        result["texte"] = node.text.strip()
    children = [_node_dict(child) for child in node if isinstance(child.tag, str)]
    if children:
        result["children"] = children
    return result


class _LocalResolver(etree.Resolver):
    """Whitelist des fichiers DTD/entités, aucune résolution réseau."""

    def __init__(self, directory: Path) -> None:
        super().__init__()
        self.allowed = {
            path.name: path.resolve() for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".dtd", ".ent"}
            and path.resolve().parent == directory.resolve()
        }

    def resolve(self, url: str, public_id: str | None, context: Any) -> Any:
        name = Path(urlparse(url).path).name
        path = self.allowed.get(name)
        if path is None:
            raise DilaXMLInvalide(f"Entité ou DTD externe interdite : {name!r}")
        return self.resolve_filename(str(path), context)


class DilaParser:
    """Parse des bytes XML. ``dtd_dir=None`` désactive le contrôle DTD.

    ``dtd_dir`` peut être le sous-répertoire ``legi`` ou la racine extraite
    de l'archive officielle. Une DTD ancienne incompatible produit
    ``dtd_valid=False`` ; le document XML valide est conservé avec ses erreurs.
    Instance prévue pour un consommateur séquentiel, pas des threads partagés.
    """

    def __init__(self, dtd_dir: Path | None = None) -> None:
        self.dtd_dir: Path | None = None
        self._validators: dict[str, etree.DTD] = {}
        if dtd_dir is not None:
            directory = Path(dtd_dir)
            if not (directory / "legi_article.dtd").is_file():
                candidates = sorted(directory.rglob("legi_article.dtd"))
                if len(candidates) != 1:
                    raise FileNotFoundError(f"Répertoire DTD LEGI absent ou ambigu : {directory}")
                directory = candidates[0].parent
            self.dtd_dir = directory.resolve()
            for root, filename in _DTDS.items():
                path = self.dtd_dir / filename
                if not path.is_file():
                    raise FileNotFoundError(f"DTD officielle manquante : {path}")
                try:
                    self._validators[root] = etree.DTD(str(path))
                except etree.DTDParseError as exc:
                    raise DilaXMLInvalide(f"DTD illisible : {filename}") from exc
        self._xml_parser = etree.XMLParser(
            load_dtd=self.dtd_dir is not None,
            resolve_entities=self.dtd_dir is not None, no_network=True,
            recover=False, remove_comments=False, strip_cdata=False, huge_tree=False,
        )
        if self.dtd_dir is not None:
            self._xml_parser.resolvers.add(_LocalResolver(self.dtd_dir))

    def _read(self, data: bytes, *, fragment: bool = False) -> etree._Element:
        # UTF-16/32 intercale des NUL dans les mots-clés XML : ne pas laisser
        # ce changement d'encodage contourner le refus des entités internes.
        security_scan = data.replace(b"\x00", b"") if b"\x00" in data else data
        if _INTERNAL_DTD.search(security_scan):
            raise DilaXMLInvalide("Sous-ensemble DTD interne ou déclaration ENTITY interdit")
        # Les exports omettent souvent DOCTYPE. Ne charger les entités XHTML
        # que si nécessaire : relire toute la DTD à chaque article multiplierait
        # les E/S. La validation explicite utilise toujours la DTD compilée.
        if self.dtd_dir is not None and not _DOCTYPE.search(data) and _NAMED_ENTITY.search(data):
            without_comments = re.sub(rb"<!--.*?-->", b"", data, flags=re.DOTALL)
            match = _ROOT.search(without_comments)
            if match:
                root_name = match.group(1).decode("ascii")
                filename = _DTDS.get(root_name)
                if fragment and root_name == "CONTENU":
                    filename = _DTDS["ARTICLE"]
                if filename:
                    declaration = f'<!DOCTYPE {root_name} SYSTEM "{filename}">'.encode()
                    xml_decl = _XML_DECL.match(data)
                    pos = xml_decl.end() if xml_decl else 0
                    data = data[:pos] + b"\n" + declaration + b"\n" + data[pos:]
        if self.dtd_dir is None and _DOCTYPE.search(security_scan):
            raise DilaXMLInvalide("DOCTYPE externe interdit sans DTD locale officielle")
        try:
            return etree.fromstring(data, parser=self._xml_parser)
        except DilaXMLInvalide:
            raise
        except (etree.XMLSyntaxError, ValueError, OSError) as exc:
            raise DilaXMLInvalide(str(exc)) from exc

    def _content(self, node: etree._Element | None, warnings: list[str]) -> str:
        if node is None:
            return ""
        # CDATA contenant du XHTML : lecture comme fragment strict, jamais
        # HTML recovery. Si le fragment est malformé, texte brut conservé.
        if len(node) == 0 and node.text and re.search(r"</?[A-Za-z]", node.text):
            fragment = f"<CONTENU>{node.text}</CONTENU>".encode("utf-8")
            try:
                node = self._read(fragment, fragment=True)
            except DilaXMLInvalide as exc:
                warnings.append(f"Fragment littéral conservé sans interprétation : {exc}")
        return _text(node)

    def parse(self, data: bytes) -> dict[str, Any]:
        if not isinstance(data, bytes):
            raise TypeError("DilaParser.parse attend des bytes XML")
        document = self._read(data)
        root_name = _tag(document)
        validator = self._validators.get(root_name)
        dtd_valid: bool | None = None
        errors: list[str] = []
        if validator is not None:
            dtd_valid = validator.validate(document)
            errors = [str(error) for error in validator.error_log]
        elif self.dtd_dir is not None:
            errors = [f"Aucune DTD LEGI sélectionnée pour la racine {root_name}"]
        common = document.find("META/META_COMMUN")
        common_meta = {_tag(child).lower(): _text(child) for child in common} if common is not None else {}
        warnings: list[str] = []
        result: dict[str, Any] = {
            "root": root_name, **common_meta, "nature_document": common_meta.get("nature", ""),
            "dtd_valid": dtd_valid, "dtd_errors": errors, "fragment_errors": warnings,
        }
        context_node = document.find("CONTEXTE/TEXTE")
        attrs = dict(context_node.attrib) if context_node is not None else {}
        result["contexte"] = _node_dict(context_node) if context_node is not None else {}
        result["texte_id"] = attrs.get("cid", "")
        result["code"] = (
            attrs["cid"] if attrs.get("nature") == "CODE"
            and re.fullmatch(r"LEGITEXT\d{12}", attrs.get("cid", "")) else None
        )
        result["liens"] = [
            {**dict(link.attrib), "texte": _text(link)}
            for link in document.findall(".//LIENS/LIEN")
        ]
        result["versions"] = []
        for version in document.findall("VERSIONS/VERSION"):
            for link in version:
                if _tag(link) not in {"LIEN_ART", "LIEN_TXT"}:
                    continue
                result["versions"].append({
                    "article_id": link.get("id", "") if root_name == "ARTICLE" else "",
                    "id": link.get("id", ""), "numero": link.get("num", ""),
                    "date_debut": link.get("debut", ""), "date_fin": link.get("fin", ""),
                    "statut": link.get("etat", version.get("etat", "")), "attrs": dict(link.attrib),
                })
        if root_name == "ARTICLE":
            meta = "META/META_SPEC/META_ARTICLE/"
            contents = document.find("BLOC_TEXTUEL/CONTENU")
            titles = context_node.findall("TITRE_TXT") if context_node is not None else []
            title = next((t for t in titles if t.get("id_txt") == attrs.get("cid")), None)
            if title is None and titles:
                title = titles[-1]
            result.update({
                "article_id": common_meta.get("id", ""), "nature": attrs.get("nature", ""),
                "titre": _text(title), "numero": _at(document, meta + "NUM"),
                "date_debut": _at(document, meta + "DATE_DEBUT"),
                "date_fin": _at(document, meta + "DATE_FIN"), "statut": _at(document, meta + "ETAT"),
                "texte": self._content(contents, warnings),
                "contenu_xml": etree.tostring(contents, encoding="unicode", with_tail=False)
                if contents is not None else "", "nota": self._content(document.find("NOTA/CONTENU"), warnings),
                "type_article": _at(document, meta + "TYPE"),
            })
        elif root_name in {"TEXTELR", "TEXTE_VERSION"}:
            meta = "META/META_SPEC/"
            version = meta + "META_TEXTE_VERSION/"
            result.update({
                "cid": _at(document, meta + "META_TEXTE_CHRONICLE/CID"),
                "titre": _at(document, version + "TITREFULL") or _at(document, version + "TITRE"),
                "numero": _at(document, meta + "META_TEXTE_CHRONICLE/NUM"),
                "date_debut": _at(document, version + "DATE_DEBUT"),
                "date_fin": _at(document, version + "DATE_FIN"), "statut": _at(document, version + "ETAT"),
                "structure": [{"tag": _tag(child), **dict(child.attrib), "texte": _text(child)}
                              for child in document.findall("STRUCT/*")],
            })
        elif root_name == "SECTION_TA":
            result.update({
                "id": _at(document, "ID"), "titre": _at(document, "TITRE_TA"),
                "structure": [{"tag": _tag(child), **dict(child.attrib), "texte": _text(child)}
                              for child in document.findall("STRUCTURE_TA/*")],
            })
        return result
