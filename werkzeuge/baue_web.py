#!/usr/bin/env python3
"""Baut die Browser-Fassung ``web/kinderturnen.html``.

Die Datei ist danach vollstaendig eigenstaendig: Katalog, Oberflaeche und
PDF-Erzeugung stecken darin. Sie laesst sich per Doppelklick oeffnen - auf dem
Rechner wie auf dem Handy, ohne Installation.

Aufbau, Gestaltung, Daten und Programm liegen in einem gepackten Block
(siehe ``werkzeuge/packen.py``); im Seitenquelltext steht nur der kurze
Lader. Die lesbaren Quellen bleiben hier im Projekt und werden nicht
veroeffentlicht.

Aufruf:  python3 werkzeuge/baue_web.py [--oeffnen | --pruefen]

``--oeffnen`` zeigt die gebaute Datei gleich im Browser, ``--pruefen`` baut nur
im Speicher und meldet, ob die abgelegte Datei aktuell ist (fuer die Tests).
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from sportstunden.katalog import Katalog  # noqa: E402
from sportstunden.pdf import _HELVETICA, _HELVETICA_BOLD  # noqa: E402
from sportstunden.platzierung import GERAETEMASSE, ORTSFESTE_GERAETE  # noqa: E402
from werkzeuge import lizenzen  # noqa: E402
from werkzeuge.packen import (  # noqa: E402
    lader,
    ohne_css_kommentare,
    ohne_html_kommentare,
    ohne_kommentare,
    verschluessele,
)

QUELLE = WURZEL / "web" / "quelle"
ZIEL = WURZEL / "web" / "kinderturnen.html"


def sammle_daten() -> dict:
    """Alle Stammdaten in der Form, die die Browser-Fassung braucht."""
    katalog = Katalog.laden()
    geraete_datei = json.loads(
        (WURZEL / "sportstunden" / "data" / "geraete.json").read_text(encoding="utf-8")
    )
    orte = [o.to_dict() for o in Katalog.beispiel_orte()]

    return {
        "geraete": [
            {
                "id": g.id,
                "name": g.name,
                "kurz": g.kurzname,
                "kategorie": g.kategorie,
            }
            for g in katalog.geraete.values()
        ],
        "sicherheitsregeln": katalog.sicherheitsregeln,
        "sicherheitshinweise": geraete_datei.get("sicherheitsregeln_hinweis", {}),
        "altersgruppen": [g.to_dict() for g in katalog.altersgruppen],
        "koordination_ab_alter": katalog.koordination_ab_alter,
        "uebungen": [u.to_dict() for u in katalog.uebungen],
        "orte": orte,
        "geraetemasse": {k: list(v) for k, v in GERAETEMASSE.items()},
        "ortsfeste_geraete": list(ORTSFESTE_GERAETE),
        "schriftbreiten": {"normal": _HELVETICA, "fett": _HELVETICA_BOLD},
    }


def nutzlast() -> str:
    """Das komplette Programm als ein Stueck JavaScript.

    Es baut zuerst Gestaltung und Aufbau der Seite, legt dann die Daten ab
    und startet zuletzt die Anwendung.
    """
    stil = ohne_css_kommentare((QUELLE / "stil.css").read_text(encoding="utf-8"))
    inhalt = ohne_html_kommentare((QUELLE / "inhalt.html").read_text(encoding="utf-8"))
    anwendung = ohne_kommentare((QUELLE / "app.js").read_text(encoding="utf-8"))
    daten = json.dumps(sammle_daten(), ensure_ascii=False, separators=(",", ":"))

    return "\n".join(
        [
            '"use strict";',
            "var _s=document.createElement('style');",
            "_s.textContent=" + json.dumps(stil) + ";",
            "document.head.appendChild(_s);",
            "document.body.innerHTML=" + json.dumps(inhalt) + ";",
            "const DATEN=" + daten + ";",
            anwendung,
        ]
    )


def baue(server: str = None) -> str:
    """Die fertige Seite: verschluesselter Block plus sichtbarer Lader."""
    daten = lizenzen.lade()
    if not daten.get("vorrat"):
        lizenzen.fuelle(daten, lizenzen.VORGABE_VORRAT)
        lizenzen.sichere(daten)
    if server is not None and server != daten.get("server"):
        daten["server"] = server
        lizenzen.sichere(daten)

    block = verschluessele(nutzlast(), bytes.fromhex(daten["blockschluessel"]))
    huellen = [
        {"k": eintrag["kennung"], "h": eintrag["huelle"]}
        for eintrag in daten["vorrat"]
        if not eintrag.get("gesperrt")
    ]

    vorlage = (QUELLE / "vorlage.html").read_text(encoding="utf-8")
    quelle = (QUELLE / "lader.js").read_text(encoding="utf-8")
    return vorlage.replace(
        "__LADER__", lader(quelle, block, huellen, daten.get("server", ""))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pruefen",
        action="store_true",
        help="nur pruefen, ob die abgelegte Datei aktuell ist",
    )
    parser.add_argument(
        "--oeffnen",
        action="store_true",
        help="die gebaute Datei anschliessend im Browser oeffnen",
    )
    parser.add_argument(
        "--server",
        metavar="ADRESSE",
        help='Adresse der Freischaltung (Vorgabe "/freischalten", "" = keine)',
    )
    args = parser.parse_args()

    seite = baue(args.server)
    if args.pruefen:
        if not ZIEL.exists():
            print(f"{ZIEL} fehlt - bitte 'python3 werkzeuge/baue_web.py' ausfuehren.")
            return 1
        if ZIEL.read_text(encoding="utf-8") != seite:
            print(
                f"{ZIEL} ist nicht aktuell - bitte "
                "'python3 werkzeuge/baue_web.py' ausfuehren."
            )
            return 1
        print(f"{ZIEL.name} ist aktuell ({len(seite) // 1024} KB).")
        return 0

    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(seite, encoding="utf-8")
    print(f"{ZIEL} geschrieben ({len(seite) // 1024} KB, eine Datei, keine Abhaengigkeiten).")
    if args.oeffnen:
        webbrowser.open(ZIEL.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
