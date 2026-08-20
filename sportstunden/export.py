"""PDF-Export einer Kinderturnstunde als Stundenbild.

Seite 1 ist das Stundenbild im Stil einer handgeschriebenen Stundenskizze:
Anfang, Hallenplan mit nummerierten Stationen, Stationsliste mit Material,
Ende. Auf den Folgeseiten stehen Ablauf, Beschreibungen, Aufbau und
Sicherheitshinweise.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .hallenplan import zeichne_hallenplan
from .katalog import Katalog
from .models import ORTSARTEN, Stunde
from .pdf import AKZENT, AKZENT_HELL, GRAU, HELLGRAU, PDF, SCHWARZ, Farbe, WARNROT
from .planer import aufbauplan, pruefe_bestand

ORGANISATION_TEXT = {
    "ganze_gruppe": "Gesamte Gruppe",
    "gruppen": "Kleingruppen",
    "riegen": "Riegen",
    "stationen": "Station",
    "partner": "Partner",
    "einzeln": "Jedes Kind",
}

WARNGELB = Farbe(0.99, 0.94, 0.85)
KREIS_ZIFFERN = "0123456789"


def _datum_deutsch(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso


def _material_kurz(katalog: Katalog, bedarf: Dict[str, int]) -> str:
    """Materialliste in der Kurzschreibweise des Stundenbilds."""
    if not bedarf:
        return "kein Material"
    teile = []
    for geraet, anzahl in sorted(
        bedarf.items(), key=lambda x: katalog.geraet_kurz(x[0])
    ):
        name = katalog.geraet_kurz(geraet)
        teile.append(f"{anzahl}x {name}" if anzahl > 1 else name)
    return ", ".join(teile)


def _material_lang(katalog: Katalog, bedarf: Dict[str, int]) -> str:
    if not bedarf:
        return "kein Material"
    return ", ".join(
        f"{anzahl} x {katalog.geraet_name(geraet)}"
        for geraet, anzahl in sorted(
            bedarf.items(), key=lambda x: katalog.geraet_name(x[0])
        )
    )


# ---------------------------------------------------------------------------
# Seite 1: Stundenbild
# ---------------------------------------------------------------------------


def _kopf(pdf: PDF, stunde: Stunde, titel: str, gruppe_zusatz: str) -> None:
    oben = pdf.hoehe - 42
    pdf.text_zentriert(titel, pdf.breite / 2, oben, 20, fett=True, farbe=AKZENT)
    datum = _datum_deutsch(stunde.datum)
    pdf._text(
        datum,
        pdf.breite - pdf.rand - 60,
        oben,
        11,
        farbe=SCHWARZ,
    )
    pdf.y = oben - 16
    zeile = [
        stunde.altersgruppe_name,
        stunde.ort_name,
        f"{stunde.gesamtdauer} min",
        f"{stunde.teilnehmer} Kinder",
    ]
    if stunde.thema:
        zeile.append(f"Motto: {stunde.thema.capitalize()}")
    if gruppe_zusatz:
        zeile.append(gruppe_zusatz)
    pdf.text_zentriert(
        "   -   ".join(z for z in zeile if z), pdf.breite / 2, pdf.y, 9, farbe=GRAU
    )
    pdf.y -= 16


def _eckzeile(
    pdf: PDF, beschriftung: str, stunde: Stunde, phase: str, katalog: Katalog
) -> None:
    """Zeile 'Anfang:' bzw. 'Ende:' wie im handschriftlichen Stundenbild."""
    from .pdf import umbrechen

    teil = stunde.teil(phase)
    if not teil or not teil.uebungen:
        return
    pdf.abstand(14)
    pdf._text(beschriftung, pdf.rand, pdf.y, 11, fett=True, farbe=AKZENT)
    versatz = pdf.rand + 76
    for nummer, uebung in enumerate(teil.uebungen):
        if nummer:
            pdf.abstand(12)
        pdf._text(f"{uebung.name}  ({uebung.dauer} min)", versatz, pdf.y, 10.5, fett=True)
        material = _material_kurz(katalog, uebung.gesamtbedarf)
        if material != "kein Material":
            for zeile in umbrechen(material, pdf.breite - pdf.rand - versatz, 8.5):
                pdf.abstand(11)
                pdf._text(zeile, versatz, pdf.y, 8.5, farbe=GRAU)
    pdf.abstand(4)


def _stationsliste(pdf: PDF, stationen, katalog: Katalog, parallel: bool) -> None:
    """Nummerierte Stationsliste unter dem Plan - Name und Material."""
    from .pdf import textbreite, umbrechen

    pdf.abstand(8)
    for nummer, station in enumerate(stationen, start=1):
        pdf.abstand(14)
        kreis_x = pdf.rand + 7
        pdf.kreis(kreis_x, pdf.y + 3, 7, AKZENT, 0.9)
        pdf.text_zentriert(str(nummer), kreis_x, pdf.y, 8, fett=True, farbe=AKZENT)

        name = f"{station.name}:"
        pdf._text(name, pdf.rand + 19, pdf.y, 10, fett=True)
        text_x = pdf.rand + 19 + textbreite(name, 10, True) + 5
        breite = pdf.breite - pdf.rand - text_x
        material = _material_kurz(katalog, station.gesamtbedarf)
        if not parallel and station.dauer:
            breite -= 34
        zeilen = umbrechen(material, breite, 9)
        for stelle, zeile in enumerate(zeilen):
            if stelle:
                pdf.abstand(11)
            pdf._text(zeile, text_x if stelle == 0 else pdf.rand + 19, pdf.y, 9)
        if not parallel and station.dauer:
            pdf._text(
                f"{station.dauer} min",
                pdf.breite - pdf.rand - 30,
                pdf.y,
                8.5,
                farbe=GRAU,
            )


def _textbreite(text: str, groesse: float, fett: bool = False) -> float:
    from .pdf import textbreite

    return textbreite(text, groesse, fett)


def stundenbild_seite(
    pdf: PDF,
    stunde: Stunde,
    katalog: Katalog,
    titel: str = "Ki Tu",
    gruppe_zusatz: str = "",
) -> None:
    _kopf(pdf, stunde, titel, gruppe_zusatz)
    _eckzeile(pdf, "Anfang:", stunde, "aufwaermen", katalog)
    _eckzeile(pdf, "Koordination:", stunde, "koordination", katalog)

    hauptteil = stunde.teil("hauptteil")
    stationen = list(hauptteil.uebungen) if hauptteil else []
    if hauptteil and hauptteil.parallel and stationen:
        pdf.abstand(13)
        wechsel = stationen[0].dauer
        pdf._text(
            f"Hauptteil: {len(stationen)} Stationen, je {wechsel} min, "
            "Wechsel im Uhrzeigersinn",
            pdf.rand,
            pdf.y,
            9,
            farbe=GRAU,
        )

    # Hallenplan - nimmt den Platz ein, der nach Liste und Abschluss bleibt.
    listen_hoehe = 15.0 * max(1, len(stationen)) + 24
    abschluss_hoehe = 46.0
    verfuegbar = pdf.y - pdf.rand - listen_hoehe - abschluss_hoehe
    plan_hoehe = max(150.0, min(430.0, verfuegbar))
    pdf.abstand(plan_hoehe + 12)
    zeichne_hallenplan(
        pdf, stunde, katalog, pdf.rand, pdf.y, pdf.satzbreite, plan_hoehe
    )
    pdf.abstand(4)

    _stationsliste(pdf, stationen, katalog, bool(hauptteil and hauptteil.parallel))
    pdf.abstand(6)
    _eckzeile(pdf, "Ende:", stunde, "abschluss", katalog)


# ---------------------------------------------------------------------------
# Folgeseiten: Ablauf, Aufbau, Sicherheit
# ---------------------------------------------------------------------------


def _detailseiten(
    pdf: PDF,
    stunde: Stunde,
    katalog: Katalog,
    bestand: Optional[Dict[str, int]],
    trainer: str,
) -> None:
    pdf.neue_seite()
    pdf.ueberschrift("Ablauf")

    kopfdaten = [
        f"Datum: {_datum_deutsch(stunde.datum)}",
        f"Gruppe: {stunde.altersgruppe_name}",
        f"Ort: {stunde.ort_name} ({ORTSARTEN.get(stunde.ortsart, stunde.ortsart)})",
        f"Dauer: {stunde.gesamtdauer} min, {stunde.teilnehmer} Kinder",
    ]
    if stunde.thema:
        kopfdaten.append(f"Motto: {stunde.thema.capitalize()}")
    if stunde.schwerpunkt:
        kopfdaten.append(f"Schwerpunkt: {stunde.schwerpunkt}")
    if trainer:
        kopfdaten.append(f"Uebungsleitung: {trainer}")
    pdf.hinweiskasten("Stunde auf einen Blick", kopfdaten, farbe=AKZENT_HELL)

    laufzeit = 0
    for teil in stunde.teile:
        von = f"{laufzeit:02d}"
        bis = f"{laufzeit + teil.dauer:02d}"
        laufzeit += teil.dauer
        pdf.zwischentitel(f"{teil.titel}  ({teil.dauer} min, Minute {von}-{bis})")
        if teil.notiz:
            pdf.absatz(teil.notiz, groesse=8.5, farbe=GRAU, kursiv=True)
            pdf.abstand(4)
        if not teil.uebungen:
            pdf.absatz("Keine Uebung geplant.", farbe=WARNROT)
            continue
        zeilen = []
        for uebung in teil.uebungen:
            organisation = ORGANISATION_TEXT.get(
                uebung.organisation, uebung.organisation
            )
            if uebung.gruppen > 1:
                organisation += f" ({uebung.gruppen}x)"
            zeilen.append(
                [
                    f"{uebung.dauer} min",
                    uebung.name,
                    organisation,
                    _material_lang(katalog, uebung.gesamtbedarf),
                ]
            )
        pdf.tabelle(
            ["Zeit", "Inhalt", "Form", "Material inkl. Absicherung"],
            zeilen,
            [0.09, 0.27, 0.16, 0.48],
        )
        for uebung in teil.uebungen:
            pdf.zwischentitel(f"{uebung.name} ({uebung.dauer} min)", groesse=9.5)
            pdf.absatz(uebung.beschreibung, groesse=9.0, einzug=6)
            if uebung.aufbau:
                pdf.absatz(f"Aufbau: {uebung.aufbau}", groesse=8.5, einzug=6, farbe=GRAU)
            if uebung.hinweise:
                pdf.absatz(
                    f"Hinweis: {uebung.hinweise}", groesse=8.5, einzug=6, kursiv=True
                )
        pdf.abstand(4)

    # Material und Aufbau
    pdf.ueberschrift("Material und Aufbau")
    material = stunde.materialliste()
    if material:
        zeilen = []
        for geraet, anzahl in sorted(
            material.items(), key=lambda x: katalog.geraet_name(x[0])
        ):
            zeile = [
                katalog.geraet_name(geraet),
                str(anzahl),
                "Absicherung" if katalog.ist_absicherung(geraet) else "Geraet",
            ]
            if bestand is not None:
                zeile.append(str(bestand.get(geraet, 0)))
            zeilen.append(zeile)
        kopf = ["Geraet", "Gebraucht", "Art"]
        breiten = [0.5, 0.16, 0.34]
        if bestand is not None:
            kopf.append("Vorhanden")
            breiten = [0.44, 0.15, 0.23, 0.18]
        pdf.tabelle(kopf, zeilen, breiten)
        pdf.absatz(
            "Angegeben ist der hoechste gleichzeitige Bedarf. Die Absicherung "
            "(Matten, Weichboden, Niedersprungmatte) ist enthalten und darf nicht "
            "reduziert werden.",
            groesse=8.5,
            farbe=GRAU,
        )

    plan = aufbauplan(stunde, katalog)
    for eintrag in plan:
        if not eintrag["schritte"]:
            continue
        pdf.zwischentitel(f"Aufbau {eintrag['titel']}")
        if eintrag["zusaetzlich_aufbauen"]:
            pdf.absatz(
                "Zusaetzlich zum vorherigen Teil: "
                + ", ".join(
                    f"{a}x {g}" for g, a in eintrag["zusaetzlich_aufbauen"].items()
                ),
                groesse=8.5,
                einzug=6,
                farbe=GRAU,
            )
        pdf.aufzaehlung(eintrag["schritte"], groesse=9.0)
        pdf.abstand(3)

    sicherheit: List[str] = []
    for eintrag in plan:
        for hinweis in eintrag["sicherheit"]:
            if hinweis not in sicherheit:
                sicherheit.append(hinweis)
    if sicherheit:
        pdf.ueberschrift("Sicherheit und Absicherung")
        pdf.hinweiskasten("Vor der Stunde pruefen", sicherheit, farbe=WARNGELB)

    if bestand is not None:
        verstoesse = pruefe_bestand(stunde, bestand)
        if verstoesse:
            pdf.hinweiskasten(
                "ACHTUNG: Geraetebestand ueberschritten",
                verstoesse,
                farbe=Farbe(0.98, 0.88, 0.87),
                textfarbe=WARNROT,
            )


# ---------------------------------------------------------------------------
# Einstieg
# ---------------------------------------------------------------------------


def stunden_pdf(
    stunde: Stunde,
    katalog: Katalog,
    pfad: Path | str,
    bestand: Optional[Dict[str, int]] = None,
    trainer: str = "",
    verein: str = "",
    titel: str = "Ki Tu",
    nur_stundenbild: bool = False,
) -> Path:
    """Schreibt die Stunde als PDF und gibt den Pfad zurueck."""
    erstellt = datetime.now().strftime("%d.%m.%Y")
    fusstext = f"Kinderturnen - Stundenbild vom {erstellt}"
    if verein:
        fusstext += f" - {verein}"
    pdf = PDF(titel=f"{titel} {_datum_deutsch(stunde.datum)}", fusstext=fusstext)

    stundenbild_seite(pdf, stunde, katalog, titel=titel, gruppe_zusatz=trainer)
    if not nur_stundenbild:
        _detailseiten(pdf, stunde, katalog, bestand, trainer)
    return pdf.speichern(pfad)


def dateiname_fuer(stunde: Stunde) -> str:
    """Sprechender, dateisystemsicherer Dateiname."""
    roh = f"{stunde.datum}_{stunde.altersgruppe_id}_{stunde.titel}"
    ersetzungen = {
        "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss",
    }
    for alt, neu in ersetzungen.items():
        roh = roh.replace(alt, neu)
    erlaubt = [
        zeichen if zeichen.isalnum() or zeichen in "-_" else "_" for zeichen in roh
    ]
    name = "".join(erlaubt).strip("_")
    while "__" in name:
        name = name.replace("__", "_")
    return f"{name[:80]}.pdf"
