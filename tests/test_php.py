"""Tests des Serverbetriebs in ``php/``.

Fuer die Tests laeuft der eingebaute PHP-Server auf einem freien Port, mit
einer eigenen Konfiguration im Temp-Ordner: Datenbank ueber PDO (SQLite,
sofern ``KITU_TEST_DSN`` nichts anderes sagt) und Mail als Textdatei im
Postfach. Fehlt PHP, werden die Tests uebersprungen.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
PHPORDNER = WURZEL / "php"
SEITE = WURZEL / "web" / "kinderturnen.html"

sys.path.insert(0, str(WURZEL))
from werkzeuge import lizenzen  # noqa: E402
from werkzeuge.packen import entschluessele, oeffne_huelle  # noqa: E402

PHP = shutil.which("php")

try:  # pragma: no cover - haengt von der Installation ab
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_DA = True
except Exception:  # pragma: no cover
    PLAYWRIGHT_DA = False


def chromium_pfad():
    for muster in ("chromium-*/chrome-linux/chrome", "chromium-*/chrome-mac/*/Chromium"):
        for pfad in Path("/opt/pw-browsers").glob(muster):
            return str(pfad)
    return None


CHROMIUM = chromium_pfad() if PLAYWRIGHT_DA else None


def freier_port() -> int:
    with socket.socket() as dose:
        dose.bind(("127.0.0.1", 0))
        return dose.getsockname()[1]


class Browser:
    """Winziger Ersatzbrowser: merkt sich Cookies, folgt Weiterleitungen."""

    def __init__(self, wurzel: str) -> None:
        self.wurzel = wurzel
        self.kekse = CookieJar()
        self.oeffner = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.kekse)
        )

    def hole(self, pfad: str):
        try:
            with self.oeffner.open(self.wurzel + pfad) as antwort:
                return antwort.status, antwort.read().decode("utf-8"), antwort.url
        except urllib.error.HTTPError as fehler:
            return fehler.code, fehler.read().decode("utf-8", "replace"), fehler.url

    def marke(self, pfad: str) -> str:
        _, text, _ = self.hole(pfad)
        treffer = re.search(r'name="marke" value="([0-9a-f]+)"', text)
        return treffer.group(1) if treffer else ""

    def sende(self, pfad: str, daten: dict, marke_von: str = None):
        daten = dict(daten)
        daten.setdefault("marke", self.marke(marke_von or pfad))
        roh = urllib.parse.urlencode(daten).encode("utf-8")
        try:
            with self.oeffner.open(self.wurzel + pfad, roh) as antwort:
                return antwort.status, antwort.read().decode("utf-8"), antwort.url
        except urllib.error.HTTPError as fehler:
            return fehler.code, fehler.read().decode("utf-8", "replace"), fehler.url


@unittest.skipUnless(PHP, "PHP fehlt")
class PhpTest(unittest.TestCase):
    """Gemeinsamer Unterbau: ein PHP-Server je Testklasse."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ordner = tempfile.TemporaryDirectory()
        pfad = Path(cls.ordner.name)
        cls.daten = pfad / "daten"
        cls.postfach = cls.daten / "postfach"
        dsn = os.environ.get("KITU_TEST_DSN", f"sqlite:{pfad}/kitu.sqlite")

        cls.konfig = pfad / "konfig.php"
        cls.konfig.write_text(
            "<?php return "
            + json_zu_php(
                {
                    "dsn": dsn,
                    "db_nutzer": os.environ.get("KITU_TEST_NUTZER", ""),
                    "db_kennwort": os.environ.get("KITU_TEST_KENNWORT", ""),
                    "geheim": "test-geheim-0123456789",
                    "adresse": "https://kitu.test",
                    "mail": "datei",
                    "absender": "Ki Tu <kitu@test>",
                    "daten": str(cls.daten),
                    "anwendung": str(SEITE),
                    "lizenzen": str(lizenzen.DATEI),
                    "https": False,
                }
            )
            + ";",
            encoding="utf-8",
        )
        # Kleines Werkzeug, um zwischen den Tests aufzuraeumen.
        cls.leeren = pfad / "leeren.php"
        cls.leeren.write_text(
            "<?php require " + php_string(str(PHPORDNER / "inc" / "start.php")) + ";\n"
            "foreach (['konten','codes','fehlversuche','protokoll'] as $t) {\n"
            "    db()->exec(\"DELETE FROM $t\");\n}\n",
            encoding="utf-8",
        )

        cls.umgebung = dict(os.environ, KITU_KONFIG=str(cls.konfig))
        cls.port = freier_port()
        cls.wurzel = f"http://127.0.0.1:{cls.port}"
        cls.protokoll = open(pfad / "server.log", "w", encoding="utf-8")
        cls.prozess = subprocess.Popen(
            [PHP, "-S", f"127.0.0.1:{cls.port}", "-t", str(PHPORDNER)],
            cwd=str(PHPORDNER),
            env=cls.umgebung,
            stdout=cls.protokoll,
            stderr=subprocess.STDOUT,
        )
        cls._warte_auf_server()

    @classmethod
    def _warte_auf_server(cls) -> None:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("PHP-Server kam nicht hoch")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.prozess.terminate()
        cls.prozess.wait(timeout=5)
        cls.protokoll.close()
        cls.ordner.cleanup()

    def setUp(self) -> None:
        subprocess.run([PHP, str(self.leeren)], env=self.umgebung, check=True,
                       capture_output=True)
        if self.postfach.exists():
            shutil.rmtree(self.postfach)
        self.browser = Browser(self.wurzel)

    # -- Hilfen ------------------------------------------------------------
    def mail_an(self, kennung: str) -> str:
        sauber = re.sub(r"[^a-z0-9._-]+", "_", kennung.lower())
        dateien = sorted(self.postfach.glob(f"*_{sauber}.txt"))
        return dateien[-1].read_text(encoding="utf-8") if dateien else ""

    def code_aus_mail(self, kennung: str) -> str:
        treffer = re.search(r"^ {2,}(\d{3}) (\d{3})\s*$", self.mail_an(kennung), re.M)
        return treffer.group(1) + treffer.group(2) if treffer else ""

    def melde_neu_an(self, browser: Browser, kennung="turnen@beispiel.de", name="Test"):
        """Nur registrieren - das Konto ist danach noch unbestaetigt."""
        return browser.sende(
            "/registrieren.php",
            {"name": name, "kennung": kennung,
             "kennwort": "turnhalle1", "kennwort2": "turnhalle1"},
        )

    def registriere(self, browser: Browser, kennung="turnen@beispiel.de", name="Test"):
        """Registrieren und den Code aus der Mail gleich bestaetigen."""
        self.melde_neu_an(browser, kennung, name)
        return browser.sende(
            "/bestaetigen.php",
            {"kennung": kennung, "code": self.code_aus_mail(kennung)},
        )

    def verwalte(self, tat: str, kennung: str, browser: Browser = None):
        browser = browser or self.browser
        return browser.sende("/verwaltung.php", {"tat": tat, "konto": kennung},
                             marke_von="/verwaltung.php")

    def konto_lesen(self, kennung: str) -> dict:
        """Ein Konto direkt aus der Datenbank - zum Nachrechnen im Test."""
        skript = Path(self.ordner.name) / "lesen.php"
        skript.write_text(
            "<?php require " + php_string(str(PHPORDNER / "inc" / "start.php")) + ";\n"
            "echo json_encode(konto($argv[1]));\n",
            encoding="utf-8",
        )
        ergebnis = subprocess.run([PHP, str(skript), kennung], env=self.umgebung,
                                  capture_output=True, text=True, check=True)
        return json.loads(ergebnis.stdout or "null")

    def setze(self, kennung: str, feld: str, wert) -> None:
        """Ein Feld direkt setzen - um Zeit vorzuspulen."""
        skript = Path(self.ordner.name) / "setzen.php"
        skript.write_text(
            "<?php require " + php_string(str(PHPORDNER / "inc" / "start.php")) + ";\n"
            "konto_feld_setzen($argv[1], $argv[2], $argv[3]);\n",
            encoding="utf-8",
        )
        subprocess.run([PHP, str(skript), kennung, feld, str(wert)],
                       env=self.umgebung, capture_output=True, check=True)


