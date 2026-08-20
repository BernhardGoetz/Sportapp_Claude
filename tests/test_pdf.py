import re
import tempfile
import unittest
import zlib
from pathlib import Path

from sportstunden.export import dateiname_fuer, stunden_pdf
from sportstunden.katalog import Katalog
from sportstunden.pdf import PDF, textbreite, umbrechen
from tests.hilfen import auftrag, planer, temp_speicher

TEXT_MUSTER = re.compile(
    r"BT [\d.]+ [\d.]+ [\d.]+ rg /(F\d) ([\d.]+) Tf 1 0 0 1 ([\d.]+) ([\d.]+) Tm "
    r"\((.*?)\) Tj ET"
)


def seiten_streams(daten: bytes):
    streams = []
    for treffer in re.finditer(rb"/FlateDecode >>\nstream\n", daten):
        rest = daten[treffer.end() :]
        streams.append(
            zlib.decompress(rest[: rest.find(b"\nendstream")]).decode("latin-1")
        )
    return streams


def texte_aus_pdf(daten: bytes):
    seiten = []
    for stream in seiten_streams(daten):
        eintraege = []
        for m in TEXT_MUSTER.finditer(stream):
            text = (
                m.group(5)
                .replace("\\(", "(")
                .replace("\\)", ")")
                .replace("\\\\", "\\")
            )
            eintraege.append(
                (
                    float(m.group(3)),
                    float(m.group(4)),
                    float(m.group(2)),
                    m.group(1) == "F2",
                    text,
                )
            )
        seiten.append(eintraege)
    return seiten


class PDFGrundlagenTest(unittest.TestCase):
    def test_umbruch_haelt_breite_ein(self):
        text = "Ein langer Satz ueber Absicherung, Weichbodenmatten und Aufbau. " * 4
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

    def test_zeichenbefehle(self):
        pdf = PDF()
        pdf.kreis(100, 100, 10)
        pdf.pfad([(10, 10), (20, 20), (30, 10)], schliessen=True)
        pdf.rechteck_rand(5, 5, 50, 50)
        stream = pdf.seiten[0].stream().decode("latin-1")
        self.assertIn(" c ", stream)
        self.assertIn(" l ", stream)
        self.assertIn(" re S", stream)


class StundenbildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.katalog = Katalog.laden()
        cls.speicher = temp_speicher()
        cls.ort = cls.speicher.ort("halle-grundschule")
        p = planer(cls.katalog, gruppen_id="vorschule")
        cls.ergebnis = p.plane(
            auftrag(
                cls.ort,
                cls.katalog,
                gruppen_id="vorschule",
                teilnehmer=18,
                seed=21,
                stationsbetrieb=True,
                thema="sommer",
                datum="2026-07-24",
            )
        )
        cls.stunde = cls.ergebnis.stunde
        cls.ordner = Path(tempfile.mkdtemp())
        cls.pfad = cls.ordner / dateiname_fuer(cls.stunde)
        stunden_pdf(
            cls.stunde,
            cls.katalog,
            cls.pfad,
            bestand=cls.ergebnis.bestand,
            trainer="Testtrainer",
            verein="TSV Test",
        )
        cls.daten = cls.pfad.read_bytes()
        cls.seiten = texte_aus_pdf(cls.daten)

    def text_der_seite(self, nummer: int) -> str:
        return " ".join(t[4] for t in self.seiten[nummer])

    def test_datei_wird_geschrieben(self):
        self.assertTrue(self.pfad.exists())
        self.assertGreater(self.pfad.stat().st_size, 2000)

    def test_stundenbild_hat_die_form_der_vorlage(self):
        erste = self.text_der_seite(0)
        self.assertIn("Ki Tu", erste)
        self.assertIn("24.07.2026", erste)
        self.assertIn("Anfang:", erste)
        self.assertIn("Ende:", erste)
        self.assertIn("Motto: Sommer", erste)
        self.assertIn("Kinder", erste)

    def test_stundenbild_listet_alle_stationen_mit_nummer(self):
        erste = self.text_der_seite(0)
        stationen = self.stunde.teil("hauptteil").uebungen
        for nummer, station in enumerate(stationen, start=1):
            self.assertIn(str(nummer), erste)
            self.assertIn(station.name[:14], erste)

    def test_stundenbild_nennt_material_in_kurzform(self):
        erste = self.text_der_seite(0)
        kurzformen = set()
        for station in self.stunde.teil("hauptteil").uebungen:
            for geraet in station.gesamtbedarf:
                kurzformen.add(self.katalog.geraet_kurz(geraet))
        self.assertTrue(kurzformen)
        for kurz in kurzformen:
            self.assertIn(kurz, erste, kurz)

    def test_hallenplan_wird_gezeichnet(self):
        stream = seiten_streams(self.daten)[0]
        self.assertIn("re S", stream)  # Hallenrechteck
        self.assertGreater(stream.count(" c "), 8)  # Nummernkreise und Symbole

    def test_detailseiten_enthalten_aufbau_und_sicherheit(self):
        self.assertGreater(len(self.seiten), 1)
        rest = " ".join(self.text_der_seite(i) for i in range(1, len(self.seiten)))
        for begriff in ("Ablauf", "Material und Aufbau", "Aufbau ", "Testtrainer"):
            self.assertIn(begriff, rest, begriff)
        for uebung in self.stunde.alle_uebungen():
            self.assertIn(uebung.name[:16], rest, uebung.name)

    def test_nur_stundenbild_ergibt_eine_seite(self):
        pfad = self.ordner / "kurz.pdf"
        stunden_pdf(
            self.stunde,
            self.katalog,
            pfad,
            bestand=self.ergebnis.bestand,
            nur_stundenbild=True,
        )
        self.assertEqual(len(texte_aus_pdf(pfad.read_bytes())), 1)

    def test_text_bleibt_im_satzspiegel(self):
        for seite in self.seiten:
            for x, y, groesse, fett, text in seite:
                self.assertGreater(y, 18, text)
                self.assertLess(y, 841.89 - 18, text)
                self.assertLessEqual(
                    x + textbreite(text, groesse, fett), 595.28 - 18, text
                )

    def test_spielstunde_ohne_stationen(self):
        p = planer(self.katalog, gruppen_id="grundschule_2")
        ergebnis = p.plane(
            auftrag(
                self.ort,
                self.katalog,
                gruppen_id="grundschule_2",
                teilnehmer=16,
                seed=4,
                stationsbetrieb=False,
            )
        )
        pfad = self.ordner / "spiel.pdf"
        stunden_pdf(ergebnis.stunde, self.katalog, pfad, bestand=ergebnis.bestand)
        text = " ".join(t[4] for t in texte_aus_pdf(pfad.read_bytes())[0])
        self.assertIn("Anfang:", text)
        for uebung in ergebnis.stunde.teil("hauptteil").uebungen:
            self.assertIn(uebung.name[:14], text)

    def test_dateiname_ist_sicher(self):
        name = dateiname_fuer(self.stunde)
        self.assertRegex(name, r"^[A-Za-z0-9_\-]+\.pdf$")


if __name__ == "__main__":
    unittest.main()
