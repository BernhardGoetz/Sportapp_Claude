"""Stil-Lernen: aus eigenen Stunden den Planungsstil des Nutzers ableiten.

Der Stil wird pro Altersgruppe gelernt. Weil einzelne Altersgruppen anfangs
nur wenige Beispielstunden haben, wird in drei Stufen gemischt:

    Neutralprofil  ->  Gesamtstil des Nutzers  ->  Stil dieser Altersgruppe

Je mehr eigene Stunden vorliegen, desto staerker zaehlt die speziellere Stufe.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .katalog import Katalog
from .models import Altersgruppe, Stunde, Uebung

# Wie schnell der gelernte Stil das Neutralprofil verdraengt (Shrinkage).
LERNTRAEGHEIT = 2.0
# Grenzen fuer gelernte Gewichte, damit einzelne Ausreisser nicht dominieren.
GEWICHT_GRENZE = 1.2

NEUTRALE_PHASEN_ANTEILE = {
    "aufwaermen": 0.20,
    "koordination": 0.13,
    "hauptteil": 0.52,
    "abschluss": 0.15,
}

# Kinderturnen: ein Anfangsspiel, ein Koordinationsteil, eine
# Bewegungslandschaft mit mehreren Stationen, ein Abschlussspiel.
NEUTRALE_UEBUNGSZAHL = {
    "aufwaermen": 1.1,
    "koordination": 1.0,
    "hauptteil": 5.0,
    "abschluss": 1.1,
}


def _mischen(a: float, b: float, gewicht: float) -> float:
    return a * (1.0 - gewicht) + b * gewicht


def _mische_dicts(
    a: Dict[str, float], b: Dict[str, float], gewicht: float
) -> Dict[str, float]:
    ergebnis: Dict[str, float] = {}
    for schluessel in set(a) | set(b):
        ergebnis[schluessel] = _mischen(
            a.get(schluessel, 0.0), b.get(schluessel, 0.0), gewicht
        )
    return ergebnis


def _normiere_anteile(anteile: Dict[str, float], phasen: Iterable[str]) -> Dict[str, float]:
    phasen = list(phasen)
    werte = {p: max(0.05, anteile.get(p, NEUTRALE_PHASEN_ANTEILE.get(p, 0.2))) for p in phasen}
    summe = sum(werte.values()) or 1.0
    return {p: w / summe for p, w in werte.items()}


@dataclass
class Stilprofil:
    """Der gelernte Planungsstil - immer bezogen auf eine Altersgruppe."""

    altersgruppe_id: str = ""
    stichprobe: int = 0
    phasen_anteile: Dict[str, float] = field(
        default_factory=lambda: dict(NEUTRALE_PHASEN_ANTEILE)
    )
    uebungen_pro_phase: Dict[str, float] = field(
        default_factory=lambda: dict(NEUTRALE_UEBUNGSZAHL)
    )
    tag_gewichte: Dict[str, float] = field(default_factory=dict)
    organisation_gewichte: Dict[str, float] = field(default_factory=dict)
    geraete_gewichte: Dict[str, float] = field(default_factory=dict)
    lieblingsuebungen: Dict[str, float] = field(default_factory=dict)
    intensitaet: float = 3.0
    stationsanteil: float = 0.75

    # -- Bewertung ---------------------------------------------------------
    def bewerte(self, uebung: Uebung) -> float:
        """Wie gut passt eine Uebung zum Stil? Hoeher ist besser."""
        punkte = 1.0
        for tag in uebung.tags:
            punkte += self.tag_gewichte.get(tag, 0.0)
        punkte += self.organisation_gewichte.get(uebung.organisation, 0.0)

        geraete = list(uebung.geraete_fix) + list(uebung.geraete_pro_gruppe)
        if geraete:
            punkte += 0.5 * sum(
                self.geraete_gewichte.get(g, 0.0) for g in geraete
            ) / len(geraete)

        punkte += 1.5 * self.lieblingsuebungen.get(uebung.id, 0.0)
        punkte -= 0.15 * abs(uebung.intensitaet - self.intensitaet)
        return punkte

    def anteile_fuer(self, phasen: Iterable[str]) -> Dict[str, float]:
        return _normiere_anteile(self.phasen_anteile, phasen)

    def uebungszahl(self, phase: str) -> float:
        return self.uebungen_pro_phase.get(
            phase, NEUTRALE_UEBUNGSZAHL.get(phase, 1.5)
        )

    # -- Darstellung -------------------------------------------------------
    def beschreibung(self, katalog: Optional[Katalog] = None) -> List[str]:
        zeilen: List[str] = []
        if self.stichprobe == 0:
            zeilen.append(
                "Noch keine eigenen Stunden gelernt - es wird neutral geplant."
            )
        else:
            zeilen.append(f"Gelernt aus {self.stichprobe} eigenen Stunde(n).")
        anteile = ", ".join(
            f"{phase} {round(anteil * 100)}%"
            for phase, anteil in sorted(
                self.phasen_anteile.items(), key=lambda x: -x[1]
            )
        )
        zeilen.append(f"Zeitaufteilung: {anteile}")
        zeilen.append(
            "Uebungen je Teil: "
            + ", ".join(
                f"{phase} {zahl:.1f}"
                for phase, zahl in sorted(self.uebungen_pro_phase.items())
            )
        )
        zeilen.append(f"Ziel-Intensitaet: {self.intensitaet:.1f} von 5")
        zeilen.append(f"Anteil Stations-/Gruppenbetrieb: {self.stationsanteil * 100:.0f}%")

        mag = sorted(self.tag_gewichte.items(), key=lambda x: -x[1])
        bevorzugt = [t for t, w in mag if w > 0.15][:6]
        gemieden = [t for t, w in sorted(self.tag_gewichte.items(), key=lambda x: x[1]) if w < -0.15][:4]
        if bevorzugt:
            zeilen.append("Bevorzugte Inhalte: " + ", ".join(bevorzugt))
        if gemieden:
            zeilen.append("Seltener genutzt: " + ", ".join(gemieden))

        lieblinge = sorted(self.lieblingsuebungen.items(), key=lambda x: -x[1])[:5]
        if lieblinge and katalog is not None:
            namen = []
            for uebung_id, wert in lieblinge:
                uebung = katalog.uebung(uebung_id)
                namen.append(f"{uebung.name if uebung else uebung_id} ({wert:.2f})")
            zeilen.append("Lieblingsuebungen: " + ", ".join(namen))
        return zeilen

    def to_dict(self) -> Dict[str, object]:
        return {
            "altersgruppe_id": self.altersgruppe_id,
            "stichprobe": self.stichprobe,
            "phasen_anteile": self.phasen_anteile,
            "uebungen_pro_phase": self.uebungen_pro_phase,
            "tag_gewichte": self.tag_gewichte,
            "organisation_gewichte": self.organisation_gewichte,
            "geraete_gewichte": self.geraete_gewichte,
            "lieblingsuebungen": self.lieblingsuebungen,
            "intensitaet": self.intensitaet,
            "stationsanteil": self.stationsanteil,
        }


class Stillernen:
    """Wertet die eigenen Stunden des Nutzers aus."""

    def __init__(self, katalog: Katalog, stunden: Iterable[Stunde]) -> None:
        self.katalog = katalog
        self.stunden = [s for s in stunden if s.ist_eigene]
        self._basis_tags = self._basisfrequenz(lambda u: u.tags)
        self._basis_organisation = self._basisfrequenz(lambda u: [u.organisation])
        self._basis_geraete = self._basisfrequenz(
            lambda u: list(u.geraete_fix) + list(u.geraete_pro_gruppe)
        )
        self._gesamtprofil = self._profil_aus(self.stunden, "")
        self._cache: Dict[str, Stilprofil] = {}

    # -- Basisfrequenzen des Katalogs -------------------------------------
    def _basisfrequenz(self, merkmale) -> Dict[str, float]:
        zaehler: Counter = Counter()
        for uebung in self.katalog.uebungen:
            zaehler.update(set(merkmale(uebung)))
        gesamt = max(1, len(self.katalog.uebungen))
        return {schluessel: anzahl / gesamt for schluessel, anzahl in zaehler.items()}

    @staticmethod
    def _gewicht(anteil_nutzer: float, anteil_basis: float) -> float:
        wert = math.log((anteil_nutzer + 0.02) / (anteil_basis + 0.02))
        return max(-GEWICHT_GRENZE, min(GEWICHT_GRENZE, wert))

    # -- Profilberechnung --------------------------------------------------
    def _profil_aus(self, stunden: List[Stunde], gruppen_id: str) -> Stilprofil:
        profil = Stilprofil(altersgruppe_id=gruppen_id, stichprobe=len(stunden))
        if not stunden:
            return profil

        anteile: Dict[str, List[float]] = {}
        zahlen: Dict[str, List[float]] = {}
        tag_zaehler: Counter = Counter()
        org_zaehler: Counter = Counter()
        geraete_zaehler: Counter = Counter()
        uebungs_zaehler: Counter = Counter()
        intensitaeten: List[float] = []
        gewichte: List[float] = []
        stationen = 0
        teile_gesamt = 0
        uebungen_gesamt = 0

        for stunde in stunden:
            gesamt = max(1, stunde.gesamtdauer)
            for teil in stunde.teile:
                anteile.setdefault(teil.phase, []).append(teil.dauer / gesamt)
                zahlen.setdefault(teil.phase, []).append(len(teil.uebungen))
                teile_gesamt += 1
                if teil.parallel:
                    stationen += 1
                for uebung in teil.uebungen:
                    uebungen_gesamt += 1
                    tag_zaehler.update(set(uebung.tags))
                    org_zaehler.update([uebung.organisation])
                    geraete_zaehler.update(set(uebung.geraete) | set(uebung.absicherung))
                    if uebung.uebung_id:
                        uebungs_zaehler.update([uebung.uebung_id])
                    intensitaeten.append(uebung.intensitaet)
                    gewichte.append(max(1, uebung.dauer))

        profil.phasen_anteile = {
            phase: sum(werte) / len(werte) for phase, werte in anteile.items()
        }
        profil.uebungen_pro_phase = {
            phase: sum(werte) / len(werte) for phase, werte in zahlen.items()
        }

        anzahl_uebungen = max(1, uebungen_gesamt)
        profil.tag_gewichte = {
            tag: self._gewicht(anzahl / anzahl_uebungen, self._basis_tags.get(tag, 0.0))
            for tag, anzahl in tag_zaehler.items()
        }
        profil.organisation_gewichte = {
            org: self._gewicht(
                anzahl / anzahl_uebungen, self._basis_organisation.get(org, 0.0)
            )
            for org, anzahl in org_zaehler.items()
        }
        profil.geraete_gewichte = {
            geraet: self._gewicht(
                anzahl / anzahl_uebungen, self._basis_geraete.get(geraet, 0.0)
            )
            for geraet, anzahl in geraete_zaehler.items()
        }
        profil.lieblingsuebungen = {
            uebung_id: anzahl / len(stunden)
            for uebung_id, anzahl in uebungs_zaehler.items()
        }
        if intensitaeten:
            profil.intensitaet = sum(
                i * g for i, g in zip(intensitaeten, gewichte)
            ) / sum(gewichte)
        if teile_gesamt:
            profil.stationsanteil = stationen / teile_gesamt
        return profil

    def _mische(self, basis: Stilprofil, spezifisch: Stilprofil) -> Stilprofil:
        n = spezifisch.stichprobe
        gewicht = n / (n + LERNTRAEGHEIT) if n else 0.0
        gemischt = Stilprofil(
            altersgruppe_id=spezifisch.altersgruppe_id or basis.altersgruppe_id,
            stichprobe=n,
            phasen_anteile=_mische_dicts(
                basis.phasen_anteile, spezifisch.phasen_anteile, gewicht
            )
            if n
            else dict(basis.phasen_anteile),
            uebungen_pro_phase=_mische_dicts(
                basis.uebungen_pro_phase, spezifisch.uebungen_pro_phase, gewicht
            )
            if n
            else dict(basis.uebungen_pro_phase),
            tag_gewichte=_mische_dicts(
                basis.tag_gewichte, spezifisch.tag_gewichte, gewicht
            ),
            organisation_gewichte=_mische_dicts(
                basis.organisation_gewichte, spezifisch.organisation_gewichte, gewicht
            ),
            geraete_gewichte=_mische_dicts(
                basis.geraete_gewichte, spezifisch.geraete_gewichte, gewicht
            ),
            lieblingsuebungen=_mische_dicts(
                basis.lieblingsuebungen, spezifisch.lieblingsuebungen, gewicht
            ),
            intensitaet=_mischen(basis.intensitaet, spezifisch.intensitaet, gewicht),
            stationsanteil=_mischen(
                basis.stationsanteil, spezifisch.stationsanteil, gewicht
            ),
        )
        return gemischt

    # -- Oeffentliche Schnittstelle ---------------------------------------
    def gesamtprofil(self) -> Stilprofil:
        """Stil ueber alle Altersgruppen hinweg."""
        return self._mische(Stilprofil(), self._gesamtprofil)

    def profil(self, altersgruppe: Optional[Altersgruppe]) -> Stilprofil:
        """Stil fuer eine Altersgruppe - faellt weich auf den Gesamtstil zurueck."""
        gruppen_id = altersgruppe.id if altersgruppe else ""
        if gruppen_id in self._cache:
            return self._cache[gruppen_id]

        basis = self.gesamtprofil()
        if not gruppen_id:
            self._cache[gruppen_id] = basis
            return basis

        eigene = [s for s in self.stunden if s.altersgruppe_id == gruppen_id]
        profil = self._mische(basis, self._profil_aus(eigene, gruppen_id))
        profil.altersgruppe_id = gruppen_id
        self._cache[gruppen_id] = profil
        return profil

    def stichproben(self) -> Dict[str, int]:
        zaehler: Counter = Counter(s.altersgruppe_id for s in self.stunden)
        return dict(zaehler)
