#!/usr/bin/env python3
"""Mailversand und die Texte dazu.

Zwei Faelle brauchen Post: die **Bestaetigung** einer neuen Registrierung und
das **Zuruecksetzen des Kennworts**. Beide laufen ueber einen sechsstelligen
Code, der eine halbe Stunde gilt.

Versandwege:

* ``Dateipost`` legt jede Mail als Textdatei in ``server/postfach/`` ab. Das
  ist die Vorgabe - so laesst sich alles ohne Mailserver ausprobieren und
  pruefen.
* ``SMTPPost`` verschickt ueber einen richtigen Mailserver (STARTTLS, Login).

Der Server waehlt ueber ``--smtp`` zwischen beiden.
"""

from __future__ import annotations

import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

ABSENDER = "Ki Tu - Stundenplaner <kitu@localhost>"
GRUSS = "Viele Gruesse\nKi Tu - Stundenplaner fuer das Kinderturnen"
CODE_MINUTEN = 30


def _anrede(name: str) -> str:
    return f"Hallo {name.strip()}," if name and name.strip() else "Hallo,"


def _gruppiert(code: str) -> str:
    """123456 -> '123 456' - so liest es sich vom Bildschirm ab."""
    return f"{code[:3]} {code[3:]}" if len(code) == 6 else code


def text_bestaetigung(name: str, code: str, adresse: str = "") -> tuple:
    """(Betreff, Text) fuer die Bestaetigung einer neuen Registrierung."""
    verweis = f"\n{adresse.rstrip('/')}/bestaetigen" if adresse else ""
    text = f"""{_anrede(name)}

schoen, dass du beim Ki-Tu-Stundenplaner dabei bist. Mit diesem Code
schaltest du dein Konto frei:

    {_gruppiert(code)}

Der Code gilt {CODE_MINUTEN} Minuten. Gib ihn auf der Seite ein, die nach der
Registrierung offen ist - oder hier:{verweis or " auf der Bestaetigungsseite."}

Danach kann es losgehen: Ort und Gruppe waehlen, planen, Stundenbild als PDF
speichern.

Hast du dich nicht registriert? Dann ist diese Mail hinfaellig - ohne den
Code passiert nichts, und das Konto verfaellt von selbst.

{GRUSS}
"""
    return "Dein Bestaetigungscode fuer den Ki-Tu-Stundenplaner", text


def text_kennwort(name: str, code: str, adresse: str = "") -> tuple:
    """(Betreff, Text) fuer ein vergessenes Kennwort."""
    verweis = f"\n{adresse.rstrip('/')}/kennwort-neu" if adresse else ""
    text = f"""{_anrede(name)}

du moechtest dein Kennwort fuer den Ki-Tu-Stundenplaner neu setzen. Dieser
Code macht den Weg frei:

    {_gruppiert(code)}

Der Code gilt {CODE_MINUTEN} Minuten und laesst sich nur einmal verwenden.
Gib ihn zusammen mit deinem neuen Kennwort hier ein:{verweis or " auf der Seite 'Kennwort neu'."}

Kam die Anfrage nicht von dir? Dann ignoriere diese Mail einfach - dein
bisheriges Kennwort bleibt unveraendert gueltig.

{GRUSS}
"""
    return "Neues Kennwort fuer den Ki-Tu-Stundenplaner", text


class Postausgang:
    """Gemeinsame Schnittstelle: eine Mail verschicken."""

    def sende(self, an: str, betreff: str, text: str) -> None:  # pragma: no cover
        raise NotImplementedError


class Dateipost(Postausgang):
    """Legt jede Mail als lesbare Textdatei ab - fuer Probelauf und Tests."""

    def __init__(self, ordner: Path, absender: str = ABSENDER) -> None:
        self.ordner = Path(ordner)
        self.ordner.mkdir(parents=True, exist_ok=True)
        self.absender = absender

    def sende(self, an: str, betreff: str, text: str) -> None:
        zeit = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        sauber = re.sub(r"[^a-z0-9._-]+", "_", an.lower())
        datei = self.ordner / f"{zeit}_{sauber}.txt"
        datei.write_text(
            f"An: {an}\nVon: {self.absender}\nBetreff: {betreff}\n\n{text}",
            encoding="utf-8",
        )

    def letzte(self, an: str = None) -> str:
        """Zuletzt abgelegte Mail (an diese Adresse) - fuer die Tests."""
        dateien = sorted(self.ordner.glob("*.txt"))
        if an:
            sauber = re.sub(r"[^a-z0-9._-]+", "_", an.lower())
            dateien = [d for d in dateien if d.name.endswith(f"_{sauber}.txt")]
        return dateien[-1].read_text(encoding="utf-8") if dateien else ""


class SMTPPost(Postausgang):
    """Versand ueber einen richtigen Mailserver."""

    def __init__(self, wirt: str, port: int = 587, nutzer: str = "",
                 kennwort: str = "", absender: str = ABSENDER, tls: bool = True) -> None:
        self.wirt = wirt
        self.port = port
        self.nutzer = nutzer
        self.kennwort = kennwort
        self.absender = absender
        self.tls = tls

    def sende(self, an: str, betreff: str, text: str) -> None:  # pragma: no cover
        nachricht = EmailMessage()
        nachricht["From"] = self.absender
        nachricht["To"] = an
        nachricht["Subject"] = betreff
        nachricht.set_content(text)
        with smtplib.SMTP(self.wirt, self.port, timeout=20) as verbindung:
            if self.tls:
                verbindung.starttls(context=ssl.create_default_context())
            if self.nutzer:
                verbindung.login(self.nutzer, self.kennwort)
            verbindung.send_message(nachricht)


def code_aus_text(text: str) -> str:
    """Der sechsstellige Code aus einer Mail - fuer Tests und Fehlersuche."""
    treffer = re.search(r"^\s{2,}(\d{3}) (\d{3})\s*$", text, re.MULTILINE)
    return treffer.group(1) + treffer.group(2) if treffer else ""
