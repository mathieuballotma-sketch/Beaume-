"""Usine à dossiers — version corrigée du 2026-10-22.

ÉTAT : DÉSACTIVÉE (fail-closed).

Les templates hérités du premier prototype contiennent des constantes
d'affaire codées en dur (parties, garantie, demande, articles). Ils
contaminent tout dossier généré : dossier_62bbeca0 raconte une autre
affaire que la décision source 62bbeca0 (ECLI:FR:CCASS:2022:C100555).
Voir l'audit du 2026-10-22.

Tant que les templates ne sont pas paramétrés par scénario, ce script
refuse de générer. Il ne supprime aucun dossier existant : les
productions contaminées se marquent inéligibles via
`--marquer-inelegibles`.

Corrections apportées dans ce fichier (indépendantes du préflight, à
conserver quand il sera levé) :
  - montants extraits en Decimal, ordre stable, offsets et contexte ;
  - dates contraintes à des mentions candidates identifiées (le LLM
    choisit un identifiant, pas une valeur libre) ;
  - plus de list(set(...)) ni de montants[0] ;
  - vérification que les identifiants retournés existent ;
  - manifeste d'inéligibilité pour les dossiers existants.

Étape suivante (hors de ce fichier) : construire un scénario propre par
décision (fiche de scénario), puis paramétrer les templates depuis ce
scénario. Le préflight se lèvera alors en retirant `_TEMPLATES_HERITES`.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import ollama
from datasets import Dataset

# ---------------------------------------------------------------------------
# Chemins et constantes
# ---------------------------------------------------------------------------

RACINE_PROJET = Path(__file__).resolve().parents[1]
FICHIER_ARROW = (
    RACINE_PROJET
    / "data"
    / "legal"
    / "jurisprudence"
    / "cour_de_cassation"
    / "data-00009-of-00010.arrow"
)
DOSSIER_CONSO = RACINE_PROJET / "data" / "scenarios" / "par_specialite" / "consommation"
DOSSIER_SORTIE = RACINE_PROJET / "data" / "scenarios" / "usine_generation"
MODELE_OLLAMA = "qwen2.5:7b-instruct"

# Constantes d'affaire héritées du prototype. Leur présence dans les
# templates est le défaut bloquant.
#
# ATTENTION aux écarts entre ce qui est attendu et ce que dit le texte :
# dans les templates, l'expression réelle est « 2224 du Code civil »
# (pas « article 2224 »). Une constante mal choisie donne un faux
# sentiment de couverture. Voir test_preflight_detecte_les_cinq_constantes.
CONSTANTES_AFFAIRE_INTERDITES = (
    "vieil armand",
    "sci jml",
    "m. [p]",
    "l.137-2",
    "2224 du code civil",
)

_PATTERN_DATE = re.compile(
    r"\b\d{1,2}\s+"
    r"(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)"
    r"\s+\d{4}\b",
    re.IGNORECASE,
)

# Capture 123 456,41 ; 41 ; 1 000 000 € ; 123.45 euros.
_PATTERN_MONTANT = re.compile(
    r"\b(\d{1,3}(?:[\s\u00A0.]\d{3})*|\d+)"
    r"(?:[.,](\d{1,2}))?"
    r"\s*(euros|€)"
    r"(?=[\s.,;:!?)\]]|$)",
    re.IGNORECASE,
)

_MOIS_FR = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12,
}

# ---------------------------------------------------------------------------
# Templates hérités — conservés pour diagnostic uniquement
# ---------------------------------------------------------------------------
# NE PAS les utiliser pour générer. Ils décrivent l'affaire du prototype
# (Crédit mutuel du Vieil Armand / M. [P] / SCI JML), pas la décision
# traitée. Le préflight refuse la génération tant qu'ils sont présents.

_TEMPLATES_HERITES = """*** PIÈCE SYNTHÉTIQUE - GÉNÉRÉE POUR TEST - NE PAS UTILISER EN VRAI ***

**CONTRAT DE PRÊT NOTARIÉ**

**Date :** {date_pret}

