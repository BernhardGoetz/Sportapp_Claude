"""Planungslogik: baut aus Katalog, Ort, Gruppe und Stil eine Kinderturnstunde.

Harte Regel: Der gleichzeitige Geraetebedarf einer Stunde darf den Bestand
des gewaehlten Ortes niemals uebersteigen - die Absicherung (Matten,
Weichboden, Niedersprungmatten) zaehlt dabei voll mit.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .katalog import Katalog
from .models import (
    Altersgruppe,
    Ort,
    PHASEN_TITEL,
    Stunde,
    StundenUebung,
    Stundenteil,
    Uebung,
    neue_id,
)
from .platzierung import konflikte, platziere, stellflaeche
from .stil import Stilprofil

MINDESTDAUER_TEIL = 4

# Stationszahl und Flaechenbudget der Bewegungslandschaft
MIN_STATIONEN = 3
MAX_STATIONEN = 8
WANDSTREIFEN = 1.0          # Streifen an der Wand, der frei bleibt
BELEGUNGSFAKTOR = 0.6       # Rest der Flaeche bleibt Laufweg
MITTLERE_STATIONSFLAECHE = 22.0  # Richtwert je Station in Quadratmetern
STANDARD_RIEGEN = 3         # Riegen, wenn keine Stationen geplant werden


@dataclass
class Planungsauftrag:
    ort: Ort
    altersgruppe: Altersgruppe
    dauer: int = 60
    schwerpunkt: str = ""
    titel: str = ""
    ueberschrift: str = ""
    datum: str = ""
    ausstattung: Optional[Dict[str, int]] = None
    umbau_zwischen_teilen: bool = True
    koordinationsteil: Optional[bool] = None
    thema: str = ""
    stationsbetrieb: Optional[bool] = None
    stationszahl: Optional[int] = None
    seed: Optional[int] = None

    def verfuegbare_ausstattung(self) -> Dict[str, int]:
        """Ausstattung fuer diese Planung - Standard ist die des Ortes."""
        if self.ausstattung is None:
            return dict(self.ort.ausstattung)
        return {k: int(v) for k, v in self.ausstattung.items() if int(v) > 0}


@dataclass
class Planungsergebnis:
    stunde: Stunde
    warnungen: List[str] = field(default_factory=list)
    sicherheitshinweise: List[str] = field(default_factory=list)
    bestand: Dict[str, int] = field(default_factory=dict)


class Planungsfehler(RuntimeError):
    """Wird ausgeloest, wenn mit dem Bestand keine Stunde planbar ist."""


class Planer:
    def __init__(self, katalog: Katalog, stilprofil: Optional[Stilprofil] = None) -> None:
        self.katalog = katalog
        self.stil = stilprofil or Stilprofil()

    # -- Kandidatenauswahl -------------------------------------------------
    def kandidaten(
        self,
        phase: str,
        auftrag: Planungsauftrag,
    ) -> List[Uebung]:
        gruppe = auftrag.altersgruppe
        treffer: List[Uebung] = []
        for uebung in self.katalog.uebungen:
            if uebung.phase != phase:
                continue
            if auftrag.ort.art not in uebung.orte:
                continue
            if not uebung.passt_zu_alter(gruppe.alter_min, gruppe.alter_max):
                continue
            if uebung.intensitaet > gruppe.max_intensitaet:
                continue
            if phase == "koordination" and gruppe.koordination_schwerpunkte:
                if not set(uebung.koordination) & set(gruppe.koordination_schwerpunkte):
                    continue
            treffer.append(uebung)
        return treffer

    def _bewertung(
        self,
        uebung: Uebung,
        auftrag: Planungsauftrag,
        phase: str,
        zufall: random.Random,
    ) -> float:
        punkte = self.stil.bewerte(uebung)

        if auftrag.schwerpunkt:
            schwerpunkt = auftrag.schwerpunkt.lower()
            if schwerpunkt in [t.lower() for t in uebung.tags]:
                punkte += 1.6
            elif schwerpunkt in uebung.name.lower():
                punkte += 0.8

        if auftrag.thema:
            if uebung.thema == auftrag.thema:
                punkte += 1.2
            elif uebung.thema:
                punkte -= 0.3

        gruppe = auftrag.altersgruppe
        if phase == "koordination":
            treffer = set(uebung.koordination) & set(gruppe.koordination_schwerpunkte)
            punkte += 0.4 * len(treffer)
            druck = set(uebung.druckbedingungen) & set(gruppe.druckbedingungen)
            punkte += 0.2 * len(druck)

        # Uebungen, deren Altersfenster die Gruppe gut umschliesst, bevorzugen.
        ueberlappung = min(uebung.alter_max, gruppe.alter_max) - max(
            uebung.alter_min, gruppe.alter_min
        )
        if ueberlappung >= (gruppe.alter_max - gruppe.alter_min):
            punkte += 0.3

        punkte += zufall.uniform(0.0, 0.35)
        return punkte

    # -- Bedarfspruefung ---------------------------------------------------
    def _passt_in_bestand(
        self,
        bedarf: Dict[str, int],
        rest: Dict[str, int],
    ) -> bool:
        return all(rest.get(geraet, 0) >= anzahl for geraet, anzahl in bedarf.items())

    def _buche(self, bedarf: Dict[str, int], rest: Dict[str, int]) -> None:
        for geraet, anzahl in bedarf.items():
            rest[geraet] = rest.get(geraet, 0) - anzahl

    # -- Dauerverteilung ---------------------------------------------------
    @staticmethod
    def _phasendauern(
        gesamt: int, phasen: Sequence[str], anteile: Dict[str, float]
    ) -> Dict[str, int]:
        roh = {phase: gesamt * anteile.get(phase, 0.0) for phase in phasen}
        dauern = {phase: max(MINDESTDAUER_TEIL, int(wert)) for phase, wert in roh.items()}

        # Rest bzw. Ueberhang minutengenau ausgleichen.
        differenz = gesamt - sum(dauern.values())
        reihenfolge = sorted(phasen, key=lambda p: -roh[p])
        index = 0
        while differenz != 0 and reihenfolge:
            phase = reihenfolge[index % len(reihenfolge)]
            if differenz > 0:
                dauern[phase] += 1
                differenz -= 1
            elif dauern[phase] > MINDESTDAUER_TEIL:
                dauern[phase] -= 1
                differenz += 1
            elif all(dauern[p] <= MINDESTDAUER_TEIL for p in reihenfolge):
                break
            index += 1
        return dauern

    @staticmethod
    def _verteile_dauern(uebungen: List[Uebung], ziel: int) -> List[int]:
        """Verteilt das Zeitfenster auf die Uebungen (Rest wird zu Puffer)."""
        if not uebungen:
            return []
        dauern = [u.dauer_vorschlag() for u in uebungen]

        while sum(dauern) > ziel:
            spielraum = [
                index for index, u in enumerate(uebungen) if dauern[index] > u.dauer_min
            ]
            if not spielraum:
                break
            groesster = max(spielraum, key=lambda i: dauern[i])
            dauern[groesster] -= 1

        # Nach oben nur bis zur Maximaldauer, im Notfall bis 130 Prozent davon.
        for grenze in (1.0, 1.3):
            while sum(dauern) < ziel:
                spielraum = [
                    index
                    for index, u in enumerate(uebungen)
                    if dauern[index] < int(u.dauer_max * grenze)
                ]
                if not spielraum:
                    break
                kleinster = min(spielraum, key=lambda i: dauern[i])
                dauern[kleinster] += 1

        # Zu lang darf die Stunde nie werden - notfalls wird gekuerzt.
        ueberhang = sum(dauern) - ziel
        while ueberhang > 0:
            gekuerzt = False
            for index in range(len(dauern) - 1, -1, -1):
                if dauern[index] > 3:
                    dauern[index] -= 1
                    ueberhang -= 1
                    gekuerzt = True
                    if ueberhang == 0:
                        break
            if not gekuerzt:
                break
        return dauern

    # -- Planung -----------------------------------------------------------
    def phasen_fuer(self, auftrag: Planungsauftrag) -> List[str]:
        mit_koordination = auftrag.koordinationsteil
        if mit_koordination is None:
            mit_koordination = self.katalog.braucht_koordinationsteil(
                auftrag.altersgruppe
            )
        phasen = ["aufwaermen"]
        if mit_koordination:
            phasen.append("koordination")
        phasen += ["hauptteil", "abschluss"]
        return phasen

    def plane(self, auftrag: Planungsauftrag) -> Planungsergebnis:
        zufall = random.Random(auftrag.seed)
        bestand = auftrag.verfuegbare_ausstattung()
        if not bestand:
            raise Planungsfehler(
                "Fuer diesen Ort ist keine Ausstattung hinterlegt - "
                "bitte zuerst Geraete erfassen oder auswaehlen."
            )

        phasen = self.phasen_fuer(auftrag)
        teile, warnungen = self._plane_alle(phasen, auftrag, bestand, zufall)

        # Bleibt ein Teil leer, wird seine Zeit auf die uebrigen Teile verteilt.
        gefuellte = [t.phase for t in teile if t.uebungen]
        if gefuellte and len(gefuellte) < len(phasen):
            leere = [t for t in teile if not t.uebungen]
            zufall = random.Random(auftrag.seed)
            teile, warnungen = self._plane_alle(gefuellte, auftrag, bestand, zufall)
            for teil in leere:
                warnungen.append(
                    f"Der Teil '{teil.titel}' konnte nicht besetzt werden - "
                    "die Zeit wurde auf die uebrigen Teile verteilt."
                )

        stunde = Stunde(
            id=neue_id("stunde"),
            titel=auftrag.titel or self._titel(auftrag),
            ort_id=auftrag.ort.id,
            ort_name=auftrag.ort.name,
            ortsart=auftrag.ort.art,
            altersgruppe_id=auftrag.altersgruppe.id,
            altersgruppe_name=auftrag.altersgruppe.name,
            dauer=auftrag.dauer,
            teile=teile,
            schwerpunkt=auftrag.schwerpunkt,
            thema=auftrag.thema,
            ueberschrift=auftrag.ueberschrift,
            datum=auftrag.datum or "",
            quelle="geplant",
        )
        if not stunde.datum:
            from datetime import date

            stunde.datum = date.today().isoformat()

        warnungen.extend(self._platziere_stationen(stunde, auftrag))

        verstoesse = pruefe_bestand(stunde, bestand)
        if verstoesse:
            # Darf nicht vorkommen - lieber laut scheitern als unsicher planen.
            raise Planungsfehler(
                "Interner Fehler: Geraetebestand ueberschritten - "
                + "; ".join(verstoesse)
            )

        hinweise = self._sicherheitshinweise(stunde)
        if auftrag.altersgruppe.hinweis:
            hinweise.insert(0, f"Altersgruppe: {auftrag.altersgruppe.hinweis}")

        return Planungsergebnis(
            stunde=stunde,
            warnungen=warnungen,
            sicherheitshinweise=hinweise,
            bestand=bestand,
        )

    def _platziere_stationen(
        self, stunde: Stunde, auftrag: Planungsauftrag
    ) -> List[str]:
        """Stellt die Stationen in die Halle - notfalls eine Station weniger."""
        teil = stunde.teil("hauptteil")
        if not teil or not teil.uebungen:
            stunde.ort_laenge = auftrag.ort.laenge
            stunde.ort_breite = auftrag.ort.breite
            return []

        ziel_dauer = teil.dauer  # bleibt erhalten, auch wenn Stationen wegfallen
        hinweise: List[str] = []
        for _ in range(4):
            hinweise = platziere(stunde, auftrag.ort, self.katalog)
            streit = konflikte(teil.uebungen, auftrag.ort)
            if not streit or len(teil.uebungen) <= 1:
                break
            # Eine Station zu viel fuer die Halle - die spaetere der beiden
            # sich ueberlappenden Stationen faellt weg.
            namen = [u.name for u in teil.uebungen]
            erste, zweite = streit[0]
            if erste in namen and namen.index(erste) > namen.index(zweite):
                weg = erste
            else:
                weg = zweite
            entfernt = teil.uebungen.pop(namen.index(weg))
            hinweise.append(
                f"'{entfernt.name}' hat in {auftrag.ort.name} keinen Platz mehr "
                "und wurde aus der Bewegungslandschaft genommen."
            )
            neue_dauern = self._verteile_dauern_fest(
                [u.dauer for u in teil.uebungen], max(0, ziel_dauer - teil.puffer)
            )
            for uebung, dauer in zip(teil.uebungen, neue_dauern):
                uebung.dauer = dauer
            if teil.uebungen:
                teil.notiz = (
                    f"Bewegungslandschaft mit {len(teil.uebungen)} Stationen - "
                    "Wechsel im Uhrzeigersinn. Alle Stationen stehen gleichzeitig."
                )
        return hinweise

    @staticmethod
    def _verteile_dauern_fest(dauern: List[int], ziel: int) -> List[int]:
        """Verteilt ein festes Zeitfenster gleichmaessig auf die Uebungen."""
        if not dauern:
            return []
        grund = max(3, ziel // len(dauern))
        neu = [grund] * len(dauern)
        rest = ziel - sum(neu)
        index = 0
        while rest > 0:
            neu[index % len(neu)] += 1
            rest -= 1
            index += 1
        return neu

    def _plane_alle(
        self,
        phasen: Sequence[str],
        auftrag: Planungsauftrag,
        bestand: Dict[str, int],
        zufall: random.Random,
    ) -> Tuple[List[Stundenteil], List[str]]:
        anteile = self.stil.anteile_fuer(phasen)
        ziel_dauern = self._phasendauern(auftrag.dauer, phasen, anteile)
        warnungen: List[str] = []
        teile: List[Stundenteil] = []
        gesamt_rest = dict(bestand)
        for phase in phasen:
            # Zwischen den Teilen wird umgebaut - dann steht wieder alles bereit.
            rest = dict(bestand) if auftrag.umbau_zwischen_teilen else gesamt_rest
            if phase == "hauptteil":
                teil, phasen_warnungen = self._plane_hauptteil(
                    ziel_dauern[phase], auftrag, rest, zufall
                )
            else:
                teil, phasen_warnungen = self._plane_teil(
                    phase, ziel_dauern[phase], auftrag, rest, zufall
                )
            if not auftrag.umbau_zwischen_teilen:
                gesamt_rest = rest
            warnungen.extend(phasen_warnungen)
            teile.append(teil)
        return teile, warnungen

    # -- Hauptteil: Bewegungslandschaft oder grosses Spiel ------------------
    def stationszahl(self, auftrag: Planungsauftrag) -> int:
        """Obergrenze fuer die Stationszahl - abgeleitet aus der Hallenflaeche.

        Wie viele Stationen wirklich stehen, entscheidet beim Auswaehlen das
        Flaechenbudget: jede Station zieht ihre Stellflaeche ab. Diese Zahl ist
        die Obergrenze und beruecksichtigt, dass ein Teil der Flaeche als
        Laufweg frei bleiben muss.
        """
        if auftrag.stationszahl:
            return max(1, min(MAX_STATIONEN, int(auftrag.stationszahl)))
        budget = self._flaechenbudget(auftrag)
        geschaetzt = int(budget // MITTLERE_STATIONSFLAECHE)
        return max(MIN_STATIONEN, min(MAX_STATIONEN, geschaetzt))

    @staticmethod
    def _flaechenbudget(auftrag: Planungsauftrag) -> float:
        """Nutzbare Flaeche fuer Stationen in Quadratmetern."""
        ort = auftrag.ort
        nutz_laenge = max(2.0, ort.laenge - 2 * WANDSTREIFEN)
        nutz_breite = max(2.0, ort.breite - 2 * WANDSTREIFEN)
        return nutz_laenge * nutz_breite * BELEGUNGSFAKTOR

    def _stationsbetrieb_gewaehlt(
        self, auftrag: Planungsauftrag, zufall: random.Random
    ) -> bool:
        if auftrag.stationsbetrieb is not None:
            return auftrag.stationsbetrieb
        return zufall.random() < self.stil.stationsanteil

    def _plane_hauptteil(
        self,
        ziel_dauer: int,
        auftrag: Planungsauftrag,
        rest: Dict[str, int],
        zufall: random.Random,
    ) -> Tuple[Stundenteil, List[str]]:
        stationen = self._stationsbetrieb_gewaehlt(auftrag, zufall)
        reihenfolge = [stationen, not stationen]
        letzte: Tuple[Stundenteil, List[str]] = (Stundenteil(phase="hauptteil"), [])
        for versuch in reihenfolge:
            sicherung = dict(rest)
            teil, warnungen = self._plane_teil(
                "hauptteil",
                ziel_dauer,
                auftrag,
                rest,
                zufall,
                ziel_anzahl=self.stationszahl(auftrag) if versuch else 1,
                nur_stationen=versuch,
            )
            if teil.uebungen:
                if versuch:
                    teil.notiz = (
                        f"Bewegungslandschaft mit {len(teil.uebungen)} Stationen - "
                        "Wechsel im Uhrzeigersinn. Alle Stationen stehen gleichzeitig."
                    )
                    teil.parallel = True
                return teil, warnungen
            rest.clear()
            rest.update(sicherung)
            letzte = (teil, warnungen)
        return letzte

    def _titel(self, auftrag: Planungsauftrag) -> str:
        teile = ["Kinderturnen", auftrag.altersgruppe.name.split(" (")[0]]
        if auftrag.thema:
            teile.append(f"Motto {auftrag.thema.capitalize()}")
        elif auftrag.schwerpunkt:
            teile.append(f"Schwerpunkt {auftrag.schwerpunkt.capitalize()}")
        return " - ".join(teile)

    def _plane_teil(
        self,
        phase: str,
        ziel_dauer: int,
        auftrag: Planungsauftrag,
        rest: Dict[str, int],
        zufall: random.Random,
        ziel_anzahl: Optional[int] = None,
        nur_stationen: Optional[bool] = None,
    ) -> Tuple[Stundenteil, List[str]]:
        warnungen: List[str] = []
        kandidaten = self.kandidaten(phase, auftrag)
        if nur_stationen is not None:
            kandidaten = [
                u for u in kandidaten if bool(u.stationsbetrieb) == nur_stationen
            ]
        if not kandidaten:
            warnungen.append(
                f"Fuer den Teil '{PHASEN_TITEL.get(phase, phase)}' gibt es im Katalog "
                f"keine passende Uebung ({auftrag.ort.art}, {auftrag.altersgruppe.name})."
            )
            return Stundenteil(phase=phase, notiz="Keine passende Uebung gefunden."), warnungen

        bewertet = sorted(
            kandidaten,
            key=lambda u: -self._bewertung(u, auftrag, phase, zufall),
        )

        if ziel_anzahl is None:
            ziel_anzahl = max(1, int(round(self.stil.uebungszahl(phase))))
        riegen = ziel_anzahl if nur_stationen else STANDARD_RIEGEN
        gewaehlt: List[Uebung] = []
        bedarfe: List[Tuple[Dict[str, int], Dict[str, int], List[str], int]] = []
        uebersprungen_wegen_material = 0
        # Nur die Bewegungslandschaft steht komplett gleichzeitig - dort
        # entscheidet die Hallenflaeche mit, wie viele Stationen aufgebaut werden.
        flaechenbudget = (
            self._flaechenbudget(auftrag) if nur_stationen else float("inf")
        )
        flaeche_knapp = False

        def zeit_gedeckt() -> bool:
            """Reicht die Maximaldauer der gewaehlten Uebungen fuer den Teil?

            Eine Uebung darf dabei bis zu ein Viertel laenger laufen als im
            Katalog vorgesehen - lieber ein Spiel etwas ausdehnen als ein
            zusaetzliches Spiel in ein kurzes Zeitfenster quetschen.
            """
            return sum(u.dauer_max * 1.25 for u in gewaehlt) >= ziel_dauer

        for uebung in bewertet:
            # Genug Uebungen und genug Zeitreserve - fertig.
            if len(gewaehlt) >= ziel_anzahl and zeit_gedeckt():
                break
            if len(gewaehlt) >= ziel_anzahl + 3:
                break
            geraete, absicherung, pro_kind, gruppen = self.katalog.bedarf(
                uebung, riegen, rest
            )
            gesamt = dict(geraete)
            for geraet, anzahl in absicherung.items():
                gesamt[geraet] = gesamt.get(geraet, 0) + anzahl

            if not self._passt_in_bestand(gesamt, rest):
                uebersprungen_wegen_material += 1
                continue

            platzbedarf = 0.0
            if nur_stationen:
                probe = StundenUebung(
                    uebung_id=uebung.id,
                    name=uebung.name,
                    dauer=uebung.dauer_min,
                    beschreibung="",
                    geraete=geraete,
                    absicherung=absicherung,
                )
                laenge, breite = stellflaeche(probe, self.katalog)
                # Zuschlag, weil sich Stationen nie luecken los packen lassen.
                platzbedarf = laenge * breite * 1.15
                if gewaehlt and platzbedarf > flaechenbudget:
                    flaeche_knapp = True
                    continue

            self._buche(gesamt, rest)
            flaechenbudget -= platzbedarf
            gewaehlt.append(uebung)
            bedarfe.append((geraete, absicherung, pro_kind, gruppen))

        if flaeche_knapp and gewaehlt:
            warnungen.append(
                f"{PHASEN_TITEL.get(phase, phase)}: weitere Stationen haetten in "
                f"{auftrag.ort.name} keinen Platz mehr - die Flaeche ist ausgereizt."
            )

        if not gewaehlt:
            warnungen.append(
                f"'{PHASEN_TITEL.get(phase, phase)}': keine Uebung passt in den "
                "verfuegbaren Geraetebestand."
            )
            return (
                Stundenteil(
                    phase=phase,
                    notiz="Kein Aufbau moeglich - Bestand reicht nicht aus.",
                ),
                warnungen,
            )

        if uebersprungen_wegen_material:
            warnungen.append(
                f"{PHASEN_TITEL.get(phase, phase)}: {uebersprungen_wegen_material} "
                "Uebung(en) wurden wegen fehlender Geraete oder Absicherung nicht geplant."
            )

        dauern = self._verteile_dauern(gewaehlt, ziel_dauer)
        stunden_uebungen: List[StundenUebung] = []
        for uebung, dauer, (geraete, absicherung, pro_kind, gruppen) in zip(
            gewaehlt, dauern, bedarfe
        ):
            stunden_uebungen.append(
                StundenUebung(
                    uebung_id=uebung.id,
                    name=uebung.name,
                    dauer=max(3, dauer),
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
                    pro_kind=pro_kind,
                )
            )

        parallel = len(stunden_uebungen) > 1
        hinweise: List[str] = []
        if parallel:
            hinweise.append(
                "Alle Aufbauten dieses Teils stehen gleichzeitig - der Bedarf ist "
                "die Summe aller Uebungen."
            )

        puffer = max(0, ziel_dauer - sum(u.dauer for u in stunden_uebungen))
        if puffer:
            hinweise.append(
                "Zeitpuffer fuer Aufbau, Erklaerung, Pausen und Wiederholungen."
            )
        return (
            Stundenteil(
                phase=phase,
                uebungen=stunden_uebungen,
                parallel=parallel,
                notiz=" ".join(hinweise),
                puffer=puffer,
            ),
            warnungen,
        )

    def _sicherheitshinweise(self, stunde: Stunde) -> List[str]:
        hinweise: List[str] = []
        for uebung in stunde.alle_uebungen():
            for hinweis in self.katalog.sicherheitshinweise_fuer(uebung.geraete):
                if hinweis not in hinweise:
                    hinweise.append(hinweis)
        return hinweise


# ---------------------------------------------------------------------------
# Pruefung (auch fuer importierte oder von Hand erstellte Stunden)
# ---------------------------------------------------------------------------


def pruefe_bestand(stunde: Stunde, bestand: Dict[str, int]) -> List[str]:
    """Alle Verstoesse gegen den Geraetebestand - leere Liste heisst sauber."""
    verstoesse: List[str] = []
    for teil in stunde.teile:
        for geraet, anzahl in sorted(teil.bedarf().items()):
            vorhanden = int(bestand.get(geraet, 0))
            if anzahl > vorhanden:
                verstoesse.append(
                    f"{PHASEN_TITEL.get(teil.phase, teil.phase)}: {geraet} "
                    f"benoetigt {anzahl}, vorhanden {vorhanden}"
                )
    return verstoesse


def aufbauplan(stunde: Stunde, katalog: Katalog) -> List[Dict[str, object]]:
    """Aufbau-Informationen je Stundenteil fuer Ausdruck und Anzeige."""
    plan: List[Dict[str, object]] = []
    vorher: Dict[str, int] = {}
    for teil in stunde.teile:
        bedarf = teil.bedarf()
        neu = {
            geraet: anzahl
            for geraet, anzahl in bedarf.items()
            if anzahl > vorher.get(geraet, 0)
        }
        plan.append(
            {
                "phase": teil.phase,
                "titel": teil.titel,
                "dauer": teil.dauer,
                "bedarf": {katalog.geraet_name(g): a for g, a in sorted(bedarf.items())},
                "absicherung": {
                    katalog.geraet_name(g): a
                    for g, a in sorted(bedarf.items())
                    if katalog.ist_absicherung(g)
                },
                "zusaetzlich_aufbauen": {
                    katalog.geraet_name(g): a for g, a in sorted(neu.items())
                },
                "schritte": [
                    f"{u.name}: {u.aufbau}" for u in teil.uebungen if u.aufbau
                ],
                "sicherheit": [
                    hinweis
                    for u in teil.uebungen
                    for hinweis in katalog.sicherheitshinweise_fuer(u.geraete)
                ],
            }
        )
        vorher = bedarf
    return plan
