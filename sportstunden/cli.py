"""Kommandozeile des Kinderturnen-Stundenplaners."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import __version__, ansicht
from .export import dateiname_fuer, stunden_pdf
from .katalog import Katalog
from .models import (
    ORTSARTEN,
    Altersgruppe,
    Ort,
    PHASEN_TITEL,
    Stunde,
    StundenUebung,
    Stundenteil,
    neue_id,
)
from .planer import Planer, Planungsauftrag, Planungsergebnis, Planungsfehler, pruefe_bestand
from .speicher import Speicher
from .stil import Stillernen


# ---------------------------------------------------------------------------
# Eingabehilfen
# ---------------------------------------------------------------------------


def interaktiv_moeglich() -> bool:
    """Nur an einem echten Terminal darf nach Eingaben gefragt werden."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def frage(text: str, standard: str = "") -> str:
    hinweis = f" [{standard}]" if standard else ""
    try:
        eingabe = input(f"{text}{hinweis}: ").strip()
    except EOFError:
        return standard
    return eingabe or standard


def frage_optional(text: str, standard: str = "") -> str:
    """Fragt nur nach, wenn ein Terminal vorhanden ist."""
    if not interaktiv_moeglich():
        return standard
    return frage(text, standard)


def frage_zahl(text: str, standard: int, minimum: int = 1, maximum: int = 999) -> int:
    while True:
        roh = frage(text, str(standard))
        try:
            wert = int(roh)
        except ValueError:
            print("  Bitte eine Zahl eingeben.")
            continue
        if minimum <= wert <= maximum:
            return wert
        print(f"  Bitte einen Wert zwischen {minimum} und {maximum} eingeben.")


def frage_ja(text: str, standard: bool = True) -> bool:
    vorgabe = "J/n" if standard else "j/N"
    antwort = frage(f"{text} ({vorgabe})", "").lower()
    if not antwort:
        return standard
    return antwort.startswith("j") or antwort.startswith("y")


def waehle(titel: str, eintraege: Sequence[str], standard: int = 1) -> int:
    """Nummerierte Auswahl - gibt den Index (0-basiert) zurueck."""
    print(f"\n{titel}")
    for nummer, eintrag in enumerate(eintraege, start=1):
        print(f"  [{nummer}] {eintrag}")
    while True:
        roh = frage("Auswahl", str(standard))
        try:
            nummer = int(roh)
        except ValueError:
            print("  Bitte eine Nummer eingeben.")
            continue
        if 1 <= nummer <= len(eintraege):
            return nummer - 1
        print("  Nummer nicht in der Liste.")


def geraete_aus_text(text: str) -> Dict[str, int]:
    """'matte=8, kasten_gross=2' -> {'matte': 8, 'kasten_gross': 2}"""
    ergebnis: Dict[str, int] = {}
    for teil in text.replace(";", ",").split(","):
        teil = teil.strip()
        if not teil:
            continue
        if "=" in teil:
            schluessel, wert = teil.split("=", 1)
            try:
                ergebnis[schluessel.strip()] = int(wert)
            except ValueError:
                raise ValueError(f"Ungueltige Anzahl bei '{teil}'")
        else:
            ergebnis[teil] = 0
    return ergebnis


# ---------------------------------------------------------------------------
# Kontext
# ---------------------------------------------------------------------------


class Anwendung:
    def __init__(self, speicher: Speicher) -> None:
        self.speicher = speicher
        self.katalog = Katalog.laden()
        einstellungen = speicher.einstellungen()
        self.katalog.koordination_ab_alter = int(
            einstellungen.get("koordination_ab_alter", self.katalog.koordination_ab_alter)
        )

    def lernen(self) -> Stillernen:
        return Stillernen(self.katalog, self.speicher.stunden())

    def planer_fuer(self, altersgruppe: Altersgruppe) -> Planer:
        return Planer(self.katalog, self.lernen().profil(altersgruppe))

    # -- Aufloesen ---------------------------------------------------------
    def finde_ort(self, kennung: str) -> Optional[Ort]:
        orte = self.speicher.orte()
        for ort in orte:
            if ort.id == kennung:
                return ort
        treffer = [o for o in orte if kennung.lower() in o.name.lower()]
        return treffer[0] if len(treffer) == 1 else None

    def finde_altersgruppe(
        self, kennung: str = "", alter: Optional[int] = None
    ) -> Optional[Altersgruppe]:
        if alter is not None:
            return self.katalog.altersgruppe_fuer_alter(alter)
        if not kennung:
            return None
        gruppe = self.katalog.altersgruppe(kennung)
        if gruppe:
            return gruppe
        treffer = [
            g for g in self.katalog.altersgruppen if kennung.lower() in g.name.lower()
        ]
        return treffer[0] if len(treffer) == 1 else None

    def finde_stunde(self, kennung: str) -> Optional[Stunde]:
        stunde = self.speicher.stunde(kennung)
        if stunde:
            return stunde
        treffer = [
            s for s in self.speicher.stunden() if s.id.endswith(kennung)
        ]
        return treffer[0] if len(treffer) == 1 else None


