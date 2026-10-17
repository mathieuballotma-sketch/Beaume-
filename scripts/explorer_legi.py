"""Explore AgentPublic/legi en profondeur.

Objectif : trouver les articles de codes consolides (Code du travail,
Code civil, etc.) et comprendre leurs metadonnees.
"""
from collections import Counter

from datasets import load_dataset

ds = load_dataset("AgentPublic/legi", split="train")

categories = Counter()
natures = Counter()
exemples_code_travail = []

for batch in ds.iter(batch_size=10000):
    n = len(batch["doc_id"])
    for i in range(n):
        cat = batch["category"][i] or "VIDE"
        nat = batch["nature"][i] or "VIDE"
        categories[cat] += 1
        natures[nat] += 1

        ft = batch["full_title"][i] or ""
        if "code du travail" in ft.lower() and len(exemples_code_travail) < 5:
            exemples_code_travail.append({
                "category": cat,
                "nature": nat,
                "title": batch["title"][i],
                "full_title": ft[:120],
                "number": batch["number"][i],
                "doc_id": batch["doc_id"][i],
            })

print("=== Categories (toutes) ===")
for c, n in categories.most_common(40):
    print(f"  {c} : {n}")

print()
print("=== Natures (toutes) ===")
for n, c in natures.most_common(20):
    print(f"  {n} : {c}")

print()
print("=== Exemples contenant 'Code du travail' ===")
for e in exemples_code_travail:
    print(f"  cat={e['category']} nat={e['nature']}")
    print(f"    number={e['number']} doc_id={e['doc_id']}")
    print(f"    full_title={e['full_title']}")