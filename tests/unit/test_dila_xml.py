"""Tests autonomes du parsing DILA : aucune donnée client, aucun réseau."""
from pathlib import Path

import pytest

from beaume.adapters.dila_xml import DilaParser, DilaXMLInvalide


def _article(
    contenu: str = "<p>Le salarié a un droit.</p>",
    numero: str = "L. 1233-4",
    nature: str = "CODE",
    cid: str = "LEGITEXT000006072050",
) -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ARTICLE><META><META_COMMUN><ID>LEGIARTI000006901177</ID>
<ANCIEN_ID/><ORIGINE>LEGI</ORIGINE><URL>article/test.xml</URL><NATURE>Article</NATURE>
</META_COMMUN><META_SPEC><META_ARTICLE><NUM>{numero}</NUM><ETAT>MODIFIE</ETAT>
<DATE_DEBUT>2008-05-01</DATE_DEBUT><DATE_FIN>2010-05-20</DATE_FIN><TYPE>AUTONOME</TYPE>
</META_ARTICLE></META_SPEC></META>
<CONTEXTE><TEXTE cid="{cid}" nature="{nature}">
<TITRE_TXT id_txt="{cid}" debut="2008-05-01" fin="2999-01-01">Code du travail</TITRE_TXT>
<TM><TITRE_TM id="LEGISCTA000000000001">Titre premier</TITRE_TM>
<TM><TITRE_TM id="LEGISCTA000000000002">Chapitre</TITRE_TM></TM></TM>
</TEXTE></CONTEXTE>
<VERSIONS><VERSION etat="MODIFIE"><LIEN_ART id="LEGIARTI000006901177" num="{numero}"
debut="2008-05-01" fin="2010-05-20" etat="MODIFIE"/></VERSION>
<VERSION etat="VIGUEUR"><LIEN_ART id="LEGIARTI000022000001" num="L1233-4-1"
debut="2010-05-20" fin="2999-01-01" etat="VIGUEUR"/></VERSION></VERSIONS>
<NOTA><CONTENU><p>Application conditionnelle.</p></CONTENU></NOTA>
<BLOC_TEXTUEL><CONTENU>{contenu}</CONTENU></BLOC_TEXTUEL>
<LIENS><LIEN id="LEGIARTI000000000001" typelien="CITATION" sens="source">Loi</LIEN></LIENS>
</ARTICLE>'''.encode("utf-8")


@pytest.fixture
def dtd_dir(tmp_path: Path) -> Path:
    """DTDs minimales déterministes, sans archive officielle à télécharger."""
    names = {
        "ARTICLE", "META", "META_COMMUN", "META_SPEC", "META_ARTICLE", "ID",
        "ANCIEN_ID", "ORIGINE", "URL", "NATURE", "NUM", "ETAT", "DATE_DEBUT",
        "DATE_FIN", "TYPE", "CONTEXTE", "TEXTE", "TITRE_TXT", "TM", "TITRE_TM",
        "VERSIONS", "VERSION", "LIEN_ART", "NOTA", "BLOC_TEXTUEL", "CONTENU",
        "LIENS", "LIEN", "p", "b", "br", "table", "tr", "td",
    }
    dtd = '\n'.join(f"<!ELEMENT {name} ANY>" for name in sorted(names))
    dtd += '\n<!ENTITY nbsp "&#160;">\n'
    for filename in ("legi_article.dtd", "legi_texte_struct.dtd", "legi_texte_version.dtd", "legi_section_ta.dtd"):
        (tmp_path / filename).write_text(dtd, encoding="utf-8")
    return tmp_path


def test_article_preserve_dates_numeros_liens_et_contexte():
    result = DilaParser().parse(_article())
    assert result["article_id"] == "LEGIARTI000006901177"
    assert result["code"] == "LEGITEXT000006072050"
    assert result["numero"] == "L. 1233-4"
    assert result["date_fin"] == "2010-05-20"
    assert result["statut"] == "MODIFIE"
    assert result["dtd_valid"] is None
    assert result["dtd_errors"] == []
    assert result["versions"][1]["numero"] == "L1233-4-1"
    assert result["versions"][1]["article_id"] == "LEGIARTI000022000001"
    assert result["liens"][0]["typelien"] == "CITATION"
    assert result["liens"][0]["texte"] == "Loi"
    assert result["contexte"]["children"][1]["children"][1]["children"][0]["texte"] == "Chapitre"
    assert result["nota"] == "Application conditionnelle."
    assert result["nature_document"] == "Article"
    assert result["nature"] == "CODE"


@pytest.mark.parametrize("nature,cid", [
    ("LOI", "JORFTEXT000000407771"),
    ("LOI", "LEGITEXT000005631202"),
    ("CODE", "JORFTEXT000000407771"),
    ("CODE", "LEGITEXTinvalide"),
])
def test_code_identifie_uniquement_par_contexte_code(nature, cid):
    result = DilaParser().parse(_article(nature=nature, cid=cid))
    assert result["code"] is None
    assert result["texte_id"] == cid


def test_mixed_content_paragraphes_queues_tableau_et_xml_original():
    result = DilaParser().parse(_article(
        "<p>Le <b>salarié</b> est protégé.</p><p>Suite<br/>Deuxième ligne.</p>"
        "<table><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></table>"
    ))
    assert result["texte"] == "Le salarié est protégé.\nSuite\nDeuxième ligne.\nA\tB\nC\tD"
    assert "<b>salarié</b>" in result["contenu_xml"]


def test_cdata_xhtml_est_lu_comme_fragment_strict():
    result = DilaParser().parse(_article("<![CDATA[<p>Premier <b>mot</b>.</p><p>Second.</p>]]>"))
    assert result["texte"] == "Premier mot.\nSecond."
    assert result["fragment_errors"] == []


def test_cdata_malforme_conserve_litteral_et_avertissement():
    result = DilaParser().parse(_article("<![CDATA[<p>Texte incomplet]]>"))
    assert result["texte"] == "<p>Texte incomplet"
    assert len(result["fragment_errors"]) == 1


@pytest.mark.parametrize("xml", [b"<ARTICLE><META></ARTICLE>", b"<ARTICLE/ ><ARTICLE/>", b"<ARTICLE/>garbage"])
def test_xml_malforme_non_recupere(xml):
    with pytest.raises(DilaXMLInvalide):
        DilaParser().parse(xml)


def test_xxe_interdit_meme_avec_dtd_locale(dtd_dir):
    xml = b'<!DOCTYPE ARTICLE [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><ARTICLE>&xxe;</ARTICLE>'
    with pytest.raises(DilaXMLInvalide, match="ENTITY interdit"):
        DilaParser(dtd_dir).parse(xml)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_xxe_ne_contourne_pas_controle_par_encodage(dtd_dir, encoding):
    xml = '<!DOCTYPE ARTICLE [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><ARTICLE>&xxe;</ARTICLE>'
    with pytest.raises(DilaXMLInvalide, match="ENTITY interdit"):
        DilaParser(dtd_dir).parse(xml.encode(encoding))


def test_dtd_externe_inconnue_bloquee(dtd_dir):
    with pytest.raises(DilaXMLInvalide, match="interdite"):
        DilaParser(dtd_dir).parse(b'<!DOCTYPE ARTICLE SYSTEM "https://example.org/evil.dtd"><ARTICLE/>')


def test_doctype_sans_dtd_locale_interdit():
    with pytest.raises(DilaXMLInvalide, match="sans DTD locale"):
        DilaParser().parse(b'<!DOCTYPE ARTICLE SYSTEM "file:///etc/passwd"><ARTICLE/>')


def test_validation_dtd_separee_conserve_article_incompatible(dtd_dir):
    result = DilaParser(dtd_dir).parse(_article("<p>Texte &nbsp; officiel.</p>"))
    assert result["article_id"] == "LEGIARTI000006901177"
    assert result["texte"] == "Texte officiel."
    # Les attributs sont volontairement absents de la DTD minimale.
    assert result["dtd_valid"] is False
    assert result["dtd_errors"]


def test_validation_dtd_positive_et_pas_fuite_erreurs(dtd_dir):
    parser = DilaParser(dtd_dir)
    assert parser.parse(_article())["dtd_valid"] is False
    result = parser.parse(b"<ARTICLE/>")
    assert result["dtd_valid"] is True
    assert result["dtd_errors"] == []


def test_statut_vide_et_dates_conditionnelles_restent_bruts():
    xml = _article().replace(b"<ETAT>MODIFIE</ETAT>", b"<ETAT/>").replace(b"2008-05-01", b"2222-02-22")
    result = DilaParser().parse(xml)
    assert result["statut"] == ""
    assert result["date_debut"] == "2222-02-22"


def test_section_ta_id_racine_et_structure():
    xml = b'''<SECTION_TA><ID>LEGISCTA000000000001</ID><TITRE_TA>Chapitre</TITRE_TA>
    <STRUCTURE_TA><LIEN_ART id="LEGIARTI000000000001" num="1"/></STRUCTURE_TA>
    <CONTEXTE><TEXTE cid="LEGITEXT000006072050" nature="CODE"/></CONTEXTE></SECTION_TA>'''
    result = DilaParser().parse(xml)
    assert result["id"] == "LEGISCTA000000000001"
    assert result["structure"][0]["id"] == "LEGIARTI000000000001"


def test_texte_version_metadonnees():
    xml = b'''<TEXTE_VERSION><META><META_COMMUN><ID>LEGITEXT000000000001</ID><NATURE>LOI</NATURE></META_COMMUN>
    <META_SPEC><META_TEXTE_CHRONICLE><CID>JORFTEXT000000000001</CID><NUM>2020-1</NUM></META_TEXTE_CHRONICLE>
    <META_TEXTE_VERSION><TITRE>Loi</TITRE><TITREFULL>Loi complete</TITREFULL><ETAT>ABROGE</ETAT>
    <DATE_DEBUT>2020-01-01</DATE_DEBUT><DATE_FIN>2021-01-01</DATE_FIN></META_TEXTE_VERSION></META_SPEC></META></TEXTE_VERSION>'''
    result = DilaParser().parse(xml)
    assert result["id"] == "LEGITEXT000000000001"
    assert result["cid"] == "JORFTEXT000000000001"
    assert result["nature"] == "LOI"
    assert result["titre"] == "Loi complete"
    assert result["statut"] == "ABROGE"