# ---------------------------------------------------------------------------
# Befehle: Stammdaten
# ---------------------------------------------------------------------------


def befehl_init(app: Anwendung, args) -> int:
    anzahl = app.speicher.initialisiere_beispieldaten(ueberschreiben=args.ueberschreiben)
    if anzahl:
        print(f"{anzahl} Beispielorte angelegt in {app.speicher.verzeichnis}")
    else:
        print(
            f"Es sind bereits Orte gespeichert ({app.speicher.verzeichnis}). "
            "Mit --ueberschreiben zuruecksetzen."
        )
    return 0


def befehl_geraete(app: Anwendung, args) -> int:
    suche = (args.suche or "").lower()
    print(ansicht.titelzeile("Geraetekatalog"))
    for geraet in sorted(
        app.katalog.geraete.values(), key=lambda g: (g.kategorie, g.name)
    ):
        if suche and suche not in geraet.name.lower() and suche not in geraet.id:
            continue
        regel = app.katalog.sicherheitsregeln.get(geraet.id)
        zusatz = ""
        if regel:
            zusatz = "  Pflicht-Absicherung: " + ", ".join(
                f"{anzahl}x {app.katalog.geraet_name(g)}" for g, anzahl in regel.items()
            )
        print(f"  {geraet.id:<22} {geraet.name:<32} [{geraet.kategorie}]{zusatz}")
    return 0


def befehl_altersgruppen(app: Anwendung, args) -> int:
    print(ansicht.titelzeile("Altersgruppen"))
    for gruppe in app.katalog.altersgruppen:
        koordination = (
            "mit Koordinationsteil"
            if app.katalog.braucht_koordinationsteil(gruppe)
            else "ohne Koordinationsteil"
        )
        print(f"  {gruppe.id:<12} {gruppe.name:<42} {koordination}")
        if gruppe.koordination_schwerpunkte:
            print(
                "               Schwerpunkte: "
                + ", ".join(gruppe.koordination_schwerpunkte)
            )
        if gruppe.hinweis:
            print(f"               {gruppe.hinweis}")
    print(
        f"\nKoordinationsteil ab {app.katalog.koordination_ab_alter} Jahren "
        "(aenderbar: sportstunden einstellungen --setzen koordination_ab_alter=10)"
    )
    return 0


def befehl_orte(app: Anwendung, args) -> int:
    print(ansicht.orte_liste(app.speicher.orte(), app.katalog))
    return 0


def befehl_ort_zeigen(app: Anwendung, args) -> int:
    ort = app.finde_ort(args.ort)
    if not ort:
        print(f"Ort '{args.ort}' nicht gefunden.")
        return 1
    print(ansicht.ausstattung_liste(ort, app.katalog))
    return 0


def befehl_ort_neu(app: Anwendung, args) -> int:
    name = args.name or frage_optional("Name des Ortes")
    if not name:
        print("Abgebrochen - kein Name angegeben.")
        return 1
    art = args.art
    if not art and interaktiv_moeglich():
        arten = list(ORTSARTEN)
        index = waehle(
            "Welche Art von Sportstaette?", [ORTSARTEN[a] for a in arten]
        )
        art = arten[index]
    if not art:
        print("Bitte die Art der Sportstaette angeben (--art halle|freien|sportplatz).")
        return 1
    kennung = args.id or neue_id("ort")
    ort = Ort(
        id=kennung,
        name=name,
        art=art,
        flaeche=args.flaeche or frage_optional("Flaeche / Groesse (optional)"),
        notiz=args.notiz or frage_optional("Notiz (optional)"),
    )
    if args.geraete:
        ort.ausstattung = {
            k: v for k, v in geraete_aus_text(args.geraete).items() if v > 0
        }
    app.speicher.speichere_ort(ort)
    print(f"Ort '{ort.name}' gespeichert (ID: {ort.id}).")
    if not ort.ausstattung and interaktiv_moeglich():
        if frage_ja("Ausstattung jetzt erfassen?", True):
            return ausstattung_bearbeiten(app, ort)
    return 0


def ausstattung_bearbeiten(app: Anwendung, ort: Ort) -> int:
    if not interaktiv_moeglich():
        print(
            "Ausstattung ohne Terminal bitte per Flag pflegen: "
            "sportstunden ort-bearbeiten <ort> --geraete 'matte=12,langbank=4'"
        )
        return 1
    print(
        "\nAusstattung erfassen. Eingabe: 'geraet_id anzahl' (z. B. 'matte 12'), "
        "'liste' fuer alle Geraete-IDs, 'fertig' zum Beenden."
    )
    while True:
        eingabe = frage("Geraet", "fertig")
        if eingabe.lower() in ("fertig", "ende", "q"):
            break
        if eingabe.lower() == "liste":
            for geraet in sorted(app.katalog.geraete.values(), key=lambda g: g.id):
                print(f"  {geraet.id:<22} {geraet.name}")
            continue
        teile = eingabe.split()
        geraet_id = teile[0]
        if geraet_id not in app.katalog.geraete:
            print("  Unbekannte Geraete-ID (mit 'liste' anzeigen).")
            continue
        if len(teile) > 1:
            try:
                anzahl = int(teile[1])
            except ValueError:
                print("  Anzahl muss eine Zahl sein.")
                continue
        else:
            anzahl = frage_zahl(f"  Anzahl {app.katalog.geraet_name(geraet_id)}", 1, 0, 999)
        ort.setze_bestand(geraet_id, anzahl)
        app.speicher.speichere_ort(ort)
        print(f"  {app.katalog.geraet_name(geraet_id)}: {anzahl}")
    print(ansicht.ausstattung_liste(ort, app.katalog))
    return 0