**Entre :**
La **Caisse de Crédit mutuel du Vieil Armand** (ci-après "le Prêteur"),
et **M. [P]** (ci-après "l'Emprunteur").

**Article 1 : Objet du prêt**
Le Prêteur consent à l'Emprunteur un prêt d'un montant de **{montant}**.

**Article 2 : Garanties**
Le prêt est garanti par une affectation hypothécaire sur un bien immobilier appartenant à la SCI JML.

**Article 3 : Conditions financières**
La durée et le taux d'intérêt sont fixés à [Information non disponible].

Fait à [Lieu non disponible], le {date_pret}.

---

*** PIÈCE SYNTHÉTIQUE - GÉNÉRÉE POUR TEST - NE PAS UTILISER EN VRAI ***

**Mise en demeure de payer le solde du prêt**

Le {date_dech}

**À l'attention de :** SCI JML
**Expéditeur :** Caisse de Crédit mutuel du Vieil Armand

Objet : Déchéance du terme et mise en demeure de payer

Madame, Monsieur,

Par acte notarié en date du {date_pret}, notre établissement a consenti à M. [P] un prêt d'un montant de {montant}, garanti par une affectation hypothécaire sur un bien de la SCI JML.

Suite à des échéances impayées, nous vous informons que nous prononçons la déchéance du terme. En conséquence, la totalité du solde restant dû est immédiatement exigible.

Par la présente, nous vous mettons en demeure de régler la somme due dans un délai de [Information non disponible].

Veuillez agréer, Madame, Monsieur, l'expression de nos salutations distinguées.

**Caisse de Crédit mutuel du Vieil Armand**

---

*** PIÈCE SYNTHÉTIQUE - GÉNÉRÉE POUR TEST - NE PAS UTILISER EN VRAI ***

**ASSIGNATION DEVANT [Juridiction non spécifiée]**

Le {date_assign}

**DEMANDEUR :**
M. [P]

**DÉFENDEUR :**
Caisse de Crédit mutuel du Vieil Armand

**Objet de la demande :** Constatation de la prescription de la créance.

**Faits et procédure :**
Le {date_pret}, un prêt de {montant} a été consenti par la banque à M. [P], garanti par une hypothèque sur un bien de la SCI JML.
Le {date_dech}, la banque a prononcé la déchéance du terme.
Estimant que l'action en paiement de la banque est prescrite, le demandeur sollicite la saisine de votre juridiction.

**Par ces motifs,**
Vu les articles L.137-2 du Code de la consommation et 2224 du Code civil,
Le demandeur vous prie de bien vouloir :
- Constater la prescription de la créance de la banque.
- Condamner la banque aux entiers dépens.

