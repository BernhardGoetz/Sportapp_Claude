"""Tests der Browser-Fassung ``web/kinderturnen.html``.

Die Pruefungen ohne Browser laufen immer. Die Oberflaechen-Tests brauchen
Playwright und Chromium; fehlt eines davon, werden sie uebersprungen.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SEITE = WURZEL / "web" / "kinderturnen.html"

try:  # pragma: no cover - haengt von der Installation ab
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_DA = True
except Exception:  # pragma: no cover
    PLAYWRIGHT_DA = False


def chromium_pfad():
    """Erster gefundener Chromium-Build - sonst None."""
    for muster in ("chromium-*/chrome-linux/chrome", "chromium-*/chrome-mac/*/Chromium"):
        for pfad in Path("/opt/pw-browsers").glob(muster):
            return str(pfad)
    return None


CHROMIUM = chromium_pfad() if PLAYWRIGHT_DA else None


class WebDateiTest(unittest.TestCase):
    """Pruefungen ohne Browser."""

    def test_datei_ist_vorhanden_und_eigenstaendig(self):
        self.assertTrue(SEITE.exists(), "web/kinderturnen.html fehlt")
        inhalt = SEITE.read_text(encoding="utf-8")
        self.assertGreater(len(inhalt), 50_000)
        # Keine Verweise nach draussen - die Datei muss offline laufen.
        for muster in ("http://", "https://", "<link", "src="):
            self.assertNotIn(muster, inhalt, f"externe Einbindung gefunden: {muster}")

    def test_datei_ist_aktuell(self):
        ergebnis = subprocess.run(
            [sys.executable, "werkzeuge/baue_web.py", "--pruefen"],
            cwd=WURZEL,
            capture_output=True,
            text=True,
        )
        self.assertEqual(ergebnis.returncode, 0, ergebnis.stdout + ergebnis.stderr)

    def test_katalog_steckt_in_der_datei(self):
        inhalt = SEITE.read_text(encoding="utf-8")
        treffer = re.search(
            r"^<script>const DATEN = (\{.*\});</script>$", inhalt, re.MULTILINE
        )
        self.assertIsNotNone(treffer, "eingebettete Daten nicht gefunden")
        daten = json.loads(treffer.group(1))
        self.assertGreater(len(daten["uebungen"]), 60)
        self.assertEqual(len(daten["altersgruppen"]), 5)
        self.assertTrue(daten["orte"])
        self.assertIn("sprossenwand", daten["geraetemasse"])
        self.assertEqual(len(daten["schriftbreiten"]["normal"]), 95)
        for ort in daten["orte"]:
            self.assertGreater(ort["laenge"], 5)
            self.assertGreater(ort["breite"], 5)


@unittest.skipUnless(PLAYWRIGHT_DA and CHROMIUM, "Playwright oder Chromium fehlt")
class WebOberflaecheTest(unittest.TestCase):
    """Die Seite im echten Browser."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._pw = sync_playwright().start()
        cls.browser = cls._pw.chromium.launch(executable_path=CHROMIUM)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls._pw.stop()

    def oeffne(self, breite=1280, hoehe=860):
        seite = self.browser.new_page(viewport={"width": breite, "height": hoehe})
        self.fehler = []
        seite.on("pageerror", lambda e: self.fehler.append(str(e)))
        seite.on(
            "console",
            lambda m: self.fehler.append(m.text) if m.type == "error" else None,
        )
        seite.goto(SEITE.resolve().as_uri())
        seite.wait_for_timeout(350)
        return seite

    def test_seite_plant_ohne_fehler(self):
        seite = self.oeffne()
        daten = seite.evaluate(
            """() => {
                const e = window.KiTu.zustand.ergebnis;
                return {
                    phasen: e.stunde.teile.map(t => t.phase),
                    stationen: window.KiTu.stationenVon(e.stunde).length,
                    konflikte: window.KiTu.konflikte(
                        window.KiTu.stationenVon(e.stunde), window.KiTu.zustand.orte[0]).length,
                    text: document.getElementById('stationsliste').textContent,
                };
            }"""
        )
        self.assertIn("hauptteil", daten["phasen"])
        self.assertGreaterEqual(daten["stationen"], 3)
        self.assertEqual(daten["konflikte"], 0)
        self.assertTrue(daten["text"].strip())
        self.assertEqual(self.fehler, [])
        seite.close()

    def test_stationen_liegen_in_der_halle(self):
        seite = self.oeffne()
        heraus = seite.evaluate(
            """() => {
                const s = window.KiTu.zustand.ergebnis.stunde;
                return window.KiTu.stationenVon(s).filter(
                    u => u.x < -0.01 || u.y < -0.01 ||
                         u.x + u.stellLaenge > s.ort_laenge + 0.01 ||
                         u.y + u.stellBreite > s.ort_breite + 0.01).map(u => u.name);
            }"""
        )
        self.assertEqual(heraus, [])
        seite.close()

    def test_station_laesst_sich_ziehen(self):
        seite = self.oeffne()
        vorher = seite.evaluate(
            "() => { const s = window.KiTu.stationenVon(window.KiTu.zustand.ergebnis.stunde)[0];"
            " return [s.x, s.y]; }"
        )
        punkt = seite.evaluate(
            """() => {
                const st = window.KiTu.stationenVon(window.KiTu.zustand.ergebnis.stunde)[0];
                const ms = window.KiTu.zustand.massstab;
                const leinwand = document.getElementById('plan');
                const p = ms.punkt(st.x + st.stellLaenge / 2, st.y + st.stellBreite / 2);
                const k = leinwand.getBoundingClientRect();
                return {
                    x: k.left + p[0] * k.width / leinwand.width,
                    y: k.top + (leinwand.height - p[1]) * k.height / leinwand.height,
                };
            }"""
        )
        seite.mouse.move(punkt["x"], punkt["y"])
        seite.mouse.down()
        seite.mouse.move(punkt["x"] + 70, punkt["y"] - 50, steps=6)
        seite.mouse.up()
        nachher = seite.evaluate(
            "() => { const s = window.KiTu.stationenVon(window.KiTu.zustand.ergebnis.stunde)[0];"
            " return [s.x, s.y]; }"
        )
        self.assertNotEqual(vorher, nachher)
        # Fangraster von 25 cm und innerhalb der Halle
        self.assertAlmostEqual(nachher[0] * 4, round(nachher[0] * 4), places=6)
        self.assertAlmostEqual(nachher[1] * 4, round(nachher[1] * 4), places=6)
        self.assertGreaterEqual(nachher[0], 0)
        seite.close()

    def test_ziehen_auch_im_gedrehten_plan(self):
        """Auf hochkant gehaltenen Geraeten liegt der Plan quer."""
        seite = self.oeffne(breite=390, hoehe=780)
        gedreht = seite.evaluate("() => window.KiTu.zustand.massstab.gedreht")
        self.assertTrue(gedreht)
        vorher = seite.evaluate(
            "() => { const s = window.KiTu.stationenVon(window.KiTu.zustand.ergebnis.stunde)[0];"
            " return [s.x, s.y]; }"
        )
        punkt = seite.evaluate(
            """() => {
                const st = window.KiTu.stationenVon(window.KiTu.zustand.ergebnis.stunde)[0];
                const ms = window.KiTu.zustand.massstab;
                const leinwand = document.getElementById('plan');
                const p = ms.punkt(st.x + st.stellLaenge / 2, st.y + st.stellBreite / 2);
                const k = leinwand.getBoundingClientRect();
                return {
                    x: k.left + p[0] * k.width / leinwand.width,
                    y: k.top + (leinwand.height - p[1]) * k.height / leinwand.height,
                };
            }"""
        )
        seite.mouse.move(punkt["x"], punkt["y"])
        seite.mouse.down()
        seite.mouse.move(punkt["x"], punkt["y"] + 60, steps=6)
        seite.mouse.up()
        nachher = seite.evaluate(
            "() => { const s = window.KiTu.stationenVon(window.KiTu.zustand.ergebnis.stunde)[0];"
            " return [s.x, s.y]; }"
        )
        self.assertNotEqual(vorher, nachher)
        seite.close()

    def test_plan_nimmt_viel_platz_ein(self):
        for breite, hoehe, mindestens in ((390, 780, 0.45), (820, 1100, 0.5), (1440, 900, 0.55)):
            seite = self.oeffne(breite, hoehe)
            werte = seite.evaluate(
                """() => {
                    const k = document.getElementById('plan').getBoundingClientRect();
                    return {h: k.height, w: k.width, fenster: window.innerHeight};
                }"""
            )
            self.assertGreaterEqual(
                werte["h"] / werte["fenster"],
                mindestens,
                f"{breite}x{hoehe}: Plan nur {round(werte['h'])} von {werte['fenster']} px hoch",
            )
            seite.close()

    def test_pdf_hat_eine_seite_und_optional_mehr(self):
        seite = self.oeffne()
        werte = seite.evaluate(
            """() => {
                const s = window.KiTu.zustand.ergebnis.stunde;
                const ort = window.KiTu.zustand.orte[0];
                const kurz = window.KiTu.stundenPdf(s, ort, {mitDetails: false});
                const lang = window.KiTu.stundenPdf(s, ort, {mitDetails: true});
                const text = new TextDecoder('latin1').decode(kurz);
                return {
                    kopf: text.slice(0, 8),
                    seitenKurz: (text.match(/\\/Type \\/Page[^s]/g) || []).length,
                    seitenLang: (new TextDecoder('latin1').decode(lang)
                        .match(/\\/Type \\/Page[^s]/g) || []).length,
                    hatMinuten: / min\\b/.test(text),
                    ueberschrift: text.includes('Ki Tu'),
                };
            }"""
        )
        self.assertEqual(werte["kopf"], "%PDF-1.4")
        self.assertEqual(werte["seitenKurz"], 1)
        self.assertGreater(werte["seitenLang"], 1)
        self.assertFalse(werte["hatMinuten"], "Zeitangabe im PDF gefunden")
        self.assertTrue(werte["ueberschrift"])
        seite.close()

    def test_ueberschrift_wandert_ins_pdf(self):
        seite = self.oeffne()
        seite.fill("#ueberschrift", "Turnzwerge")
        text = seite.evaluate(
            """() => {
                const s = window.KiTu.zustand.ergebnis.stunde;
                s.ueberschrift = document.getElementById('ueberschrift').value;
                const bytes = window.KiTu.stundenPdf(s, window.KiTu.zustand.orte[0], {});
                return new TextDecoder('latin1').decode(bytes);
            }"""
        )
        self.assertIn("Turnzwerge", text)
        seite.close()

    def test_geraete_lassen_sich_anpassen(self):
        seite = self.oeffne()
        seite.click("#knopf-geraete")
        seite.fill('#geraete-liste input[data-geraet="langbank"]', "0")
        seite.click("#geraete-fertig")
        seite.click("#knopf-planen")
        seite.wait_for_timeout(200)
        genutzt = seite.evaluate(
            """() => {
                const s = window.KiTu.zustand.ergebnis.stunde;
                const alle = {};
                s.teile.forEach(t => t.uebungen.forEach(u =>
                    Object.keys(u.geraete).forEach(g => alle[g] = true)));
                return Object.keys(alle);
            }"""
        )
        self.assertNotIn("langbank", genutzt)
        seite.close()


if __name__ == "__main__":
    unittest.main()
