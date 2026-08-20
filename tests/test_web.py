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

sys.path.insert(0, str(WURZEL))
from werkzeuge import lizenzen  # noqa: E402
from werkzeuge.packen import entschluessele, lizenzschluessel, ohne_kommentare  # noqa: E402

LIZENZEN = lizenzen.lade()
SCHLUESSEL = bytes.fromhex(LIZENZEN["blockschluessel"])
OFFLINE = LIZENZEN["vorrat"][0]["schluessel"]  # Offline-Schluessel fuer die Tests


def block_der_seite(inhalt: str):
    """Der verschluesselte Block aus dem Lader der gebauten Seite."""
    treffer = re.search(r'var BLOCK = "([A-Za-z0-9+/=]+)"', inhalt)
    return treffer.group(1) if treffer else None


def programmtext(inhalt: str) -> str:
    """Der entschluesselte Inhalt der Seite."""
    return entschluessele(block_der_seite(inhalt), SCHLUESSEL)

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

    def test_quelltext_ist_nicht_lesbar(self):
        """Im Seitenquelltext steht nur der Lader - kein Markup, kein Programm."""
        inhalt = SEITE.read_text(encoding="utf-8")
        block = block_der_seite(inhalt)
        self.assertIsNotNone(block, "verschluesselter Block nicht gefunden")

        # Alles ausserhalb des Blocks ist die Huelle: Lader und Schluesselhuellen.
        huelle = inhalt.replace(block, "")
        self.assertLess(len(huelle), 16_000, "zu viel offener Text in der Seite")

        verraeter = [
            "Bewegungslandschaft",
            "Sprossenwand",
            "stundenPdf",
            "zeichneAlles",
            "planflaeche",
            "stationsliste",
            "<canvas",
            "<button",
            "altersgruppe",
            "Turnhalle",
            "Aufwaermen",
        ]
        for wort in verraeter:
            self.assertNotIn(wort, huelle, f"lesbarer Quelltext gefunden: {wort}")

    def test_programm_steckt_im_block(self):
        """Entpackt enthaelt der Block Aufbau, Stil, Katalog und Programm."""
        text = programmtext(SEITE.read_text(encoding="utf-8"))
        for stueck in ('id=\\"plan\\"', "--akzent", "stundenPdf", "zeichnePlan"):
            self.assertIn(stueck, text)
        # Die Kommentare der Quellen sind draussen geblieben.
        self.assertNotIn("// ====", text)
        self.assertNotIn("Fuer Tests und Erweiterungen", text)

    def test_katalog_steckt_in_der_datei(self):
        text = programmtext(SEITE.read_text(encoding="utf-8"))
        treffer = re.search(r"^const DATEN=(\{.*\});$", text, re.MULTILINE)
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


class PackerTest(unittest.TestCase):
    """Der Kommentar-Entferner darf nur Kommentare treffen."""

    def test_kommentare_verschwinden(self):
        quelle = "// weg\nconst a = 1; /* auch weg */\n  const b = 2;\n"
        self.assertEqual(ohne_kommentare(quelle), "const a = 1;\nconst b = 2;")

    def test_zeichenketten_bleiben_heil(self):
        for text in (
            'const a = "// kein Kommentar";',
            "const b = '/* auch nicht */';",
            "const c = `Zeile ${x} /* nein */`;",
            'const d = "Umlaute: aeoeue - \\" im Text";',
        ):
            self.assertEqual(ohne_kommentare(text), text)

    def test_regulaere_ausdruecke_bleiben_heil(self):
        for text in (
            'x.replace(/[aA]/g, "b");',
            "const r = /\\/\\//;",
            "const t = a / b / c;",
            'if (/[?&]pruefung=1\\b/.test(s)) f();',
        ):
            self.assertEqual(ohne_kommentare(text), text)

    def test_vorlage_ueber_mehrere_zeilen(self):
        quelle = "const s = `<< /Type ${liste\n  .join(' ')}] >>`;"
        self.assertEqual(ohne_kommentare(quelle), "const s = `<< /Type ${liste\n.join(' ')}] >>`;")


