"""Packt die Browser-Fassung so, dass der Quelltext nicht offen dasteht.

Zwei Schritte:

1. ``ohne_kommentare()`` nimmt dem JavaScript alle Kommentare und die
   Einrueckung. Zeichenketten, Vorlagen (Backticks) und regulaere Ausdruecke
   bleiben dabei unangetastet.
2. ``verpacke()`` legt Aufbau, Gestaltung, Daten und Programm in einen
   einzigen Block, wuerfelt ihn Byte fuer Byte mit einem Schluesselstrom
   durcheinander und schreibt ihn als Base64 in die Seite. ``lader()``
   liefert das kurze Stueck JavaScript, das den Block zur Laufzeit wieder
   zusammensetzt und ausfuehrt.

Damit zeigt "Seitenquelltext anzeigen" im Browser nichts Lesbares mehr:
weder Markup noch Stil, Katalog oder Programm. Ein entschlossener Leser
kann den Block mit dem sichtbaren Lader trotzdem zurueckrechnen - eine
Seite, die im Browser laeuft, muss ihren Code dort auch entpacken koennen.
Wirklich geheim bleibt nur, was auf einem Server liegt.
"""

from __future__ import annotations

import base64
import hashlib
import re

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


def _schluessel(daten: bytes) -> int:
    """Aus dem Inhalt abgeleitet - gleicher Inhalt, gleicher Schluessel."""
    return int.from_bytes(hashlib.sha256(daten).digest()[:4], "big") | 1


def _strom(daten: bytes, schluessel: int) -> bytes:
    zustand = schluessel & 0xFFFFFFFF
    heraus = bytearray(len(daten))
    for i, byte in enumerate(daten):
        zustand = (zustand * 1664525 + 1013904223) & 0xFFFFFFFF
        heraus[i] = byte ^ ((zustand >> 24) & 0xFF)
    return bytes(heraus)


def verpacke(nutzlast: str) -> tuple:
    """(Base64-Block, Schluessel) fuer den Lader."""
    roh = nutzlast.encode("utf-8")
    schluessel = _schluessel(roh)
    return base64.b64encode(_strom(roh, schluessel)).decode("ascii"), schluessel


def entpacke(block: str, schluessel: int) -> str:
    """Gegenprobe zu :func:`verpacke` - fuer die Tests."""
    return _strom(base64.b64decode(block), schluessel).decode("utf-8")


def lader(block: str, schluessel: int) -> str:
    """Das sichtbare Stueck JavaScript: entpackt und startet die Anwendung."""
    return (
        "(function(){"
        f'var q="{block}",b=atob(q),n=b.length,u=new Uint8Array(n),s={schluessel}>>>0;'
        "for(var i=0;i<n;i++){s=(s*1664525+1013904223)>>>0;u[i]=b.charCodeAt(i)^(s>>>24);}"
        "new Function(new TextDecoder().decode(u))();"
        "})();"
    )
