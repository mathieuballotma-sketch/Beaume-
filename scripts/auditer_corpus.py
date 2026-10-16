"""Audite le corpus legi_full.sqlite.

Repond a :
- Combien d'articles distincts ?
- Combien de versions par article ?
- Quels codes sont couverts ?
- Quelle est la plage temporelle ?
- Combien d'articles ont plusieurs versions ?
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from beaume.config import paths

CHEMIN_DB = paths.VECTOR / "legi_full.sqlite"


def main() -> int:
    if not CHEMIN_DB.exists():
        raise SystemExit(f"Introuvable : {CHEMIN_DB}")

    conn = sqlite3.connect(str(CHEMIN_DB))
    conn.row_factory = sqlite3.Row
    try:
        print("=== Schema ===")
        for ligne in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ):
            print(f"  Table : {ligne['name']}")

        print()
        print("=== Compteurs ===")
        n_articles = conn.execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0]
        n_versions = conn.execute(
            "SELECT COUNT(*) FROM versions"
        ).fetchone()[0]
        print(f"Articles distincts : {n_articles}")
        print(f"Versions totales   : {n_versions}")

        print()
        print("=== Distribution versions/article ===")
        rows = conn.execute("""
            SELECT n_versions, COUNT(*) AS n_articles
            FROM (
                SELECT article_id, COUNT(*) AS n_versions
                FROM versions
                GROUP BY article_id
            )
            GROUP BY n_versions
            ORDER BY n_versions
        """).fetchall()
        for r in rows:
            print(f"  {r['n_versions']:3d} version(s) : {r['n_articles']} article(s)")

        print()
        print("=== Codes couverts ===")
        rows = conn.execute("""
            SELECT code, COUNT(*) AS n
            FROM articles
            GROUP BY code
            ORDER BY n DESC
        """).fetchall()
        for r in rows:
            print(f"  {r['code']:20s} : {r['n']} articles")

        print()
        print("=== Plage temporelle ===")
        row = conn.execute("""
            SELECT MIN(date_debut) AS mini, MAX(date_debut) AS maxi
            FROM versions
        """).fetchone()
        print(f"  Date min : {row['mini']}")
        print(f"  Date max : {row['maxi']}")

        print()
        print("=== Articles avec plusieurs versions (top 5) ===")
        rows = conn.execute("""
            SELECT a.numero, COUNT(*) AS n
            FROM articles a
            JOIN versions v ON v.article_id = a.id
            GROUP BY a.id
            ORDER BY n DESC
            LIMIT 5
        """).fetchall()
        for r in rows:
            print(f"  {r['numero']:15s} : {r['n']} versions")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())