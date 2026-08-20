"""Packt und verschluesselt die Browser-Fassung.

Drei Schritte:

1. ``ohne_kommentare()`` nimmt dem JavaScript alle Kommentare und die
   Einrueckung. Zeichenketten, Vorlagen (Backticks) und regulaere Ausdruecke
   bleiben dabei unangetastet.
2. ``verschluessele()`` legt Aufbau, Gestaltung, Daten und Programm in einen
   einzigen Block und verschluesselt ihn mit einem 32-Byte-Schluessel
   (Schluesselstrom aus SHA-256 im Zaehlerbetrieb). Der Block steht als
   Base64 in der Seite.
3. ``huelle()`` verpackt diesen Schluessel je Lizenz noch einmal: aus dem
   Lizenzschluessel wird ueber 20000 SHA-256-Runden ein Ableitungsschluessel,
   der den Blockschluessel verdeckt. Ohne passenden Lizenzschluessel - oder
   ohne einen Server, der den Blockschluessel herausgibt - laesst sich der
   Block nicht entschluesseln und die Seite startet nicht.

"Seitenquelltext anzeigen" zeigt damit nichts Lesbares: weder Markup noch
Stil, Katalog oder Programm. Anders als eine blosse Verschleierung haelt das
auch einem entschlossenen Leser stand, solange er keinen Schluessel hat. Wer
einen Schluessel besitzt, kommt an den Klartext heran - was der Browser
ausfuehrt, muss der Browser entpacken koennen.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets

# Schluesselwoerter, nach denen ein "/" einen regulaeren Ausdruck einleitet
# und keine Division ist.
_SCHLUESSELWOERTER = {
    "await",
    "case",
    "delete",
    "do",
    "else",
    "in",
    "instanceof",
    "new",
    "of",
    "return",
    "throw",
    "typeof",
    "void",
    "yield",
}

_WORTZEICHEN = "_$"


def _ist_wortzeichen(zeichen: str) -> bool:
    return zeichen.isalnum() or zeichen in _WORTZEICHEN


def _regulaerer_ausdruck_folgt(aus: list) -> bool:
    """Steht an dieser Stelle ein regulaerer Ausdruck oder eine Division?"""
    i = len(aus) - 1
    while i >= 0 and aus[i] in " \t\n":
        i -= 1
    if i < 0:
        return True
    zeichen = aus[i]
    if zeichen in ")]":
        return False
    if _ist_wortzeichen(zeichen):
        j = i
        while j >= 0 and _ist_wortzeichen(aus[j]):
            j -= 1
        return "".join(aus[j + 1 : i + 1]) in _SCHLUESSELWOERTER
    return True


def ohne_kommentare(js: str) -> str:
    """JavaScript ohne Kommentare, Einrueckung und Leerzeilen."""
    aus: list = []
    i, n = 0, len(js)
    # Stapel der offenen Vorlagen-Zeichenketten; je Eintrag die Klammertiefe,
    # bei der die Vorlage weitergeht.
    vorlagen: list = []
    tiefe = 0
    in_vorlage = False

    def schreib(zeichen: str) -> None:
        aus.append(zeichen)

    while i < n:
        zeichen = js[i]

        if in_vorlage:
            if zeichen == "\\" and i + 1 < n:
                schreib(zeichen)
                schreib(js[i + 1])
                i += 2
                continue
            if zeichen == "`":
                in_vorlage = False
                vorlagen.pop()
                schreib(zeichen)
                i += 1
                continue
            if zeichen == "$" and i + 1 < n and js[i + 1] == "{":
                in_vorlage = False
                tiefe = 0
                schreib("$")
                schreib("{")
                i += 2
                continue
            schreib(zeichen)
            i += 1
            continue

        # --- Programmtext ---
        if zeichen == "/" and i + 1 < n and js[i + 1] == "/":
            while i < n and js[i] != "\n":
                i += 1
            continue
        if zeichen == "/" and i + 1 < n and js[i + 1] == "*":
            ende = js.find("*/", i + 2)
            i = n if ende < 0 else ende + 2
            continue
        if zeichen in "\"'":
            schreib(zeichen)
            i += 1
            while i < n:
                if js[i] == "\\" and i + 1 < n:
                    schreib(js[i])
                    schreib(js[i + 1])
                    i += 2
                    continue
                schreib(js[i])
                if js[i] == zeichen:
                    i += 1
                    break
                i += 1
            continue
        if zeichen == "`":
            vorlagen.append(tiefe)
            in_vorlage = True
            schreib(zeichen)
            i += 1
            continue
        if zeichen == "/" and _regulaerer_ausdruck_folgt(aus):
            schreib(zeichen)
            i += 1
            in_klasse = False
            while i < n:
                if js[i] == "\\" and i + 1 < n:
                    schreib(js[i])
                    schreib(js[i + 1])
                    i += 2
                    continue
                if js[i] == "[":
                    in_klasse = True
                elif js[i] == "]":
                    in_klasse = False
                schreib(js[i])
                if js[i] == "/" and not in_klasse:
                    i += 1
                    break
                i += 1
            while i < n and js[i].isalpha():  # Kennzeichen wie g, i, u
                schreib(js[i])
                i += 1
            continue
        if zeichen == "{":
            tiefe += 1
        elif zeichen == "}":
            if tiefe == 0 and vorlagen:
                tiefe = vorlagen[-1]
                in_vorlage = True
                schreib(zeichen)
                i += 1
                continue
            tiefe = max(0, tiefe - 1)
        if zeichen == "\n":
            while aus and aus[-1] in " \t":
                aus.pop()
            if aus and aus[-1] != "\n":
                schreib("\n")
            i += 1
            while i < n and js[i] in " \t":
                i += 1
            continue
        schreib(zeichen)
        i += 1

    while aus and aus[-1] in " \t\n":
        aus.pop()
    return "".join(aus)


def ohne_css_kommentare(css: str) -> str:
    """CSS ohne ``/* ... */`` und ohne Leerzeilen."""
    ohne = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    zeilen = [zeile.rstrip() for zeile in ohne.splitlines()]
    return "\n".join(zeile for zeile in zeilen if zeile.strip())


def ohne_html_kommentare(html: str) -> str:
    """Markup ohne ``<!-- ... -->`` und ohne Leerzeilen."""
    ohne = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    zeilen = [zeile.rstrip() for zeile in ohne.splitlines()]
    return "\n".join(zeile for zeile in zeilen if zeile.strip())


MARKE = "/*KITU1*/\n"  # steht am Anfang des Klartexts - so ist ein
# falscher Schluessel sofort zu erkennen.
_RUNDEN = 20000  # Ableitung des Lizenzschluessels: absichtlich zaehfluessig


def normiere(lizenz: str) -> str:
    """Lizenzschluessel ohne Bindestriche, Leerzeichen und Kleinschreibung."""
    return "".join(z for z in (lizenz or "").upper() if z.isalnum())


def kennung(lizenz: str) -> str:
    """Kurzes, oeffentliches Merkmal einer Lizenz (verraet sie nicht)."""
    roh = ("kitu1-kennung:" + normiere(lizenz)).encode("utf-8")
    return hashlib.sha256(roh).hexdigest()[:8]


def lizenzschluessel(lizenz: str) -> bytes:
    """Ableitungsschluessel aus dem Lizenzschluessel - 20000 Runden SHA-256."""
    h = hashlib.sha256(("kitu1:" + normiere(lizenz)).encode("utf-8")).digest()
    marke = b"kitu1"
    for _ in range(_RUNDEN):
        h = hashlib.sha256(h + marke).digest()
    return h


def neuer_lizenzschluessel(zufall=None) -> str:
    """Neuer Lizenzschluessel in der Form KITU-XXXX-XXXX-XXXX-XXXX."""
    zeichen = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # ohne I, O, 0, 1
    quelle = zufall or secrets.choice
    bloecke = ["".join(quelle(zeichen) for _ in range(4)) for _ in range(4)]
    return "KITU-" + "-".join(bloecke)


def neuer_blockschluessel() -> str:
    """Neuer Schluessel fuer den Block, als Hex."""
    return secrets.token_hex(32)


def huelle(blockschluessel: bytes, lizenz: str) -> str:
    """Blockschluessel, verdeckt mit dem Ableitungsschluessel der Lizenz."""
    ableitung = lizenzschluessel(lizenz)
    return bytes(a ^ b for a, b in zip(blockschluessel, ableitung)).hex()


def _strom(laenge: int, schluessel: bytes) -> bytes:
    """Schluesselstrom: SHA-256(Schluessel || Zaehler), aneinandergehaengt."""
    heraus = bytearray()
    block = 0
    while len(heraus) < laenge:
        heraus += hashlib.sha256(schluessel + block.to_bytes(4, "big")).digest()
        block += 1
    return bytes(heraus[:laenge])


def verschluessele(nutzlast: str, schluessel: bytes) -> str:
    """Klartext -> Base64-Block."""
    roh = (MARKE + nutzlast).encode("utf-8")
    strom = _strom(len(roh), schluessel)
    return base64.b64encode(bytes(a ^ b for a, b in zip(roh, strom))).decode("ascii")


def entschluessele(block: str, schluessel: bytes):
    """Base64-Block -> Klartext, oder None bei falschem Schluessel."""
    roh = base64.b64decode(block)
    strom = _strom(len(roh), schluessel)
    try:
        text = bytes(a ^ b for a, b in zip(roh, strom)).decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text[len(MARKE):] if text.startswith(MARKE) else None


def lader(quelle: str, block: str, huellen: list, server: str) -> str:
    """Der sichtbare Lader: Vorlage aus web/quelle/lader.js mit Werten."""
    fertig = ohne_kommentare(quelle)
    fertig = fertig.replace("__BLOCK__", block)
    fertig = fertig.replace("__HUELLEN__", json.dumps(huellen, separators=(",", ":")))
    fertig = fertig.replace("__SERVER__", server)
    return fertig
