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
        self.assertIn("Turnhalle Grundschule", self.text)
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
                "4",         # Gruppe: Grundschule 1./2. Klasse
                "60",        # Dauer
                "turnen",    # Schwerpunkt
                "Turnzwerge",  # Ueberschrift
                "4",         # Motto: Dschungel
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
        self.assertEqual(stunde.ueberschrift, "Turnzwerge")
        verwendet = {
            geraet for uebung in stunde.alle_uebungen() for geraet in uebung.geraete
        }
        self.assertNotIn("minitrampolin", verwendet)
        self.assertEqual(len(list((self.verzeichnis / "pdf").glob("*.pdf"))), 1)

    def test_erfassen_ohne_terminal(self):
        self.assertEqual(self.lauf("erfassen"), 1)
        self.assertIn("braucht ein Terminal", self.text)

    def test_unbekanntes_geraet_wird_abgelehnt(self):
        code = self.lauf("ort-bearbeiten", "halle-grundschule", "--geraete", "trampolin=2")
        self.assertEqual(code, 1)
        self.assertIn("Unbekannte Geraete-ID", self.text)

    # -- Planung -----------------------------------------------------------
    def test_planen_json(self):
        code = self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "grundschule_1",
            "--dauer", "60", "--seed", "3", "--json",
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
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "grundschule_1",
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
            "planen", "--ort", "halle-grundschule", "--alter", "6",
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

    def test_planen_mit_thema_und_stationen(self):
        code = self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule",
            "--thema", "dschungel", "--stationen", "--seed", "5", "--json",
        )
        self.assertEqual(code, 0)
        daten = json.loads(self.text)
        self.assertEqual(daten["thema"], "dschungel")
        hauptteil = [t for t in daten["teile"] if t["phase"] == "hauptteil"][0]
        self.assertTrue(hauptteil["parallel"])
        self.assertGreaterEqual(len(hauptteil["uebungen"]), 3)

    def test_planen_als_grosses_spiel(self):
        self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "grundschule_1",
            "--spiel", "--seed", "2", "--json",
        )
        hauptteil = [
            t for t in json.loads(self.text)["teile"] if t["phase"] == "hauptteil"
        ][0]
        self.assertLessEqual(len(hauptteil["uebungen"]), 2)

    def test_export_ist_standardmaessig_einseitig(self):
        ziel = self.verzeichnis / "kurz.pdf"
        code = self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule",
            "--seed", "7", "--pdf", str(ziel),
        )
        self.assertEqual(code, 0)
        self.assertIn(b"/Count 1", ziel.read_bytes())

    def test_detailseiten_auf_wunsch(self):
        ziel = self.verzeichnis / "lang.pdf"
        code = self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule",
            "--seed", "7", "--mit-details", "--pdf", str(ziel),
        )
        self.assertEqual(code, 0)
        self.assertNotIn(b"/Count 1", ziel.read_bytes())

    def test_ueberschrift_ist_frei_waehlbar(self):
        code = self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule",
            "--ueberschrift", "Turnzwerge", "--seed", "3", "--json",
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.text)["ueberschrift"], "Turnzwerge")

    def test_ueberschrift_im_pdf_befehl(self):
        self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule",
            "--seed", "3", "--speichern",
        )
        stunde_id = Speicher(self.verzeichnis).stunden()[0].id
        ziel = self.verzeichnis / "kopf.pdf"
        self.assertEqual(
            self.lauf("pdf", stunde_id, "--datei", str(ziel), "--ueberschrift", "Turnkids"),
            0,
        )
        self.assertEqual(
            Speicher(self.verzeichnis).stunde(stunde_id).ueberschrift, "Turnkids"
        )

    def test_stationszahl_laesst_sich_vorgeben(self):
        self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule",
            "--stationen", "4", "--seed", "5", "--json",
        )
        hauptteil = [
            t for t in json.loads(self.text)["teile"] if t["phase"] == "hauptteil"
        ][0]
        self.assertEqual(len(hauptteil["uebungen"]), 4)

    def test_stationen_ohne_zahl_nutzt_die_halle(self):
        self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule",
            "--stationen", "--seed", "5", "--json",
        )
        gross = [
            t for t in json.loads(self.text)["teile"] if t["phase"] == "hauptteil"
        ][0]
        self.lauf(
            "planen", "--ort", "halle-vereinsheim", "--altersgruppe", "vorschule",
            "--stationen", "--seed", "5", "--json",
        )
        klein = [
            t for t in json.loads(self.text)["teile"] if t["phase"] == "hauptteil"
        ][0]
        self.assertGreater(len(gross["uebungen"]), len(klein["uebungen"]))

    def test_stationen_haben_positionen(self):
        self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule",
            "--stationen", "--seed", "8", "--json",
        )
        daten = json.loads(self.text)
        hauptteil = [t for t in daten["teile"] if t["phase"] == "hauptteil"][0]
        self.assertEqual(daten["ort_laenge"], 27.0)
        for uebung in hauptteil["uebungen"]:
            self.assertGreater(uebung["stell_laenge"], 0)
            self.assertLessEqual(
                uebung["x"] + uebung["stell_laenge"], daten["ort_laenge"] + 0.01
            )

    def test_planen_ohne_ort_nicht_interaktiv(self):
        code = self.lauf("planen", "--altersgruppe", "grundschule_1")
        self.assertEqual(code, 1)

    def test_planen_unbekannter_ort(self):
        self.assertEqual(self.lauf("planen", "--ort", "gibtsnicht"), 1)

    # -- Stunden verwalten -------------------------------------------------
    def test_stunden_markieren_export_import(self):
        self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "grundschule_2",
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
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "grundschule_1",
            "--seed", "1", "--speichern",
        )
        stunde_id = Speicher(self.verzeichnis).stunden()[0].id
        self.assertEqual(self.lauf("loeschen", stunde_id), 0)
        self.assertEqual(self.lauf("loeschen", stunde_id), 1)

    def test_einstellungen_setzen(self):
        self.lauf("einstellungen", "--setzen", "standard_dauer=90", "--setzen", "trainer=B. Goetz")
        self.assertIn("90", self.text)
        self.assertEqual(Speicher(self.verzeichnis).einstellungen()["standard_dauer"], 90)

        self.lauf("planen", "--ort", "halle-grundschule", "--altersgruppe", "grundschule_1", "--json")
        self.assertEqual(json.loads(self.text)["dauer"], 90)

    def test_koordination_ab_alter_einstellbar(self):
        # Standard: ab 6 Jahren, also schon fuer die Vorschulkinder.
        self.lauf("planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule", "--json")
        self.assertIn("koordination", [t["phase"] for t in json.loads(self.text)["teile"]])

        self.lauf("einstellungen", "--setzen", "koordination_ab_alter=9")
        self.lauf("planen", "--ort", "halle-grundschule", "--altersgruppe", "vorschule", "--json")
        phasen = [t["phase"] for t in json.loads(self.text)["teile"]]
        self.assertNotIn("koordination", phasen)

        self.lauf(
            "planen", "--ort", "halle-grundschule", "--altersgruppe", "grundschule_2", "--json"
        )
        phasen = [t["phase"] for t in json.loads(self.text)["teile"]]
        self.assertIn("koordination", phasen)

    # -- Interaktives Erfassen --------------------------------------------
    def test_erfassen_interaktiv(self):
        eingaben = iter(
            [
                "1",            # Ort: erster Eintrag
                "4",            # Gruppe: Grundschule 1./2. Klasse
                "Meine Stunde", # Titel
                "Ki Tu",        # Ueberschrift
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
        self.assertEqual(stunde.altersgruppe_id, "grundschule_1")
        self.assertEqual(len(stunde.teile), 4)
        self.assertEqual(stunde.gesamtdauer, 50)

        self.lauf("stil", "--altersgruppe", "grundschule_1")
        self.assertIn("Gelernt aus 1 eigenen Stunde(n).", self.text)


if __name__ == "__main__":
    unittest.main()