def befehl_ort_bearbeiten(app: Anwendung, args) -> int:
    ort = app.finde_ort(args.ort)
    if not ort:
        print(f"Ort '{args.ort}' nicht gefunden.")
        return 1
    if args.geraete:
        for geraet_id, anzahl in geraete_aus_text(args.geraete).items():
            if geraet_id not in app.katalog.geraete:
                print(f"Unbekannte Geraete-ID: {geraet_id}")
                return 1
            ort.setze_bestand(geraet_id, anzahl)
        app.speicher.speichere_ort(ort)
        print(ansicht.ausstattung_liste(ort, app.katalog))
        return 0
    return ausstattung_bearbeiten(app, ort)


def befehl_ort_loeschen(app: Anwendung, args) -> int:
    if app.speicher.loesche_ort(args.ort):
        print(f"Ort '{args.ort}' geloescht.")
        return 0
    print(f"Ort '{args.ort}' nicht gefunden.")
    return 1


# ---------------------------------------------------------------------------
# Befehle: Planung
# ---------------------------------------------------------------------------


def _ausstattung_auswaehlen(app: Anwendung, ort: Ort) -> Dict[str, int]:
    """Vor dem Planen wird die heute verfuegbare Ausstattung bestaetigt."""
    print(ansicht.ausstattung_liste(ort, app.katalog))
    index = waehle(
        "Welche Ausstattung steht heute zur Verfuegung?",
        [
            "Alles wie gespeichert",
            "Einzelne Geraete ausschliessen",
            "Anzahlen anpassen",
            "Nur bestimmte Geraete verwenden",
        ],
    )
    ausstattung = dict(ort.ausstattung)
    if index == 0:
        return ausstattung
    if index == 1:
        roh = frage("Geraete-IDs (Komma-getrennt), die heute fehlen")
        for geraet_id in geraete_aus_text(roh):
            ausstattung.pop(geraet_id, None)
    elif index == 2:
        roh = frage("Anpassungen als id=anzahl (Komma-getrennt)")
        for geraet_id, anzahl in geraete_aus_text(roh).items():
            if anzahl > 0:
                ausstattung[geraet_id] = anzahl
            else:
                ausstattung.pop(geraet_id, None)
    else:
        roh = frage("Nur diese Geraete verwenden (id oder id=anzahl)")
        gewaehlt = geraete_aus_text(roh)
        ausstattung = {
            geraet_id: (anzahl if anzahl > 0 else ort.bestand(geraet_id))
            for geraet_id, anzahl in gewaehlt.items()
        }
        ausstattung = {k: v for k, v in ausstattung.items() if v > 0}
    print(
        "\nVerwendete Ausstattung: "
        + (
            ", ".join(
                f"{anzahl}x {app.katalog.geraet_name(g)}"
                for g, anzahl in sorted(ausstattung.items())
            )
            or "keine"
        )
    )
    return ausstattung


def _pdf_schreiben(
    app: Anwendung,
    stunde: Stunde,
    ziel: Optional[str],
    bestand: Dict[str, int],
    nur_stundenbild: bool = False,
) -> Path:
    einstellungen = app.speicher.einstellungen()
    if ziel:
        pfad = Path(ziel)
        if pfad.is_dir():
            pfad = pfad / dateiname_fuer(stunde)
    else:
        pfad = app.speicher.pdf_pfad(dateiname_fuer(stunde))
    return stunden_pdf(
        stunde,
        app.katalog,
        pfad,
        bestand=bestand,
        trainer=einstellungen.get("trainer", ""),
        verein=einstellungen.get("verein", ""),
        titel=einstellungen.get("kopftitel", "Ki Tu"),
        nur_stundenbild=nur_stundenbild,
    )


