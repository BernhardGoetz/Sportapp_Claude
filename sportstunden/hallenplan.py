"""Massstaeblicher Hallenplan fuer das Stundenbild.

Gezeichnet wird ueber ein schmales Zeichner-Protokoll, damit dieselben
Geraetesymbole im PDF und in der grafischen Oberflaeche verwendet werden
koennen. Die Stationen stehen an den Positionen, die ``platzierung`` ihnen in
der Halle gegeben hat.

Koordinaten der Zeichenflaeche: Punkte, Ursprung links unten (wie im PDF).
Hallenkoordinaten: Meter, Ursprung links unten.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .katalog import Katalog
from .models import Geraeteplatz, Ort, Stunde, StundenUebung
from .pdf import PDF, Farbe, textbreite
from .platzierung import GERAETEMASSE, STANDARDMASS, masse_der_stunde

PLAN_LINIE = Farbe(0.09, 0.34, 0.55)
PLAN_RASTER = Farbe(0.87, 0.91, 0.95)
GERAET_FARBE = Farbe(0.13, 0.40, 0.62)
FEST_FARBE = Farbe(0.62, 0.67, 0.72)
STATIONSFLAECHE = Farbe(0.95, 0.96, 0.98)
BESCHRIFTUNG = Farbe(0.10, 0.10, 0.12)
GRAUTON = Farbe(0.45, 0.47, 0.52)

# Reihenfolge, in der Geraete im Plan gezeichnet werden (Grossgeraete zuerst).
KATEGORIE_RANG = {
    "grossgeraet": 0,
    "absicherung": 1,
    "spielfeld": 2,
    "kleingeraet": 3,
    "sonstiges": 4,
}


# ---------------------------------------------------------------------------
# Zeichenflaechen
# ---------------------------------------------------------------------------


class Zeichner:
    """Schnittstelle, die PDF und Bildschirm gemeinsam bedienen."""

    def rechteck(self, x, y, breite, hoehe, farbe=GERAET_FARBE, staerke=0.8) -> None:
        raise NotImplementedError

    def flaeche(self, x, y, breite, hoehe, farbe=STATIONSFLAECHE) -> None:
        raise NotImplementedError

    def linie(self, x1, y1, x2, y2, farbe=GERAET_FARBE, staerke=0.6) -> None:
        raise NotImplementedError

    def kreis(self, x, y, radius, farbe=GERAET_FARBE, staerke=0.8, fuellen=False) -> None:
        raise NotImplementedError

    def pfad(self, punkte, farbe=GERAET_FARBE, staerke=0.8, schliessen=False, fuellen=False) -> None:
        raise NotImplementedError

    def text(self, inhalt, x, y, groesse=7.0, farbe=BESCHRIFTUNG, fett=False, zentriert=False) -> None:
        raise NotImplementedError


class PDFZeichner(Zeichner):
    """Zeichnet in ein :class:`~sportstunden.pdf.PDF`."""

    def __init__(self, pdf: PDF) -> None:
        self.pdf = pdf

    def rechteck(self, x, y, breite, hoehe, farbe=GERAET_FARBE, staerke=0.8) -> None:
        self.pdf.rechteck_rand(x, y, breite, hoehe, farbe, staerke)

    def flaeche(self, x, y, breite, hoehe, farbe=STATIONSFLAECHE) -> None:
        self.pdf.rechteck(x, y, breite, hoehe, farbe)

    def linie(self, x1, y1, x2, y2, farbe=GERAET_FARBE, staerke=0.6) -> None:
        self.pdf.linie(x1, y1, x2, y2, farbe, staerke)

    def kreis(self, x, y, radius, farbe=GERAET_FARBE, staerke=0.8, fuellen=False) -> None:
        self.pdf.kreis(x, y, radius, farbe, staerke, fuellen)

    def pfad(self, punkte, farbe=GERAET_FARBE, staerke=0.8, schliessen=False, fuellen=False) -> None:
        self.pdf.pfad(punkte, farbe, staerke, schliessen, fuellen)

    def text(self, inhalt, x, y, groesse=7.0, farbe=BESCHRIFTUNG, fett=False, zentriert=False) -> None:
        if zentriert:
            self.pdf.text_zentriert(inhalt, x, y, groesse, fett=fett, farbe=farbe)
        else:
            self.pdf._text(inhalt, x, y, groesse, fett=fett, farbe=farbe)


# ---------------------------------------------------------------------------
# Geraetesymbole - jedes zeichnet in eine Box (x, y = links unten)
# ---------------------------------------------------------------------------


def _matte(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y, b, h, GERAET_FARBE, 0.8)
    z.linie(x + b * 0.08, y + h * 0.25, x + b * 0.92, y + h * 0.25, GERAET_FARBE, 0.35)
    z.linie(x + b * 0.08, y + h * 0.75, x + b * 0.92, y + h * 0.75, GERAET_FARBE, 0.35)


def _weichboden(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y, b, h, GERAET_FARBE, 1.0)
    for anteil in (0.3, 0.6, 0.9):
        z.linie(x + b * anteil, y, x + b * max(0.0, anteil - 0.25), y + h, GERAET_FARBE, 0.45)


def _kasten(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y, b, h, GERAET_FARBE, 0.9)
    for anteil in (0.33, 0.66):
        z.linie(x, y + h * anteil, x + b, y + h * anteil, GERAET_FARBE, 0.5)


def _bank(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y + h * 0.25, b, h * 0.5, GERAET_FARBE, 0.9)
    for anteil in (0.1, 0.9):
        z.linie(x + b * anteil, y + h * 0.25, x + b * anteil, y, GERAET_FARBE, 0.6)


def _reifen(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) / 2.2
    spalten = max(1, int(b // (radius * 2.2)))
    for index in range(min(3, spalten)):
        z.kreis(x + radius * 1.1 + index * radius * 2.2, y + h / 2, radius, GERAET_FARBE, 0.8)


def _reck(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.linie(x + b * 0.1, y, x + b * 0.1, y + h, GERAET_FARBE, 0.9)
    z.linie(x + b * 0.9, y, x + b * 0.9, y + h, GERAET_FARBE, 0.9)
    z.linie(x, y + h * 0.5, x + b, y + h * 0.5, GERAET_FARBE, 1.2)


def _barren(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    for anteil in (0.3, 0.7):
        z.linie(x, y + h * anteil, x + b, y + h * anteil, GERAET_FARBE, 1.1)
    for anteil in (0.15, 0.85):
        z.linie(x + b * anteil, y + h * 0.3, x + b * anteil, y + h * 0.7, GERAET_FARBE, 0.6)


def _ringe(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) * 0.18
    for anteil in (0.3, 0.7):
        z.kreis(x + b * anteil, y + h * 0.5, radius, GERAET_FARBE, 0.9)
    z.linie(x + b * 0.3, y + h * 0.5, x + b * 0.7, y + h * 0.5, GERAET_FARBE, 0.4)


def _tau(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    punkte = []
    schritte = 6
    for index in range(schritte + 1):
        anteil = index / schritte
        punkte.append((x + b * (0.5 + 0.3 * math.sin(index * 1.6)), y + h * anteil))
    z.pfad(punkte, GERAET_FARBE, 0.9)


def _sprossenwand(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y, b, h, GERAET_FARBE, 0.9)
    schritte = 5 if h >= b else 3
    for index in range(1, schritte):
        if h >= b:
            hoehe = y + h * index / schritte
            z.linie(x, hoehe, x + b, hoehe, GERAET_FARBE, 0.45)
        else:
            senkrecht = x + b * index / schritte
            z.linie(senkrecht, y, senkrecht, y + h, GERAET_FARBE, 0.45)


def _trampolin(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.pfad(
        [
            (x + b * 0.05, y),
            (x + b * 0.95, y),
            (x + b * 0.75, y + h),
            (x + b * 0.25, y + h),
        ],
        GERAET_FARBE,
        0.9,
        schliessen=True,
    )


def _sprungbrett(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.pfad(
        [(x, y), (x + b, y + h * 0.8), (x + b, y)],
        GERAET_FARBE,
        0.9,
        schliessen=True,
    )


def _balken(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y + h * 0.3, b, h * 0.4, GERAET_FARBE, 0.9)
    for anteil in (0.2, 0.8):
        z.linie(x + b * anteil, y + h * 0.3, x + b * anteil, y, GERAET_FARBE, 0.6)


def _schwungtuch(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) * 0.45
    mitte_x, mitte_y = x + b / 2, y + h / 2
    z.kreis(mitte_x, mitte_y, radius, GERAET_FARBE, 0.9)
    for index in range(6):
        winkel = index * math.pi / 3
        z.linie(
            mitte_x,
            mitte_y,
            mitte_x + radius * math.cos(winkel),
            mitte_y + radius * math.sin(winkel),
            GERAET_FARBE,
            0.35,
        )


def _rollbrett(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y, b, h, GERAET_FARBE, 0.9)
    for punkt_x in (x + b * 0.2, x + b * 0.8):
        for punkt_y in (y + h * 0.2, y + h * 0.8):
            z.kreis(punkt_x, punkt_y, min(b, h) * 0.1, GERAET_FARBE, 0.5, fuellen=True)


def _baelle(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    radius = min(b / 4.5, h / 2.2)
    for index in range(3):
        z.kreis(x + radius * 1.2 + index * radius * 2.4, y + h / 2, radius, GERAET_FARBE, 0.7)


def _huetchen(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    breite = b / 3.0
    for index in range(3):
        links = x + index * breite
        z.pfad(
            [
                (links + breite * 0.1, y),
                (links + breite * 0.5, y + h),
                (links + breite * 0.9, y),
            ],
            GERAET_FARBE,
            0.7,
            schliessen=True,
        )


def _leiter(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y, b, h, GERAET_FARBE, 0.8)
    for index in range(1, 5):
        punkt_x = x + b * index / 5.0
        z.linie(punkt_x, y, punkt_x, y + h, GERAET_FARBE, 0.45)


def _seil(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    punkte = []
    schritte = 8
    for index in range(schritte + 1):
        anteil = index / schritte
        punkte.append((x + b * anteil, y + h * (0.5 + 0.4 * math.sin(index * 1.3))))
    z.pfad(punkte, GERAET_FARBE, 0.8)


def _eimer(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.pfad(
        [
            (x + b * 0.2, y),
            (x + b * 0.8, y),
            (x + b * 0.9, y + h),
            (x + b * 0.1, y + h),
        ],
        GERAET_FARBE,
        0.8,
        schliessen=True,
    )


def _bausteine(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y, b * 0.45, h * 0.45, GERAET_FARBE, 0.7)
    z.rechteck(x + b * 0.55, y, b * 0.45, h * 0.45, GERAET_FARBE, 0.7)
    z.rechteck(x + b * 0.27, y + h * 0.55, b * 0.45, h * 0.45, GERAET_FARBE, 0.7)


def _tuecher(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    for index in range(2):
        links = x + index * b * 0.5
        z.pfad(
            [
                (links + b * 0.05, y),
                (links + b * 0.2, y + h),
                (links + b * 0.4, y + h * 0.4),
            ],
            GERAET_FARBE,
            0.7,
            schliessen=True,
        )


def _saeckchen(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    for index in range(3):
        z.rechteck(x + index * b * 0.34, y + h * 0.25, b * 0.28, h * 0.5, GERAET_FARBE, 0.7)


def _tor(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.pfad(
        [(x, y), (x, y + h), (x + b, y + h), (x + b, y)],
        GERAET_FARBE,
        0.9,
    )


def _scheibe(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) * 0.4
    z.kreis(x + b / 2, y + h / 2, radius, GERAET_FARBE, 0.9)
    z.kreis(x + b / 2, y + h / 2, radius * 0.45, GERAET_FARBE, 0.5)


def _karten(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    for index in range(2):
        z.rechteck(
            x + b * index * 0.3, y + h * index * 0.15, b * 0.6, h * 0.7, GERAET_FARBE, 0.7
        )


def _pedalo(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    z.rechteck(x, y + h * 0.3, b, h * 0.4, GERAET_FARBE, 0.8)
    for anteil in (0.25, 0.75):
        z.kreis(x + b * anteil, y + h * 0.2, min(b, h) * 0.14, GERAET_FARBE, 0.6)


def _kreisel(z: Zeichner, x: float, y: float, b: float, h: float) -> None:
    radius = min(b, h) * 0.4
    z.kreis(x + b / 2, y + h / 2, radius, GERAET_FARBE, 0.9)
    z.kreis(x + b / 2, y + h / 2, radius * 0.25, GERAET_FARBE, 0.6, fuellen=True)


SYMBOLE: Dict[str, Callable[[Zeichner, float, float, float, float], None]] = {
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
    "jongliertuch": _tuecher,
    "sandsaeckchen": _saeckchen,
    "kleintor": _tor,
    "wurfscheibe": _scheibe,
    "bewegungskarten": _karten,
    "pedalo": _pedalo,
    "balancekreisel": _kreisel,
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
    uebung: StundenUebung, katalog: Optional[Katalog], hoechstens: int = 4
) -> List[Tuple[str, int]]:
    bedarf = uebung.gesamtbedarf

    def rang(eintrag: Tuple[str, int]) -> Tuple[int, int]:
        geraet_id = eintrag[0]
        geraet = katalog.geraete.get(geraet_id) if katalog else None
        kategorie = geraet.kategorie if geraet else "sonstiges"
        hat_symbol = 0 if _symbol(geraet_id) else 1
        return (hat_symbol, KATEGORIE_RANG.get(kategorie, 5))

    return sorted(bedarf.items(), key=rang)[:hoechstens]


class _Massstab:
    """Rechnet Hallenmeter in Zeichenpunkte um."""

    def __init__(
        self,
        halle: Tuple[float, float],
        x: float,
        y: float,
        breite: float,
        hoehe: float,
    ) -> None:
        self.halle_laenge, self.halle_breite = halle
        self.faktor = min(breite / self.halle_laenge, hoehe / self.halle_breite)
        self.plan_breite = self.halle_laenge * self.faktor
        self.plan_hoehe = self.halle_breite * self.faktor
        self.x = x + (breite - self.plan_breite) / 2
        self.y = y + (hoehe - self.plan_hoehe) / 2

    def punkt(self, meter_x: float, meter_y: float) -> Tuple[float, float]:
        return (self.x + meter_x * self.faktor, self.y + meter_y * self.faktor)

    def laenge(self, meter: float) -> float:
        return meter * self.faktor

    def meter(self, punkt_x: float, punkt_y: float) -> Tuple[float, float]:
        return ((punkt_x - self.x) / self.faktor, (punkt_y - self.y) / self.faktor)


def massstab_fuer(
    stunde: Stunde, x: float, y: float, breite: float, hoehe: float
) -> _Massstab:
    return _Massstab(masse_der_stunde(stunde), x, y, breite, hoehe)


def _raster(z: Zeichner, massstab: _Massstab) -> None:
    """Meterraster wie auf kariertem Papier."""
    schritt = 1.0
    meter_x = schritt
    while meter_x < massstab.halle_laenge:
        von = massstab.punkt(meter_x, 0)
        bis = massstab.punkt(meter_x, massstab.halle_breite)
        z.linie(von[0], von[1], bis[0], bis[1], PLAN_RASTER, 0.3)
        meter_x += schritt
    meter_y = schritt
    while meter_y < massstab.halle_breite:
        von = massstab.punkt(0, meter_y)
        bis = massstab.punkt(massstab.halle_laenge, meter_y)
        z.linie(von[0], von[1], bis[0], bis[1], PLAN_RASTER, 0.3)
        meter_y += schritt


def _feste_geraete(z: Zeichner, ort: Optional[Ort], massstab: _Massstab) -> None:
    """Ortsfeste Geraete grau andeuten, damit der Plan die Halle zeigt."""
    if not ort:
        return
    for platz in ort.geraeteplaetze:
        links_unten = massstab.punkt(platz.x, platz.y)
        breite = massstab.laenge(platz.laenge)
        hoehe = massstab.laenge(platz.breite)
        z.rechteck(links_unten[0], links_unten[1], breite, hoehe, FEST_FARBE, 0.5)


def zeichne_hallenplan(
    z: Zeichner,
    stunde: Stunde,
    katalog: Optional[Katalog],
    x: float,
    y: float,
    breite: float,
    hoehe: float,
    ort: Optional[Ort] = None,
    mit_flaechen: bool = False,
    mit_namen: bool = False,
) -> _Massstab:
    """Zeichnet Halle, feste Geraete und die Stationen an ihren Positionen."""
    massstab = massstab_fuer(stunde, x, y, breite, hoehe)

    _raster(z, massstab)
    z.rechteck(
        massstab.x, massstab.y, massstab.plan_breite, massstab.plan_hoehe, PLAN_LINIE, 1.6
    )
    _feste_geraete(z, ort, massstab)

    masse = f"{massstab.halle_laenge:.0f} x {massstab.halle_breite:.0f} m"
    z.text(masse, massstab.x + 3, massstab.y - 9, 6.5, GRAUTON)

    stationen = stationen_der_stunde(stunde)
    if not stationen:
        z.text(
            "Kein Stationsaufbau - freie Flaeche",
            massstab.x + massstab.plan_breite / 2,
            massstab.y + massstab.plan_hoehe / 2,
            9,
            GRAUTON,
            zentriert=True,
        )
        return massstab

    for nummer, station in enumerate(stationen, start=1):
        zeichne_station(
            z,
            station,
            katalog,
            nummer,
            massstab,
            mit_flaeche=mit_flaechen,
            mit_namen=mit_namen,
        )
    return massstab


def zeichne_station(
    z: Zeichner,
    station: StundenUebung,
    katalog: Optional[Katalog],
    nummer: int,
    massstab: _Massstab,
    mit_flaeche: bool = False,
    farbe_rahmen: Optional[Farbe] = None,
    mit_namen: bool = False,
) -> None:
    """Zeichnet eine Station an ihrer Position in der Halle."""
    if not station.hat_position:
        return
    links_unten = massstab.punkt(station.x, station.y)
    breite = massstab.laenge(station.stell_laenge)
    hoehe = massstab.laenge(station.stell_breite)

    if mit_flaeche:
        z.flaeche(links_unten[0], links_unten[1], breite, hoehe, STATIONSFLAECHE)
    if farbe_rahmen is not None:
        z.rechteck(links_unten[0], links_unten[1], breite, hoehe, farbe_rahmen, 1.0)

    # Geraete massstaeblich in die Stellflaeche legen
    rand = min(0.4, station.stell_laenge * 0.08)
    cursor_x = station.x + rand
    zeilen_oben = station.y + station.stell_breite - rand
    zeilen_hoehe = 0.0
    for geraet_id, anzahl in _wichtigste_geraete(station, katalog):
        geraet_laenge, geraet_breite = GERAETEMASSE.get(geraet_id, STANDARDMASS)
        geraet_laenge = min(geraet_laenge, station.stell_laenge - 2 * rand)
        geraet_breite = min(geraet_breite, station.stell_breite - 2 * rand)
        if cursor_x + geraet_laenge > station.x + station.stell_laenge - rand:
            cursor_x = station.x + rand
            zeilen_oben -= zeilen_hoehe + 0.2
            zeilen_hoehe = 0.0
        if zeilen_oben - geraet_breite < station.y + rand:
            break
        zeichner = _symbol(geraet_id)
        ecke = massstab.punkt(cursor_x, zeilen_oben - geraet_breite)
        if zeichner:
            zeichner(
                z,
                ecke[0],
                ecke[1],
                massstab.laenge(geraet_laenge),
                massstab.laenge(geraet_breite),
            )
        else:
            z.rechteck(
                ecke[0],
                ecke[1],
                massstab.laenge(geraet_laenge),
                massstab.laenge(geraet_breite),
                GERAET_FARBE,
                0.6,
            )
        cursor_x += geraet_laenge + 0.25
        zeilen_hoehe = max(zeilen_hoehe, geraet_breite)

    # Nummernkreis oben links, Name darunter
    kreis_x = links_unten[0] + 8
    kreis_y = links_unten[1] + hoehe - 8
    z.kreis(kreis_x, kreis_y, 7.5, PLAN_LINIE, 1.0)
    z.text(str(nummer), kreis_x, kreis_y - 2.6, 8, PLAN_LINIE, fett=True, zentriert=True)

    if mit_namen:
        name = station.name
        while textbreite(name, 6.5) > breite - 4 and len(name) > 6:
            name = name[:-2]
        z.text(
            name,
            links_unten[0] + breite / 2,
            links_unten[1] + 3,
            6.5,
            BESCHRIFTUNG,
            zentriert=True,
        )


def station_an_punkt(
    stationen: Sequence[StundenUebung], massstab: _Massstab, punkt_x: float, punkt_y: float
) -> Optional[StundenUebung]:
    """Welche Station liegt unter diesem Zeichenpunkt? (fuer die Oberflaeche)"""
    meter_x, meter_y = massstab.meter(punkt_x, punkt_y)
    for station in reversed(list(stationen)):
        if not station.hat_position:
            continue
        if (
            station.x <= meter_x <= station.x + station.stell_laenge
            and station.y <= meter_y <= station.y + station.stell_breite
        ):
            return station
    return None
