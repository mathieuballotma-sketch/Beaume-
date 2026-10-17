"""Verifie que les faits inventes correspondent bien aux articles de loi.

Utilise Qwen 2.5 7B comme 'juge' pour évaluer la cohérence.
"""
import json
import ollama
from pathlib import Path

FICHIER = Path("data/entrainement/dataset_ft.jsonl")
MODELE_JUGE = "qwen2.5:7b-instruct"

def verifier_correspondance(fait, loi):
    """Demande a Qwen de juger la correspondance."""
    prompt = f"""Tu es un juge juridique français très strict.
Un étudiant en droit a inventé la situation factuelle suivante pour illustrer cet article de loi :

ARTICLE DE LOI :
{loi[:600]}

SITUATION INVENTÉE :
{fait}

Question : Cette situation factuelle justifie-t-elle vraiment l'application de cet article de loi ?

Réponds UNIQUEMENT par :
- 'OUI' si la situation est pertinente et réaliste.
- 'NON' si la situation est hors sujet, trop vague, ou ne correspond pas à l'article.

Ta réponse (OUI ou NON) :"""
    
    try:
        r = ollama.generate(model=MODELE_JUGE, prompt=prompt, options={"temperature": 0.0})
        reponse = r["response"].strip().upper()
        return "OUI" in reponse
    except Exception as e:
        print(f"Erreur Ollama : {e}")
        return False

def main():
    if not FICHIER.exists():
        print(f"Fichier introuvable : {FICHIER}")
        return
        
    valides = 0
    total = 0
    erreurs = []

    with FICHIER.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            data = json.loads(line)
            human = data['conversations'][1]['value']
            gpt = json.loads(data['conversations'][2]['value'])
            
            # Extraction du fait (la ligne qui commence par [dossier.pdf, page 1])
            fait = "Non trouvé"
            for l in human.split('\n'):
                if l.startswith('[dossier.pdf, page 1]'):
                    fait = l.replace('[dossier.pdf, page 1] ', '')
                    break
            
            loi = gpt['citations'][0]['extrait']
            
            print(f"Vérification {i+1}...", end=" ", flush=True)
            if verifier_correspondance(fait, loi):
                print("✅ OK")
                valides += 1
            else:
                print("❌ DOUTEUX")
                erreurs.append({"ligne": i+1, "fait": fait, "loi": loi[:150]})
            total += 1

    print(f"\n--- RÉSULTAT ---")
    print(f"Exemples valides : {valides}/{total}")
    
    if erreurs:
        print("\n⚠️ Exemples à corriger manuellement :")
        for e in erreurs[:5]: # On affiche les 5 premiers
            print(f"- Ligne {e['ligne']} :")
            print(f"  Fait : {e['fait'][:100]}...")
            print(f"  Loi  : {e['loi'][:100]}...")
            print()

if __name__ == "__main__":
    main()