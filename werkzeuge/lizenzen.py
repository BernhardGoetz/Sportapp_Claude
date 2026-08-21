#!/usr/bin/env python3
"""Verwaltet den Blockschluessel der Browser-Fassung.

Die ausgelieferte Datei ist mit einem einzigen **Blockschluessel**
verschluesselt. Ihn gibt der Server an angemeldete Konten heraus; fuer den
Offline-Betrieb verdeckt ihn eine **Huelle**, die aus Kontokennung *und*
Offline-Schluessel abgeleitet wird - jede Huelle passt damit auf genau ein
Konto. Die Huellen erzeugt der Server bei der Freigabe, sie stecken in der
persoenlichen Kopie der Datei; hier steht nur der Blockschluessel selbst.

Aufruf::

    python3 werkzeuge/lizenzen.py                 # Zustand anzeigen
    python3 werkzeuge/lizenzen.py --server freischalten.php
    python3 werkzeuge/lizenzen.py --neuer-blockschluessel   # macht alles alte ungueltig

``web/lizenzen.json`` enthaelt den Blockschluessel im Klartext und darf nicht
weitergegeben werden. Weitergegeben wird allein ``web/kinderturnen.html``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from werkzeuge.packen import neuer_blockschluessel  # noqa: E402

DATEI = WURZEL / "web" / "lizenzen.json"
VORGABE_SERVER = "freischalten.php"


def lade(datei: Path = DATEI) -> dict:
    """Lizenzdatei lesen - fehlt sie, entsteht eine frische im Speicher."""
    if datei.exists():
        daten = json.loads(datei.read_text(encoding="utf-8"))
        daten.setdefault("blockschluessel", neuer_blockschluessel())
        daten.setdefault("server", VORGABE_SERVER)
        return daten
    return {"blockschluessel": neuer_blockschluessel(), "server": VORGABE_SERVER}


def sichere(daten: dict, datei: Path = DATEI) -> None:
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(
        json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", metavar="ADRESSE",
                        help='Adresse der Freischaltung (z. B. "freischalten.php", "" = keine)')
    parser.add_argument("--neuer-blockschluessel", action="store_true",
                        help="neuen Blockschluessel wuerfeln - alle Offline-Schluessel "
                             "und die ausgelieferte Datei werden dadurch ungueltig")
    args = parser.parse_args()

    daten = lade()
    geaendert = not DATEI.exists()

    if args.neuer_blockschluessel:
        daten["blockschluessel"] = neuer_blockschluessel()
        geaendert = True
        print("Neuer Blockschluessel. Jetzt neu bauen; alle bisher vergebenen "
              "Offline-Schluessel muessen neu freigegeben werden.")
    if args.server is not None:
        daten["server"] = args.server
        geaendert = True
        print(f"Serveradresse: {args.server or '(keine)'}")

    if geaendert:
        sichere(daten)

    print(f"Blockschluessel: {daten['blockschluessel'][:8]}... ({DATEI})")
    print(f"Server:          {daten.get('server') or '(keiner)'}")
    print("Offline-Schluessel vergibt der Verwalter unter /verwaltung.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
