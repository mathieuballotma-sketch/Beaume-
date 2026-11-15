"""Test du post-filtre etendu (personne + verbe)."""
import unittest
from verbs_action import contient_verbe_action
from unittest.mock import patch
from parcours_vertical_v1 import extraire_affirmations
from profil_materiel import Profil


class TestVerbe(unittest.TestCase):
    def test_affirme(self):
        self.assertTrue(contient_verbe_action("Nordex affirme ne jamais avoir recu"))

    def test_nie(self):
        self.assertTrue(contient_verbe_action("Nordex nie avoir recu"))

    def test_pas_de_verbe(self):
        self.assertFalse(contient_verbe_action("Le service conserve dans une chemise"))

    def test_filler_classement(self):
        self.assertFalse(contient_verbe_action("Le suivi du dossier porte le numero F-10"))


class TestPostFiltreEtendu(unittest.TestCase):
    def _aff(self, texte, date, personnes):
        return {"texte": texte, "date": date, "personnes": personnes}

    def test_personne_verbe_sans_date_retenu(self):
        """Cas p17 : 'Nordex affirme ne jamais avoir recu...' date inconnue
        mais personne+verbe -> retenu marque concret_sans_date."""
        # Simule via la fonction de decision qui est inline dans extraire.
        # On verifie la regle en isolant les 3 conditions.
        from verbs_action import contient_verbe_action
        aff = self._aff("Nordex affirme ne jamais avoir recu le dossier", "inconnue", "Nordex")
        pers = (aff.get("personnes") or "").strip().lower()
        date = (aff.get("date") or "").strip().lower()
        personne_nommee = pers not in ("", "aucune", "aucun")
        date_ancree = date not in ("", "inconnue", "inconnu")
        retenu = (date_ancree and personne_nommee) or (
            personne_nommee and contient_verbe_action(aff["texte"])
        )
        self.assertTrue(retenu)

    def test_filler_jete(self):
        from verbs_action import contient_verbe_action
        aff = self._aff("Le service conserve dans une chemise les notes", "inconnue", "aucune")
        pers = (aff.get("personnes") or "").strip().lower()
        date = (aff.get("date") or "").strip().lower()
        personne_nommee = pers not in ("", "aucune", "aucun")
        date_ancree = date not in ("", "inconnue", "inconnu")
        retenu = (date_ancree and personne_nommee) or (
            personne_nommee and contient_verbe_action(aff["texte"])
        )
        self.assertFalse(retenu)



    def test_filler_notice_exclu(self):
        """Cas reel du run v4 : la notice 'La presence de cette feuille...'
        ne nomme aucun dossier numerote -> hors_condition malgre 'confirme'."""
        import re
        aff = {"texte": "La presence de cette feuille dans le dossier ne confirme pas a elle seule",
               "date": "inconnue", "personnes": "des personnes"}
        from verbs_action import contient_verbe_action
        texte = aff["texte"]
        a_numero = bool(re.search(r"dossier[^.]*?\d{2,}|\bnumero\s+\d{2,}", texte, re.IGNORECASE))
        pers = (aff.get("personnes") or "").strip().lower()
        personne_nommee = pers not in ("", "aucune", "aucun")
        retenu = (
            personne_nommee and contient_verbe_action(texte) and a_numero
        )
        self.assertFalse(retenu, "la notice ne doit pas passer sans numero de dossier")

    def test_p17_undated_retenu(self):
        """Cas p17 sans date : 'Nordex affirme ne jamais avoir recu le dossier 482'
        -> numero de dossier present -> retenu."""
        import re
        from verbs_action import contient_verbe_action
        texte = "Nordex affirme ne jamais avoir recu le dossier bleu numero 482"
        a_numero = bool(re.search(r"dossier[^.]*?\d{2,}|\bnumero\s+\d{2,}", texte, re.IGNORECASE))
        pers = "Nordex"
        personne_nommee = pers not in ("", "aucune", "aucun")
        retenu = personne_nommee and contient_verbe_action(texte) and a_numero
        self.assertTrue(retenu)


if __name__ == "__main__":
    unittest.main(verbosity=2)
