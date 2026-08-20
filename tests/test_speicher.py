import tempfile
import unittest
from pathlib import Path

from sportstunden.katalog import Katalog
from sportstunden.models import Ort
from sportstunden.speicher import Speicher
from tests.hilfen import eigene_stunde


class SpeicherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.katalog = Katalog.laden()
        self.speicher = Speicher(Path(tempfile.mkdtemp()))

    def test_beispieldaten_nur_einmal(self):
        self.assertEqual(self.speicher.initialisiere_beispieldaten(), 4)
        self.assertEqual(self.speicher.initialisiere_beispieldaten(), 0)
        self.assertEqual(len(self.speicher.orte()), 4)

    def test_ort_speichern_und_lesen(self):
        ort = Ort(id="halle-x", name="Halle X", art="halle", ausstattung={"matte": 6})
        self.speicher.speichere_ort(ort)
        geladen = self.speicher.ort("halle-x")
        self.assertEqual(geladen.name, "Halle X")
        self.assertEqual(geladen.bestand("matte"), 6)

        geladen.setze_bestand("matte", 10)
        geladen.setze_bestand("langbank", 3)
        self.speicher.speichere_ort(geladen)
        self.assertEqual(self.speicher.ort("halle-x").bestand("matte"), 10)
        self.assertEqual(len(self.speicher.orte()), 1)

        self.assertTrue(self.speicher.loesche_ort("halle-x"))
        self.assertFalse(self.speicher.loesche_ort("halle-x"))

    def test_bestand_null_entfernt_geraet(self):
        ort = Ort(id="h", name="H", art="halle", ausstattung={"matte": 4})
        ort.setze_bestand("matte", 0)
        self.assertEqual(ort.ausstattung, {})

    def test_unbekannte_ortsart_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            Ort(id="x", name="X", art="schwimmbad")

    def test_stunden_roundtrip_und_eigene(self):
        self.speicher.initialisiere_beispieldaten()
        ort = self.speicher.ort("halle-grundschule")
        stunde = eigene_stunde(
            self.katalog, ort, "grundschule_1", {"aufwaermen": ["aufw_versteinern"]}
        )
        self.speicher.speichere_stunde(stunde)
        geladen = self.speicher.stunde(stunde.id)
        self.assertEqual(geladen.titel, stunde.titel)
        self.assertEqual(
            [u.name for u in geladen.alle_uebungen()],
            [u.name for u in stunde.alle_uebungen()],
        )
        self.assertEqual(len(self.speicher.eigene_stunden()), 1)

        geladen.quelle = "geplant"
        self.speicher.speichere_stunde(geladen)
        self.assertEqual(len(self.speicher.eigene_stunden()), 0)
        self.assertEqual(len(self.speicher.stunden()), 1)
        self.assertTrue(self.speicher.loesche_stunde(stunde.id))

    def test_einstellungen(self):
        self.assertEqual(self.speicher.einstellungen()["standard_dauer"], 60)
        self.speicher.setze_einstellung("standard_dauer", 90)
        self.speicher.setze_einstellung("trainer", "B. G.")
        einstellungen = self.speicher.einstellungen()
        self.assertEqual(einstellungen["standard_dauer"], 90)
        self.assertEqual(einstellungen["trainer"], "B. G.")

    def test_verzeichnis_aus_umgebung(self, ):
        import os

        ziel = Path(tempfile.mkdtemp()) / "unterordner"
        os.environ["SPORTSTUNDEN_HOME"] = str(ziel)
        try:
            speicher = Speicher()
            self.assertEqual(speicher.verzeichnis, ziel)
            self.assertTrue(ziel.exists())
        finally:
            del os.environ["SPORTSTUNDEN_HOME"]


if __name__ == "__main__":
    unittest.main()