def _nachbearbeitung(app: Anwendung, ergebnis: Planungsergebnis, auftrag: Planungsauftrag) -> int:
    """Interaktives Menue nach der Planung."""
    while True:
        print(
            "\n[s] speichern   [p] PDF   [a] Aufbauplan   [n] neu planen   "
            "[e] als eigene Stunde uebernehmen   [q] Ende"
        )
        wahl = frage("Aktion", "q").lower()
        if wahl == "s":
            app.speicher.speichere_stunde(ergebnis.stunde)
            print(f"Gespeichert unter ID {ergebnis.stunde.id}.")
        elif wahl == "p":
            ziel = frage("Zieldatei (leer = Standardordner)")
            pfad = _pdf_schreiben(app, ergebnis.stunde, ziel or None, ergebnis.bestand)
            print(f"PDF geschrieben: {pfad}")
        elif wahl == "a":
            print(ansicht.aufbau_text(ergebnis.stunde, app.katalog))
        elif wahl == "n":
            auftrag.seed = None
            planer = app.planer_fuer(auftrag.altersgruppe)
            ergebnis = planer.plane(auftrag)
            print(ansicht.stunde_text(ergebnis.stunde, app.katalog, ergebnis))
        elif wahl == "e":
            ergebnis.stunde.quelle = "eigene"
            app.speicher.speichere_stunde(ergebnis.stunde)
            print(
                "Als eigene Stunde gespeichert - sie fliesst ab sofort in den "
                "gelernten Stil ein."
            )
        elif wahl in ("q", "ende", ""):
            return 0
        else:
            print("Unbekannte Auswahl.")


