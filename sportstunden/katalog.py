"""Stammdaten: Geraete, Sicherheitsregeln, Uebungen, Altersgruppen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Altersgruppe, Geraet, Ort, Uebung

DATEN_VERZEICHNIS = Path(__file__).resolve().parent / "data"


def _lade(datei: str) -> dict:
    with open(DATEN_VERZEICHNIS / datei, "r", encoding="utf-8") as fh:
        return json.load(fh)


class Katalog:
    """Kapselt alle mitgelieferten Stammdaten."""

    def __init__(
        self,
        geraete: Dict[str, Geraet],
        sicherheitsregeln: Dict[str, Dict[str, int]],
        sicherheitshinweise: Dict[str, str],
        uebungen: List[Uebung],
        altersgruppen: List[Altersgruppe],
        koordination_ab_alter: int = 8,
    ) -> None:
        self.geraete = geraete
        self.sicherheitsregeln = sicherheitsregeln
        self.sicherheitshinweise = sicherheitshinweise
        self.uebungen = uebungen
        self.altersgruppen = altersgruppen
        self.koordination_ab_alter = koordination_ab_alter

    # -- Laden -------------------------------------------------------------
    @classmethod
    def laden(cls) -> "Katalog":
        geraete_daten = _lade("geraete.json")
        uebungen_daten = _lade("uebungen.json")
        alter_daten = _lade("altersgruppen.json")

        geraete = {
            g["id"]: Geraet.from_dict(g) for g in geraete_daten["geraete"]
        }
        uebungen = [Uebung.from_dict(u) for u in uebungen_daten["uebungen"]]
        altersgruppen = [
            Altersgruppe.from_dict(a) for a in alter_daten["altersgruppen"]
        ]

        katalog = cls(
            geraete=geraete,
            sicherheitsregeln={
                k: {kk: int(vv) for kk, vv in v.items()}
                for k, v in geraete_daten.get("sicherheitsregeln", {}).items()
            },
            sicherheitshinweise=geraete_daten.get("sicherheitsregeln_hinweis", {}),
            uebungen=uebungen,
            altersgruppen=altersgruppen,
            koordination_ab_alter=int(alter_daten.get("koordination_ab_alter", 8)),
        )
        katalog.pruefe_konsistenz()
        return katalog

    @staticmethod
    def beispiel_orte() -> List[Ort]:
        return [Ort.from_dict(o) for o in _lade("orte.json")["orte"]]

    # -- Zugriff -----------------------------------------------------------
    def geraet_name(self, geraet_id: str) -> str:
        geraet = self.geraete.get(geraet_id)
        return geraet.name if geraet else geraet_id

    def ist_absicherung(self, geraet_id: str) -> bool:
        geraet = self.geraete.get(geraet_id)
        return bool(geraet and geraet.kategorie == "absicherung")

    def uebung(self, uebung_id: str) -> Optional[Uebung]:
        for uebung in self.uebungen:
            if uebung.id == uebung_id:
                return uebung
        return None

    def altersgruppe(self, gruppen_id: str) -> Optional[Altersgruppe]:
        for gruppe in self.altersgruppen:
            if gruppe.id == gruppen_id:
                return gruppe
        return None

    def altersgruppe_fuer_alter(self, alter: int) -> Altersgruppe:
        for gruppe in self.altersgruppen:
            if gruppe.alter_min <= alter <= gruppe.alter_max:
                return gruppe
        return self.altersgruppen[-1]

    def braucht_koordinationsteil(self, gruppe: Altersgruppe) -> bool:
        """Ab einer bestimmten Altersklasse gehoert der Koordinationsteil dazu."""
        return gruppe.alter_max >= self.koordination_ab_alter

    # -- Bedarfsrechnung ---------------------------------------------------
    def sicherheitsbedarf(self, geraete: Dict[str, int]) -> Dict[str, int]:
        """Pflicht-Absicherung, die sich aus den Sicherheitsregeln ergibt."""
        bedarf: Dict[str, int] = {}
        for geraet_id, anzahl in geraete.items():
            for sicherungs_id, faktor in self.sicherheitsregeln.get(
                geraet_id, {}
            ).items():
                bedarf[sicherungs_id] = bedarf.get(sicherungs_id, 0) + faktor * anzahl
        return bedarf

    def bedarf(
        self, uebung: Uebung, teilnehmer: int
    ) -> Tuple[Dict[str, int], Dict[str, int], int]:
        """Geraete-, Absicherungsbedarf und Gruppenzahl einer Uebung.

        Die Absicherung ist immer mindestens so gross, wie es die
        Sicherheitsregeln fuer die eingesetzten Geraete vorschreiben.
        """
        gruppen = uebung.gruppen(teilnehmer)

        geraete: Dict[str, int] = dict(uebung.geraete_fix)
        for geraet_id, anzahl in uebung.geraete_pro_gruppe.items():
            geraete[geraet_id] = geraete.get(geraet_id, 0) + anzahl * gruppen

        absicherung: Dict[str, int] = dict(uebung.absicherung_fix)
        for geraet_id, anzahl in uebung.absicherung_pro_gruppe.items():
            absicherung[geraet_id] = absicherung.get(geraet_id, 0) + anzahl * gruppen

        for geraet_id, anzahl in self.sicherheitsbedarf(geraete).items():
            absicherung[geraet_id] = max(absicherung.get(geraet_id, 0), anzahl)

        geraete = {k: v for k, v in geraete.items() if v > 0}
        absicherung = {k: v for k, v in absicherung.items() if v > 0}
        return geraete, absicherung, gruppen

    def sicherheitshinweise_fuer(self, geraete: Dict[str, int]) -> List[str]:
        hinweise: List[str] = []
        for geraet_id in geraete:
            hinweis = self.sicherheitshinweise.get(geraet_id)
            if hinweis:
                hinweise.append(f"{self.geraet_name(geraet_id)}: {hinweis}")
        return hinweise

    # -- Pruefung ----------------------------------------------------------
    def pruefe_konsistenz(self) -> None:
        """Stellt sicher, dass der Katalog nur bekannte Geraete verwendet."""
        unbekannt = set()
        for uebung in self.uebungen:
            for quelle in (
                uebung.geraete_fix,
                uebung.geraete_pro_gruppe,
                uebung.absicherung_fix,
                uebung.absicherung_pro_gruppe,
            ):
                unbekannt |= {g for g in quelle if g not in self.geraete}
        for geraet_id, regel in self.sicherheitsregeln.items():
            if geraet_id not in self.geraete:
                unbekannt.add(geraet_id)
            unbekannt |= {g for g in regel if g not in self.geraete}
        if unbekannt:
            raise ValueError(
                "Unbekannte Geraete-IDs im Katalog: " + ", ".join(sorted(unbekannt))
            )
