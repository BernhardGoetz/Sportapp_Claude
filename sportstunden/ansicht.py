"""Textausgabe fuer das Terminal."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .katalog import Katalog
from .models import ORTSARTEN, Ort, Stunde
from .planer import Planungsergebnis, aufbauplan
from .stil import Stilprofil

BREITE = 78


def linie(zeichen: str = "-") -> str:
    return zeichen * BREITE


def titelzeile(text: str) -> str:
    return f"\n{text}\n{linie('=')}"


def _material(katalog: Katalog, bedarf: Dict[str, int]) -> str:
    if not bedarf:
        return "-"
    return ", ".join(
        f"{anzahl}x {katalog.geraet_name(geraet)}"
        for geraet, anzahl in sorted(
            bedarf.items(), key=lambda x: katalog.geraet_name(x[0])
        )
    )


def ort_zeile(ort: Ort, katalog: Katalog) -> str:
    geraete = len(ort.ausstattung)
    stueck = sum(ort.ausstattung.values())
    return (
        f"  {ort.id:<24} {ort.name:<32} {ORTSARTEN.get(ort.art, ort.art):<28}"
        f" {geraete} Geraetearten / {stueck} Stueck"
    )


def orte_liste(orte: Iterable[Ort], katalog: Katalog) -> str:
    orte = list(orte)
    if not orte:
        return "Keine Orte gespeichert. Mit 'sportstunden init' Beispiele anlegen."
    zeilen = [titelzeile("Gespeicherte Orte")]
    for art in ORTSARTEN:
        passende = [o for o in orte if o.art == art]
        if not passende:
            continue
        zeilen.append(f"\n{ORTSARTEN[art]}:")
        zeilen.extend(ort_zeile(o, katalog) for o in passende)
    return "\n".join(zeilen)


def ausstattung_liste(ort: Ort, katalog: Katalog) -> str:
    zeilen = [titelzeile(f"Ausstattung: {ort.name}")]
    if ort.flaeche:
        zeilen.append(f"Flaeche: {ort.flaeche}")
    if ort.notiz:
        zeilen.append(f"Notiz:   {ort.notiz}")
    if not ort.ausstattung:
        zeilen.append("\nNoch keine Geraete erfasst.")
        return "\n".join(zeilen)
    nach_kategorie: Dict[str, List[str]] = {}
    for geraet_id, anzahl in ort.ausstattung.items():
        geraet = katalog.geraete.get(geraet_id)
        kategorie = geraet.kategorie if geraet else "sonstiges"
        nach_kategorie.setdefault(kategorie, []).append(
            f"  {geraet_id:<22} {katalog.geraet_name(geraet_id):<30} {anzahl:>4}"
        )
    for kategorie in sorted(nach_kategorie):
        zeilen.append(f"\n[{kategorie}]")
        zeilen.extend(sorted(nach_kategorie[kategorie]))
    return "\n".join(zeilen)


def stunde_text(
    stunde: Stunde,
    katalog: Katalog,
    ergebnis: Optional[Planungsergebnis] = None,
    ausfuehrlich: bool = True,
) -> str:
    zeilen = [titelzeile(stunde.titel)]
    zeilen.append(
        f"Ort:          {stunde.ort_name} ({ORTSARTEN.get(stunde.ortsart, stunde.ortsart)})"
    )
    zeilen.append(f"Gruppe:       {stunde.altersgruppe_name}")
    zeilen.append(
        f"Dauer:        {stunde.gesamtdauer} min   Kinder: {stunde.teilnehmer}"
        + (f"   Schwerpunkt: {stunde.schwerpunkt}" if stunde.schwerpunkt else "")
        + (f"   Motto: {stunde.thema.capitalize()}" if stunde.thema else "")
    )
    zeilen.append(f"Datum:        {stunde.datum}   ID: {stunde.id}")

    laufzeit = 0
    for teil in stunde.teile:
        zeilen.append("")
        zeilen.append(
            f"{teil.titel} ({teil.dauer} min, ab Minute {laufzeit})"
        )
        zeilen.append(linie())
        laufzeit += teil.dauer
        if not teil.uebungen:
            zeilen.append(f"  ! {teil.notiz or 'Keine Uebung geplant.'}")
            continue
        if teil.notiz:
            zeilen.append(f"  ({teil.notiz})")
        for uebung in teil.uebungen:
            zeilen.append(f"  {uebung.dauer:>3} min  {uebung.name}")
            zeilen.append(
                f"          Material gesamt: {_material(katalog, uebung.gesamtbedarf)}"
            )
            if uebung.absicherung:
                zeilen.append(
                    f"          davon Absicherung: {_material(katalog, uebung.absicherung)}"
                )
            if ausfuehrlich:
                zeilen.append(f"          {uebung.beschreibung}")
                if uebung.aufbau:
                    zeilen.append(f"          Aufbau: {uebung.aufbau}")
                if uebung.hinweise:
                    zeilen.append(f"          Hinweis: {uebung.hinweise}")
            if uebung.koordination:
                zeilen.append(
                    "          Koordination: " + ", ".join(uebung.koordination)
                )

    zeilen.append("")
    zeilen.append("Gesamtmaterial (hoechster gleichzeitiger Bedarf, inkl. Absicherung)")
    zeilen.append(linie())
    zeilen.append("  " + _material(katalog, stunde.materialliste()))

    if ergebnis:
        if ergebnis.sicherheitshinweise:
            zeilen.append("")
            zeilen.append("Sicherheit")
            zeilen.append(linie())
            zeilen.extend(f"  * {hinweis}" for hinweis in ergebnis.sicherheitshinweise)
        if ergebnis.warnungen:
            zeilen.append("")
            zeilen.append("Hinweise zur Planung")
            zeilen.append(linie())
            zeilen.extend(f"  ! {warnung}" for warnung in ergebnis.warnungen)
    return "\n".join(zeilen)


def aufbau_text(stunde: Stunde, katalog: Katalog) -> str:
    zeilen = [titelzeile("Aufbauplan")]
    for eintrag in aufbauplan(stunde, katalog):
        zeilen.append(f"\n{eintrag['titel']} ({eintrag['dauer']} min)")
        zeilen.append(linie())
        if eintrag["bedarf"]:
            zeilen.append(
                "  Benoetigt: "
                + ", ".join(f"{a}x {g}" for g, a in eintrag["bedarf"].items())
            )
        if eintrag["zusaetzlich_aufbauen"]:
            zeilen.append(
                "  Zusaetzlich aufbauen: "
                + ", ".join(
                    f"{a}x {g}" for g, a in eintrag["zusaetzlich_aufbauen"].items()
                )
            )
        for schritt in eintrag["schritte"]:
            zeilen.append(f"  - {schritt}")
        for hinweis in eintrag["sicherheit"]:
            zeilen.append(f"  ! {hinweis}")
    return "\n".join(zeilen)


def stil_text(profil: Stilprofil, katalog: Katalog, ueberschrift: str) -> str:
    zeilen = [titelzeile(ueberschrift)]
    zeilen.extend(f"  {zeile}" for zeile in profil.beschreibung(katalog))
    return "\n".join(zeilen)


def stunden_liste(stunden: Iterable[Stunde]) -> str:
    stunden = list(stunden)
    if not stunden:
        return "Noch keine Stunden gespeichert."
    zeilen = [titelzeile("Gespeicherte Stunden")]
    zeilen.append(
        f"  {'ID':<18} {'Datum':<12} {'Gruppe':<16} {'Dauer':<7} {'Quelle':<8} Titel"
    )
    for stunde in sorted(stunden, key=lambda s: s.datum, reverse=True):
        zeilen.append(
            f"  {stunde.id:<18} {stunde.datum:<12} {stunde.altersgruppe_id:<16} "
            f"{str(stunde.gesamtdauer) + ' min':<7} {stunde.quelle:<8} {stunde.titel}"
        )
    return "\n".join(zeilen)
