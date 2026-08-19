import re
import tempfile
import unittest
import zlib
from pathlib import Path

from sportstunden.export import dateiname_fuer, stunden_pdf
from sportstunden.katalog import Katalog
from sportstunden.pdf import PDF, textbreite, umbrechen
from tests.hilfen import auftrag, planer, temp_speicher


def texte_aus_pdf(daten: bytes):
    """(x, y, groesse, fett, text) aller Textbefehle - je Seite."""
    seiten = []
    muster = re.compile(
        r"BT [\d.]+ [\d.]+ [\d.]+ rg /(F\d) ([\d.]+) Tf 1 0 0 1 ([\d.]+) ([\d.]+) Tm "
        r"\((.*?)\) Tj ET"
    )
    for treffer in re.finditer(rb"/FlateDecode >>\nstream\n", daten):
        rest = daten[treffer.end() :]
        stream = zlib.decompress(rest[: rest.find(b"\nendstream")]).decode("latin-1")
        eintraege = []
        for m in muster.finditer(stream):
            text = m.group(5).replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
            eintraege.append(
                (float(m.group(3)), float(m.group(4)), float(m.group(2)), m.group(1) == "F2", text)
            )
        seiten.append(eintraege)
    return seiten


class PDFGrundlagenTest(unittest.TestCase):
    def test_umbruch_haelt_breite_ein(self):
        text = "Ein sehr langer Satz ueber Absicherung, Weichbodenmatten und Aufbau. " * 4
        for zeile in umbrechen(text, 200, 9.5):
            self.assertLessEqual(textbreite(zeile, 9.5), 200.5)

    def test_struktur_ist_gueltig(self):
        pdf = PDF(titel="Test")
        pdf.kopfzeile("Titel", "Untertitel")
        pdf.absatz("Text mit Klammern (test), Backslash \\ und Umlauten aeoeue.")
        pdf.tabelle(["A", "B"], [["1", "2"]] * 60, [0.5, 0.5])
        daten = pdf.bytes()

        self.assertTrue(daten.startswith(b"%PDF-1.4"))
        self.assertTrue(daten.rstrip().endswith(b"%%EOF"))
        start = int(re.search(rb"startxref\s+(\d+)", daten).group(1))
        zeilen = daten[start:].split(b"\n")
        self.assertEqual(zeilen[0], b"xref")
        anzahl = int(zeilen[1].split()[1])
        for nummer, zeile in enumerate(zeilen[3 : 3 + anzahl - 1], start=1):
            versatz = int(zeile.split()[0])
            self.assertTrue(
                daten[versatz:].startswith(f"{nummer} 0 obj".encode()),
                f"Objekt {nummer} nicht am angegebenen Offset",
            )

    def test_mehrere_seiten_bei_viel_inhalt(self):
        pdf = PDF()
        for _ in range(120):
            pdf.absatz("Zeile mit Inhalt")
        self.assertGreater(len(pdf.seiten), 1)


class StundenPDFTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.katalog = Katalog.laden()
        cls.speicher = temp_speicher()
        cls.ort = cls.speicher.ort("halle-schulzentrum")
        p = planer(cls.katalog, gruppen_id="d")
        cls.ergebnis = p.plane(
            auftrag(cls.ort, cls.katalog, gruppen_id="d", teilnehmer=18, seed=5)
        )
        cls.pfad = Path(tempfile.mkdtemp()) / dateiname_fuer(cls.ergebnis.stunde)
        stunden_pdf(
            cls.ergebnis.stunde,
            cls.katalog,
            cls.pfad,
            bestand=cls.ergebnis.bestand,
            trainer="Testtrainer",
            verein="TSV Test",
        )
        cls.daten = cls.pfad.read_bytes()
        cls.seiten = texte_aus_pdf(cls.daten)

    def test_datei_wird_geschrieben(self):
        self.assertTrue(self.pfad.exists())
        self.assertGreater(self.pfad.stat().st_size, 2000)
        self.assertTrue(self.pfad.name.endswith(".pdf"))

    def test_enthaelt_kernabschnitte(self):
        alle = " ".join(t[4] for seite in self.seiten for t in seite)
        for begriff in (
            "Aufwaermen",
            "Koordinationsteil",
            "Hauptteil",
            "Abschluss",
            "Material und Absicherung",
            "Aufbau je Stundenteil",
            "Stundenuebersicht",
            "Testtrainer",
        ):
            self.assertIn(begriff, alle, begriff)

    def test_enthaelt_alle_uebungen_und_aufbau(self):
        alle = " ".join(t[4] for seite in self.seiten for t in seite)
        for uebung in self.ergebnis.stunde.alle_uebungen():
            self.assertIn(uebung.name[:20], alle, uebung.name)
            if uebung.aufbau:
                self.assertIn(uebung.aufbau.split(",")[0][:25], alle, uebung.aufbau)

    def test_text_bleibt_im_satzspiegel(self):
        for seite in self.seiten:
            for x, y, groesse, fett, text in seite:
                self.assertGreater(y, 18, text)
                self.assertLess(y, 841.89 - 18, text)
                self.assertLessEqual(
                    x + textbreite(text, groesse, fett), 595.28 - 20, text
                )

    def test_dateiname_ist_sicher(self):
        name = dateiname_fuer(self.ergebnis.stunde)
        self.assertRegex(name, r"^[A-Za-z0-9_\-]+\.pdf$")


if __name__ == "__main__":
    unittest.main()
