"""Tests des Kontoservers ``werkzeuge/server.py``.

Der Server laeuft dafuer in einem eigenen Faden auf einem freien Port, mit
einem Datenverzeichnis im Temp-Ordner.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from werkzeuge import post as postfach  # noqa: E402
from werkzeuge import server  # noqa: E402


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
            return fehler.code, fehler.read().decode("utf-8"), fehler.url

    def marke(self, pfad: str) -> str:
        """CSRF-Marke von einer Formularseite holen."""
        _, text, _ = self.hole(pfad)
        treffer = re.search(r'name=marke value="([0-9a-f]+)"', text)
        return treffer.group(1) if treffer else ""

    def sende(self, pfad: str, daten: dict, marke_von: str = None):
        daten = dict(daten)
        daten.setdefault("marke", self.marke(marke_von or pfad))
        roh = urllib.parse.urlencode(daten).encode("utf-8")
        try:
            with self.oeffner.open(self.wurzel + pfad, roh) as antwort:
                return antwort.status, antwort.read().decode("utf-8"), antwort.url
        except urllib.error.HTTPError as fehler:
            return fehler.code, fehler.read().decode("utf-8"), fehler.url


class ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.server = server.baue_server(0, Path(self.ordner.name), host="127.0.0.1")
        self.anwendung = self.server.anwendung
        # Kennwoerter im Test schnell pruefen - 240000 Runden waeren zu zaeh.
        self.anwendung._hash = lambda kennwort, salz, runden=1000: server.hashlib.pbkdf2_hmac(
            "sha256", kennwort.encode("utf-8"), bytes.fromhex(salz), 1000
        ).hex()
        self.faden = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.faden.start()
        port = self.server.server_address[1]
        self.browser = Browser(f"http://127.0.0.1:{port}")

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.faden.join(timeout=5)
        self.ordner.cleanup()

    # -- Hilfen ------------------------------------------------------------
    def melde_neu_an(self, browser: Browser, kennung="turnen@beispiel.de", name="Test"):
        """Nur registrieren - das Konto ist danach noch unbestaetigt."""
        return browser.sende(
            "/registrieren",
            {
                "name": name,
                "kennung": kennung,
                "kennwort": "turnhalle1",
                "kennwort2": "turnhalle1",
            },
        )

    def code_aus_mail(self, kennung: str) -> str:
        return postfach.code_aus_text(self.anwendung.postausgang.letzte(kennung))

    def registriere(self, browser: Browser, kennung="turnen@beispiel.de", name="Test"):
        """Registrieren und den Code aus der Mail gleich bestaetigen."""
        self.melde_neu_an(browser, kennung, name)
        return browser.sende(
            "/bestaetigen",
            {"kennung": kennung, "code": self.code_aus_mail(kennung)},
        )

    # -- Tests -------------------------------------------------------------
    def test_ohne_anmeldung_fuehrt_alles_zur_anmeldung(self):
        status, text, adresse = self.browser.hole("/")
        self.assertEqual(status, 200)
        self.assertTrue(adresse.endswith("/anmelden"))
        self.assertIn("Anmelden", text)

    def test_freischalten_braucht_eine_anmeldung(self):
        status, text, _ = self.browser.hole("/freischalten")
        self.assertEqual(status, 401)
        self.assertNotIn(self.anwendung.blockschluessel(), text)

    def test_registrierung_schaltet_frei(self):
        status, _, adresse = self.registriere(self.browser)
        self.assertEqual(status, 200)
        self.assertTrue(adresse.endswith("/"), adresse)

        status, text, _ = self.browser.hole("/freischalten")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["schluessel"], self.anwendung.blockschluessel())

    def test_erstes_konto_wird_verwalter(self):
        self.registriere(self.browser, "erste@beispiel.de")
        zweiter = Browser(self.browser.wurzel)
        self.registriere(zweiter, "zweite@beispiel.de")
        self.assertEqual(self.anwendung.konto("erste@beispiel.de")["rolle"], "verwalter")
        self.assertEqual(self.anwendung.konto("zweite@beispiel.de")["rolle"], "nutzer")

    def test_kennwoerter_stehen_nur_als_hash_in_der_datei(self):
        self.registriere(self.browser)
        inhalt = (Path(self.ordner.name) / "konten.json").read_text(encoding="utf-8")
        self.assertNotIn("turnhalle1", inhalt)
        konto = json.loads(inhalt)["konten"][0]
        self.assertEqual(len(konto["hash"]), 64)
        self.assertTrue(konto["salz"])

    def test_anmeldung_und_abmeldung(self):
        self.registriere(self.browser)
        self.browser.sende("/abmelden", {}, marke_von="/konto")
        self.assertEqual(self.browser.hole("/freischalten")[0], 401)

        status, _, adresse = self.browser.sende(
            "/anmelden", {"kennung": "turnen@beispiel.de", "kennwort": "turnhalle1"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(adresse.endswith("/"))
        self.assertEqual(self.browser.hole("/freischalten")[0], 200)

    def test_falsches_kennwort_und_sperre_nach_zehn_versuchen(self):
        self.registriere(self.browser)
        anderer = Browser(self.browser.wurzel)
        for _ in range(10):
            _, text, _ = anderer.sende(
                "/anmelden", {"kennung": "turnen@beispiel.de", "kennwort": "falsch123"}
            )
            self.assertIn("stimmt nicht", text)
        # Auch das richtige Kennwort kommt jetzt nicht mehr durch.
        _, text, _ = anderer.sende(
            "/anmelden", {"kennung": "turnen@beispiel.de", "kennwort": "turnhalle1"}
        )
        self.assertIn("Zu viele Fehlversuche", text)
        self.assertEqual(anderer.hole("/freischalten")[0], 401)

    def test_registrierung_prueft_die_eingaben(self):
        _, text, _ = self.browser.sende(
            "/registrieren",
            {"name": "X", "kennung": "keinemail", "kennwort": "turnhalle1",
             "kennwort2": "turnhalle1"},
        )
        self.assertIn("gueltige E-Mail", text)
        _, text, _ = self.browser.sende(
            "/registrieren",
            {"name": "X", "kennung": "a@b.de", "kennwort": "kurz", "kennwort2": "kurz"},
        )
        self.assertIn("mindestens 8 Zeichen", text)
        _, text, _ = self.browser.sende(
            "/registrieren",
            {"name": "X", "kennung": "a@b.de", "kennwort": "turnhalle1",
             "kennwort2": "turnhalle2"},
        )
        self.assertIn("nicht ueberein", text)
        self.registriere(self.browser, "a@b.de")
        zweiter = Browser(self.browser.wurzel)
        _, text, _ = self.melde_neu_an(zweiter, "a@b.de")
        self.assertIn("schon ein Konto", text)

    def test_ohne_marke_geht_nichts(self):
        status, text, _ = self.browser.sende(
            "/registrieren",
            {"name": "X", "kennung": "a@b.de", "kennwort": "turnhalle1",
             "kennwort2": "turnhalle1", "marke": "gefaelscht"},
        )
        self.assertEqual(status, 403)
        self.assertIn("Formular war zu alt", text)
        self.assertEqual(self.anwendung.konten, [])

    def test_nutzer_kommt_nicht_in_die_verwaltung(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.browser.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        status, text, _ = nutzer.hole("/verwaltung")
        self.assertEqual(status, 403)
        self.assertIn("Kein Zutritt", text)

    def test_verwalter_vergibt_offline_schluessel(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.browser.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        self.browser.sende(
            "/verwaltung", {"tat": "abo_jahr", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )

        _, text, _ = self.browser.sende(
            "/verwaltung", {"tat": "offline_geben", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertIn("offline arbeiten", text)
        schluessel = self.anwendung.konto("helfer@beispiel.de")["offline"]
        self.assertTrue(schluessel.startswith("KITU-"))

        _, konto, _ = nutzer.hole("/konto")
        self.assertIn(schluessel, konto)

        # Zweimal vergeben ergibt zwei verschiedene Schluessel.
        self.browser.sende(
            "/verwaltung", {"tat": "offline_geben", "konto": "chef@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertNotEqual(self.anwendung.konto("chef@beispiel.de")["offline"], schluessel)

        # Und wieder entziehen.
        self.browser.sende(
            "/verwaltung", {"tat": "offline_nehmen", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertIsNone(self.anwendung.konto("helfer@beispiel.de")["offline"])

    def test_verwalter_sperrt_ein_konto(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.browser.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        self.assertEqual(nutzer.hole("/freischalten")[0], 200)

        self.browser.sende(
            "/verwaltung", {"tat": "sperren", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertEqual(nutzer.hole("/freischalten")[0], 401)

        self.browser.sende(
            "/verwaltung", {"tat": "entsperren", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertEqual(nutzer.hole("/freischalten")[0], 200)

    def test_datei_gibt_es_nur_fuer_angemeldete(self):
        _, text, adresse = self.browser.hole("/kinderturnen.html")
        self.assertIn("/anmelden", adresse)
        self.assertNotIn("var BLOCK", text)

        self.registriere(self.browser)
        status, text, _ = self.browser.hole("/kinderturnen.html")
        self.assertEqual(status, 200)
        self.assertIn("var BLOCK", text)

    # -- Bestaetigung per Mail ---------------------------------------------
    def test_neues_konto_ist_erst_nach_dem_code_freigeschaltet(self):
        status, text, adresse = self.melde_neu_an(self.browser)
        self.assertEqual(status, 200)
        self.assertIn("/bestaetigen", adresse)
        self.assertIn("Konto bestaetigen", text)
        self.assertFalse(self.anwendung.konto("turnen@beispiel.de")["bestaetigt"])
        # Ohne Bestaetigung gibt es den Schluessel nicht.
        status, koerper, _ = self.browser.hole("/freischalten")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(koerper)["fehler"], "bestaetigung")
        # Auch das Programm bleibt zu.
        _, _, adresse = self.browser.hole("/")
        self.assertIn("/bestaetigen", adresse)

    def test_mail_traegt_namen_code_und_verweis(self):
        self.anwendung.adresse = "https://kitu.beispiel.de"
        self.melde_neu_an(self.browser, name="Anna Uebungsleiterin")
        mail = self.anwendung.postausgang.letzte("turnen@beispiel.de")
        self.assertIn("An: turnen@beispiel.de", mail)
        self.assertIn("Bestaetigungscode", mail)
        self.assertIn("Hallo Anna Uebungsleiterin,", mail)
        self.assertIn("https://kitu.beispiel.de/bestaetigen", mail)
        self.assertIn("30 Minuten", mail)
        self.assertRegex(mail, r"\n {4}\d{3} \d{3}\n")
        self.assertNotIn("{", mail)  # keine offenen Platzhalter

    def test_falscher_code_haelt_die_tuer_zu(self):
        self.melde_neu_an(self.browser)
        _, text, _ = self.browser.sende("/bestaetigen", {"code": "000000"})
        self.assertIn("stimmt nicht", text)
        self.assertFalse(self.anwendung.konto("turnen@beispiel.de")["bestaetigt"])
        self.assertEqual(self.browser.hole("/freischalten")[0], 401)

    def test_code_ist_nach_fuenf_versuchen_verbraucht(self):
        self.melde_neu_an(self.browser)
        for _ in range(5):
            self.browser.sende("/bestaetigen", {"code": "000000"})
        richtig = self.code_aus_mail("turnen@beispiel.de")
        _, text, _ = self.browser.sende("/bestaetigen", {"code": richtig})
        self.assertIn("stimmt nicht", text)
        # Ein neuer Code hilft.
        self.browser.sende("/code-neu", {}, marke_von="/bestaetigen")
        neuer = self.code_aus_mail("turnen@beispiel.de")
        self.assertNotEqual(neuer, richtig)
        _, _, adresse = self.browser.sende("/bestaetigen", {"code": neuer})
        self.assertTrue(adresse.endswith("/"))

    def test_abgelaufener_code_wird_abgewiesen(self):
        self.melde_neu_an(self.browser)
        konto = self.anwendung.konto("turnen@beispiel.de")
        code = self.code_aus_mail("turnen@beispiel.de")
        konto["code"]["bis"] = server.jetzt() - 1
        _, text, _ = self.browser.sende("/bestaetigen", {"code": code})
        self.assertIn("abgelaufen", text)

    def test_code_steht_nur_als_hash_in_der_datei(self):
        self.melde_neu_an(self.browser)
        code = self.code_aus_mail("turnen@beispiel.de")
        inhalt = (Path(self.ordner.name) / "konten.json").read_text(encoding="utf-8")
        self.assertNotIn(code, inhalt)

    def test_nie_bestaetigtes_konto_verfaellt(self):
        self.melde_neu_an(self.browser, "vergessen@beispiel.de")
        konto = self.anwendung.konto("vergessen@beispiel.de")
        konto["angelegt"] = server.in_tagen(-server.UNBESTAETIGT_TAGE - 1)
        self.assertEqual(self.anwendung.raeume_konten_auf(), 1)
        self.assertIsNone(self.anwendung.konto("vergessen@beispiel.de"))
        # Bestaetigte Konten bleiben unangetastet.
        self.registriere(self.browser, "bleibt@beispiel.de")
        self.anwendung.konto("bleibt@beispiel.de")["angelegt"] = server.in_tagen(-99)
        self.assertEqual(self.anwendung.raeume_konten_auf(), 0)
        self.assertIsNotNone(self.anwendung.konto("bleibt@beispiel.de"))

    # -- Kennwort vergessen -------------------------------------------------
    def test_kennwort_zuruecksetzen_ueber_die_mail(self):
        self.registriere(self.browser)
        abgemeldet = Browser(self.browser.wurzel)
        _, text, _ = abgemeldet.sende(
            "/kennwort-vergessen", {"kennung": "turnen@beispiel.de"}
        )
        self.assertIn("ist ein Code unterwegs", text)
        mail = self.anwendung.postausgang.letzte("turnen@beispiel.de")
        self.assertIn("Neues Kennwort", mail)
        code = postfach.code_aus_text(mail)

        _, _, adresse = abgemeldet.sende(
            "/kennwort-neu",
            {"kennung": "turnen@beispiel.de", "code": code,
             "kennwort": "neueshaus1", "kennwort2": "neueshaus1"},
        )
        self.assertTrue(adresse.endswith("/"))
        self.assertEqual(abgemeldet.hole("/freischalten")[0], 200)

        # Das alte Kennwort gilt nicht mehr, das neue schon.
        dritter = Browser(self.browser.wurzel)
        _, text, _ = dritter.sende(
            "/anmelden", {"kennung": "turnen@beispiel.de", "kennwort": "turnhalle1"}
        )
        self.assertIn("stimmt nicht", text)
        _, _, adresse = dritter.sende(
            "/anmelden", {"kennung": "turnen@beispiel.de", "kennwort": "neueshaus1"}
        )
        self.assertTrue(adresse.endswith("/"))

    def test_kennwortcode_gilt_nur_einmal(self):
        self.registriere(self.browser)
        self.browser.sende("/kennwort-vergessen", {"kennung": "turnen@beispiel.de"})
        code = self.code_aus_mail("turnen@beispiel.de")
        felder = {"kennung": "turnen@beispiel.de", "code": code,
                  "kennwort": "neueshaus1", "kennwort2": "neueshaus1"}
        self.browser.sende("/kennwort-neu", dict(felder))
        _, text, _ = self.browser.sende("/kennwort-neu", dict(felder))
        self.assertIn("stimmt nicht", text)

    def test_unbekannte_adresse_verraet_nichts(self):
        vorher = len(list((Path(self.ordner.name) / "postfach").glob("*.txt"))) \
            if (Path(self.ordner.name) / "postfach").exists() else 0
        _, text, _ = self.browser.sende(
            "/kennwort-vergessen", {"kennung": "niemand@beispiel.de"}
        )
        self.assertIn("Wenn es zu dieser E-Mail ein Konto gibt", text)
        nachher = len(list((Path(self.ordner.name) / "postfach").glob("*.txt")))
        self.assertEqual(nachher, vorher, "es wurde doch eine Mail verschickt")

    # -- Abo ----------------------------------------------------------------
    def test_neues_konto_ist_dauerhaft_kostenlos(self):
        self.registriere(self.browser)
        abo = self.anwendung.konto("turnen@beispiel.de")["abo"]
        self.assertEqual(abo["art"], "frei")
        self.assertEqual(abo["bis"], "", "der freie Zugang hat kein Ablaufdatum")
        _, text, _ = self.browser.hole("/konto")
        self.assertIn("dauerhaft", text)
        self.assertEqual(self.browser.hole("/freischalten")[0], 200)

    def test_freier_zugang_laeuft_nie_ab(self):
        """Auch nach Jahren kommt ein kostenloses Konto noch hinein."""
        self.registriere(self.browser)
        konto = self.anwendung.konto("turnen@beispiel.de")
        konto["angelegt"] = server.in_tagen(-2000)
        konto["abo"]["seit"] = server.in_tagen(-2000)
        self.anwendung.sichere_konten()
        self.assertEqual(self.browser.hole("/freischalten")[0], 200)
        self.assertFalse(self.anwendung.abo_laeuft(konto))
        self.assertFalse(self.anwendung.abo_gelaufen(konto))

    def test_abo_laeuft_ab_und_der_freie_zugang_bleibt(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.browser.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        konto = self.anwendung.konto("helfer@beispiel.de")

        self.browser.sende(
            "/verwaltung", {"tat": "abo_monat", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertEqual(konto["abo"]["bis"], server.in_tagen(31))
        self.assertEqual(konto["abo"]["art"], "Monatsabo")

        # Zeit vorspulen: das Abo ist um.
        konto["abo"]["bis"] = server.in_tagen(-1)
        self.assertFalse(self.anwendung.abo_laeuft(konto))
        self.assertTrue(self.anwendung.abo_gelaufen(konto))
        # Der Zugang bleibt trotzdem offen.
        self.assertEqual(nutzer.hole("/freischalten")[0], 200)
        _, text, _ = nutzer.hole("/konto")
        self.assertIn("wieder", text)
        self.assertIn("kostenlos", text)

    def test_verwalter_waehlt_die_laufzeit(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.browser.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        konto = self.anwendung.konto("helfer@beispiel.de")

        _, text, _ = self.browser.sende(
            "/verwaltung", {"tat": "abo_jahr", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertIn("Jahresabo", text)
        self.assertEqual(konto["abo"]["bis"], server.in_tagen(365))
        # Verlaengern haengt hinten an, nicht ab heute.
        self.browser.sende(
            "/verwaltung", {"tat": "abo_monat", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertEqual(konto["abo"]["bis"], server.in_tagen(31, server.in_tagen(365)))

    def test_abo_beenden_laesst_das_konto_kostenlos_weiterplanen(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.browser.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        self.browser.sende(
            "/verwaltung", {"tat": "abo_jahr", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.browser.sende(
            "/verwaltung", {"tat": "offline_geben", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        konto = self.anwendung.konto("helfer@beispiel.de")
        self.assertTrue(konto["offline"])

        _, text, _ = self.browser.sende(
            "/verwaltung", {"tat": "abo_stop", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertIn("kostenlos weiter", text)
        self.assertEqual(konto["abo"]["art"], "frei")
        self.assertEqual(konto["abo"]["bis"], "")
        self.assertIsNone(konto["offline"], "ohne Abo kein Offline-Schluessel")
        self.assertEqual(nutzer.hole("/freischalten")[0], 200)

    def test_offline_gibt_es_nur_mit_abo(self):
        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.browser.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        _, text, _ = self.browser.sende(
            "/verwaltung", {"tat": "offline_geben", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        self.assertIn("kein laufendes Abo", text)
        self.assertIsNone(self.anwendung.konto("helfer@beispiel.de")["offline"])

    # -- Offline-Schluessel je Konto ---------------------------------------
    def test_schluessel_passt_nur_auf_sein_konto(self):
        from werkzeuge.packen import entschluessele, oeffne_huelle

        self.registriere(self.browser, "chef@beispiel.de")
        nutzer = Browser(self.browser.wurzel)
        self.registriere(nutzer, "helfer@beispiel.de")
        for tat in ("abo_jahr", "offline_geben"):
            self.browser.sende(
                "/verwaltung", {"tat": tat, "konto": "helfer@beispiel.de"},
                marke_von="/verwaltung",
            )
        konto = self.anwendung.konto("helfer@beispiel.de")
        schluessel = konto["offline"]

        # Persoenliche Datei: genau eine Huelle, mit dem Ablaufdatum des Abos.
        seite = self.anwendung.persoenliche_seite(konto).decode("utf-8")
        huellen = json.loads(re.search(r"var HUELLEN = (\[.*?\]);", seite).group(1))
        self.assertEqual(len(huellen), 1)
        self.assertEqual(huellen[0]["bis"], konto["abo"]["bis"])

        block = re.search(r'var BLOCK = "([A-Za-z0-9+/=]+)"', seite).group(1)
        richtig = oeffne_huelle(huellen[0]["h"], "helfer@beispiel.de", schluessel)
        self.assertIsNotNone(entschluessele(block, richtig))

        # Mit einem anderen Konto oeffnet derselbe Schluessel nichts.
        falsch = oeffne_huelle(huellen[0]["h"], "chef@beispiel.de", schluessel)
        self.assertIsNone(entschluessele(block, falsch))

    def test_allgemeine_datei_traegt_keine_huelle(self):
        inhalt = (WURZEL / "web" / "kinderturnen.html").read_text(encoding="utf-8")
        self.assertIn("var HUELLEN = [];", inhalt)

    def test_kennwort_aendern(self):
        self.registriere(self.browser)
        _, text, _ = self.browser.sende(
            "/konto", {"alt": "falsch123", "neu": "neueshaus1", "neu2": "neueshaus1"},
            marke_von="/konto",
        )
        self.assertIn("bisherige Kennwort stimmt nicht", text)
        _, text, _ = self.browser.sende(
            "/konto", {"alt": "turnhalle1", "neu": "neueshaus1", "neu2": "neueshaus1"},
            marke_von="/konto",
        )
        self.assertIn("Kennwort ist geaendert", text)

        self.browser.sende("/abmelden", {}, marke_von="/konto")
        _, _, adresse = self.browser.sende(
            "/anmelden", {"kennung": "turnen@beispiel.de", "kennwort": "neueshaus1"}
        )
        self.assertTrue(adresse.endswith("/"))

    def test_anmeldung_wechselt_die_sitzungsmarke(self):
        """Gegen untergeschobene Sitzungen: nach dem Anmelden gilt eine neue."""
        self.registriere(self.browser)
        self.browser.sende("/abmelden", {}, marke_von="/konto")
        self.browser.hole("/anmelden")
        vorher = [k.value for k in self.browser.kekse if k.name == server.COOKIE][0]
        self.browser.sende(
            "/anmelden", {"kennung": "turnen@beispiel.de", "kennwort": "turnhalle1"}
        )
        nachher = [k.value for k in self.browser.kekse if k.name == server.COOKIE][0]
        self.assertNotEqual(vorher, nachher)

    def test_protokoll_haelt_die_zugriffe_fest(self):
        self.registriere(self.browser)
        self.browser.hole("/freischalten")
        text = (Path(self.ordner.name) / "zugriff.log").read_text(encoding="utf-8")
        self.assertIn("registrierung", text)
        self.assertIn("freischalten", text)
        self.assertIn("turnen@beispiel.de", text)

    def test_cookie_ist_httponly(self):
        self.registriere(self.browser)
        status, _, _ = self.browser.hole("/konto")
        self.assertEqual(status, 200)
        # HttpOnly steht in der Kopfzeile; der CookieJar merkt es sich als Zusatz.
        keks = [k for k in self.browser.kekse if k.name == server.COOKIE][0]
        self.assertTrue(keks.has_nonstandard_attr("HttpOnly"))


from tests.test_web import CHROMIUM, PLAYWRIGHT_DA, SEITE  # noqa: E402

if PLAYWRIGHT_DA:  # pragma: no cover - haengt von der Installation ab
    from playwright.sync_api import sync_playwright


@unittest.skipUnless(PLAYWRIGHT_DA and CHROMIUM and SEITE.exists(),
                     "Playwright, Chromium oder die gebaute Seite fehlt")
class EndeZuEndeTest(ServerTest):
    """Vom leeren Browser bis zur geplanten Stunde - ueber den Server."""

    def setUp(self) -> None:
        super().setUp()
        self._pw = sync_playwright().start()
        self.chrom = self._pw.chromium.launch(executable_path=CHROMIUM)

    def tearDown(self) -> None:
        self.chrom.close()
        self._pw.stop()
        super().tearDown()

    def test_registrieren_und_planen(self):
        seite = self.chrom.new_page(viewport={"width": 1100, "height": 800})
        fehler = []
        seite.on("pageerror", lambda e: fehler.append(str(e)))
        seite.goto(self.browser.wurzel + "/")
        self.assertTrue(seite.url.endswith("/anmelden"))

        seite.click("text=Hier registrieren")
        seite.fill("#name", "Uebungsleiterin")
        seite.fill("#kennung", "leitung@beispiel.de")
        seite.fill("#kennwort", "turnhalle1")
        seite.fill("#kennwort2", "turnhalle1")
        seite.click("#knopf-registrieren")

        # Erst der Code aus der Mail, dann das Programm.
        seite.wait_for_selector("#knopf-bestaetigen", timeout=15000)
        self.assertIn("Konto bestaetigen", seite.content())
        seite.fill("#code", self.code_aus_mail("leitung@beispiel.de"))
        seite.click("#knopf-bestaetigen")

        # Der Server gibt den Schluessel heraus, die Seite entschluesselt sich.
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=30000)
        stationen = seite.evaluate(
            "() => document.querySelectorAll('#stationsliste li').length"
        )
        self.assertGreaterEqual(stationen, 3)
        self.assertEqual(fehler, [])

        # Abmelden: danach kommt wieder die Anmeldung statt des Programms.
        seite.goto(self.browser.wurzel + "/konto")
        seite.click("#knopf-abmelden")
        seite.goto(self.browser.wurzel + "/")
        self.assertTrue(seite.url.endswith("/anmelden"))
        self.assertFalse(seite.evaluate("() => !!document.getElementById('plan')"))
        seite.close()

    def test_persoenliche_datei_laeuft_offline(self):
        """Herunterladen, oeffnen, E-Mail und Schluessel eingeben - fertig."""
        self.registriere(self.browser, "chef@beispiel.de")
        konto = self.anwendung.konto("chef@beispiel.de")
        for tat in ("abo_jahr", "offline_geben"):
            self.browser.sende(
                "/verwaltung", {"tat": tat, "konto": "chef@beispiel.de"},
                marke_von="/verwaltung",
            )
        schluessel = konto["offline"]
        datei = Path(self.ordner.name) / "meine.html"
        datei.write_bytes(self.anwendung.persoenliche_seite(konto))

        seite = self.chrom.new_page()
        seite.goto(datei.resolve().as_uri())
        seite.wait_for_selector("#lizenzfeld", timeout=15000)
        seite.fill("#kontofeld", "chef@beispiel.de")
        seite.fill("#lizenzfeld", schluessel)
        seite.click("#lizenzknopf")
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=30000)
        seite.close()

    def test_gesperrtes_konto_kommt_nicht_mehr_hinein(self):
        self.registriere(self.browser, "chef@beispiel.de")  # erster = Verwalter
        seite = self.chrom.new_page()
        seite.goto(self.browser.wurzel + "/registrieren")
        seite.fill("#name", "Helfer")
        seite.fill("#kennung", "helfer@beispiel.de")
        seite.fill("#kennwort", "turnhalle1")
        seite.fill("#kennwort2", "turnhalle1")
        seite.click("#knopf-registrieren")
        seite.wait_for_selector("#knopf-bestaetigen", timeout=15000)
        seite.fill("#code", self.code_aus_mail("helfer@beispiel.de"))
        seite.click("#knopf-bestaetigen")
        seite.wait_for_function("() => !!document.getElementById('plan')", timeout=30000)

        self.browser.sende(
            "/verwaltung", {"tat": "sperren", "konto": "helfer@beispiel.de"},
            marke_von="/verwaltung",
        )
        seite.goto(self.browser.wurzel + "/")
        self.assertTrue(seite.url.endswith("/anmelden"))
        seite.close()


if __name__ == "__main__":
    unittest.main()