**M. [P]**
"""

# ---------------------------------------------------------------------------
# Préflight
# ---------------------------------------------------------------------------

def _detecter_constantes(texte: str) -> tuple[list[str], list[str]]:
    """Retourne (présentes, absentes) parmi CONSTANTES_AFFAIRE_INTERDITES.

    Comparaison insensible à la casse. Rendre aussi les absentes permet
    de distinguer « vérifié et absent » de « jamais vérifié » : un
    diagnostic honnête sur la couverture du contrôle.
    """
    bas = texte.lower()
    presentes = [c for c in CONSTANTES_AFFAIRE_INTERDITES if c in bas]
    absentes = [c for c in CONSTANTES_AFFAIRE_INTERDITES if c not in bas]
    return presentes, absentes


def preflight() -> None:
    """Refuse la génération tant que les templates hérités sont utilisés.

    Fail-closed : aucune écriture, aucun dossier créé, aucune suppression.
    Le préflight se lève en paramétrant les templates par scénario, puis
    en vidant `_TEMPLATES_HERITES`.
    """
    presentes, absentes = _detecter_constantes(_TEMPLATES_HERITES)
    if presentes:
        message = (
            "Génération désactivée : générateur non paramétré par scénario.\n"
            "Constantes d'affaire détectées dans les templates hérités : "
            + ", ".join(presentes)
        )
        if absentes:
            message += (
                "\nConstantes non trouvées (vérifiées, absentes) : "
                + ", ".join(absentes)
            )
        message += (
            "\nAucun dossier n'a été créé.\n"
            "Marquer les dossiers existants inéligibles avant toute "
            "réutilisation : python scripts/11_usine_a_dossiers.py "
            "--marquer-inelegibles"
        )
        raise SystemExit(message)


# ---------------------------------------------------------------------------
# Extraction (corrigée)
# ---------------------------------------------------------------------------

def extraire_contexte(texte: str, debut: int, fin: int, fenetre: int = 200) -> str:
    d = max(0, debut - fenetre)
    f = min(len(texte), fin + fenetre)
    return "..." + texte[d:f].replace("\n", " ") + "..."


def extraire_dates_candidates(texte: str) -> list[dict]:
    """Mentions de date avec identifiant stable, offsets et contexte.

    Le LLM choisira un identifiant (`date_N`), jamais une valeur libre.
    Conserver toutes les occurrences : une même date peut apparaître
    dans plusieurs contextes.
    """
    mentions: list[dict] = []
    for i, m in enumerate(_PATTERN_DATE.finditer(texte)):
        mentions.append(
            {
                "id": f"date_{i}",
                "valeur": m.group(0),
                "debut": m.start(),
                "fin": m.end(),
                "contexte": extraire_contexte(texte, m.start(), m.end()),
            }
        )
    return mentions


def extraire_montants(texte: str) -> list[dict]:
    """Montants en Decimal, ordre stable, offsets et contexte.

    Aucun rôle n'est attribué : capital initial, solde restant dû,
    intérêts, indemnité et frais restent à distinguer explicitement.
    Un montant inconnu ne doit pas être inventé ni approximé.
    """
    montants: list[dict] = []
    for m in _PATTERN_MONTANT.finditer(texte):
        entier = re.sub(r"[\s\u00A0.]", "", m.group(1))
        decimales = (m.group(2) or "").ljust(2, "0")[:2]
        try:
            valeur = Decimal(f"{entier}.{decimales}")
        except InvalidOperation:
            continue
        montants.append(
            {
                "valeur": valeur,
                "brut": m.group(0),
                "debut": m.start(),
                "fin": m.end(),
                "contexte": extraire_contexte(texte, m.start(), m.end()),
            }
        )
    return montants


def parser_date_fr(mention: str) -> datetime | None:
    m = re.match(r"(\d{1,2})\s+([a-zéûô]+)\s+(\d{4})", mention.lower())
    if not m:
        return None
    mois = _MOIS_FR.get(m.group(2))
    if not mois:
        return None
    try:
        return datetime(int(m.group(3)), mois, int(m.group(1)))
    except ValueError:
        return None


def verifier_chronologie(ids: dict, mentions: dict) -> bool:
    """Vérifie que les identifiants existent puis que la chronologie tient.

    L'ordre inverse de l'audit : d'abord vérifier que le LLM a choisi un
    identifiant réellement présent dans les mentions candidates, ensuite
    seulement vérifier l'ordre. Trois dates plausibles inventées ne
    doivent pas passer.
    """
    valeurs: list[datetime] = []
    for role in ("date_pret", "date_dech", "date_assign"):
        mid = ids.get(role)
        if not mid or mid not in mentions:
            return False
        dt = parser_date_fr(mentions[mid]["valeur"])
        if dt is None:
            return False
        valeurs.append(dt)
    return valeurs[0] < valeurs[1] < valeurs[2]


# ---------------------------------------------------------------------------
# Génération (désactivée tant que le préflight n'est pas levé)
# ---------------------------------------------------------------------------

def generer_dossier(base: dict, dossier_nom: str) -> None:
    """Refuse d'écrire un dossier tant que les templates ne sont pas paramétrés.

    Cette fonction n'est jamais atteinte dans l'état actuel (preflight
    lève SystemExit). Elle est conservée comme point d'insertion pour
    l'étape 2.
    """
    raise RuntimeError(
        "generer_dossier est désactivée : templates non paramétrés par "
        "scénario. Voir preflight()."
    )


# ---------------------------------------------------------------------------
# Inéligibilité des dossiers existants
# ---------------------------------------------------------------------------

def marquer_inelegibles(motif: str = "contamination_affaire") -> Path:
    """Écrit un manifeste listant les dossiers existants comme inéligibles.

    Ne supprime rien. Idempotent : réécrit le manifeste à chaque appel.
    """
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    manifeste = DOSSIER_SORTIE / "INELIGIBLE.json"
    existants = sorted(
        p.name for p in DOSSIER_SORTIE.glob("dossier_*") if p.is_dir()
    )
    data = {
        "genere_le": datetime.now(timezone.utc).isoformat(),
        "motif": motif,
        "dossiers": [
            {"nom": nom, "eligible_entrainement": False, "motif": motif}
            for nom in existants
        ],
    }
    manifeste.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Manifeste écrit : {manifeste} ({len(existants)} dossiers marqués)")
    return manifeste


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

def main() -> int:
    # 1) Préflight : bloque tant que les templates hérités sont utilisés.
    preflight()

    # 2) Code inatteignable dans l'état actuel. Il est prêt pour l'étape 2
    #    (templates paramétrés par scénario), quand `_TEMPLATES_HERITES`
    #    aura été retiré et le préflight levé.
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    print("=== DÉMARRAGE DE L'USINE (V6 - préflight) ===")

    ds = Dataset.from_file(str(FICHIER_ARROW))
    succes = 0

    for fichier in sorted(DOSSIER_CONSO.glob("*.json")):
        fiche = json.loads(fichier.read_text(encoding="utf-8"))
        decision_id = fiche["decision_id"]
        texte = next((row["text"] for row in ds if row["id"] == decision_id), None)
        if not texte or len(texte) < 1000:
            continue

        mentions = extraire_dates_candidates(texte)
        if not mentions:
            continue
        montants = extraire_montants(texte)

        ctx = "\n".join(
            f"- {m['id']} : {m['valeur']} — {m['contexte']}" for m in mentions
        )
        prompt = (
            f"Voici des mentions de date extraites d'une décision :\n{ctx}\n\n"
            "Tâche : associe chaque rôle à l'identifiant d'une mention.\n"
            "- date_pret : signature du prêt\n"
            "- date_dech : mise en demeure / déchéance du terme\n"
            "- date_assign : assignation en justice\n\n"
            "Réponds UNIQUEMENT en JSON, en choisissant un identifiant parmi "
            "ceux ci-dessus, ou null si aucun ne convient :\n"
            '{"date_pret": "date_N" | null, '
            '"date_dech": "date_N" | null, '
            '"date_assign": "date_N" | null}\n'
        )

        print(f"\nAnalyse {decision_id}...")
        try:
            rep = ollama.chat(
                model=MODELE_OLLAMA,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.0},
            )
            ids = json.loads(rep["message"]["content"])
        except Exception as e:
            print(f"  [ERREUR] {e}")
            continue

        mentions_par_id = {m["id"]: m for m in mentions}
        if not verifier_chronologie(ids, mentions_par_id):
            print("  [REJET] Dates manquantes, inconnues ou chronologie invalide.")
            continue

        print("  [OK] Dates et chronologie validées (écriture désactivée).")
        base = {
            "date_pret": mentions_par_id[ids["date_pret"]]["valeur"],
            "date_dech": mentions_par_id[ids["date_dech"]]["valeur"],
            "date_assign": mentions_par_id[ids["date_assign"]]["valeur"],
            "montants": montants,  # liste de dicts, plus de montants[0]
        }
        try:
            generer_dossier(base, f"dossier_{decision_id[:8]}")
            succes += 1
        except RuntimeError as e:
            print(f"  [BLOQUÉ] {e}")
            break  # inutile de boucler si l'écriture est désactivée

    print(f"\n=== BILAN : {succes} dossiers générés ===")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--marquer-inelegibles":
        marquer_inelegibles()
    else:
        sys.exit(main())