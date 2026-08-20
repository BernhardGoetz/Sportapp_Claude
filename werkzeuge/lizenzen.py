#!/usr/bin/env python3
"""Verwaltet den Blockschluessel und den Vorrat an Offline-Schluesseln.

Die Browser-Fassung ist verschluesselt. Wer angemeldet ist, bekommt den
Schluessel vom Server; wer offline arbeiten will, braucht einen
**Offline-Schluessel**. Alle moeglichen Offline-Schluessel werden hier einmal
auf Vorrat erzeugt und beim Bauen in die Seite eingebaut - der Server vergibt
danach aus diesem Vorrat, ohne dass neu gebaut werden muss.

Aufruf::

    python3 werkzeuge/lizenzen.py --vorrat 50       # Vorrat auffuellen
    python3 werkzeuge/lizenzen.py --liste           # Ueberblick
    python3 werkzeuge/lizenzen.py --sperren KITU-…  # erst nach Neubau wirksam
    python3 werkzeuge/lizenzen.py --entsperren KITU-…

``web/lizenzen.json`` enthaelt die Schluessel im Klartext und darf nicht
weitergegeben werden. Weitergegeben wird allein ``web/kinderturnen.html``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from werkzeuge.packen import (  # noqa: E402
    huelle,
    kennung,
    neuer_blockschluessel,
    neuer_lizenzschluessel,
    normiere,
)

DATEI = WURZEL / "web" / "lizenzen.json"
KONTEN = WURZEL / "server" / "konten.json"
VORGABE_VORRAT = 50


def lade(datei: Path = DATEI) -> dict:
    """Lizenzdatei lesen - fehlt sie, entsteht eine frische im Speicher."""
    if datei.exists():
        return json.loads(datei.read_text(encoding="utf-8"))
    return {"blockschluessel": neuer_blockschluessel(), "server": "/freischalten", "vorrat": []}


def sichere(daten: dict, datei: Path = DATEI) -> None:
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(
        json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def fuelle(daten: dict, anzahl: int) -> int:
    """Vorrat auf ``anzahl`` Schluessel bringen. Gibt die Zahl der neuen zurueck."""
    block = bytes.fromhex(daten["blockschluessel"])
    vorrat = daten.setdefault("vorrat", [])
    neu = 0
    while len(vorrat) < anzahl:
        schluessel = neuer_lizenzschluessel()
        if any(e["schluessel"] == schluessel for e in vorrat):
            continue
        vorrat.append(
            {
                "schluessel": schluessel,
                "kennung": kennung(schluessel),
                "huelle": huelle(block, schluessel),
                "gesperrt": False,
            }
        )
        neu += 1
    return neu


def eintrag(daten: dict, schluessel: str):
    """Vorratseintrag zu einem Schluessel - unabhaengig von Schreibweise."""
    gesucht = normiere(schluessel)
    for e in daten.get("vorrat", []):
        if normiere(e["schluessel"]) == gesucht:
            return e
    return None


def vergeben() -> dict:
    """Welcher Schluessel gehoert welchem Konto? (aus server/konten.json)"""
    if not KONTEN.exists():
        return {}
    konten = json.loads(KONTEN.read_text(encoding="utf-8")).get("konten", [])
    return {
        normiere(k["offline"]): k.get("kennung", "?")
        for k in konten
        if k.get("offline")
    }


def freie(daten: dict) -> list:
    """Schluessel, die weder gesperrt noch einem Konto zugeteilt sind."""
    belegt = vergeben()
    return [
        e
        for e in daten.get("vorrat", [])
        if not e.get("gesperrt") and normiere(e["schluessel"]) not in belegt
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vorrat", type=int, metavar="ANZAHL", help="Vorrat auffuellen")
    parser.add_argument("--liste", action="store_true", help="Ueberblick anzeigen")
    parser.add_argument("--sperren", metavar="SCHLUESSEL")
    parser.add_argument("--entsperren", metavar="SCHLUESSEL")
    args = parser.parse_args()

    daten = lade()
    geaendert = not DATEI.exists()

    if args.vorrat is not None:
        neu = fuelle(daten, args.vorrat)
        geaendert = geaendert or neu > 0
        print(f"{neu} Schluessel angelegt, Vorrat jetzt {len(daten['vorrat'])}.")

    for schluessel, wert in ((args.sperren, True), (args.entsperren, False)):
        if not schluessel:
            continue
        treffer = eintrag(daten, schluessel)
        if not treffer:
            print(f"{schluessel} steht nicht im Vorrat.")
            return 1
        treffer["gesperrt"] = wert
        geaendert = True
        zustand = "gesperrt" if wert else "wieder frei"
        print(f"{treffer['schluessel']} ist {zustand} - bitte neu bauen.")

    if geaendert:
        sichere(daten)

    if args.liste or not (args.vorrat or args.sperren or args.entsperren):
        belegt = vergeben()
        vorrat = daten.get("vorrat", [])
        print(f"Vorrat: {len(vorrat)} Schluessel, davon {len(freie(daten))} frei.")
        print(f"Server: {daten.get('server') or '(keiner)'}")
        for e in vorrat:
            konto = belegt.get(normiere(e["schluessel"]))
            zustand = "gesperrt" if e.get("gesperrt") else (konto or "frei")
            print(f"  {e['schluessel']}  {zustand}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
