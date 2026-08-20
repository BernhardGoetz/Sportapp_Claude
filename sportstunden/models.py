"""Datenmodelle des Kinderturnen-Stundenplaners."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

ORTSARTEN = {
    "halle": "Turnhalle",
    "freien": "Im Freien (Wiese, Wald, Park)",
    "sportplatz": "Sportplatz / Sportanlage",
}

PHASEN = ["aufwaermen", "koordination", "hauptteil", "abschluss"]

PHASEN_TITEL = {
    "aufwaermen": "Aufwaermen",
    "koordination": "Koordinationsteil",
    "hauptteil": "Hauptteil",
    "abschluss": "Abschluss",
}

# Koordinative Faehigkeiten nach Hirtz / Meinel-Schnabel
KOORDINATIVE_FAEHIGKEITEN = {
    "reaktion": "Reaktionsfaehigkeit",
    "orientierung": "Orientierungsfaehigkeit",
    "gleichgewicht": "Gleichgewichtsfaehigkeit",
    "rhythmus": "Rhythmisierungsfaehigkeit",
    "differenzierung": "Differenzierungsfaehigkeit",
    "kopplung": "Kopplungsfaehigkeit",
    "umstellung": "Umstellungsfaehigkeit",
}


def neue_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _mengen_addieren(ziel: Dict[str, int], quelle: Dict[str, int]) -> Dict[str, int]:
    for key, wert in quelle.items():
        ziel[key] = ziel.get(key, 0) + int(wert)
    return ziel


def _mengen_maximum(ziel: Dict[str, int], quelle: Dict[str, int]) -> Dict[str, int]:
    for key, wert in quelle.items():
        ziel[key] = max(ziel.get(key, 0), int(wert))
    return ziel


# ---------------------------------------------------------------------------
# Geraete und Orte
# ---------------------------------------------------------------------------


@dataclass
class Geraet:
    """Ein Geraetetyp aus dem Stammdaten-Katalog."""

    id: str
    name: str
    kategorie: str = "sonstiges"
    einheit: str = "Stueck"
    kurz: str = ""

    @property
    def kurzname(self) -> str:
        """Kurzform fuer den Stundenplan (z. B. 'LB', 'WB', 'kl. Kasten')."""
        return self.kurz or self.name

    @staticmethod
    def from_dict(daten: Dict[str, Any]) -> "Geraet":
        return Geraet(
            id=daten["id"],
            name=daten["name"],
            kategorie=daten.get("kategorie", "sonstiges"),
            einheit=daten.get("einheit", "Stueck"),
            kurz=daten.get("kurz", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Ort:
    """Eine Turnhalle, ein Sportplatz oder ein Aussengelaende.

    ``ausstattung`` merkt sich dauerhaft, wie viele Exemplare eines
    Geraetes an diesem Ort vorhanden sind.
    """

    id: str
    name: str
    art: str
    ausstattung: Dict[str, int] = field(default_factory=dict)
    notiz: str = ""
    flaeche: str = ""

    def __post_init__(self) -> None:
        if self.art not in ORTSARTEN:
            raise ValueError(
                f"Unbekannte Ortsart '{self.art}'. Moeglich: {', '.join(ORTSARTEN)}"
            )
        self.ausstattung = {k: int(v) for k, v in self.ausstattung.items() if int(v) > 0}

    def bestand(self, geraet_id: str) -> int:
        return int(self.ausstattung.get(geraet_id, 0))

    def setze_bestand(self, geraet_id: str, anzahl: int) -> None:
        anzahl = int(anzahl)
        if anzahl <= 0:
            self.ausstattung.pop(geraet_id, None)
        else:
            self.ausstattung[geraet_id] = anzahl

    @staticmethod
    def from_dict(daten: Dict[str, Any]) -> "Ort":
        return Ort(
            id=daten["id"],
            name=daten["name"],
            art=daten["art"],
            ausstattung={k: int(v) for k, v in daten.get("ausstattung", {}).items()},
            notiz=daten.get("notiz", ""),
            flaeche=daten.get("flaeche", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Altersklassen
# ---------------------------------------------------------------------------


@dataclass
class Altersgruppe:
    id: str
    name: str
    alter_min: int
    alter_max: int
    koordination_schwerpunkte: List[str] = field(default_factory=list)
    druckbedingungen: List[str] = field(default_factory=list)
    hinweis: str = ""
    max_intensitaet: int = 5
    kinder_pro_station: int = 4

    @property
    def mittleres_alter(self) -> float:
        return (self.alter_min + self.alter_max) / 2

    @staticmethod
    def from_dict(daten: Dict[str, Any]) -> "Altersgruppe":
        return Altersgruppe(
            id=daten["id"],
            name=daten["name"],
            alter_min=int(daten["alter_min"]),
            alter_max=int(daten["alter_max"]),
            koordination_schwerpunkte=list(daten.get("koordination_schwerpunkte", [])),
            druckbedingungen=list(daten.get("druckbedingungen", [])),
            hinweis=daten.get("hinweis", ""),
            max_intensitaet=int(daten.get("max_intensitaet", 5)),
            kinder_pro_station=int(daten.get("kinder_pro_station", 4)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Uebungen
# ---------------------------------------------------------------------------


@dataclass
class Uebung:
    """Eine Uebung aus dem Katalog.

    Der Geraetebedarf wird in zwei Teile getrennt:

    * ``geraete_fix``      - unabhaengig von der Gruppengroesse
    * ``geraete_pro_gruppe`` - pro Kleingruppe / Station

    Zusaetzlich wird die Absicherung (Matten, Weichboden, Niedersprungmatten)
    getrennt gefuehrt, damit sie beim Bedarf niemals vergessen wird.
    """

    id: str
    name: str
    phase: str
    orte: List[str]
    alter_min: int
    alter_max: int
    dauer_min: int
    dauer_max: int
    beschreibung: str
    aufbau: str = ""
    hinweise: str = ""
    tags: List[str] = field(default_factory=list)
    organisation: str = "ganze_gruppe"
    gruppengroesse: int = 0
    geraete_fix: Dict[str, int] = field(default_factory=dict)
    geraete_pro_gruppe: Dict[str, int] = field(default_factory=dict)
    absicherung_fix: Dict[str, int] = field(default_factory=dict)
    absicherung_pro_gruppe: Dict[str, int] = field(default_factory=dict)
    intensitaet: int = 3
    koordination: List[str] = field(default_factory=list)
    druckbedingungen: List[str] = field(default_factory=list)
    stationsbetrieb: bool = False
    thema: str = ""

    # -- Bedarf ------------------------------------------------------------
    def gruppen(self, teilnehmer: int) -> int:
        """Anzahl paralleler Gruppen/Stationen bei ``teilnehmer`` Sportlern."""
        if self.gruppengroesse <= 0:
            return 1
        return max(1, math.ceil(teilnehmer / self.gruppengroesse))

    def dauer_vorschlag(self, minuten: Optional[int] = None) -> int:
        if minuten is None:
            return int(round((self.dauer_min + self.dauer_max) / 2))
        return max(self.dauer_min, min(self.dauer_max, int(minuten)))

    def passt_zu_alter(self, alter_min: int, alter_max: int) -> bool:
        return not (self.alter_max < alter_min or self.alter_min > alter_max)

    @staticmethod
    def from_dict(daten: Dict[str, Any]) -> "Uebung":
        return Uebung(
            id=daten["id"],
            name=daten["name"],
            phase=daten["phase"],
            orte=list(daten.get("orte", [])),
            alter_min=int(daten.get("alter_min", 4)),
            alter_max=int(daten.get("alter_max", 99)),
            dauer_min=int(daten.get("dauer_min", 5)),
            dauer_max=int(daten.get("dauer_max", 15)),
            beschreibung=daten.get("beschreibung", ""),
            aufbau=daten.get("aufbau", ""),
            hinweise=daten.get("hinweise", ""),
            tags=list(daten.get("tags", [])),
            organisation=daten.get("organisation", "ganze_gruppe"),
            gruppengroesse=int(daten.get("gruppengroesse", 0)),
            geraete_fix={k: int(v) for k, v in daten.get("geraete_fix", {}).items()},
            geraete_pro_gruppe={
                k: int(v) for k, v in daten.get("geraete_pro_gruppe", {}).items()
            },
            absicherung_fix={
                k: int(v) for k, v in daten.get("absicherung_fix", {}).items()
            },
            absicherung_pro_gruppe={
                k: int(v) for k, v in daten.get("absicherung_pro_gruppe", {}).items()
            },
            intensitaet=int(daten.get("intensitaet", 3)),
            koordination=list(daten.get("koordination", [])),
            druckbedingungen=list(daten.get("druckbedingungen", [])),
            stationsbetrieb=bool(daten.get("stationsbetrieb", False)),
            thema=daten.get("thema", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Geplante Stunde
# ---------------------------------------------------------------------------


@dataclass
class StundenUebung:
    """Eine in einer Stunde eingeplante Uebung inklusive konkretem Bedarf."""

    uebung_id: str
    name: str
    dauer: int
    beschreibung: str
    aufbau: str = ""
    hinweise: str = ""
    organisation: str = "ganze_gruppe"
    gruppen: int = 1
    tags: List[str] = field(default_factory=list)
    koordination: List[str] = field(default_factory=list)
    intensitaet: int = 3
    geraete: Dict[str, int] = field(default_factory=dict)
    absicherung: Dict[str, int] = field(default_factory=dict)

    @property
    def gesamtbedarf(self) -> Dict[str, int]:
        bedarf: Dict[str, int] = dict(self.geraete)
        return _mengen_addieren(bedarf, self.absicherung)

    @staticmethod
    def from_dict(daten: Dict[str, Any]) -> "StundenUebung":
        return StundenUebung(
            uebung_id=daten.get("uebung_id", ""),
            name=daten["name"],
            dauer=int(daten.get("dauer", 5)),
            beschreibung=daten.get("beschreibung", ""),
            aufbau=daten.get("aufbau", ""),
            hinweise=daten.get("hinweise", ""),
            organisation=daten.get("organisation", "ganze_gruppe"),
            gruppen=int(daten.get("gruppen", 1)),
            tags=list(daten.get("tags", [])),
            koordination=list(daten.get("koordination", [])),
            intensitaet=int(daten.get("intensitaet", 3)),
            geraete={k: int(v) for k, v in daten.get("geraete", {}).items()},
            absicherung={k: int(v) for k, v in daten.get("absicherung", {}).items()},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Stundenteil:
    phase: str
    uebungen: List[StundenUebung] = field(default_factory=list)
    parallel: bool = False
    notiz: str = ""
    puffer: int = 0

    @property
    def titel(self) -> str:
        return PHASEN_TITEL.get(self.phase, self.phase.capitalize())

    @property
    def dauer(self) -> int:
        """Gesamtdauer des Teils inklusive Puffer fuer Umbau und Pausen."""
        return sum(u.dauer for u in self.uebungen) + self.puffer

    def bedarf(self) -> Dict[str, int]:
        """Gleichzeitiger Geraetebedarf des Teils inklusive Absicherung.

        Bei Stationsbetrieb (``parallel``) werden die Bedarfe addiert, sonst
        wird das Maximum gebildet - die Geraete werden nacheinander genutzt.
        """
        bedarf: Dict[str, int] = {}
        for uebung in self.uebungen:
            if self.parallel:
                _mengen_addieren(bedarf, uebung.gesamtbedarf)
            else:
                _mengen_maximum(bedarf, uebung.gesamtbedarf)
        return bedarf

    @staticmethod
    def from_dict(daten: Dict[str, Any]) -> "Stundenteil":
        return Stundenteil(
            phase=daten["phase"],
            uebungen=[StundenUebung.from_dict(u) for u in daten.get("uebungen", [])],
            parallel=bool(daten.get("parallel", False)),
            notiz=daten.get("notiz", ""),
            puffer=int(daten.get("puffer", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "uebungen": [u.to_dict() for u in self.uebungen],
            "parallel": self.parallel,
            "notiz": self.notiz,
            "puffer": self.puffer,
        }


@dataclass
class Stunde:
    id: str
    titel: str
    ort_id: str
    ort_name: str
    ortsart: str
    altersgruppe_id: str
    altersgruppe_name: str
    dauer: int
    teilnehmer: int
    teile: List[Stundenteil] = field(default_factory=list)
    schwerpunkt: str = ""
    thema: str = ""
    datum: str = field(default_factory=lambda: date.today().isoformat())
    quelle: str = "geplant"  # "geplant" | "eigene"
    notiz: str = ""

    @property
    def ist_eigene(self) -> bool:
        return self.quelle == "eigene"

    def teil(self, phase: str) -> Optional[Stundenteil]:
        for teil in self.teile:
            if teil.phase == phase:
                return teil
        return None

    @property
    def phasen(self) -> List[str]:
        return [teil.phase for teil in self.teile]

    @property
    def gesamtdauer(self) -> int:
        return sum(teil.dauer for teil in self.teile)

    def alle_uebungen(self) -> Iterable[StundenUebung]:
        for teil in self.teile:
            yield from teil.uebungen

    def materialliste(self) -> Dict[str, int]:
        """Maximaler gleichzeitiger Bedarf ueber alle Stundenteile."""
        gesamt: Dict[str, int] = {}
        for teil in self.teile:
            _mengen_maximum(gesamt, teil.bedarf())
        return gesamt

    @staticmethod
    def from_dict(daten: Dict[str, Any]) -> "Stunde":
        return Stunde(
            id=daten.get("id") or neue_id("stunde"),
            titel=daten.get("titel", "Sportstunde"),
            ort_id=daten.get("ort_id", ""),
            ort_name=daten.get("ort_name", ""),
            ortsart=daten.get("ortsart", "halle"),
            altersgruppe_id=daten.get("altersgruppe_id", ""),
            altersgruppe_name=daten.get("altersgruppe_name", ""),
            dauer=int(daten.get("dauer", 60)),
            teilnehmer=int(daten.get("teilnehmer", 12)),
            teile=[Stundenteil.from_dict(t) for t in daten.get("teile", [])],
            schwerpunkt=daten.get("schwerpunkt", ""),
            thema=daten.get("thema", ""),
            datum=daten.get("datum", date.today().isoformat()),
            quelle=daten.get("quelle", "geplant"),
            notiz=daten.get("notiz", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "titel": self.titel,
            "ort_id": self.ort_id,
            "ort_name": self.ort_name,
            "ortsart": self.ortsart,
            "altersgruppe_id": self.altersgruppe_id,
            "altersgruppe_name": self.altersgruppe_name,
            "dauer": self.dauer,
            "teilnehmer": self.teilnehmer,
            "teile": [t.to_dict() for t in self.teile],
            "schwerpunkt": self.schwerpunkt,
            "thema": self.thema,
            "datum": self.datum,
            "quelle": self.quelle,
            "notiz": self.notiz,
        }