def php_string(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def json_zu_php(werte: dict) -> str:
    """Kleines PHP-Array aus einem Wörterbuch - nur fuer die Testkonfiguration."""
    teile = []
    for name, wert in werte.items():
        if isinstance(wert, bool):
            gebaut = "true" if wert else "false"
        elif wert == "":
            gebaut = "null" if name.startswith("db_") else "''"
        else:
            gebaut = php_string(str(wert))
        teile.append(f"{php_string(name)} => {gebaut}")
    return "[" + ", ".join(teile) + "]"


class AufbauTest(PhpTest):
    """Die Aufstellung selbst: Logik in PHP, Markup in HTML, Stil in CSS."""

    def test_kein_php_im_markup(self):
        for datei in (PHPORDNER / "seiten").glob("*.html"):
            inhalt = datei.read_text(encoding="utf-8")
            self.assertNotIn("<?php", inhalt, f"{datei.name} enthaelt Logik")
            self.assertNotIn("<script", inhalt, f"{datei.name} enthaelt Skript")
            self.assertNotIn("style=", inhalt, f"{datei.name} enthaelt Stil")

    def test_kein_markup_in_den_seiten(self):
        """Die Seiten steuern nur - gebaut wird aus den Vorlagen."""
        for datei in PHPORDNER.glob("*.php"):
            inhalt = datei.read_text(encoding="utf-8")
            for muster in ("<html", "<body", "<style", "<!doctype"):
                self.assertNotIn(muster, inhalt.lower(), f"{datei.name}: {muster}")

    def test_alle_php_dateien_sind_fehlerfrei(self):
        for datei in sorted(PHPORDNER.rglob("*.php")):
            ergebnis = subprocess.run([PHP, "-l", str(datei)],
                                      capture_output=True, text=True)
            self.assertEqual(ergebnis.returncode, 0, ergebnis.stdout)

    def test_stil_kommt_aus_der_css_datei(self):
        css = (PHPORDNER / "stil" / "server.css").read_text(encoding="utf-8")
        self.assertIn(".karte", css)
        rahmen = (PHPORDNER / "seiten" / "rahmen.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="stylesheet" href="stil/server.css">', rahmen)

    def test_verzeichnisse_sind_gesperrt(self):
        for ordner in ("inc", "seiten", "daten"):
            wache = PHPORDNER / ordner / ".htaccess"
            self.assertTrue(wache.exists(), f"{ordner}/.htaccess fehlt")
            self.assertIn("denied", wache.read_text(encoding="utf-8"))

    def test_konfiguration_hat_eine_vorlage(self):
        vorlage = (PHPORDNER / "inc" / "konfig.beispiel.php").read_text(encoding="utf-8")
        for schluessel in ("dsn", "geheim", "adresse", "mail", "anwendung", "lizenzen"):
            self.assertIn(f"'{schluessel}'", vorlage)
        self.assertFalse((PHPORDNER / "inc" / "konfig.php").exists(),
                         "konfig.php gehoert nicht ins Projektverzeichnis")


class ZugangTest(PhpTest):
    """Registrierung, Bestaetigung, Anmeldung."""

    def test_ohne_anmeldung_fuehrt_alles_zur_anmeldung(self):
        status, text, adresse = self.browser.hole("/")
        self.assertEqual(status, 200)
        self.assertTrue(adresse.endswith("anmelden.php"), adresse)
        self.assertIn("Anmelden", text)

    def test_freischalten_braucht_eine_anmeldung(self):
        status, text, _ = self.browser.hole("/freischalten.php")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(text)["fehler"], "anmeldung")

    def test_neues_konto_ist_erst_nach_dem_code_freigeschaltet(self):
        status, text, adresse = self.melde_neu_an(self.browser)
        self.assertEqual(status, 200)
        self.assertIn("bestaetigen.php", adresse)
        self.assertIn("Konto bestaetigen", text)
        self.assertEqual(int(self.konto_lesen("turnen@beispiel.de")["bestaetigt"]), 0)

        status, koerper, _ = self.browser.hole("/freischalten.php")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(koerper)["fehler"], "bestaetigung")

    def test_bestaetigung_schaltet_frei(self):
        status, _, adresse = self.registriere(self.browser)
        self.assertEqual(status, 200)
        self.assertTrue(adresse.endswith("index.php"), adresse)

        status, text, _ = self.browser.hole("/freischalten.php")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["schluessel"],
                         lizenzen.lade()["blockschluessel"])

    def test_erstes_konto_wird_verwalter(self):
        self.registriere(self.browser, "erste@beispiel.de")
        zweiter = Browser(self.wurzel)
        self.registriere(zweiter, "zweite@beispiel.de")
        self.assertEqual(self.konto_lesen("erste@beispiel.de")["rolle"], "verwalter")
        self.assertEqual(self.konto_lesen("zweite@beispiel.de")["rolle"], "nutzer")

    def test_kennwoerter_stehen_nur_als_hash_in_der_datenbank(self):
        self.registriere(self.browser)
        gespeichert = self.konto_lesen("turnen@beispiel.de")["kennwort"]
        self.assertNotIn("turnhalle1", gespeichert)
        self.assertRegex(gespeichert, r"^\$2y\$|^\$argon2")

    def test_anmeldung_und_abmeldung(self):
        self.registriere(self.browser)
        self.browser.sende("/abmelden.php", {}, marke_von="/konto.php")
        self.assertEqual(self.browser.hole("/freischalten.php")[0], 401)

        status, _, adresse = self.browser.sende(
            "/anmelden.php", {"kennung": "turnen@beispiel.de", "kennwort": "turnhalle1"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(adresse.endswith("index.php"), adresse)
        self.assertEqual(self.browser.hole("/freischalten.php")[0], 200)

    def test_falsches_kennwort_und_sperre_nach_zehn_versuchen(self):
        self.registriere(self.browser)
        anderer = Browser(self.wurzel)
        for _ in range(10):
            _, text, _ = anderer.sende(
                "/anmelden.php", {"kennung": "turnen@beispiel.de", "kennwort": "falsch123"}
            )
            self.assertIn("stimmt nicht", text)
        _, text, _ = anderer.sende(
            "/anmelden.php", {"kennung": "turnen@beispiel.de", "kennwort": "turnhalle1"}
        )
        self.assertIn("Zu viele Fehlversuche", text)

    def test_registrierung_prueft_die_eingaben(self):
        faelle = [
            ({"kennung": "keinemail", "kennwort": "turnhalle1", "kennwort2": "turnhalle1"},
             "gueltige E-Mail"),
            ({"kennung": "a@b.de", "kennwort": "kurz", "kennwort2": "kurz"},
             "mindestens 8 Zeichen"),
            ({"kennung": "a@b.de", "kennwort": "turnhalle1", "kennwort2": "turnhalle2"},
             "nicht ueberein"),
        ]
        for felder, erwartet in faelle:
            _, text, _ = self.browser.sende("/registrieren.php", dict(felder, name="X"))
            self.assertIn(erwartet, text)

        self.registriere(self.browser, "a@b.de")
        zweiter = Browser(self.wurzel)
        _, text, _ = self.melde_neu_an(zweiter, "a@b.de")
        self.assertIn("schon ein Konto", text)

    def test_ohne_marke_geht_nichts(self):
        status, text, _ = self.browser.sende(
            "/registrieren.php",
            {"name": "X", "kennung": "a@b.de", "kennwort": "turnhalle1",
             "kennwort2": "turnhalle1", "marke": "gefaelscht"},
        )
        self.assertEqual(status, 403)
        self.assertIn("Bitte noch einmal", text)
        self.assertIsNone(self.konto_lesen("a@b.de"))

    def test_anmeldung_wechselt_die_sitzungsmarke(self):
        self.registriere(self.browser)
        self.browser.sende("/abmelden.php", {}, marke_von="/konto.php")
        self.browser.hole("/anmelden.php")
        vorher = [k.value for k in self.browser.kekse if k.name == "kitu_sitzung"][0]
        self.browser.sende(
            "/anmelden.php", {"kennung": "turnen@beispiel.de", "kennwort": "turnhalle1"}
        )
        nachher = [k.value for k in self.browser.kekse if k.name == "kitu_sitzung"][0]
        self.assertNotEqual(vorher, nachher)


class MailTest(PhpTest):
    """Die beiden Mailtexte und die Codes."""

    def test_mail_traegt_namen_code_und_verweis(self):
        self.melde_neu_an(self.browser, name="Anna Uebungsleiterin")
        mail = self.mail_an("turnen@beispiel.de")
        self.assertIn("An: turnen@beispiel.de", mail)
        self.assertIn("Bestaetigungscode", mail)
        self.assertIn("Hallo Anna Uebungsleiterin,", mail)
        self.assertIn("https://kitu.test/bestaetigen.php", mail)
        self.assertIn("30 Minuten", mail)
        self.assertRegex(mail, r"\n {4}\d{3} \d{3}\n")
        self.assertNotIn("{", mail)
        self.assertTrue(mail.rstrip().endswith("Kinderturnen"))

    def test_kennwortmail_ist_eine_andere(self):
        self.registriere(self.browser)
        self.browser.sende("/kennwort-vergessen.php", {"kennung": "turnen@beispiel.de"})
        mail = self.mail_an("turnen@beispiel.de")
        self.assertIn("Neues Kennwort", mail)
        self.assertIn("nur einmal verwenden", mail)
        self.assertIn("https://kitu.test/kennwort-neu.php", mail)
        self.assertIn("bisheriges Kennwort bleibt", mail)

    def test_falscher_code_haelt_die_tuer_zu(self):
        self.melde_neu_an(self.browser)
        _, text, _ = self.browser.sende("/bestaetigen.php", {"code": "000000"})
        self.assertIn("stimmt nicht", text)
        self.assertEqual(int(self.konto_lesen("turnen@beispiel.de")["bestaetigt"]), 0)
        self.assertEqual(self.browser.hole("/freischalten.php")[0], 401)

    def test_code_ist_nach_fuenf_versuchen_verbraucht(self):
        self.melde_neu_an(self.browser)
        for _ in range(5):
            self.browser.sende("/bestaetigen.php", {"code": "000000"})
        richtig = self.code_aus_mail("turnen@beispiel.de")
        _, text, _ = self.browser.sende("/bestaetigen.php", {"code": richtig})
        self.assertIn("stimmt nicht", text)

        self.browser.sende("/code-neu.php", {}, marke_von="/bestaetigen.php")
        neuer = self.code_aus_mail("turnen@beispiel.de")
        self.assertNotEqual(neuer, richtig)
        _, _, adresse = self.browser.sende("/bestaetigen.php", {"code": neuer})
        self.assertTrue(adresse.endswith("index.php"), adresse)

    def test_code_steht_nur_als_hash_in_der_datenbank(self):
        self.melde_neu_an(self.browser)
        code = self.code_aus_mail("turnen@beispiel.de")
        self.assertTrue(code)
        skript = Path(self.ordner.name) / "codes.php"
        skript.write_text(
            "<?php require " + php_string(str(PHPORDNER / "inc" / "start.php")) + ";\n"
            "echo json_encode(db_zeilen('SELECT * FROM codes'));\n",
            encoding="utf-8",
        )
        ergebnis = subprocess.run([PHP, str(skript)], env=self.umgebung,
                                  capture_output=True, text=True, check=True)
        self.assertNotIn(code, ergebnis.stdout)

    def test_kennwort_zuruecksetzen_ueber_die_mail(self):
        self.registriere(self.browser)
        abgemeldet = Browser(self.wurzel)
        _, text, _ = abgemeldet.sende(
            "/kennwort-vergessen.php", {"kennung": "turnen@beispiel.de"}
        )
        self.assertIn("ist ein Code unterwegs", text)
        code = self.code_aus_mail("turnen@beispiel.de")

        _, _, adresse = abgemeldet.sende(
            "/kennwort-neu.php",
            {"kennung": "turnen@beispiel.de", "code": code,
             "kennwort": "neueshaus1", "kennwort2": "neueshaus1"},
        )
        self.assertTrue(adresse.endswith("index.php"), adresse)
        self.assertEqual(abgemeldet.hole("/freischalten.php")[0], 200)

        dritter = Browser(self.wurzel)
        _, text, _ = dritter.sende(
            "/anmelden.php", {"kennung": "turnen@beispiel.de", "kennwort": "turnhalle1"}
        )
        self.assertIn("stimmt nicht", text)
        _, _, adresse = dritter.sende(
            "/anmelden.php", {"kennung": "turnen@beispiel.de", "kennwort": "neueshaus1"}
        )
        self.assertTrue(adresse.endswith("index.php"), adresse)

    def test_kennwortcode_gilt_nur_einmal(self):
        self.registriere(self.browser)
        self.browser.sende("/kennwort-vergessen.php", {"kennung": "turnen@beispiel.de"})
        code = self.code_aus_mail("turnen@beispiel.de")
        felder = {"kennung": "turnen@beispiel.de", "code": code,
                  "kennwort": "neueshaus1", "kennwort2": "neueshaus1"}
        self.browser.sende("/kennwort-neu.php", dict(felder))
        _, text, _ = self.browser.sende("/kennwort-neu.php", dict(felder))
        self.assertIn("stimmt nicht", text)

    def test_unbekannte_adresse_verraet_nichts(self):
        _, text, _ = self.browser.sende(
            "/kennwort-vergessen.php", {"kennung": "niemand@beispiel.de"}
        )
        self.assertIn("Wenn es zu dieser E-Mail ein Konto gibt", text)
        self.assertEqual(self.mail_an("niemand@beispiel.de"), "")


class AboTest(PhpTest):
    """Kostenlos ist dauerhaft - nur das Abo laeuft ab."""

    def test_neues_konto_ist_dauerhaft_kostenlos(self):
        self.registriere(self.browser)
        konto = self.konto_lesen("turnen@beispiel.de")
        self.assertEqual(konto["abo_art"], "frei")
        self.assertEqual(konto["abo_bis"], "")
        _, text, _ = self.browser.hole("/konto.php")
        self.assertIn("dauerhaft", text)
        self.assertEqual(self.browser.hole("/freischalten.php")[0], 200)

    def test_abo_laeuft_ab_und_der_freie_zugang_bleibt(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")

        _, text, _ = self.verwalte("abo_monat", "helfer@beispiel.de")
        self.assertIn("Monatsabo", text)
        konto = self.konto_lesen("helfer@beispiel.de")
        self.assertEqual(konto["abo_art"], "Monatsabo")

        self.setze("helfer@beispiel.de", "abo_bis", "2020-01-01")
        self.assertEqual(nutzer.hole("/freischalten.php")[0], 200)
        _, text, _ = nutzer.hole("/konto.php")
        self.assertIn("kostenlos", text)

    def test_verwalter_waehlt_die_laufzeit(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")

        _, text, _ = self.verwalte("abo_jahr", "helfer@beispiel.de")
        self.assertIn("Jahresabo", text)
        erstes = self.konto_lesen("helfer@beispiel.de")["abo_bis"]

        self.verwalte("abo_monat", "helfer@beispiel.de")
        zweites = self.konto_lesen("helfer@beispiel.de")["abo_bis"]
        self.assertGreater(zweites, erstes, "Verlaengern haengt hinten an")

    def test_abo_beenden_laesst_das_konto_kostenlos_weiterplanen(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        self.verwalte("abo_jahr", "helfer@beispiel.de")
        self.verwalte("offline_geben", "helfer@beispiel.de")
        self.assertTrue(self.konto_lesen("helfer@beispiel.de")["offline"])

        _, text, _ = self.verwalte("abo_stop", "helfer@beispiel.de")
        self.assertIn("kostenlos weiter", text)
        konto = self.konto_lesen("helfer@beispiel.de")
        self.assertEqual(konto["abo_art"], "frei")
        self.assertEqual(konto["offline"], "")
        self.assertEqual(nutzer.hole("/freischalten.php")[0], 200)

    def test_probeabo_laeuft_vierzehn_tage(self):
        self.registriere(self.browser)
        _, text, _ = self.browser.sende("/probeabo.php", {}, marke_von="/konto.php")
        self.assertIn("Probeabo laeuft bis", text)
        konto = self.konto_lesen("turnen@beispiel.de")
        self.assertEqual(konto["abo_art"], "Probeabo")
        self.assertEqual(konto["probe_zuletzt"], time.strftime("%Y-%m-%d", time.gmtime()))

    def test_probeabo_gibt_es_nur_einmal_im_jahr(self):
        self.registriere(self.browser)
        self.browser.sende("/probeabo.php", {}, marke_von="/konto.php")

        _, text, _ = self.browser.sende("/probeabo.php", {}, marke_von="/konto.php")
        self.assertIn("einmal im Jahr", text)

        # Abo abgelaufen, Probe aber im selben Jahr genutzt: weiter nichts.
        self.setze("turnen@beispiel.de", "abo_bis", "2020-01-01")
        _, text, _ = self.browser.sende("/probeabo.php", {}, marke_von="/konto.php")
        self.assertIn("einmal im Jahr", text)

        # Ein Jahr spaeter geht es wieder.
        self.setze("turnen@beispiel.de", "probe_zuletzt", "2020-01-01")
        _, text, _ = self.browser.sende("/probeabo.php", {}, marke_von="/konto.php")
        self.assertIn("Probeabo laeuft bis", text)

    def test_offline_gibt_es_nur_mit_abo(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        _, text, _ = self.verwalte("offline_geben", "helfer@beispiel.de")
        self.assertIn("kein laufendes Abo", text)
        self.assertEqual(self.konto_lesen("helfer@beispiel.de")["offline"], "")


class SchluesselTest(PhpTest):
    """Der Offline-Schluessel gehoert zu genau einem Konto."""

    def vorbereiten(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        self.verwalte("abo_jahr", "helfer@beispiel.de")
        self.verwalte("offline_geben", "helfer@beispiel.de")
        return nutzer, self.konto_lesen("helfer@beispiel.de")

    def test_php_und_python_rechnen_gleich(self):
        _, konto = self.vorbereiten()
        block = re.search(
            r'var BLOCK = "([A-Za-z0-9+/=]+)"', SEITE.read_text(encoding="utf-8")
        ).group(1)
        seite = self.browser.hole("/kinderturnen.php")  # als Verwalter ohne Huelle
        self.assertEqual(seite[0], 200)

        skript = Path(self.ordner.name) / "huelle.php"
        skript.write_text(
            "<?php require " + php_string(str(PHPORDNER / "inc" / "start.php")) + ";\n"
            "echo json_encode(huelleneintrag(konto($argv[1])));\n",
            encoding="utf-8",
        )
        ergebnis = subprocess.run([PHP, str(skript), "helfer@beispiel.de"],
                                  env=self.umgebung, capture_output=True,
                                  text=True, check=True)
        eintrag = json.loads(ergebnis.stdout)

        # Was PHP verdeckt hat, rechnet Python wieder auf.
        richtig = oeffne_huelle(eintrag["h"], "helfer@beispiel.de", konto["offline"])
        self.assertIsNotNone(entschluessele(block, richtig))
        falsch = oeffne_huelle(eintrag["h"], "chef@beispiel.de", konto["offline"])
        self.assertIsNone(entschluessele(block, falsch))
        self.assertEqual(eintrag["bis"], konto["abo_bis"])

    def test_persoenliche_datei_traegt_genau_eine_huelle(self):
        nutzer, konto = self.vorbereiten()
        status, text, _ = nutzer.hole("/kinderturnen.php")
        self.assertEqual(status, 200)
        huellen = json.loads(re.search(r"var HUELLEN = (\[.*?\]);", text).group(1))
        self.assertEqual(len(huellen), 1)
        self.assertEqual(huellen[0]["bis"], konto["abo_bis"])

        block = re.search(r'var BLOCK = "([A-Za-z0-9+/=]+)"', text).group(1)
        richtig = oeffne_huelle(huellen[0]["h"], "helfer@beispiel.de", konto["offline"])
        self.assertIsNotNone(entschluessele(block, richtig))

    def test_ohne_anmeldung_keine_datei(self):
        fremder = Browser(self.wurzel)
        status, text, adresse = fremder.hole("/kinderturnen.php")
        self.assertIn("anmelden.php", adresse)
        self.assertNotIn("var BLOCK", text)


class RollenTest(PhpTest):
    """Verwaltung und Wartung."""

    def test_wartung_darf_schauen_aber_nicht_anfassen(self):
        self.registriere(self.browser, "chef@beispiel.de")
        wart = Browser(self.wurzel)
        self.registriere(wart, "wartung@beispiel.de")
        self.verwalte("wartung", "wartung@beispiel.de")
        self.assertEqual(self.konto_lesen("wartung@beispiel.de")["rolle"], "wartung")

        status, text, _ = wart.hole("/wartung.php")
        self.assertEqual(status, 200)
        self.assertIn("laufende Abos", text)
        self.assertIn("Konten", text)

        self.assertEqual(wart.hole("/verwaltung.php")[0], 403)
        status, _, _ = wart.sende(
            "/verwaltung.php", {"tat": "verwalter", "konto": "wartung@beispiel.de"},
            marke_von="/konto.php",
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.konto_lesen("wartung@beispiel.de")["rolle"], "wartung")

    def test_normale_nutzer_sehen_die_wartung_nicht(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        self.assertEqual(nutzer.hole("/wartung.php")[0], 403)
        self.assertEqual(self.browser.hole("/wartung.php")[0], 200)
        self.assertEqual(self.browser.hole("/verwaltung.php")[0], 200)

    def test_verwalter_sperrt_ein_konto(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        self.assertEqual(nutzer.hole("/freischalten.php")[0], 200)

        self.verwalte("sperren", "helfer@beispiel.de")
        self.assertEqual(nutzer.hole("/freischalten.php")[0], 401)
        self.verwalte("entsperren", "helfer@beispiel.de")
        self.assertEqual(nutzer.hole("/freischalten.php")[0], 200)

    def test_dienstkonten_von_der_kommandozeile(self):
        ergebnis = subprocess.run(
            [PHP, str(PHPORDNER / "einrichten.php")],
            env=dict(self.umgebung, KITU_VERWALTER="chefin@beispiel.de",
                     KITU_WARTUNG="pflege@beispiel.de"),
            capture_output=True, text=True, check=True,
        )
        self.assertIn("verwalter", ergebnis.stdout)
        self.assertIn("chefin@beispiel.de", ergebnis.stdout)
        kennwort = re.search(r"Kennwort\s+(\S{20,})", ergebnis.stdout).group(1)

        self.assertEqual(self.konto_lesen("chefin@beispiel.de")["rolle"], "verwalter")
        self.assertEqual(self.konto_lesen("pflege@beispiel.de")["rolle"], "wartung")
        self.assertEqual(int(self.konto_lesen("chefin@beispiel.de")["bestaetigt"]), 1)

        _, _, adresse = self.browser.sende(
            "/anmelden.php", {"kennung": "chefin@beispiel.de", "kennwort": kennwort}
        )
        self.assertTrue(adresse.endswith("index.php"), adresse)
        self.assertEqual(self.browser.hole("/verwaltung.php")[0], 200)

    def test_einrichten_laeuft_nicht_ueber_den_browser(self):
        status, text, _ = self.browser.hole("/einrichten.php")
        self.assertEqual(status, 403)
        self.assertIn("Kommandozeile", text)


class DatenbankTest(unittest.TestCase):
    """``datenbank/kitu.sql`` und ``php/inc/db.php`` muessen dasselbe sagen."""

    SQL = WURZEL / "datenbank" / "kitu.sql"

    @staticmethod
    def tabellen(text: str) -> dict:
        """{Tabelle: [Spalten]} aus CREATE-TABLE-Anweisungen."""
        gefunden = {}
        muster = re.compile(
            r"CREATE TABLE IF NOT EXISTS\s+`?(\w+)`?\s*\((.*?)\n\s*\)", re.S
        )
        for name, koerper in muster.findall(text):
            spalten = []
            for zeile in koerper.splitlines():
                zeile = zeile.strip().rstrip(",")
                treffer = re.match(r"`?(\w+)`?\s+(VARCHAR\(\d+\)|TINYINT|BIGINT|INT)", zeile)
                if treffer and not zeile.upper().startswith(("PRIMARY", "KEY", "UNIQUE")):
                    spalten.append((treffer.group(1), treffer.group(2)))
            gefunden[name] = spalten
        return gefunden

    def test_datei_ist_vorhanden(self):
        self.assertTrue(self.SQL.exists(), "datenbank/kitu.sql fehlt")
        inhalt = self.SQL.read_text(encoding="utf-8")
        self.assertIn("CREATE DATABASE IF NOT EXISTS `kitu`", inhalt)
        self.assertIn("utf8mb4", inhalt)
        self.assertIn("ENGINE=InnoDB", inhalt)
        # Kein echtes Kennwort in der ausgelieferten Datei.
        self.assertIn("bitte-hier-ein-eigenes-kennwort", inhalt)

    def test_sql_und_php_beschreiben_dieselben_tabellen(self):
        aus_sql = self.tabellen(self.SQL.read_text(encoding="utf-8"))
        aus_php = self.tabellen((PHPORDNER / "inc" / "db.php").read_text(encoding="utf-8"))

        self.assertEqual(sorted(aus_sql), sorted(aus_php), "andere Tabellen")
        self.assertEqual(sorted(aus_sql), ["codes", "fehlversuche", "konten", "protokoll"])
        for tabelle in aus_sql:
            self.assertEqual(
                aus_sql[tabelle], aus_php[tabelle],
                f"Tabelle {tabelle}: Spalten laufen auseinander",
            )

    def test_alle_spalten_der_anwendung_stehen_darin(self):
        """Was konten.php schreibt, muss die Tabelle auch haben."""
        spalten = {name for name, _ in self.tabellen(
            self.SQL.read_text(encoding="utf-8"))["konten"]}
        gebraucht = {"kennung", "name", "kennwort", "rolle", "angelegt", "bestaetigt",
                     "gesperrt", "abo_art", "abo_seit", "abo_bis", "probe_zuletzt",
                     "offline"}
        self.assertEqual(spalten, gebraucht)

    @unittest.skipUnless(shutil.which("mariadb") or shutil.which("mysql"),
                         "kein MySQL-Kommando vorhanden")
    def test_sql_laeuft_auf_einer_echten_datenbank(self):
        """Nur wenn ein Server erreichbar ist - sonst uebersprungen."""
        werkzeug = shutil.which("mariadb") or shutil.which("mysql")
        socket_pfad = os.environ.get("KITU_TEST_SOCKET", "/tmp/kitu-maria.sock")
        if not Path(socket_pfad).exists():
            self.skipTest("kein Datenbankserver erreichbar")

        skript = self.SQL.read_text(encoding="utf-8").replace("`kitu`", "`kitu_probe`")
        skript = skript.replace("'kitu'@'localhost'", "'kitu_probe'@'localhost'")
        ergebnis = subprocess.run(
            [werkzeug, f"--socket={socket_pfad}"],
            input=skript + "\nDROP DATABASE `kitu_probe`;\nDROP USER 'kitu_probe'@'localhost';\n",
            capture_output=True, text=True,
        )
        self.assertEqual(ergebnis.returncode, 0, ergebnis.stderr)


@unittest.skipUnless(PHP and PLAYWRIGHT_DA and CHROMIUM and SEITE.exists(),
                     "PHP, Playwright, Chromium oder die gebaute Datei fehlt")
class EndeZuEndeTest(PhpTest):
    """Vom leeren Browser bis zur geplanten Stunde."""

    def setUp(self) -> None:
        super().setUp()
        self._pw = sync_playwright().start()
        self.chrom = self._pw.chromium.launch(executable_path=CHROMIUM)

    def tearDown(self) -> None:
        self.chrom.close()
        self._pw.stop()

    def test_registrieren_bestaetigen_planen(self):
        seite = self.chrom.new_page(viewport={"width": 1100, "height": 800})
        fehler = []
        seite.on("pageerror", lambda e: fehler.append(str(e)))
        seite.goto(self.wurzel + "/")
        self.assertTrue(seite.url.endswith("anmelden.php"))

        seite.click("text=Hier registrieren")
        seite.fill("#name", "Uebungsleiterin")
        seite.fill("#kennung", "leitung@beispiel.de")
        seite.fill("#kennwort", "turnhalle1")
        seite.fill("#kennwort2", "turnhalle1")
        seite.click("#knopf-registrieren")

        seite.wait_for_selector("#knopf-bestaetigen", timeout=15000)
        seite.fill("#code", self.code_aus_mail("leitung@beispiel.de"))
        seite.click("#knopf-bestaetigen")

        # Der Server gibt den Schluessel heraus, die Seite entschluesselt sich.
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=30000)
        stationen = seite.evaluate(
            "() => document.querySelectorAll('#stationsliste li').length"
        )
        self.assertGreaterEqual(stationen, 3)
        self.assertEqual(fehler, [])

        seite.goto(self.wurzel + "/konto.php")
        seite.click("#knopf-abmelden")
        seite.goto(self.wurzel + "/")
        self.assertTrue(seite.url.endswith("anmelden.php"))
        seite.close()

    def test_persoenliche_datei_laeuft_offline(self):
        self.registriere(self.browser, "chef@beispiel.de")
        self.verwalte("abo_jahr", "chef@beispiel.de")
        self.verwalte("offline_geben", "chef@beispiel.de")
        konto = self.konto_lesen("chef@beispiel.de")

        datei = Path(self.ordner.name) / "meine.html"
        _, text, _ = self.browser.hole("/kinderturnen.php")
        datei.write_text(text, encoding="utf-8")

        seite = self.chrom.new_page()
        seite.goto(datei.resolve().as_uri())
        seite.wait_for_selector("#lizenzfeld", timeout=15000)
        seite.fill("#kontofeld", "chef@beispiel.de")
        seite.fill("#lizenzfeld", konto["offline"])
        seite.click("#lizenzknopf")
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=30000)
        seite.close()


if __name__ == "__main__":
    unittest.main()
