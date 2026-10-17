"""Genere les datasets (Embedder + LLM) avec validation de statut."""
from __future__ import annotations

import json
import sqlite3
import random
from pathlib import Path

import ollama

DB_PATH = Path("data/vector/legi_full.sqlite")
SORTIE_EMBEDDER = Path("data/entrainement/train_embedder.jsonl")
SORTIE_LLM = Path("data/entrainement/train_llm.jsonl")
MODELE_GEN = "qwen2.5:7b-instruct"
NB_EXEMPLES = 50

SYSTEM_PROMPT = """Tu es un assistant juridique francais.
Tu produis UNIQUEMENT un objet JSON valide."""

USER_TEMPLATE = """Analyse ce dossier.

=== LISTE DES FICHIERS ===
- dossier.pdf

=== DOSSIER CLIENT ===
[dossier.pdf, page 1] {fait}

=== ARTICLES DISPONIBLES ===
{articles_formates}

=== REPONSE (JSON uniquement) ==="""

def generer_fait(article_texte: str, article_numero: str) -> str:
    prompt = (
        f"Voici un article de loi : {article_numero}\n"
        f"Texte : {article_texte[:400]}\n\n"
        "Agis comme un justiciable qui explique son problème à son avocat. "
        "Raconte une histoire courte (2 phrases max). "
        "RÈGLES : Ne mentionne jamais le mot 'article' ou le numéro de loi. "
        "Ne définis pas la loi, raconte des FAITS (conflits, dates, actions).\n"
        "Ton histoire :"
    )
    try:
        r = ollama.generate(model=MODELE_GEN, prompt=prompt, options={"temperature": 0.7})
        return r["response"].strip().replace('"', '')
    except Exception:
        return ""

def main() -> None:
    if not DB_PATH.exists():
        return

    SORTIE_EMBEDDER.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT code, numero, texte FROM articles_fts LIMIT ?", (NB_EXEMPLES,))
    rows = cursor.fetchall()
    tous_les_articles = conn.execute("SELECT code, numero, texte FROM articles_fts").fetchall()

    lignes_embedder = []
    lignes_llm = []
    
    print(f"Generation de {NB_EXEMPLES} exemples...")
    
    for i, row in enumerate(rows, 1):
        if len(row["texte"]) < 50:
            continue
            
        fait = generer_fait(row["texte"], row["numero"])
        if not fait or len(fait) < 10:
            continue
            
        statut = "genere_auto_filtre"
        
        # --- 1. DATASET EMBEDDER (Paire simple pour la recherche) ---
        lignes_embedder.append({
            "fait": fait,
            "article_positif": {
                "code": row["code"],
                "numero": row["numero"],
                "texte": row["texte"]
            },
            "statut": statut
        })
        
        # --- 2. DATASET LLM (Avec leurres et JSON) ---
        # On pioche 4 leurres au hasard
        leurres = [a for a in tous_les_articles if a["numero"] != row["numero"]]
        leurres_choisis = random.sample(leurres, min(4, len(leurres)))
        
        articles_melanges = [
            {"code": row["code"], "numero": row["numero"], "texte": row["texte"], "est_vrai": True}
        ] + [
            {"code": l["code"], "numero": l["numero"], "texte": l["texte"], "est_vrai": False} 
            for l in leurres_choisis
        ]
        random.shuffle(articles_melanges) # Mélange critique pour le biais de position
        
        articles_formates = "\n".join(
            [f"- {a['code']} {a['numero']} : {a['texte'][:300]}" for a in articles_melanges]
        )
        
        reponse = {
            "statut": statut,
            "contexte": fait,
            "citations": [{
                "code": row["code"],
                "numero": row["numero"],
                "extrait": row["texte"][:150],
                "fichier": "dossier.pdf",
                "pages": [1],
            }],
        }
        
        lignes_llm.append({
            "conversations": [
                {"from": "system", "value": SYSTEM_PROMPT},
                {"from": "human", "value": USER_TEMPLATE.format(
                    fait=fait,
                    articles_formates=articles_formates,
                )},
                {"from": "gpt", "value": json.dumps(reponse, ensure_ascii=False)},
            ]
        })
        print(f"[{i}/{NB_EXEMPLES}] Fait genere et melange avec 4 leurres.")

    # Écriture des deux fichiers
    with SORTIE_EMBEDDER.open("w", encoding="utf-8") as f:
        for ligne in lignes_embedder:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            
    with SORTIE_LLM.open("w", encoding="utf-8") as f:
        for ligne in lignes_llm:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    print(f"\nSucces !")
    print(f"- {len(lignes_embedder)} exemples Embedder -> {SORTIE_EMBEDDER}")
    print(f"- {len(lignes_llm)} exemples LLM -> {SORTIE_LLM}")

if __name__ == "__main__":
    main()