class SchluesselTest(unittest.TestCase):
    """Verschluesselung und Ableitung aus dem Lizenzschluessel."""

    def test_verschluesseln_und_zurueck(self):
        from werkzeuge.packen import neuer_blockschluessel, verschluessele

        text = 'const x = "Groesse: 27 x 15 m";'
        schluessel = bytes.fromhex(neuer_blockschluessel())
        block = verschluessele(text, schluessel)
        self.assertNotIn("Groesse", block)
        self.assertEqual(entschluessele(block, schluessel), text)

    def test_falscher_schluessel_gibt_nichts_her(self):
        from werkzeuge.packen import verschluessele

        block = verschluessele("geheim", bytes(range(32)))
        self.assertIsNone(entschluessele(block, bytes(32)))

    def test_schreibweise_des_lizenzschluessels_ist_egal(self):
        from werkzeuge.packen import kennung, normiere

        for form in ("KITU-AAAA-BBBB", "kitu aaaa bbbb", "kituaaaabbbb"):
            self.assertEqual(normiere(form), "KITUAAAABBBB")
            self.assertEqual(kennung(form), kennung("KITU-AAAA-BBBB"))

    def test_huelle_gibt_den_blockschluessel_zurueck(self):
        from werkzeuge.packen import huelle

        lizenz = LIZENZEN["vorrat"][1]["schluessel"]
        verdeckt = bytes.fromhex(huelle(SCHLUESSEL, lizenz))
        zurueck = bytes(a ^ b for a, b in zip(verdeckt, lizenzschluessel(lizenz)))
        self.assertEqual(zurueck, SCHLUESSEL)
        self.assertEqual(verdeckt.hex(), LIZENZEN["vorrat"][1]["huelle"])

    def test_jeder_vorratsschluessel_oeffnet_die_seite(self):
        block = block_der_seite(SEITE.read_text(encoding="utf-8"))
        for eintrag in LIZENZEN["vorrat"][:3]:
            verdeckt = bytes.fromhex(eintrag["huelle"])
            schluessel = bytes(
                a ^ b for a, b in zip(verdeckt, lizenzschluessel(eintrag["schluessel"]))
            )
            self.assertIsNotNone(entschluessele(block, schluessel), eintrag["schluessel"])


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

    def neue_seite(self, breite=1280, hoehe=860, lizenz=OFFLINE):
        """Leere Seite mit Fehlerwaechter - der Schluessel liegt schon bereit."""
        seite = self.browser.new_page(viewport={"width": breite, "height": hoehe})
        self.fehler = []
        seite.on("pageerror", lambda e: self.fehler.append(str(e)))
        seite.on(
            "console",
            lambda m: self.fehler.append(m.text) if m.type == "error" else None,
        )
        if lizenz:
            seite.add_init_script(
                "try { localStorage.setItem('kitu.lizenz', %s); } catch (e) {}"
                % json.dumps(lizenz)
            )
        return seite

    def oeffne(self, breite=1280, hoehe=860, pruefung=True):
        """Seite mit Offline-Schluessel oeffnen und auf das Programm warten."""
        seite = self.neue_seite(breite, hoehe)
        # Die Innereien reicht die Seite nur mit "?pruefung=1" heraus.
        seite.goto(SEITE.resolve().as_uri() + ("?pruefung=1" if pruefung else ""))
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=20000)
        seite.wait_for_timeout(350)
        return seite

    def test_ohne_schluessel_bleibt_es_bei_der_abfrage(self):
        seite = self.neue_seite(lizenz=None)
        seite.goto(SEITE.resolve().as_uri())
        seite.wait_for_selector("#lizenzfeld", timeout=15000)
        self.assertFalse(seite.evaluate("() => !!document.getElementById('plan')"))
        # Nichts vom Programm ist im Dokument gelandet.
        self.assertNotIn("Bewegungslandschaft", seite.content())
        seite.close()

    def test_falscher_schluessel_wird_abgewiesen(self):
        seite = self.neue_seite(lizenz=None)
        seite.goto(SEITE.resolve().as_uri())
        seite.wait_for_selector("#lizenzfeld", timeout=15000)
        seite.fill("#lizenzfeld", "KITU-XXXX-XXXX-XXXX-XXXX")
        seite.click("#lizenzknopf")
        seite.wait_for_function(
            "() => document.getElementById('lizenzhinweis').textContent.length > 0",
            timeout=20000,
        )
        self.assertIn("passt nicht", seite.text_content("#lizenzhinweis"))
        self.assertFalse(seite.evaluate("() => !!document.getElementById('plan')"))
        seite.close()

    def test_richtiger_schluessel_schaltet_frei_und_wird_gemerkt(self):
        seite = self.neue_seite(lizenz=None)
        seite.goto(SEITE.resolve().as_uri())
        seite.wait_for_selector("#lizenzfeld", timeout=15000)
        seite.fill("#lizenzfeld", OFFLINE)
        seite.click("#lizenzknopf")
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=20000)
        self.assertEqual(
            seite.evaluate("() => localStorage.getItem('kitu.lizenz')"), OFFLINE
        )
        # Neu laden: kein Nachfragen mehr.
        seite.reload()
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=20000)
        self.assertEqual(self.fehler, [])
        seite.close()

    def test_lizenz_neu_vergisst_den_schluessel(self):
        seite = self.oeffne()
        seite.goto(SEITE.resolve().as_uri() + "?lizenz=neu")
        seite.wait_for_selector("#lizenzfeld", timeout=15000)
        self.assertIsNone(seite.evaluate("() => localStorage.getItem('kitu.lizenz')"))
        seite.close()

    def test_schluessel_darf_auch_in_der_adresse_stehen(self):
        seite = self.neue_seite(lizenz=None)
        seite.goto(SEITE.resolve().as_uri() + "#lizenz=" + OFFLINE)
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=20000)
        seite.close()

    def test_seite_baut_sich_selbst_auf(self):
        """Der Aufbau steckt im gepackten Block, nicht im Quelltext."""
        seite = self.oeffne(pruefung=False)
        werte = seite.evaluate(
            """() => ({
                knoepfe: document.querySelectorAll('button').length,
                plan: !!document.getElementById('plan'),
                stil: getComputedStyle(document.body).backgroundColor,
                innereien: typeof window.KiTu,
            })"""
        )
        self.assertGreaterEqual(werte["knoepfe"], 5)
        self.assertTrue(werte["plan"])
        self.assertNotEqual(werte["stil"], "rgba(0, 0, 0, 0)")
        self.assertEqual(werte["innereien"], "undefined", "Innereien offen zugaenglich")
        self.assertEqual(self.fehler, [])
        seite.close()

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
