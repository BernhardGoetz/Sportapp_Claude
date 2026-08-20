"""Tests der grafischen Oberflaeche.

Sie laufen nur, wenn tkinter und eine Anzeige vorhanden sind - auf
Rechnern ohne beides werden sie uebersprungen.
"""

import unittest

from tests.hilfen import temp_speicher

try:  # pragma: no cover - haengt von der Installation ab
    import tkinter

    _fenster = tkinter.Tk()
    _fenster.destroy()
    TK_VERFUEGBAR = True
except Exception:  # pragma: no cover
    TK_VERFUEGBAR = False


@unittest.skipUnless(TK_VERFUEGBAR, "tkinter oder Anzeige fehlt")
class GUITest(unittest.TestCase):
    def setUp(self) -> None:
        from tkinter import messagebox

        from sportstunden.gui import Planerfenster

        # Rueckmeldefenster wuerden den Testlauf blockieren.
        self._dialoge = (messagebox.showinfo, messagebox.showerror)
        messagebox.showinfo = lambda *args, **kwargs: None
        messagebox.showerror = lambda *args, **kwargs: None

        self.speicher = temp_speicher()
        self.fenster = Planerfenster(self.speicher)
        self.fenster.update()

    def tearDown(self) -> None:
        from tkinter import messagebox

        self.fenster.destroy()
        messagebox.showinfo, messagebox.showerror = self._dialoge

    def test_planung_zeichnet_stationen(self):
        self.fenster.planen(seed=21)
        self.fenster.update()
        stationen = self.fenster._stationen()
        self.assertTrue(stationen)
        self.assertIsNotNone(self.fenster.massstab)
        # Auf der Leinwand steht etwas.
        self.assertTrue(self.fenster.canvas.find_all())

    def test_station_laesst_sich_verschieben(self):
        self.fenster.planen(seed=21)
        self.fenster.update()
        station = self.fenster._stationen()[0]
        alt = (station.x, station.y)

        class Ereignis:
            pass

        greifen = Ereignis()
        punkt = self.fenster.massstab.punkt(station.x + 0.5, station.y + 0.5)
        greifen.x = punkt[0]
        greifen.y = self.fenster.canvas.winfo_height() - punkt[1]
        self.fenster.zieh_start(greifen)
        self.assertIs(self.fenster.gezogen, station)

        ziehen = Ereignis()
        ziel = self.fenster.massstab.punkt(station.x + 2.5, station.y + 1.5)
        ziehen.x = ziel[0]
        ziehen.y = self.fenster.canvas.winfo_height() - ziel[1]
        self.fenster.zieh_bewegung(ziehen)
        self.fenster.zieh_ende(ziehen)

        self.assertNotEqual((station.x, station.y), alt)
        # Fangraster von 25 cm
        self.assertAlmostEqual(station.x * 4, round(station.x * 4), places=6)
        # innerhalb der Halle
        self.assertGreaterEqual(station.x, 0)
        self.assertLessEqual(
            station.x + station.stell_laenge, self.fenster.massstab.halle_laenge + 0.01
        )

    def test_pdf_aus_der_oberflaeche(self):
        import tempfile
        from pathlib import Path

        from sportstunden.export import stunden_pdf

        self.fenster.planen(seed=5)
        stunde = self.fenster.ergebnis.stunde
        ziel = Path(tempfile.mkdtemp()) / "gui.pdf"
        stunden_pdf(stunde, self.fenster.katalog, ziel)
        self.assertTrue(ziel.exists())
        self.assertTrue(ziel.read_bytes().startswith(b"%PDF"))

    def test_stunde_speichern(self):
        self.fenster.planen(seed=7)
        self.fenster.speichern()
        self.assertEqual(len(self.speicher.stunden()), 1)
        self.fenster.als_eigene()
        self.assertEqual(len(self.speicher.eigene_stunden()), 1)


if __name__ == "__main__":
    unittest.main()
