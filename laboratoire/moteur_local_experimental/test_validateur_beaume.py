"""Tests du validateur JSON Schema restreint — aucune dépendance externe."""
import unittest

from validateur_beaume import valider


SCHEMA_MIN = {
    "type": "object",
    "properties": {
        "contexte": {"type": "string"},
        "parties": {"type": "array", "items": {"type": "string"}},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "enum": ["A1", "A2"]},
                    "fichier": {"type": "string", "enum": ["d.pdf"]},
                    "pages": {
                        "type": "array",
                        "items": {"type": "integer", "enum": [1, 2, 3]},
                        "minItems": 1,
                        "maxItems": 3,
                        "uniqueItems": True,
                    },
                },
                "required": ["article_id", "fichier", "pages"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["contexte", "citations"],
    "additionalProperties": False,
}


class TestParse(unittest.TestCase):
    def test_json_invalide(self):
        r = valider("{pas du json}", SCHEMA_MIN)
        self.assertFalse(r.json_parse_valide)
        self.assertFalse(r.schema_technique_valide)
        self.assertIsNone(r.valeur)
        self.assertIsNotNone(r.erreur_parse)

    def test_json_tronque(self):
        r = valider('{"contexte": "a", "citations": [', SCHEMA_MIN)
        self.assertFalse(r.json_parse_valide)
        self.assertFalse(r.schema_technique_valide)

    def test_json_valide_minimal(self):
        r = valider('{"contexte": "a", "citations": []}', SCHEMA_MIN)
        self.assertTrue(r.json_parse_valide)
        self.assertTrue(r.schema_technique_valide)


class TestRequired(unittest.TestCase):
    def test_contexte_absent(self):
        r = valider('{"citations": []}', SCHEMA_MIN)
        self.assertTrue(r.json_parse_valide)
        self.assertFalse(r.schema_technique_valide)
        self.assertTrue(any("contexte" in v for v in r.violations))

    def test_citations_absent(self):
        r = valider('{"contexte": "a"}', SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)

    def test_article_id_absent_dans_citation(self):
        brut = '{"contexte": "a", "citations": [{"fichier": "d.pdf", "pages": [1]}]}'
        r = valider(brut, SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)
        self.assertTrue(any("article_id" in v for v in r.violations))


class TestChampsOptionnels(unittest.TestCase):
    def test_parties_absent(self):
        r = valider('{"contexte": "a", "citations": []}', SCHEMA_MIN)
        self.assertTrue(r.schema_technique_valide)

    def test_parties_present(self):
        r = valider(
            '{"contexte": "a", "parties": ["X", "Y"], "citations": []}',
            SCHEMA_MIN,
        )
        self.assertTrue(r.schema_technique_valide)


class TestUniqueItems(unittest.TestCase):
    def test_pages_valides(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "d.pdf", "pages": [1, 2]}]}')
        r = valider(brut, SCHEMA_MIN)
        self.assertTrue(r.schema_technique_valide)

    def test_pages_dupliquees(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "d.pdf", "pages": [1, 1]}]}')
        r = valider(brut, SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)
        self.assertTrue(any("uniqueItems" in v for v in r.violations))

    def test_distinction_int_bool(self):
        schema = {
            "type": "object",
            "properties": {"v": {"type": "array", "items": {}, "uniqueItems": True}},
            "required": ["v"],
        }
        r = valider('{"v": [1, true]}', schema)
        # 1 et True sont distincts par _cle_unique
        self.assertTrue(r.schema_technique_valide)


class TestEnum(unittest.TestCase):
    def test_article_hors_enum(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "ZZ", '
                '"fichier": "d.pdf", "pages": [1]}]}')
        r = valider(brut, SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)
        self.assertTrue(any("hors enum" in v for v in r.violations))

    def test_fichier_hors_enum(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "x.pdf", "pages": [1]}]}')
        r = valider(brut, SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)

    def test_page_hors_enum(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "d.pdf", "pages": [9]}]}')
        r = valider(brut, SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)


class TestBornes(unittest.TestCase):
    def test_min_items_viole(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "d.pdf", "pages": []}]}')
        r = valider(brut, SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)
        self.assertTrue(any("minItems" in v for v in r.violations))

    def test_max_items_viole(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "d.pdf", "pages": [1, 2, 3, 1]}]}')
        r = valider(brut, SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)
        self.assertTrue(any("maxItems" in v for v in r.violations))


class TestAdditionalProperties(unittest.TestCase):
    def test_cle_inconnue_a_la_racine(self):
        brut = '{"contexte": "a", "citations": [], "extra": 1}'
        r = valider(brut, SCHEMA_MIN)
        self.assertFalse(r.schema_technique_valide)
        self.assertTrue(any("non autorisées" in v for v in r.violations))


class TestMetier(unittest.TestCase):
    def test_schema_metier_toujours_none(self):
        r = valider('{"contexte": "a", "citations": []}', SCHEMA_MIN)
        self.assertIsNone(r.schema_metier_valide)


class TestBoolVsInt(unittest.TestCase):
    """Un booléen ne doit pas passer pour un entier, ni dans type ni dans enum."""

    SCHEMA = {
        "type": "object",
        "properties": {"n": {"type": "integer", "enum": [1, 2]}},
        "required": ["n"],
    }

    def test_true_rejete_pour_enum_integer(self):
        r = valider('{"n": true}', self.SCHEMA)
        self.assertFalse(r.schema_technique_valide)
        self.assertTrue(any("integer" in v for v in r.violations))

    def test_false_rejete_pour_enum_integer(self):
        r = valider('{"n": false}', self.SCHEMA)
        self.assertFalse(r.schema_technique_valide)

    def test_entier_valide(self):
        r = valider('{"n": 1}', self.SCHEMA)
        self.assertTrue(r.schema_technique_valide)

    def test_bool_rejete_pour_integer_sans_enum(self):
        schema = {"type": "object",
                  "properties": {"n": {"type": "integer"}},
                  "required": ["n"]}
        r = valider('{"n": true}', schema)
        self.assertFalse(r.schema_technique_valide)


if __name__ == "__main__":
    unittest.main(verbosity=2)
