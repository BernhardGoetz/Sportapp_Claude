"""Schematischer Hallenplan fuer das Stundenbild.

Zeichnet die Halle (bzw. die Flaeche im Freien) als Rechteck und darin die
Stationen der Bewegungslandschaft mit nummerierten Kreisen und einfachen
Geraetesymbolen - angelehnt an eine handgezeichnete Stundenskizze.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Sequence, Tuple

from .katalog import Katalog
from .models import Stunde, StundenUebung
from .pdf import AKZENT, GRAU, PDF, Farbe, SCHWARZ, textbreite

PLAN_LINIE = Farbe(0.09, 0.34, 0.55)
PLAN_RASTER = Farbe(0.86, 0.90, 0.95)
GERAET_FARBE = Farbe(0.13, 0.40, 0.62)

# Reihenfolge, in der Geraete im Plan gezeichnet werden (Grossgeraete zuerst).
KATEGORIE_RANG = {
    "grossgeraet": 0,
    "absicherung": 1,
    "spielfeld": 2,
    "kleingeraet": 3,
    "sonstiges": 4,
}


# ---------------------------------------------------------------------------
# Geraetesymbole - jedes zeichnet in eine Box (x, y = links unten)
# ---------------------------------------------------------------------------


def _matte(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x, y + h * 0.25, b, h * 0.5, GERAET_FARBE, 0.8)
    pdf.linie(x + b * 0.08, y + h * 0.32, x + b * 0.92, y + h * 0.32, GERAET_FARBE, 0.35)
    pdf.linie(x + b * 0.08, y + h * 0.68, x + b * 0.92, y + h * 0.68, GERAET_FARBE, 0.35)


def _weichboden(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x, y + h * 0.1, b, h * 0.8, GERAET_FARBE, 1.0)
    for anteil in (0.25, 0.5, 0.75):
        pdf.linie(
            x + b * anteil, y + h * 0.1, x + b * (anteil - 0.15), y + h * 0.9,
            GERAET_FARBE, 0.5,
        )


def _kasten(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x, y + h * 0.15, b, h * 0.7, GERAET_FARBE, 0.9)
    for anteil in (0.38, 0.61):
        pdf.linie(x, y + h * anteil, x + b, y + h * anteil, GERAET_FARBE, 0.5)


def _bank(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x, y + h * 0.45, b, h * 0.18, GERAET_FARBE, 0.9)
    for anteil in (0.12, 0.88):
        pdf.linie(
            x + b * anteil, y + h * 0.45, x + b * anteil, y + h * 0.25, GERAET_FARBE, 0.7
        )


def _reifen(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    radius = min(b / 6.0, h / 3.0)
    for index in range(3):
        pdf.kreis(x + radius + index * radius * 2, y + h / 2, radius, GERAET_FARBE, 0.8)


def _reck(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.linie(x + b * 0.15, y, x + b * 0.15, y + h * 0.8, GERAET_FARBE, 0.9)
    pdf.linie(x + b * 0.85, y, x + b * 0.85, y + h * 0.8, GERAET_FARBE, 0.9)
    pdf.linie(x + b * 0.05, y + h * 0.8, x + b * 0.95, y + h * 0.8, GERAET_FARBE, 1.1)


def _barren(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    for anteil in (0.55, 0.8):
        pdf.linie(x, y + h * anteil, x + b, y + h * anteil, GERAET_FARBE, 1.0)
    for anteil in (0.2, 0.8):
        pdf.linie(
            x + b * anteil, y + h * 0.55, x + b * anteil, y + h * 0.1, GERAET_FARBE, 0.7
        )


def _ringe(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) * 0.16
    for anteil in (0.32, 0.68):
        pdf.linie(x + b * anteil, y + h, x + b * anteil, y + h * 0.42, GERAET_FARBE, 0.7)
        pdf.kreis(x + b * anteil, y + h * 0.3, radius, GERAET_FARBE, 0.9)


def _tau(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    punkte = []
    schritte = 6
    for index in range(schritte + 1):
        anteil = index / schritte
        punkte.append((x + b * (0.5 + 0.16 * math.sin(index * 1.6)), y + h * anteil))
    pdf.pfad(punkte, GERAET_FARBE, 0.9)


def _sprossenwand(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x + b * 0.2, y, b * 0.6, h, GERAET_FARBE, 0.9)
    for index in range(1, 5):
        hoehe = y + h * index / 5.0
        pdf.linie(x + b * 0.2, hoehe, x + b * 0.8, hoehe, GERAET_FARBE, 0.5)


def _trampolin(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.pfad(
        [
            (x + b * 0.1, y + h * 0.2),
            (x + b * 0.9, y + h * 0.2),
            (x + b * 0.75, y + h * 0.7),
            (x + b * 0.25, y + h * 0.7),
        ],
        GERAET_FARBE,
        0.9,
        schliessen=True,
    )


def _sprungbrett(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.pfad(
        [
            (x + b * 0.05, y + h * 0.25),
            (x + b * 0.95, y + h * 0.6),
            (x + b * 0.95, y + h * 0.25),
        ],
        GERAET_FARBE,
        0.9,
        schliessen=True,
    )


def _balken(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x, y + h * 0.55, b, h * 0.12, GERAET_FARBE, 0.9)
    for anteil in (0.25, 0.75):
        pdf.linie(
            x + b * anteil, y + h * 0.55, x + b * anteil, y + h * 0.15, GERAET_FARBE, 0.7
        )


def _schwungtuch(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) * 0.42
    mitte_x, mitte_y = x + b / 2, y + h / 2
    pdf.kreis(mitte_x, mitte_y, radius, GERAET_FARBE, 0.9)
    for index in range(6):
        winkel = index * math.pi / 3
        pdf.linie(
            mitte_x,
            mitte_y,
            mitte_x + radius * math.cos(winkel),
            mitte_y + radius * math.sin(winkel),
            GERAET_FARBE,
            0.4,
        )


def _rollbrett(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x + b * 0.15, y + h * 0.3, b * 0.7, h * 0.4, GERAET_FARBE, 0.9)
    for punkt_x in (x + b * 0.25, x + b * 0.75):
        for punkt_y in (y + h * 0.32, y + h * 0.68):
            pdf.kreis(punkt_x, punkt_y, min(b, h) * 0.06, GERAET_FARBE, 0.6, fuellen=True)


def _baelle(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    radius = min(b / 7.0, h / 3.5)
    for index in range(3):
        pdf.kreis(
            x + radius * 1.4 + index * radius * 2.4,
            y + h / 2,
            radius,
            GERAET_FARBE,
            0.7,
        )


def _huetchen(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    for index in range(3):
        links = x + index * b / 3.0
        pdf.pfad(
            [
                (links + b * 0.03, y + h * 0.25),
                (links + b * 0.16, y + h * 0.7),
                (links + b * 0.29, y + h * 0.25),
            ],
            GERAET_FARBE,
            0.7,
            schliessen=True,
        )


def _leiter(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x, y + h * 0.3, b, h * 0.4, GERAET_FARBE, 0.8)
    for index in range(1, 4):
        punkt_x = x + b * index / 4.0
        pdf.linie(punkt_x, y + h * 0.3, punkt_x, y + h * 0.7, GERAET_FARBE, 0.5)


def _seil(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    punkte = []
    schritte = 8
    for index in range(schritte + 1):
        anteil = index / schritte
        punkte.append((x + b * anteil, y + h * (0.5 + 0.18 * math.sin(index * 1.3))))
    pdf.pfad(punkte, GERAET_FARBE, 0.8)


def _eimer(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.pfad(
        [
            (x + b * 0.3, y + h * 0.25),
            (x + b * 0.7, y + h * 0.25),
            (x + b * 0.78, y + h * 0.7),
            (x + b * 0.22, y + h * 0.7),
        ],
        GERAET_FARBE,
        0.8,
        schliessen=True,
    )


def _bausteine(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x + b * 0.1, y + h * 0.2, b * 0.36, h * 0.28, GERAET_FARBE, 0.7)
    pdf.rechteck_rand(x + b * 0.5, y + h * 0.2, b * 0.36, h * 0.28, GERAET_FARBE, 0.7)
    pdf.rechteck_rand(x + b * 0.3, y + h * 0.5, b * 0.36, h * 0.28, GERAET_FARBE, 0.7)


def _tuecher(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    for index in range(2):
        links = x + index * b * 0.5
        pdf.pfad(
            [
                (links + b * 0.05, y + h * 0.3),
                (links + b * 0.2, y + h * 0.75),
                (links + b * 0.4, y + h * 0.45),
            ],
            GERAET_FARBE,
            0.7,
            schliessen=True,
        )


def _saeckchen(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    for index in range(3):
        pdf.rechteck_rand(
            x + index * b * 0.32 + b * 0.04,
            y + h * 0.38,
            b * 0.24,
            h * 0.24,
            GERAET_FARBE,
            0.7,
        )


def _tor(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.pfad(
        [
            (x + b * 0.1, y + h * 0.2),
            (x + b * 0.1, y + h * 0.7),
            (x + b * 0.9, y + h * 0.7),
            (x + b * 0.9, y + h * 0.2),
        ],
        GERAET_FARBE,
        0.9,
    )


def _scheibe(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) * 0.3
    pdf.kreis(x + b / 2, y + h / 2, radius, GERAET_FARBE, 0.9)
    pdf.kreis(x + b / 2, y + h / 2, radius * 0.45, GERAET_FARBE, 0.5)


def _karten(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    for index in range(2):
        pdf.rechteck_rand(
            x + b * (0.2 + index * 0.22),
            y + h * (0.3 + index * 0.08),
            b * 0.3,
            h * 0.4,
            GERAET_FARBE,
            0.7,
        )


def _pedalo(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    pdf.rechteck_rand(x + b * 0.15, y + h * 0.42, b * 0.7, h * 0.2, GERAET_FARBE, 0.8)
    for anteil in (0.3, 0.7):
        pdf.kreis(x + b * anteil, y + h * 0.34, min(b, h) * 0.09, GERAET_FARBE, 0.7)


def _kreisel(pdf: PDF, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) * 0.28
    pdf.kreis(x + b / 2, y + h / 2, radius, GERAET_FARBE, 0.9)
    pdf.kreis(x + b / 2, y + h / 2, radius * 0.2, GERAET_FARBE, 0.6, fuellen=True)


SYMBOLE: Dict[str, Callable[[PDF, float, float, float, float], None]] = {
    "jongliertuch": _tuecher,
    "sandsaeckchen": _saeckchen,
    "kleintor": _tor,
    "wurfscheibe": _scheibe,
    "bewegungskarten": _karten,
    "pedalo": _pedalo,
    "balancekreisel": _kreisel,
    "matte": _matte,
    "weichbodenmatte": _weichboden,
    "niedersprungmatte": _weichboden,
    "kasten_gross": _kasten,
    "kasten_klein": _kasten,
    "kastenteil": _kasten,
    "langbank": _bank,
    "schwebebalken": _balken,
    "reifen": _reifen,
    "reck": _reck,
    "barren": _barren,
    "ringe": _ringe,
    "tau": _tau,
    "sprossenwand": _sprossenwand,
    "klettergeruest": _sprossenwand,
    "minitrampolin": _trampolin,
    "sprungbrett": _sprungbrett,
    "schwungtuch": _schwungtuch,
    "rollbrett": _rollbrett,
    "softball": _baelle,
    "kleiner_ball": _baelle,
    "grosser_ball": _baelle,
    "luftballon": _baelle,
    "huetchen": _huetchen,
    "markierungsteller": _huetchen,
    "huerde_klein": _huetchen,
    "koordinationsleiter": _leiter,
    "seil_lang": _seil,
    "springseil": _seil,
    "gummiband": _seil,
    "eimer": _eimer,
    "baustein": _bausteine,
    "teppichfliese": _bausteine,
}


def _symbol(geraet_id: str):
    return SYMBOLE.get(geraet_id)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def stationen_der_stunde(stunde: Stunde) -> List[StundenUebung]:
    """Die Uebungen, die im Plan als Stationen gezeichnet werden."""
    teil = stunde.teil("hauptteil")
    if teil and teil.uebungen:
        return list(teil.uebungen)
    for anderer in stunde.teile:
        if anderer.uebungen:
            return list(anderer.uebungen)
    return []


def _wichtigste_geraete(
    uebung: StundenUebung, katalog: Katalog, hoechstens: int = 4
) -> List[str]:
    bedarf = uebung.gesamtbedarf

    def rang(geraet_id: str) -> Tuple[int, int]:
        geraet = katalog.geraete.get(geraet_id)
        kategorie = geraet.kategorie if geraet else "sonstiges"
        hat_symbol = 0 if _symbol(geraet_id) else 1
        return (hat_symbol, KATEGORIE_RANG.get(kategorie, 5))

    return sorted(bedarf, key=rang)[:hoechstens]


def _raster(pdf: PDF, x: float, y: float, breite: float, hoehe: float) -> None:
    schritt = 13.0
    linien = int(breite // schritt)
    for index in range(1, linien + 1):
        pdf.linie(x + index * schritt, y, x + index * schritt, y + hoehe, PLAN_RASTER, 0.3)
    zeilen = int(hoehe // schritt)
    for index in range(1, zeilen + 1):
        pdf.linie(x, y + index * schritt, x + breite, y + index * schritt, PLAN_RASTER, 0.3)


def zeichne_hallenplan(
    pdf: PDF,
    stunde: Stunde,
    katalog: Katalog,
    x: float,
    y: float,
    breite: float,
    hoehe: float,
) -> List[StundenUebung]:
    """Zeichnet den Plan und gibt die gezeichneten Stationen in Reihenfolge zurueck."""
    stationen = stationen_der_stunde(stunde)

    _raster(pdf, x, y, breite, hoehe)
    pdf.rechteck_rand(x, y, breite, hoehe, PLAN_LINIE, 1.6)

    if not stationen:
        pdf.text_zentriert(
            "Kein Stationsaufbau - freie Flaeche",
            x + breite / 2,
            y + hoehe / 2,
            9,
            farbe=GRAU,
        )
        return stationen

    anzahl = len(stationen)
    zeilen = 1 if anzahl <= 3 else (2 if anzahl <= 8 else 3)
    spalten = math.ceil(anzahl / zeilen)
    zellen_breite = breite / spalten
    zellen_hoehe = hoehe / zeilen

    for index, station in enumerate(stationen):
        zeile = index // spalten
        spalte = index % spalten
        zelle_x = x + spalte * zellen_breite
        # Von oben nach unten fuellen.
        zelle_y = y + hoehe - (zeile + 1) * zellen_hoehe

        _zeichne_station(
            pdf, station, katalog, index + 1, zelle_x, zelle_y, zellen_breite, zellen_hoehe
        )
    return stationen


def _zeichne_station(
    pdf: PDF,
    station: StundenUebung,
    katalog: Katalog,
    nummer: int,
    x: float,
    y: float,
    breite: float,
    hoehe: float,
) -> None:
    rand = 8.0
    innen_x = x + rand
    innen_y = y + rand
    innen_breite = max(20.0, breite - 2 * rand)
    innen_hoehe = max(20.0, hoehe - 2 * rand)

    geraete = _wichtigste_geraete(station, katalog)
    symbol_hoehe = min(34.0, innen_hoehe * 0.38)
    # Symbole leicht oberhalb der Zellenmitte, Name direkt darunter.
    symbol_y = innen_y + innen_hoehe * 0.5 - symbol_hoehe * 0.5

    if geraete:
        feld_breite = innen_breite / len(geraete)
        for stelle, geraet_id in enumerate(geraete):
            zeichner = _symbol(geraet_id)
            feld_x = innen_x + stelle * feld_breite
            symbol_breite = min(40.0, feld_breite * 0.8)
            if zeichner:
                zeichner(
                    pdf,
                    feld_x + (feld_breite - symbol_breite) / 2,
                    symbol_y,
                    symbol_breite,
                    symbol_hoehe,
                )
            else:
                pdf.rechteck_rand(
                    feld_x + feld_breite * 0.15,
                    symbol_y + symbol_hoehe * 0.25,
                    feld_breite * 0.7,
                    symbol_hoehe * 0.5,
                    GERAET_FARBE,
                    0.6,
                )
                kurz = katalog.geraet_kurz(geraet_id)
                pdf.text_zentriert(
                    kurz[:10],
                    feld_x + feld_breite * 0.5,
                    symbol_y + symbol_hoehe * 0.42,
                    5.5,
                    farbe=GERAET_FARBE,
                )

    # Nummernkreis oben links in der Zelle
    kreis_x = innen_x + 7
    kreis_y = innen_y + innen_hoehe - 7
    pdf.kreis(kreis_x, kreis_y, 7.5, PLAN_LINIE, 1.0)
    pdf.text_zentriert(str(nummer), kreis_x, kreis_y - 2.6, 8, fett=True, farbe=PLAN_LINIE)

    # Stationsname klein darunter
    name = station.name
    while textbreite(name, 7.0) > innen_breite - 4 and len(name) > 6:
        name = name[:-2]
    pdf.text_zentriert(name, x + breite / 2, symbol_y - 10, 7.0, farbe=SCHWARZ)