def befehl_planen(app: Anwendung, args) -> int:
    orte = app.speicher.orte()
    if not orte:
        print("Keine Orte gespeichert. Bitte zuerst 'sportstunden init' ausfuehren.")
        return 1

    interaktiv = args.interaktiv or (not args.ort and not args.art)
    if interaktiv and not interaktiv_moeglich() and not args.ort:
        print(
            "Kein Ort angegeben. Im nicht-interaktiven Betrieb bitte --ort verwenden."
        )
        return 1

    ort: Optional[Ort] = None
    ausstattung: Optional[Dict[str, int]] = None

    if args.ort:
        ort = app.finde_ort(args.ort)
        if not ort:
            print(f"Ort '{args.ort}' nicht gefunden.")
            return 1
    else:
        arten = [a for a in ORTSARTEN if any(o.art == a for o in orte)]
        if args.art:
            art = args.art
        else:
            index = waehle(
                "Wo findet das Training statt?", [ORTSARTEN[a] for a in arten]
            )
            art = arten[index]
        passende = [o for o in orte if o.art == art]
        if not passende:
            print(f"Keine Orte der Art '{art}' gespeichert.")
            return 1
        if len(passende) == 1:
            ort = passende[0]
            print(f"Ort: {ort.name}")
        else:
            index = waehle(
                "Welcher Ort?",
                [f"{o.name} ({len(o.ausstattung)} Geraetearten)" for o in passende],
            )
            ort = passende[index]

    if args.geraete:
        ausstattung = {
            k: v for k, v in geraete_aus_text(args.geraete).items() if v > 0
        }
    elif args.ohne:
        ausstattung = dict(ort.ausstattung)
        for geraet_id in geraete_aus_text(args.ohne):
            ausstattung.pop(geraet_id, None)
    elif interaktiv and interaktiv_moeglich():
        ausstattung = _ausstattung_auswaehlen(app, ort)
    else:
        ausstattung = dict(ort.ausstattung)

    if not ausstattung:
        print("Ohne Ausstattung kann keine Stunde geplant werden.")
        return 1

    gruppe = app.finde_altersgruppe(args.altersgruppe or "", args.alter)
    if not gruppe and not interaktiv_moeglich():
        print("Bitte eine Altersgruppe angeben (--altersgruppe oder --alter).")
        return 1
    if not gruppe:
        index = waehle(
            "Fuer welche Gruppe?",
            [g.name for g in app.katalog.altersgruppen],
            standard=3,
        )
        gruppe = app.katalog.altersgruppen[index]

    einstellungen = app.speicher.einstellungen()
    dauer = args.dauer or int(einstellungen.get("standard_dauer", 60))
    teilnehmer = args.teilnehmer or int(einstellungen.get("standard_teilnehmer", 12))
    if interaktiv and interaktiv_moeglich():
        dauer = frage_zahl("Dauer in Minuten", dauer, 20, 240)
        teilnehmer = frage_zahl("Anzahl Kinder", teilnehmer, 1, 60)
        schwerpunkt = args.schwerpunkt or frage("Schwerpunkt (optional, z. B. turnen)")
    else:
        schwerpunkt = args.schwerpunkt or ""

    koordination: Optional[bool] = None
    if args.mit_koordination:
        koordination = True
    elif args.ohne_koordination:
        koordination = False

    stationsbetrieb: Optional[bool] = None
    if args.stationen:
        stationsbetrieb = True
    elif args.spiel:
        stationsbetrieb = False

    thema = args.thema or ""
    if interaktiv and interaktiv_moeglich() and not thema:
        themen = app.katalog.themen()
        auswahl = waehle(
            "Motto der Stunde?",
            ["ohne Motto"] + [t.capitalize() for t in themen] + ["Zufall"],
        )
        if auswahl == 0:
            thema = ""
        elif auswahl <= len(themen):
            thema = themen[auswahl - 1]
        else:
            thema = "auto"
    if thema == "auto":
        import random as _random

        thema = _random.Random(args.seed).choice(app.katalog.themen())
        print(f"Motto der Stunde: {thema.capitalize()}")

    auftrag = Planungsauftrag(
        ort=ort,
        altersgruppe=gruppe,
        dauer=dauer,
        teilnehmer=teilnehmer,
        schwerpunkt=schwerpunkt,
        titel=args.titel or "",
        datum=args.datum or date.today().isoformat(),
        ausstattung=ausstattung,
        umbau_zwischen_teilen=not args.gemeinsames_material,
        koordinationsteil=koordination,
        thema=thema,
        stationsbetrieb=stationsbetrieb,
        seed=args.seed,
    )

    planer = app.planer_fuer(gruppe)
    try:
        ergebnis = planer.plane(auftrag)
    except Planungsfehler as fehler:
        print(f"Planung nicht moeglich: {fehler}")
        return 2

    if args.json:
        print(json.dumps(ergebnis.stunde.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(ansicht.stunde_text(ergebnis.stunde, app.katalog, ergebnis))
        if args.aufbau:
            print(ansicht.aufbau_text(ergebnis.stunde, app.katalog))

    if args.speichern or args.eigene:
        if args.eigene:
            ergebnis.stunde.quelle = "eigene"
        app.speicher.speichere_stunde(ergebnis.stunde)
        print(f"\nStunde gespeichert (ID: {ergebnis.stunde.id}).")

    if args.pdf is not None:
        pfad = _pdf_schreiben(
            app,
            ergebnis.stunde,
            args.pdf or None,
            ergebnis.bestand,
            nur_stundenbild=args.nur_stundenbild,
        )
        print(f"PDF geschrieben: {pfad}")

    if interaktiv and interaktiv_moeglich() and not args.json:
        return _nachbearbeitung(app, ergebnis, auftrag)
    return 0


# ---------------------------------------------------------------------------
# Befehle: Stunden verwalten
# ---------------------------------------------------------------------------


def befehl_stunden(app: Anwendung, args) -> int:
    stunden = app.speicher.stunden()
    if args.nur_eigene:
        stunden = [s for s in stunden if s.ist_eigene]
    print(ansicht.stunden_liste(stunden))
    return 0


def befehl_zeigen(app: Anwendung, args) -> int:
    stunde = app.finde_stunde(args.stunde)
    if not stunde:
        print(f"Stunde '{args.stunde}' nicht gefunden.")
        return 1
    if args.json:
        print(json.dumps(stunde.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(ansicht.stunde_text(stunde, app.katalog))
    if args.aufbau:
        print(ansicht.aufbau_text(stunde, app.katalog))
    ort = app.speicher.ort(stunde.ort_id)
    if ort:
        verstoesse = pruefe_bestand(stunde, ort.ausstattung)
        if verstoesse:
            print("\nACHTUNG - Bestand des Ortes reicht nicht:")
            for verstoss in verstoesse:
                print(f"  ! {verstoss}")
    return 0


def befehl_pdf(app: Anwendung, args) -> int:
    stunde = app.finde_stunde(args.stunde)
    if not stunde:
        print(f"Stunde '{args.stunde}' nicht gefunden.")
        return 1
    ort = app.speicher.ort(stunde.ort_id)
    bestand = dict(ort.ausstattung) if ort else {}
    pfad = _pdf_schreiben(
        app, stunde, args.datei, bestand, nur_stundenbild=args.nur_stundenbild
    )
    print(f"PDF geschrieben: {pfad}")
    return 0


def befehl_markieren(app: Anwendung, args) -> int:
    stunde = app.finde_stunde(args.stunde)
    if not stunde:
        print(f"Stunde '{args.stunde}' nicht gefunden.")
        return 1
    stunde.quelle = "geplant" if args.geplant else "eigene"
    app.speicher.speichere_stunde(stunde)
    print(f"Stunde {stunde.id} ist jetzt als '{stunde.quelle}' markiert.")
    return 0


def befehl_loeschen(app: Anwendung, args) -> int:
    if app.speicher.loesche_stunde(args.stunde):
        print(f"Stunde '{args.stunde}' geloescht.")
        return 0
    print(f"Stunde '{args.stunde}' nicht gefunden.")
    return 1


def befehl_importieren(app: Anwendung, args) -> int:
    pfad = Path(args.datei)
    if not pfad.exists():
        print(f"Datei '{pfad}' nicht gefunden.")
        return 1
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    roh_stunden = daten.get("stunden", [daten]) if isinstance(daten, dict) else daten
    quelle = "geplant" if args.geplant else "eigene"
    anzahl = 0
    for roh in roh_stunden:
        stunde = Stunde.from_dict(roh)
        stunde.quelle = quelle
        if not stunde.altersgruppe_name:
            gruppe = app.katalog.altersgruppe(stunde.altersgruppe_id)
            if gruppe:
                stunde.altersgruppe_name = gruppe.name
        app.speicher.speichere_stunde(stunde)
        anzahl += 1
    print(f"{anzahl} Stunde(n) als '{quelle}' importiert.")
    if quelle == "eigene":
        print("Der Stil wird beim naechsten Planen automatisch beruecksichtigt.")
    return 0


def befehl_exportieren(app: Anwendung, args) -> int:
    stunde = app.finde_stunde(args.stunde)
    if not stunde:
        print(f"Stunde '{args.stunde}' nicht gefunden.")
        return 1
    pfad = Path(args.datei)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(stunde.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Stunde nach {pfad} exportiert.")
    return 0


# ---------------------------------------------------------------------------
# Befehl: eigene Stunde erfassen
# ---------------------------------------------------------------------------


def befehl_erfassen(app: Anwendung, args) -> int:
    """Eine selbst geplante Stunde erfassen - Grundlage fuer das Stil-Lernen."""
    if not interaktiv_moeglich():
        print(
            "'erfassen' braucht ein Terminal. Alternativ eine Stunde als JSON "
            "importieren: sportstunden importieren <datei.json>"
        )
        return 1
    orte = app.speicher.orte()
    if not orte:
        print("Bitte zuerst Orte anlegen ('sportstunden init').")
        return 1
    index = waehle("Ort der Stunde", [f"{o.name} ({ORTSARTEN[o.art]})" for o in orte])
    ort = orte[index]
    index = waehle(
        "Gruppe", [g.name for g in app.katalog.altersgruppen], standard=3
    )
    gruppe = app.katalog.altersgruppen[index]
    teilnehmer = frage_zahl("Anzahl Kinder", 12, 1, 60)
    titel = frage("Titel der Stunde", f"Eigene Stunde {gruppe.name.split(' (')[0]}")
    datum = frage("Datum", date.today().isoformat())

    teile: List[Stundenteil] = []
    phasen = ["aufwaermen", "koordination", "hauptteil", "abschluss"]
    for phase in phasen:
        if phase == "koordination" and not app.katalog.braucht_koordinationsteil(gruppe):
            if not frage_ja("Koordinationsteil aufnehmen?", False):
                continue
        print(f"\n=== {PHASEN_TITEL[phase]} ===")
        kandidaten = [
            u
            for u in app.katalog.uebungen
            if u.phase == phase
            and ort.art in u.orte
            and u.passt_zu_alter(gruppe.alter_min, gruppe.alter_max)
        ]
        for nummer, uebung in enumerate(kandidaten, start=1):
            print(f"  [{nummer:>2}] {uebung.name}  ({', '.join(uebung.tags[:3])})")
        print("  [f] freie Uebung selbst eingeben    [Enter] Teil beenden")

        uebungen: List[StundenUebung] = []
        while True:
            eingabe = frage("Uebung waehlen", "")
            if not eingabe:
                break
            if eingabe.lower() == "f":
                name = frage("Name der Uebung")
                if not name:
                    continue
                dauer = frage_zahl("Dauer in Minuten", 10, 1, 120)
                beschreibung = frage("Beschreibung")
                material = geraete_aus_text(frage("Material als id=anzahl (optional)"))
                uebungen.append(
                    StundenUebung(
                        uebung_id="",
                        name=name,
                        dauer=dauer,
                        beschreibung=beschreibung,
                        organisation=frage("Organisation", "ganze_gruppe"),
                        tags=[t.strip() for t in frage("Tags (Komma-getrennt)").split(",") if t.strip()],
                        intensitaet=frage_zahl("Intensitaet 1-5", 3, 1, 5),
                        geraete={k: v for k, v in material.items() if v > 0},
                    )
                )
                continue
            try:
                nummer = int(eingabe)
            except ValueError:
                print("  Bitte Nummer, 'f' oder Enter.")
                continue
            if not 1 <= nummer <= len(kandidaten):
                print("  Nummer nicht in der Liste.")
                continue
            uebung = kandidaten[nummer - 1]
            dauer = frage_zahl(
                f"Dauer fuer '{uebung.name}'", uebung.dauer_vorschlag(),
                1, 120,
            )
            geraete, absicherung, gruppen = app.katalog.bedarf(uebung, teilnehmer)
            uebungen.append(
                StundenUebung(
                    uebung_id=uebung.id,
                    name=uebung.name,
                    dauer=dauer,
                    beschreibung=uebung.beschreibung,
                    aufbau=uebung.aufbau,
                    hinweise=uebung.hinweise,
                    organisation=uebung.organisation,
                    gruppen=gruppen,
                    tags=list(uebung.tags),
                    koordination=list(uebung.koordination),
                    intensitaet=uebung.intensitaet,
                    geraete=geraete,
                    absicherung=absicherung,
                )
            )
            print(f"  + {uebung.name} ({dauer} min)")
        if uebungen:
            teile.append(
                Stundenteil(phase=phase, uebungen=uebungen, parallel=len(uebungen) > 1)
            )

    if not teile:
        print("Keine Uebungen erfasst - nichts gespeichert.")
        return 1

    stunde = Stunde(
        id=neue_id("stunde"),
        titel=titel,
        ort_id=ort.id,
        ort_name=ort.name,
        ortsart=ort.art,
        altersgruppe_id=gruppe.id,
        altersgruppe_name=gruppe.name,
        dauer=sum(t.dauer for t in teile),
        teilnehmer=teilnehmer,
        teile=teile,
        datum=datum,
        quelle="eigene",
    )
    verstoesse = pruefe_bestand(stunde, ort.ausstattung)
    if verstoesse:
        print("\nWarnung - der Bestand des Ortes reicht rechnerisch nicht:")
        for verstoss in verstoesse:
            print(f"  ! {verstoss}")
        if not frage_ja("Trotzdem speichern?", True):
            return 1
    app.speicher.speichere_stunde(stunde)
    print(f"\nEigene Stunde gespeichert (ID: {stunde.id}).")
    print(ansicht.stunde_text(stunde, app.katalog, ausfuehrlich=False))
    return 0


# ---------------------------------------------------------------------------
# Befehle: Stil und Einstellungen
# ---------------------------------------------------------------------------


def befehl_stil(app: Anwendung, args) -> int:
    lernen = app.lernen()
    stichproben = lernen.stichproben()
    if args.altersgruppe:
        gruppe = app.finde_altersgruppe(args.altersgruppe)
        if not gruppe:
            print(f"Altersgruppe '{args.altersgruppe}' nicht gefunden.")
            return 1
        print(
            ansicht.stil_text(
                lernen.profil(gruppe), app.katalog, f"Stil fuer {gruppe.name}"
            )
        )
        return 0

    print(ansicht.stil_text(lernen.gesamtprofil(), app.katalog, "Gesamtstil"))
    if not stichproben:
        print(
            "\nTipp: eigene Stunden mit 'sportstunden erfassen' oder "
            "'sportstunden markieren <id>' hinterlegen - danach plant das "
            "Programm in diesem Stil."
        )
        return 0
    for gruppe in app.katalog.altersgruppen:
        anzahl = stichproben.get(gruppe.id, 0)
        if not anzahl:
            continue
        print(
            ansicht.stil_text(
                lernen.profil(gruppe),
                app.katalog,
                f"Stil fuer {gruppe.name} ({anzahl} eigene Stunde(n))",
            )
        )
    return 0


def befehl_einstellungen(app: Anwendung, args) -> int:
    if args.setzen:
        for eintrag in args.setzen:
            if "=" not in eintrag:
                print(f"Bitte als schluessel=wert angeben: {eintrag}")
                return 1
            schluessel, wert = eintrag.split("=", 1)
            gewandelt: object = wert
            if wert.isdigit():
                gewandelt = int(wert)
            app.speicher.setze_einstellung(schluessel.strip(), gewandelt)
    einstellungen = app.speicher.einstellungen()
    print(ansicht.titelzeile("Einstellungen"))
    print(f"  Datenverzeichnis: {app.speicher.verzeichnis}")
    for schluessel, wert in sorted(einstellungen.items()):
        print(f"  {schluessel:<24} {wert}")
    return 0


# ---------------------------------------------------------------------------
# Argumente
# ---------------------------------------------------------------------------


def parser_bauen() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sportstunden",
        description=(
            "Automatische Planung von Kinderturnstunden (1-10 Jahre) - "
            "Freizeitsport, mit Stundenbild als PDF."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--daten",
        help="Datenverzeichnis (Standard: ~/.sportstunden oder $SPORTSTUNDEN_HOME)",
    )
    unter = parser.add_subparsers(dest="befehl")

    p = unter.add_parser("init", help="Beispielorte und Datenverzeichnis anlegen")
    p.add_argument("--ueberschreiben", action="store_true")
    p.set_defaults(funktion=befehl_init)

    p = unter.add_parser("geraete", help="Geraetekatalog anzeigen")
    p.add_argument("--suche", help="Nach Name oder ID filtern")
    p.set_defaults(funktion=befehl_geraete)

    p = unter.add_parser("altersgruppen", help="Altersgruppen und Koordinationsschwerpunkte")
    p.set_defaults(funktion=befehl_altersgruppen)

    p = unter.add_parser("orte", help="Gespeicherte Orte anzeigen")
    p.set_defaults(funktion=befehl_orte)

    p = unter.add_parser("ort", help="Ausstattung eines Ortes anzeigen")
    p.add_argument("ort")
    p.set_defaults(funktion=befehl_ort_zeigen)

    p = unter.add_parser("ort-neu", help="Neuen Ort anlegen")
    p.add_argument("--id")
    p.add_argument("--name")
    p.add_argument("--art", choices=sorted(ORTSARTEN))
    p.add_argument("--flaeche")
    p.add_argument("--notiz")
    p.add_argument("--geraete", help="Ausstattung als 'matte=12,langbank=4'")
    p.set_defaults(funktion=befehl_ort_neu)

    p = unter.add_parser("ort-bearbeiten", help="Ausstattung eines Ortes pflegen")
    p.add_argument("ort")
    p.add_argument("--geraete", help="Aenderungen als 'matte=12,minitrampolin=0'")
    p.set_defaults(funktion=befehl_ort_bearbeiten)

    p = unter.add_parser("ort-loeschen", help="Ort loeschen")
    p.add_argument("ort")
    p.set_defaults(funktion=befehl_ort_loeschen)

    p = unter.add_parser("planen", help="Kinderturnstunde planen")
    p.add_argument("--ort", help="Orts-ID oder Namensteil")
    p.add_argument("--art", choices=sorted(ORTSARTEN), help="Halle, Freien, Sportplatz")
    p.add_argument("--altersgruppe", help="ID der Altersgruppe, z. B. 'd'")
    p.add_argument("--alter", type=int, help="Alter der Kinder (waehlt die Gruppe)")
    p.add_argument("--dauer", type=int)
    p.add_argument("--teilnehmer", type=int, help="Anzahl Kinder")
    p.add_argument("--schwerpunkt", help="z. B. turnen, ballschule, klettern")
    p.add_argument("--titel")
    p.add_argument("--datum")
    p.add_argument("--geraete", help="Nur diese Ausstattung verwenden ('matte=8,...')")
    p.add_argument("--ohne", help="Diese Geraete heute ausschliessen")
    p.add_argument("--seed", type=int, help="Zufallsstartwert fuer reproduzierbare Plaene")
    p.add_argument("--thema", help="Motto der Stunde (z. B. sommer, dschungel, 'auto')")
    p.add_argument(
        "--stationen",
        action="store_true",
        help="Hauptteil als Bewegungslandschaft mit Stationen planen",
    )
    p.add_argument(
        "--spiel",
        action="store_true",
        help="Hauptteil als grosses Spiel statt Stationen planen",
    )
    p.add_argument(
        "--nur-stundenbild",
        action="store_true",
        dest="nur_stundenbild",
        help="PDF nur als einseitiges Stundenbild (ohne Detailseiten)",
    )
    p.add_argument("--mit-koordination", action="store_true", dest="mit_koordination")
    p.add_argument("--ohne-koordination", action="store_true", dest="ohne_koordination")
    p.add_argument(
        "--gemeinsames-material",
        action="store_true",
        dest="gemeinsames_material",
        help="Kein Umbau zwischen den Teilen - Material wird fuer die ganze Stunde reserviert",
    )
    p.add_argument("--speichern", action="store_true")
    p.add_argument("--eigene", action="store_true", help="Direkt als eigene Stunde speichern")
    p.add_argument("--pdf", nargs="?", const="", help="PDF schreiben (optional Pfad)")
    p.add_argument("--aufbau", action="store_true", help="Aufbauplan mit ausgeben")
    p.add_argument("--json", action="store_true")
    p.add_argument("--interaktiv", action="store_true")
    p.set_defaults(funktion=befehl_planen)

    p = unter.add_parser("stunden", help="Gespeicherte Stunden auflisten")
    p.add_argument("--nur-eigene", action="store_true", dest="nur_eigene")
    p.set_defaults(funktion=befehl_stunden)

    p = unter.add_parser("zeigen", help="Stunde anzeigen")
    p.add_argument("stunde")
    p.add_argument("--aufbau", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(funktion=befehl_zeigen)

    p = unter.add_parser("pdf", help="Stunde als PDF-Stundenbild speichern")
    p.add_argument("stunde")
    p.add_argument("--datei", help="Zieldatei oder Zielordner")
    p.add_argument(
        "--nur-stundenbild",
        action="store_true",
        dest="nur_stundenbild",
        help="Nur die erste Seite (Stundenbild) ausgeben",
    )
    p.set_defaults(funktion=befehl_pdf)

    p = unter.add_parser("erfassen", help="Eigene Stunde erfassen (Stil-Vorlage)")
    p.set_defaults(funktion=befehl_erfassen)

    p = unter.add_parser("markieren", help="Stunde als eigene Stunde markieren")
    p.add_argument("stunde")
    p.add_argument("--geplant", action="store_true", help="Markierung zuruecknehmen")
    p.set_defaults(funktion=befehl_markieren)

    p = unter.add_parser("loeschen", help="Stunde loeschen")
    p.add_argument("stunde")
    p.set_defaults(funktion=befehl_loeschen)

    p = unter.add_parser("importieren", help="Stunden aus JSON importieren")
    p.add_argument("datei")
    p.add_argument("--geplant", action="store_true", help="Nicht als eigene Stunde werten")
    p.set_defaults(funktion=befehl_importieren)

    p = unter.add_parser("exportieren", help="Stunde als JSON exportieren")
    p.add_argument("stunde")
    p.add_argument("datei")
    p.set_defaults(funktion=befehl_exportieren)

    p = unter.add_parser("stil", help="Gelernten Planungsstil anzeigen")
    p.add_argument("--altersgruppe")
    p.set_defaults(funktion=befehl_stil)

    p = unter.add_parser("einstellungen", help="Einstellungen anzeigen oder setzen")
    p.add_argument("--setzen", action="append", help="schluessel=wert")
    p.set_defaults(funktion=befehl_einstellungen)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = parser_bauen()
    args = parser.parse_args(argv)
    if not getattr(args, "funktion", None):
        parser.print_help()
        return 0
    speicher = Speicher(Path(args.daten) if args.daten else None)
    app = Anwendung(speicher)
    try:
        return args.funktion(app, args)
    except (ValueError, RuntimeError) as fehler:
        print(f"Fehler: {fehler}")
        return 2
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
