"""PDF-Export einer Stunde inklusive Aufbau-Informationen."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .katalog import Katalog
from .models import ORTSARTEN, Stunde
from .pdf import AKZENT_HELL, GRAU, PDF, Farbe, WARNROT
from .planer import aufbauplan, pruefe_bestand

ORGANISATION_TEXT = {
    "ganze_gruppe": "Gesamte Gruppe",
    "gruppen": "Kleingruppen",
    "riegen": "Riegenbetrieb",
    "stationen": "Stationsbetrieb",
    "partner": "Partnerarbeit",
    "einzeln": "Einzelarbeit",
}

WARNGELB = Farbe(0.99, 0.94, 0.85)


def _zeitstempel(minuten: int) -> str:
    return f"{minuten // 60:02d}:{minuten % 60:02d}"


def _material_text(katalog: Katalog, bedarf: Dict[str, int]) -> str:
    if not bedarf:
        return "kein Material"
    return ", ".join(
        f"{anzahl} x {katalog.geraet_name(geraet)}"
        for geraet, anzahl in sorted(bedarf.items(), key=lambda x: katalog.geraet_name(x[0]))
    )


def stunden_pdf(
    stunde: Stunde,
    katalog: Katalog,
    pfad: Path | str,
    bestand: Optional[Dict[str, int]] = None,
    trainer: str = "",
    verein: str = "",
    startzeit: str = "",
) -> Path:
    """Schreibt die Stunde als PDF und gibt den Pfad zurueck."""
    erstellt = datetime.now().strftime("%d.%m.%Y %H:%M")
    pdf = PDF(
        titel=stunde.titel,
        fusstext=f"Sportstunden-Planer - erstellt am {erstellt}"
        + (f" - {verein}" if verein else ""),
    )

    untertitel_teile = [
        stunde.ort_name,
        ORTSARTEN.get(stunde.ortsart, stunde.ortsart),
        stunde.altersgruppe_name,
        f"{stunde.gesamtdauer} Minuten",
        f"{stunde.teilnehmer} Teilnehmende",
    ]
    pdf.kopfzeile(stunde.titel, "  |  ".join(t for t in untertitel_teile if t))

    kopfdaten = [
        f"Datum: {stunde.datum}",
        f"Ort: {stunde.ort_name} ({ORTSARTEN.get(stunde.ortsart, stunde.ortsart)})",
        f"Altersgruppe: {stunde.altersgruppe_name}",
        f"Dauer: {stunde.gesamtdauer} Minuten"
        + (f", Beginn {startzeit}" if startzeit else ""),
        f"Teilnehmende: {stunde.teilnehmer}",
    ]
    if stunde.schwerpunkt:
        kopfdaten.append(f"Schwerpunkt: {stunde.schwerpunkt}")
    if trainer:
        kopfdaten.append(f"Uebungsleitung: {trainer}")
    if stunde.notiz:
        kopfdaten.append(f"Notiz: {stunde.notiz}")
    pdf.hinweiskasten("Stundenuebersicht", kopfdaten, farbe=AKZENT_HELL)

    # -- Materialliste -----------------------------------------------------
    pdf.ueberschrift("Material und Absicherung (Gesamtbedarf)")
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
        kopf = ["Geraet", "Benoetigt", "Art"]
        breiten = [0.5, 0.15, 0.35]
        if bestand is not None:
            kopf.append("Vorhanden")
            breiten = [0.44, 0.14, 0.24, 0.18]
        pdf.tabelle(kopf, zeilen, breiten)
        pdf.absatz(
            "Angegeben ist der hoechste gleichzeitige Bedarf. Die Absicherung "
            "(Matten, Weichboden, Niedersprungmatten) ist darin enthalten und darf "
            "nicht reduziert werden.",
            groesse=8.5,
            farbe=GRAU,
        )
    else:
        pdf.absatz("Fuer diese Stunde wird kein Material benoetigt.")

    # -- Ablauf ------------------------------------------------------------
    pdf.ueberschrift("Ablauf")
    laufzeit = 0
    for teil in stunde.teile:
        von = _zeitstempel(laufzeit)
        bis = _zeitstempel(laufzeit + teil.dauer)
        laufzeit += teil.dauer
        pdf.zwischentitel(f"{teil.titel}  ({teil.dauer} min, {von} - {bis})")
        if teil.phase == "koordination":
            pdf.absatz(
                "Koordinationsteil direkt nach dem Aufwaermen - abgestimmt auf "
                f"{stunde.altersgruppe_name}.",
                groesse=8.5,
                farbe=GRAU,
                kursiv=True,
            )
        if not teil.uebungen:
            pdf.absatz(teil.notiz or "Keine Uebung geplant.", farbe=WARNROT)
            continue

        zeilen = []
        for uebung in teil.uebungen:
            organisation = ORGANISATION_TEXT.get(uebung.organisation, uebung.organisation)
            if uebung.gruppen > 1:
                organisation += f" ({uebung.gruppen} Gruppen)"
            zeilen.append(
                [
                    f"{uebung.dauer} min",
                    uebung.name,
                    organisation,
                    _material_text(katalog, uebung.gesamtbedarf),
                ]
            )
        pdf.tabelle(
            ["Zeit", "Uebung", "Organisation", "Material inkl. Absicherung"],
            zeilen,
            [0.09, 0.29, 0.22, 0.40],
        )

        for uebung in teil.uebungen:
            pdf.zwischentitel(f"{uebung.name} ({uebung.dauer} min)", groesse=9.5)
            pdf.absatz(uebung.beschreibung, groesse=9.0, einzug=6)
            if uebung.koordination:
                pdf.absatz(
                    "Koordinative Faehigkeiten: " + ", ".join(uebung.koordination),
                    groesse=8.5,
                    einzug=6,
                    farbe=GRAU,
                )
            if uebung.hinweise:
                pdf.absatz(
                    f"Hinweis: {uebung.hinweise}", groesse=8.5, einzug=6, kursiv=True
                )
        pdf.abstand(4)

    # -- Aufbau ------------------------------------------------------------
    pdf.ueberschrift("Aufbau je Stundenteil")
    plan = aufbauplan(stunde, katalog)
    for eintrag in plan:
        if not eintrag["schritte"] and not eintrag["bedarf"]:
            continue
        pdf.zwischentitel(f"{eintrag['titel']} ({eintrag['dauer']} min)")
        if eintrag["bedarf"]:
            pdf.absatz(
                "Benoetigt: "
                + ", ".join(f"{a} x {g}" for g, a in eintrag["bedarf"].items()),
                groesse=9.0,
                einzug=6,
            )
        if eintrag["zusaetzlich_aufbauen"]:
            pdf.absatz(
                "Zusaetzlich zum vorherigen Teil aufbauen: "
                + ", ".join(
                    f"{a} x {g}" for g, a in eintrag["zusaetzlich_aufbauen"].items()
                ),
                groesse=9.0,
                einzug=6,
                farbe=GRAU,
            )
        if eintrag["schritte"]:
            pdf.aufzaehlung(eintrag["schritte"], groesse=9.0)
        pdf.abstand(3)

    # -- Sicherheit --------------------------------------------------------
    sicherheit: List[str] = []
    for eintrag in plan:
        for hinweis in eintrag["sicherheit"]:
            if hinweis not in sicherheit:
                sicherheit.append(hinweis)
    if sicherheit:
        pdf.ueberschrift("Sicherheit und Absicherung")
        pdf.hinweiskasten(
            "Vor dem ersten Durchgang pruefen", sicherheit, farbe=WARNGELB
        )

    if bestand is not None:
        verstoesse = pruefe_bestand(stunde, bestand)
        if verstoesse:
            pdf.hinweiskasten(
                "ACHTUNG: Geraetebestand ueberschritten",
                verstoesse,
                farbe=Farbe(0.98, 0.88, 0.87),
                textfarbe=WARNROT,
            )

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
