"""Tests der Mailtexte und des Versands (``werkzeuge/post.py``)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from werkzeuge import post  # noqa: E402

ADRESSE = "https://kitu.mein-verein.de"


class MailtextTest(unittest.TestCase):
    """Beide Texte muessen ohne Nachfragen verstaendlich sein."""

    def test_bestaetigung_hat_alles_wichtige(self):
        betreff, text = post.text_bestaetigung("Anna Uebungsleiterin", "482913", ADRESSE)
        self.assertIn("Bestaetigungscode", betreff)
        self.assertIn("Ki-Tu-Stundenplaner", betreff)
        self.assertIn("Hallo Anna Uebungsleiterin,", text)
        self.assertIn("482 913", text)  # gruppiert, gut abzulesen
        self.assertIn(f"{post.CODE_MINUTEN} Minuten", text)
        self.assertIn(ADRESSE + "/bestaetigen", text)
        self.assertIn("nicht registriert", text)  # was tun, wenn fremd angefordert
        self.assertTrue(text.rstrip().endswith("Kinderturnen"))

    def test_kennwort_hat_alles_wichtige(self):
        betreff, text = post.text_kennwort("Bernhard", "100200", ADRESSE)
        self.assertIn("Neues Kennwort", betreff)
        self.assertIn("Hallo Bernhard,", text)
        self.assertIn("100 200", text)
        self.assertIn("nur einmal verwenden", text)
        self.assertIn(ADRESSE + "/kennwort-neu", text)
        self.assertIn("bisheriges Kennwort bleibt", text)

    def test_die_beiden_texte_sind_nicht_zu_verwechseln(self):
        betreff1, text1 = post.text_bestaetigung("A", "111222", ADRESSE)
        betreff2, text2 = post.text_kennwort("A", "111222", ADRESSE)
        self.assertNotEqual(betreff1, betreff2)
        self.assertNotEqual(text1, text2)

    def test_ohne_namen_und_ohne_adresse_bleibt_es_lesbar(self):
        for bauer in (post.text_bestaetigung, post.text_kennwort):
            _, text = bauer("", "123456", "")
            self.assertIn("Hallo,", text)
            self.assertIn("123 456", text)
            self.assertNotIn("None", text)
            self.assertNotIn("{", text)  # keine offenen Platzhalter
            self.assertNotIn("  \n", text)  # keine Leerstellen-Reste

    def test_code_laesst_sich_wieder_herauslesen(self):
        for code in ("000123", "482913"):
            _, text = post.text_bestaetigung("A", code, ADRESSE)
            self.assertEqual(post.code_aus_text(text), code)
        self.assertEqual(post.code_aus_text("ohne Code"), "")


class VersandTest(unittest.TestCase):
    """Dateipost - der Weg ohne Mailserver."""

    def test_mail_landet_lesbar_im_postfach(self):
        with tempfile.TemporaryDirectory() as ordner:
            ausgang = post.Dateipost(Path(ordner))
            betreff, text = post.text_bestaetigung("Anna", "482913", ADRESSE)
            ausgang.sende("anna@beispiel.de", betreff, text)

            dateien = list(Path(ordner).glob("*.txt"))
            self.assertEqual(len(dateien), 1)
            self.assertIn("anna_beispiel.de", dateien[0].name)
            inhalt = dateien[0].read_text(encoding="utf-8")
            self.assertIn("An: anna@beispiel.de", inhalt)
            self.assertIn("Von: ", inhalt)
            self.assertIn(f"Betreff: {betreff}", inhalt)
            self.assertIn("482 913", inhalt)

    def test_letzte_findet_die_richtige_mail(self):
        with tempfile.TemporaryDirectory() as ordner:
            ausgang = post.Dateipost(Path(ordner))
            ausgang.sende("eine@beispiel.de", "Erste", "Text A")
            ausgang.sende("andere@beispiel.de", "Zweite", "Text B")
            self.assertIn("Text A", ausgang.letzte("eine@beispiel.de"))
            self.assertIn("Text B", ausgang.letzte("andere@beispiel.de"))
            self.assertIn("Text B", ausgang.letzte())
            self.assertEqual(ausgang.letzte("niemand@beispiel.de"), "")


if __name__ == "__main__":
    unittest.main()
