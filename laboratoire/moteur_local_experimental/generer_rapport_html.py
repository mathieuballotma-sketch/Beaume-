"""generer_rapport_html.py — Produit un rapport HTML auto-suffisant.

Lit resultat_24_pages_final_v2.json (ou un autre) et génère un fichier HTML
autonome, embarqué, ouvrable dans n'importe quel navigateur sans serveur.
"""
import json
import sys
from html import escape
from pathlib import Path


def _ech(t):
    return escape(str(t))


def _badge(etat):
    couleurs = {
        "propose": "#2e7d32",
        "incertain": "#f57c00",
        "manquant": "#c62828",
        "contradiction": "#b71c1c",
        "tension": "#e65100",
        "hors_condition": "#616161",
        "ok": "#2e7d32",
    }
    c = couleurs.get(etat, "#424242")
    return (
        '<span style="display:inline-block;padding:2px 8px;border-radius:3px;'
        'background:' + c + ';color:#fff;font-size:11px;font-weight:600;'
        'text-transform:uppercase;letter-spacing:0.5px">' + _ech(etat) + '</span>'
    )


def rendre_html(data, chemin_json):
    affs_total = []
    for pg in data["pages"]:
        for aff in pg.get("affirmations", []):
            affs_total.append((pg["page"], aff))
    hc_total = sum(len(pg.get("hors_condition", [])) for pg in data["pages"])
    contradictions = data.get("contradictions", [])
    duree = sum(pg.get("duree_modele_s", 0) or 0 for pg in data["pages"])
    journal = [e for e in data["journal"] if not e["nom"].startswith("page_")]

    parts = []
    parts.append('<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">')
    parts.append('<title>Rapport Beaume — ' + _ech(data["piece"]) + '</title>')
    parts.append('<style>')
    parts.append('''
    body { font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
           max-width: 980px; margin: 2em auto; padding: 0 1.5em; color: #212121;
           line-height: 1.55; background: #fafafa; }
    h1 { font-size: 24px; margin-bottom: 4px; }
    h2 { font-size: 18px; margin-top: 2em; padding-bottom: 6px;
         border-bottom: 2px solid #e0e0e0; }
    .meta { color: #616161; font-size: 13px; font-family: "SF Mono", Menlo, monospace; }
    .card { background: #fff; border-radius: 6px; padding: 14px 18px;
            margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
    .card.tension { border-left: 4px solid #e65100; }
    .card.contradiction { border-left: 4px solid #b71c1c; }
    .card.fait { border-left: 4px solid #2e7d32; }
    .card.hors { border-left: 4px solid #9e9e9e; background: #f5f5f5; }
    .page { font-family: "SF Mono", Menlo, monospace; font-size: 12px;
            color: #1976d2; margin-right: 8px; }
    .texte { font-size: 14px; }
    .raison { font-size: 12px; color: #616161; margin-top: 6px;
              font-style: italic; }
    details summary { cursor: pointer; font-weight: 600; padding: 8px 0;
                       color: #424242; }
    details[open] summary { margin-bottom: 8px; }
    .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
            margin: 10px 0; }
    .pair > div { padding: 10px 12px; background: #fff; border-radius: 4px;
                  border: 1px solid #e0e0e0; font-size: 13px; }
    .pair .label { font-size: 11px; color: #757575; text-transform: uppercase;
                    margin-bottom: 4px; letter-spacing: 0.5px; }
    .journal-row { display: flex; justify-content: space-between;
                    font-size: 13px; padding: 4px 0;
                    border-bottom: 1px solid #eeeeee; }
    .journal-row:last-child { border-bottom: none; }
    .journal-nom { font-family: "SF Mono", Menlo, monospace; }
    .footer { color: #757575; font-size: 12px; margin-top: 3em; padding-top: 1em;
              border-top: 1px solid #e0e0e0; }
    .limite { background: #fff8e1; border-left: 3px solid #ffa000;
              padding: 10px 14px; margin: 12px 0; font-size: 13px; }
    ''')
    parts.append('</style></head><body>')

    parts.append('<h1>Rapport Beaume — analyse de dossier</h1>')
    parts.append('<div class="meta">')
    parts.append('Pièce : ' + _ech(data["piece"]) + ' · ')
    parts.append('SHA-256 : ' + _ech(data["sha_piece"][:16]) + '… · ')
    parts.append('Pages : ' + str(len(data["pages"])) + ' · ')
    parts.append('Durée analyse : ' + format(duree, ".1f") + ' s')
    parts.append('</div>')

    parts.append('<div class="limite">')
    parts.append('<strong>Rapport expérimental — données fictives.</strong> '
                 'Ce rapport ne constitue pas une analyse juridique et ne doit pas '
                 'être utilisé sur des données réelles sans revue préalable. '
                 'L\'avocat reste décideur.')
    parts.append('</div>')

    # --- Contradictions et tensions ---
    if contradictions:
        parts.append('<h2>⚠ Points à examiner (' + str(len(contradictions)) + ')</h2>')
        for c in contradictions:
            niveau = c["niveau"]
            parts.append('<div class="card ' + niveau + '">')
            parts.append(_badge(niveau) + ' <strong>Dossier ' + _ech(c["dossier"]) + '</strong>')
            parts.append('<div class="pair">')
            parts.append('<div><div class="label">Page ' + str(c["page_a"]) + '</div>' + _ech(c["texte_a"]) + '</div>')
            parts.append('<div><div class="label">Page ' + str(c["page_b"]) + '</div>' + _ech(c["texte_b"]) + '</div>')
            parts.append('</div>')
            parts.append('<div class="raison">' + _ech(c["raison"]) + '</div>')
            parts.append('</div>')

    # --- Faits retenus ---
    parts.append('<h2>Faits extraits (' + str(len(affs_total)) + ')</h2>')
    if not affs_total:
        parts.append('<p>Aucun fait extrait.</p>')
    for page, aff in affs_total:
        parts.append('<div class="card fait">')
        parts.append('<span class="page">p' + str(page) + '</span>')
        parts.append('<span class="texte">' + _ech(aff["texte"]) + '</span>')
        date = aff.get("date", "")
        pers = aff.get("personnes", "")
        propos = aff.get("date_proposee_modele", "")
        non_ancree = aff.get("date_non_ancree", False)
        sans_date = aff.get("concret_sans_date", False)
        detail = []
        if date and date != "inconnue":
            detail.append("date : " + _ech(date))
        elif non_ancree and propos:
            detail.append("date <strong>non ancrée</strong> (modèle a proposé " + _ech(propos) + ", absent du texte)")
        elif sans_date:
            detail.append("fait <strong>non daté</strong> dans le texte")
        if pers and pers != "aucune":
            detail.append("personnes : " + _ech(pers))
        if detail:
            parts.append('<div class="raison">' + " · ".join(detail) + '</div>')
        parts.append('</div>')

    # --- Phrases écartées (repliable) ---
    if hc_total:
        parts.append('<details><summary>Phrases écartées (' + str(hc_total) + ' — descriptives ou sans fait) </summary>')
        for pg in data["pages"]:
            hc = pg.get("hors_condition", [])
            if not hc:
                continue
            parts.append('<div style="margin-bottom:10px"><span class="page">p' + str(pg["page"]) + '</span>')
            for aff in hc:
                parts.append('<div style="font-size:12px;color:#616161;margin:3px 0">— ' + _ech(aff["texte"][:140]) + '</div>')
            parts.append('</div>')
        parts.append('</details>')

    # --- Journal ---
    parts.append('<h2>Journal des étapes</h2>')
    for e in journal:
        parts.append('<div class="journal-row">')
        parts.append('<span class="journal-nom">' + _ech(e["nom"]) + '</span>')
        parts.append('<span>' + _badge(e["statut"]) + ' ' + format(e["duree_s"], ".2f") + ' s</span>')
        parts.append('</div>')

    # --- Footer ---
    parts.append('<div class="footer">')
    parts.append('Source : ' + _ech(chemin_json) + '<br>')
    parts.append('Pipeline : llama-completion + granite-3.1-dense-2b (local). ')
    parts.append('Cache de prompt refusé. Aucune donnée envoyée sur Internet.<br>')
    parts.append('Contradictions détectées par règles déterministes, pas par IA. '
                 'Les cas ambigus restent non conclus.')
    parts.append('</div>')

    parts.append('</body></html>')
    return "\n".join(parts)


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else "resultat_24_pages_final_v2.json"
    sortie = sys.argv[2] if len(sys.argv) > 2 else "rapport.html"
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    html = rendre_html(data, source)
    Path(sortie).write_text(html, encoding="utf-8")
    print("écrit : " + sortie + " (" + str(len(html)) + " octets)")


if __name__ == "__main__":
    main()
