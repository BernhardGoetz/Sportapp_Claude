import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from sportstunden.cli import main
from sportstunden.speicher import Speicher


class CLITest(unittest.TestCase):
    def setUp(self) -> None:
        self.verzeichnis = Path(tempfile.mkdtemp())
        self.basis = ["--daten", str(self.verzeichnis)]
        self.assertEqual(self.lauf("init"), 0)

    def lauf(self, *args) -> int:
        self.ausgabe = io.StringIO()
        with redirect_stdout(self.ausgabe):
            code = main(self.basis + list(args))
        self.text = self.ausgabe.getvalue()
        return code

    # -- Stammdaten --------------------------------------------------------
    def test_init_und_orte(self):
        self.lauf("orte")
        self.assertIn("Dreifachhalle Schulzentrum", self.text)
        self.assertIn("Sportplatz Am Wald", self.text)

    def test_geraete_und_altersgruppen(self):
        self.lauf("geraete", "--suche", "matte")
        self.assertIn("Weichbodenmatte", self.text)
        self.lauf("altersgruppen")
        self.assertIn("mit Koordinationsteil", self.text)
        self.assertIn("ohne Koordinationsteil", self.text)

    def test_ort_anlegen_und_ausstatten(self):
        code = self.lauf(
            "ort-neu",
            "--id", "halle-test",
            "--name", "Testhalle",
            "--art", "halle",
            "--geraete", "matte=8,langbank=4,softball=10",
        )
        self.assertEqual(code, 0)
        self.lauf("ort", "halle-test")
        self.assertIn("Turnmatte", self.text)

        self.lauf("ort-bearbeiten", "halle-test", "--geraete", "matte=12,langbank=0")
        speicher = Speicher(self.verzeichnis)
        ort = speicher.ort("halle-test")
        self.assertEqual(ort.bestand("matte"), 12)
        self.assertEqual(ort.bestand("langbank"), 0)

        self.assertEqual(self.lauf("ort-loeschen", "halle-test"), 0)
        self.assertEqual(self.lauf("ort-loeschen", "halle-test"), 1)

    def test_planen_interaktiv(self):
        eingaben = iter(
            [
                "1",      # Ortsart: Turnhalle
                "1",      # Ort: Dreifachhalle
                "3",      # Ausstattung: Anzahlen anpassen
                "minitrampolin=0,tau=2",
                "4",      # Altersgruppe: D-Jugend
                "60",     # Dauer
                "16",     # Teilnehmer
                "turnen", # Schwerpunkt
                "s",      # speichern
                "a",      # Aufbauplan
                "p", "",  # PDF in den Standardordner
                "e",      # als eigene Stunde uebernehmen
                "q",      # Ende
            ]
        )
        with patch("builtins.input", lambda *args: next(eingaben)), patch(
            "sportstunden.cli.interaktiv_moeglich", return_value=True
        ):
            code = self.lauf("planen")
        self.assertEqual(code, 0)
        self.assertIn("Aufbauplan", self.text)
        self.assertIn("PDF geschrieben", self.text)

        speicher = Speicher(self.verzeichnis)
        eigene = speicher.eigene_stunden()
        self.assertEqual(len(eigene), 1)
        stunde = eigene[0]
        self.assertEqual(stunde.gesamtdauer, 60)
        self.assertEqual(stunde.teilnehmer, 16)
        verwendet = {
            geraet for uebung in stunde.alle_uebungen() for geraet in uebung.geraete
        }
        self.assertNotIn("minitrampolin", verwendet)
        self.assertEqual(len(list((self.verzeichnis / "pdf").glob("*.pdf"))), 1)

    def test_erfassen_ohne_terminal(self):
        self.assertEqual(self.lauf("erfassen"), 1)
        self.assertIn("braucht ein Terminal", self.text)

    def test_unbekanntes_geraet_wird_abgelehnt(self):
        code = self.lauf("ort-bearbeiten", "halle-schulzentrum", "--geraete", "trampolin=2")
        self.assertEqual(code, 1)
        self.assertIn("Unbekannte Geraete-ID", self.text)

    # -- Planung -----------------------------------------------------------
    def test_planen_json(self):
        code = self.lauf(
            "planen", "--ort", "halle-schulzentrum", "--altersgruppe", "d",
            "--dauer", "60", "--teilnehmer", "16", "--seed", "3", "--json",
        )
        self.assertEqual(code, 0)
        daten = json.loads(self.text)
        self.assertEqual(sum(t["puffer"] + sum(u["dauer"] for u in t["uebungen"]) for t in daten["teile"]), 60)
        self.assertEqual(
            [t["phase"] for t in daten["teile"]],
            ["aufwaermen", "koordination", "hauptteil", "abschluss"],
        )

    def test_planen_mit_ohne_geraeten(self):
        code = self.lauf(
            "planen", "--ort", "halle-schulzentrum", "--altersgruppe", "d",
            "--ohne", "minitrampolin,kasten_gross,tau", "--seed", "2", "--json",
        )
        self.assertEqual(code, 0)
        daten = json.loads(self.text)
        verwendet = {
            geraet
            for teil in daten["teile"]
            for uebung in teil["uebungen"]
            for geraet in uebung["geraete"]
        }
        self.assertNotIn("minitrampolin", verwendet)
        self.assertNotIn("tau", verwendet)

    def test_planen_speichern_und_pdf(self):
        code = self.lauf(
            "planen", "--ort", "halle-schulzentrum", "--alter", "9",
            "--seed", "4", "--speichern", "--pdf",
        )
        self.assertEqual(code, 0)
        self.assertIn("PDF geschrieben", self.text)
        pdfs = list((self.verzeichnis / "pdf").glob("*.pdf"))
        self.assertEqual(len(pdfs), 1)
        self.assertTrue(pdfs[0].read_bytes().startswith(b"%PDF"))

        speicher = Speicher(self.verzeichnis)
        stunden = speicher.stunden()
        self.assertEqual(len(stunden), 1)

        ziel = self.verzeichnis / "extra.pdf"
        self.assertEqual(self.lauf("pdf", stunden[0].id, "--datei", str(ziel)), 0)
        self.assertTrue(ziel.exists())

    def test_planen_ohne_ort_nicht_interaktiv(self):
        code = self.lauf("planen", "--altersgruppe", "d")
        self.assertEqual(code, 1)

    def test_planen_unbekannter_ort(self):
        self.assertEqual(self.lauf("planen", "--ort", "gibtsnicht"), 1)

    # -- Stunden verwalten -------------------------------------------------
    def test_stunden_markieren_export_import(self):
        self.lauf(
            "planen", "--ort", "halle-schulzentrum", "--altersgruppe", "c",
            "--seed", "6", "--speichern",
        )
        speicher = Speicher(self.verzeichnis)
        stunde_id = speicher.stunden()[0].id

        self.lauf("stunden")
        self.assertIn(stunde_id, self.text)

        self.lauf("zeigen", stunde_id, "--aufbau")
        self.assertIn("Aufbauplan", self.text)

        self.assertEqual(self.lauf("markieren", stunde_id), 0)
        self.assertEqual(len(Speicher(self.verzeichnis).eigene_stunden()), 1)

        datei = self.verzeichnis / "export.json"
        self.assertEqual(self.lauf("exportieren", stunde_id, str(datei)), 0)

        zweites = Path(tempfile.mkdtemp())
        self.basis = ["--daten", str(zweites)]
        self.lauf("init")
        self.assertEqual(self.lauf("importieren", str(datei)), 0)
        self.assertEqual(len(Speicher(zweites).eigene_stunden()), 1)

        self.lauf("stil")
        self.assertIn("Gelernt aus 1 eigenen Stunde(n).", self.text)

    def test_loeschen(self):
        self.lauf(
            "planen", "--ort", "halle-schulzentrum", "--altersgruppe", "d",
            "--seed", "1", "--speichern",
        )
        stunde_id = Speicher(self.verzeichnis).stunden()[0].id
        self.assertEqual(self.lauf("loeschen", stunde_id), 0)
        self.assertEqual(self.lauf("loeschen", stunde_id), 1)

    def test_einstellungen_setzen(self):
        self.lauf("einstellungen", "--setzen", "standard_dauer=90", "--setzen", "trainer=B. Goetz")
        self.assertIn("90", self.text)
        self.assertEqual(Speicher(self.verzeichnis).einstellungen()["standard_dauer"], 90)

        self.lauf("planen", "--ort", "halle-schulzentrum", "--altersgruppe", "d", "--json")
        self.assertEqual(json.loads(self.text)["dauer"], 90)

    def test_koordination_ab_alter_einstellbar(self):
        self.lauf("einstellungen", "--setzen", "koordination_ab_alter=12")
        self.lauf("planen", "--ort", "halle-schulzentrum", "--altersgruppe", "e", "--json")
        phasen = [t["phase"] for t in json.loads(self.text)["teile"]]
        self.assertNotIn("koordination", phasen)

        self.lauf("planen", "--ort", "halle-schulzentrum", "--altersgruppe", "c", "--json")
        phasen = [t["phase"] for t in json.loads(self.text)["teile"]]
        self.assertIn("koordination", phasen)

    # -- Interaktives Erfassen --------------------------------------------
    def test_erfassen_interaktiv(self):
        eingaben = iter(
            [
                "1",            # Ort: erster Eintrag
                "4",            # Altersgruppe: D-Jugend
                "14",           # Teilnehmerzahl
                "Meine Stunde", # Titel
                "2026-01-07",   # Datum
                "1", "10", "",  # Aufwaermen: erste Uebung, 10 min, Ende
                "1", "8", "",   # Koordination
                "1", "25", "",  # Hauptteil
                "1", "7", "",   # Abschluss
            ]
        )
        with patch("builtins.input", lambda *args: next(eingaben)), patch(
            "sportstunden.cli.interaktiv_moeglich", return_value=True
        ):
            code = self.lauf("erfassen")
        self.assertEqual(code, 0)
        stunden = Speicher(self.verzeichnis).eigene_stunden()
        self.assertEqual(len(stunden), 1)
        stunde = stunden[0]
        self.assertEqual(stunde.titel, "Meine Stunde")
        self.assertEqual(stunde.altersgruppe_id, "d")
        self.assertEqual(stunde.teilnehmer, 14)
        self.assertEqual(len(stunde.teile), 4)
        self.assertEqual(stunde.gesamtdauer, 50)

        self.lauf("stil", "--altersgruppe", "d")
        self.assertIn("Gelernt aus 1 eigenen Stunde(n).", self.text)


if __name__ == "__main__":
    unittest.main()
