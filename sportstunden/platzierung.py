"""Platzierung der Stationen an ihren tatsaechlichen Positionen in der Halle.

Koordinatensystem: Meter, Ursprung linke untere Ecke der Flaeche. ``x`` laeuft
entlang der Hallenlaenge, ``y`` entlang der Hallenbreite.

Stationen mit ortsfesten Geraeten (Sprossenwand, Reck, Ringe, Tau ...) werden an
den beim Ort hinterlegten Geraeteplaetzen verankert. Alle uebrigen Stationen
werden auf der freien Flaeche verteilt - im Uhrzeigersinn, damit ein Rundlauf
entsteht.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .katalog import Katalog
from .models import Geraeteplatz, Ort, Stunde, StundenUebung

# Grundflaechen der Geraete in Metern (Laenge x Breite).
GERAETEMASSE: Dict[str, Tuple[float, float]] = {
    "kasten_gross": (1.6, 0.8),
    "kasten_klein": (1.2, 0.6),
    "kastenteil": (1.2, 0.6),
    "langbank": (4.0, 0.4),
    "schwebebalken": (5.0, 0.6),
    "barren": (3.5, 1.6),
    "reck": (2.4, 0.8),
    "ringe": (1.6, 1.6),
    "tau": (1.2, 1.2),
    "sprossenwand": (2.5, 0.4),
    "klettergeruest": (3.0, 0.8),
    "minitrampolin": (1.2, 1.2),
    "sprungbrett": (1.2, 0.6),
    "matte": (2.0, 1.0),
    "weichbodenmatte": (3.0, 2.0),
    "niedersprungmatte": (3.0, 2.0),
    "schwungtuch": (3.5, 3.5),
    "koordinationsleiter": (4.0, 0.6),
    "reifen": (0.9, 0.9),
    "rollbrett": (0.5, 0.4),
    "pedalo": (0.6, 0.4),
    "teppichfliese": (0.5, 0.5),
    "baustein": (0.5, 0.3),
    "eimer": (0.4, 0.4),
    "kleintor": (1.6, 0.6),
    "huerde_klein": (0.6, 0.4),
    "huetchen": (0.3, 0.3),
    "markierungsteller": (0.3, 0.3),
    "seil_lang": (3.0, 0.3),
    "springseil": (0.4, 0.4),
    "gummiband": (2.0, 0.3),
}
STANDARDMASS = (0.6, 0.6)

# Geraete, die fest an ihrem Platz stehen bzw. haengen.
ORTSFESTE_GERAETE = (
    "sprossenwand",
    "reck",
    "barren",
    "ringe",
    "tau",
    "klettergeruest",
    "schwebebalken",
)

WANDABSTAND = 0.8          # Mindestabstand zur Hallenwand
SICHERHEITSRAND = 0.9      # Freiraum rings um eine Station
SICHERHEITSRAND_SPRUNG = 1.4  # mehr Freiraum bei Sprung- und Kletterstationen
RASTER = 0.5               # Suchraster in Metern
MAX_STATIONSLAENGE = 9.0
MAX_STATIONSBREITE = 7.0

Rechteck = Tuple[float, float, float, float]  # x, y, laenge, breite


# ---------------------------------------------------------------------------
# Geometrie
# ---------------------------------------------------------------------------


def _ueberlappt(a: Rechteck, b: Rechteck) -> bool:
    ax, ay, al, ab = a
    bx, by, bl, bb = b
    return not (ax + al <= bx or bx + bl <= ax or ay + ab <= by or by + bb <= ay)


def _geraetflaeche(geraet_id: str, anzahl: int) -> Tuple[float, float]:
    """Platzbedarf fuer ``anzahl`` Exemplare eines Geraetes."""
    laenge, breite = GERAETEMASSE.get(geraet_id, STANDARDMASS)
    anzahl = max(1, int(anzahl))
    spalten = max(1, math.ceil(math.sqrt(anzahl)))
    zeilen = max(1, math.ceil(anzahl / spalten))
    return laenge * spalten, breite * zeilen


def braucht_ortsfestes_geraet(station: StundenUebung) -> Optional[str]:
    """Das ortsfeste Geraet der Station - oder None."""
    for geraet_id in ORTSFESTE_GERAETE:
        if geraet_id in station.gesamtbedarf:
            return geraet_id
    return None


def stellflaeche(station: StundenUebung, katalog: Optional[Katalog] = None) -> Tuple[float, float]:
    """Platzbedarf der Station inklusive Sicherheitsrand (Laenge, Breite).

    Die Geraete werden nicht in einer langen Reihe gedacht, sondern kompakt
    nebeneinander und hintereinander - so, wie eine Station wirklich aufgebaut
    wird. Aus der Summe der Grundflaechen entsteht ein Rechteck im Verhaeltnis
    von etwa 3:2, das mindestens so lang ist wie das laengste Geraet.
    """
    bedarf = station.gesamtbedarf
    if not bedarf:
        return (2.5, 2.5)

    flaeche = 0.0
    laengstes = 0.0
    breitestes = 0.0
    for geraet_id, anzahl in sorted(bedarf.items()):
        teil_laenge, teil_breite = _geraetflaeche(geraet_id, anzahl)
        flaeche += teil_laenge * teil_breite
        einzeln_laenge, einzeln_breite = GERAETEMASSE.get(geraet_id, STANDARDMASS)
        laengstes = max(laengstes, einzeln_laenge)
        breitestes = max(breitestes, einzeln_breite)

    flaeche *= 1.6  # Luft zwischen den Geraeten
    laenge = max(laengstes, math.sqrt(flaeche * 1.5))
    breite = max(breitestes, flaeche / laenge)

    rand = SICHERHEITSRAND
    if station.absicherung or braucht_ortsfestes_geraet(station):
        rand = SICHERHEITSRAND_SPRUNG

    laenge = min(MAX_STATIONSLAENGE, laenge) + rand
    breite = min(MAX_STATIONSBREITE, breite) + rand
    return (round(laenge, 2), round(breite, 2))


# ---------------------------------------------------------------------------
# Platzierung
# ---------------------------------------------------------------------------


def _rasterpunkte(
    halle: Tuple[float, float], flaeche: Tuple[float, float]
) -> List[Tuple[float, float]]:
    halle_laenge, halle_breite = halle
    laenge, breite = flaeche
    max_x = halle_laenge - WANDABSTAND - laenge
    max_y = halle_breite - WANDABSTAND - breite
    if max_x < WANDABSTAND:
        max_x = max(0.0, (halle_laenge - laenge) / 2)
    if max_y < WANDABSTAND:
        max_y = max(0.0, (halle_breite - breite) / 2)

    punkte: List[Tuple[float, float]] = []
    x = min(WANDABSTAND, max_x)
    while x <= max_x + 1e-6:
        y = min(WANDABSTAND, max_y)
        while y <= max_y + 1e-6:
            punkte.append((round(x, 2), round(y, 2)))
            y += RASTER
        x += RASTER
    if not punkte:
        punkte.append((0.0, 0.0))
    return punkte


def _naechster_freier_platz(
    ziel: Tuple[float, float],
    flaeche: Tuple[float, float],
    halle: Tuple[float, float],
    belegt: Sequence[Rechteck],
    hoechstabstand: Optional[float] = None,
) -> Optional[Tuple[float, float]]:
    """Freie Position, deren Mitte dem Ziel am naechsten liegt."""
    laenge, breite = flaeche
    beste: Optional[Tuple[float, float]] = None
    bester_abstand = float("inf")
    for x, y in _rasterpunkte(halle, flaeche):
        mitte_x = x + laenge / 2
        mitte_y = y + breite / 2
        abstand = math.hypot(mitte_x - ziel[0], mitte_y - ziel[1])
        if abstand >= bester_abstand:
            continue
        if hoechstabstand is not None and abstand > hoechstabstand:
            continue
        kandidat = (x, y, laenge, breite)
        if any(_ueberlappt(kandidat, anderes) for anderes in belegt):
            continue
        beste = (x, y)
        bester_abstand = abstand
    return beste


def _ringziel(
    index: int, anzahl: int, halle: Tuple[float, float]
) -> Tuple[float, float]:
    """Zielpunkt auf einem Ring - im Uhrzeigersinn, oben links beginnend."""
    halle_laenge, halle_breite = halle
    mitte_x, mitte_y = halle_laenge / 2, halle_breite / 2
    radius_x = halle_laenge * 0.32
    radius_y = halle_breite * 0.30
    winkel = math.pi / 2 + 2 * math.pi * (index / max(1, anzahl))
    return (
        mitte_x + radius_x * math.cos(winkel),
        mitte_y + radius_y * math.sin(winkel),
    )


def _platz_rechteck(platz: Geraeteplatz) -> Rechteck:
    return (platz.x, platz.y, platz.laenge, platz.breite)


def platziere(
    stunde: Stunde,
    ort: Ort,
    katalog: Optional[Katalog] = None,
    stationen: Optional[List[StundenUebung]] = None,
) -> List[str]:
    """Setzt alle Stationen der Stunde auf ihre Positionen in der Halle.

    Gibt Hinweise zurueck, wenn eine Station nur mit Kompromiss passt.
    """
    if stationen is None:
        teil = stunde.teil("hauptteil")
        stationen = list(teil.uebungen) if teil else []
    if not stationen:
        stunde.ort_laenge = ort.laenge
        stunde.ort_breite = ort.breite
        return []

    halle = (ort.laenge, ort.breite)
    hinweise: List[str] = []
    belegt: List[Rechteck] = []
    # Feste Geraeteplaetze sind fuer mobile Stationen tabu.
    freie_plaetze: Dict[str, List[Geraeteplatz]] = {}
    for platz in ort.geraeteplaetze:
        freie_plaetze.setdefault(platz.geraet, []).append(platz)
    blockiert: List[Rechteck] = [_platz_rechteck(p) for p in ort.geraeteplaetze]

    verankert: List[Tuple[StundenUebung, Geraeteplatz]] = []
    mobil: List[StundenUebung] = []
    for station in stationen:
        geraet_id = braucht_ortsfestes_geraet(station)
        plaetze = freie_plaetze.get(geraet_id or "", [])
        if geraet_id and plaetze:
            platz = plaetze.pop(0)
            verankert.append((station, platz))
        else:
            if geraet_id:
                hinweise.append(
                    f"Fuer '{station.name}' ist am Ort kein fester Platz fuer "
                    f"{katalog.geraet_name(geraet_id) if katalog else geraet_id} "
                    "hinterlegt - die Station wurde frei gesetzt."
                )
            mobil.append(station)

    # 1. Stationen an ihren festen Geraeten
    for station, platz in verankert:
        laenge, breite = stellflaeche(station, katalog)
        laenge = min(laenge, ort.laenge - 0.2)
        breite = min(breite, ort.breite - 0.2)
        mitte_x, mitte_y = platz.mitte
        ziel_x = min(max(mitte_x - laenge / 2, 0.1), ort.laenge - laenge - 0.1)
        ziel_y = min(max(mitte_y - breite / 2, 0.1), ort.breite - breite - 0.1)
        # Der eigene Geraeteplatz ist kein Hindernis - die Station gehoert dorthin.
        hindernisse = belegt + [
            r for r in blockiert if r != _platz_rechteck(platz)
        ]
        kandidat = (ziel_x, ziel_y, laenge, breite)
        if any(_ueberlappt(kandidat, anderes) for anderes in hindernisse):
            # In der Naehe des Geraetes einen freien Platz suchen.
            ausweich = None
            for radius in (2.5, 4.0):
                ausweich = _naechster_freier_platz(
                    (mitte_x, mitte_y),
                    (laenge, breite),
                    halle,
                    hindernisse,
                    hoechstabstand=radius,
                )
                if ausweich:
                    break
            if ausweich:
                ziel_x, ziel_y = ausweich
            else:
                hinweise.append(
                    f"'{station.name}' steht dicht an einer anderen Station - "
                    "Abstaende vor Ort pruefen."
                )
        _setze(station, ziel_x, ziel_y, laenge, breite)
        belegt.append((ziel_x, ziel_y, laenge, breite))

    # 2. Freie Stationen im Uhrzeigersinn verteilen
    gesamt = len(stationen)
    for nummer, station in enumerate(mobil):
        laenge, breite = stellflaeche(station, katalog)
        laenge = min(laenge, max(1.0, ort.laenge - 2 * WANDABSTAND))
        breite = min(breite, max(1.0, ort.breite - 2 * WANDABSTAND))
        index = stationen.index(station)
        ziel = _ringziel(index, gesamt, halle)
        position = _naechster_freier_platz(
            ziel, (laenge, breite), halle, belegt + blockiert
        )
        if position is None:
            position = (
                min(max(ziel[0] - laenge / 2, 0.1), max(0.1, ort.laenge - laenge - 0.1)),
                min(max(ziel[1] - breite / 2, 0.1), max(0.1, ort.breite - breite - 0.1)),
            )
            hinweise.append(
                f"Fuer '{station.name}' ist die Flaeche knapp - Aufbau vor Ort pruefen."
            )
        _setze(station, position[0], position[1], laenge, breite)
        belegt.append((position[0], position[1], laenge, breite))

    stunde.ort_laenge = ort.laenge
    stunde.ort_breite = ort.breite
    return hinweise


def _setze(
    station: StundenUebung, x: float, y: float, laenge: float, breite: float
) -> None:
    station.x = round(x, 2)
    station.y = round(y, 2)
    station.stell_laenge = round(laenge, 2)
    station.stell_breite = round(breite, 2)


def stelle_sicher(
    stunde: Stunde, ort: Optional[Ort], katalog: Optional[Katalog] = None
) -> List[str]:
    """Platziert nachtraeglich, wenn eine Stunde noch keine Positionen hat."""
    teil = stunde.teil("hauptteil")
    stationen = list(teil.uebungen) if teil else []
    if not stationen or all(s.hat_position for s in stationen):
        if stunde.ort_laenge <= 0 and ort is not None:
            stunde.ort_laenge, stunde.ort_breite = ort.laenge, ort.breite
        return []
    if ort is None:
        ort = Ort(
            id=stunde.ort_id or "unbekannt",
            name=stunde.ort_name or "Halle",
            art=stunde.ortsart or "halle",
            laenge=stunde.ort_laenge or 27.0,
            breite=stunde.ort_breite or 15.0,
        )
    return platziere(stunde, ort, katalog, stationen)


def masse_der_stunde(stunde: Stunde) -> Tuple[float, float]:
    """Hallenmasse der Stunde - mit sinnvollen Standardwerten."""
    laenge = stunde.ort_laenge if stunde.ort_laenge > 0 else 27.0
    breite = stunde.ort_breite if stunde.ort_breite > 0 else 15.0
    return (laenge, breite)


def passt_in_halle(
    station: StundenUebung, halle: Tuple[float, float]
) -> bool:
    return (
        station.x >= -0.01
        and station.y >= -0.01
        and station.x + station.stell_laenge <= halle[0] + 0.01
        and station.y + station.stell_breite <= halle[1] + 0.01
    )


def konflikte(
    stationen: Iterable[StundenUebung], ort: Optional[Ort] = None
) -> List[Tuple[str, str]]:
    """Alle Probleme im Aufbau: Ueberlappungen und besetzte Geraeteplaetze."""
    liste = [s for s in stationen if s.hat_position]
    treffer: List[Tuple[str, str]] = list(kollisionen(liste))
    if ort is None:
        return treffer
    for station in liste:
        eigenes = braucht_ortsfestes_geraet(station)
        for platz in ort.geraeteplaetze:
            if platz.geraet == eigenes:
                continue
            if _ueberlappt(
                (station.x, station.y, station.stell_laenge, station.stell_breite),
                _platz_rechteck(platz),
            ):
                treffer.append((platz.geraet, station.name))
    return treffer


def kollisionen(stationen: Iterable[StundenUebung]) -> List[Tuple[str, str]]:
    """Paare von Stationen, deren Stellflaechen sich ueberlappen."""
    liste = [s for s in stationen if s.hat_position]
    treffer: List[Tuple[str, str]] = []
    for index, erste in enumerate(liste):
        for zweite in liste[index + 1 :]:
            if _ueberlappt(
                (erste.x, erste.y, erste.stell_laenge, erste.stell_breite),
                (zweite.x, zweite.y, zweite.stell_laenge, zweite.stell_breite),
            ):
                treffer.append((erste.name, zweite.name))
    return treffer
