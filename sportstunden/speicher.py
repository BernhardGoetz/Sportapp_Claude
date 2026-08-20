"""Dauerhafte Speicherung von Orten, Ausstattung und Stunden."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .katalog import Katalog
from .models import Ort, Stunde

STANDARD_EINSTELLUNGEN: Dict[str, Any] = {
    "koordination_ab_alter": 6,
    "standard_dauer": 60,
    "standard_teilnehmer": 12,
    "trainer": "",
    "verein": "",
    "kopftitel": "Ki Tu",
}


def standard_verzeichnis() -> Path:
    """Datenverzeichnis - ueber ``SPORTSTUNDEN_HOME`` umstellbar."""
    umgebung = os.environ.get("SPORTSTUNDEN_HOME")
    if umgebung:
        return Path(umgebung).expanduser()
    return Path.home() / ".sportstunden"


class Speicher:
    """Legt Orte, Stunden und Einstellungen als JSON-Dateien ab."""

    def __init__(self, verzeichnis: Optional[Path] = None) -> None:
        self.verzeichnis = Path(verzeichnis) if verzeichnis else standard_verzeichnis()
        self.verzeichnis.mkdir(parents=True, exist_ok=True)
        self.orte_datei = self.verzeichnis / "orte.json"
        self.stunden_datei = self.verzeichnis / "stunden.json"
        self.einstellungen_datei = self.verzeichnis / "einstellungen.json"
        self.pdf_verzeichnis = self.verzeichnis / "pdf"

    # -- Hilfen ------------------------------------------------------------
    @staticmethod
    def _lies(datei: Path, standard: Any) -> Any:
        if not datei.exists():
            return standard
        try:
            with open(datei, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as fehler:
            raise RuntimeError(f"Datei {datei} kann nicht gelesen werden: {fehler}")

    @staticmethod
    def _schreib(datei: Path, inhalt: Any) -> None:
        temp = datei.with_suffix(datei.suffix + ".tmp")
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump(inhalt, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        temp.replace(datei)

    # -- Orte --------------------------------------------------------------
    def orte(self) -> List[Ort]:
        daten = self._lies(self.orte_datei, {"orte": []})
        return [Ort.from_dict(o) for o in daten.get("orte", [])]

    def speichere_orte(self, orte: List[Ort]) -> None:
        self._schreib(self.orte_datei, {"orte": [o.to_dict() for o in orte]})

    def ort(self, ort_id: str) -> Optional[Ort]:
        for ort in self.orte():
            if ort.id == ort_id:
                return ort
        return None

    def speichere_ort(self, ort: Ort) -> None:
        orte = self.orte()
        for index, vorhanden in enumerate(orte):
            if vorhanden.id == ort.id:
                orte[index] = ort
                break
        else:
            orte.append(ort)
        self.speichere_orte(orte)

    def loesche_ort(self, ort_id: str) -> bool:
        orte = self.orte()
        rest = [o for o in orte if o.id != ort_id]
        if len(rest) == len(orte):
            return False
        self.speichere_orte(rest)
        return True

    # -- Stunden -----------------------------------------------------------
    def stunden(self) -> List[Stunde]:
        daten = self._lies(self.stunden_datei, {"stunden": []})
        return [Stunde.from_dict(s) for s in daten.get("stunden", [])]

    def speichere_stunden(self, stunden: List[Stunde]) -> None:
        self._schreib(
            self.stunden_datei, {"stunden": [s.to_dict() for s in stunden]}
        )

    def stunde(self, stunden_id: str) -> Optional[Stunde]:
        for stunde in self.stunden():
            if stunde.id == stunden_id:
                return stunde
        return None

    def speichere_stunde(self, stunde: Stunde) -> None:
        stunden = self.stunden()
        for index, vorhanden in enumerate(stunden):
            if vorhanden.id == stunde.id:
                stunden[index] = stunde
                break
        else:
            stunden.append(stunde)
        self.speichere_stunden(stunden)

    def loesche_stunde(self, stunden_id: str) -> bool:
        stunden = self.stunden()
        rest = [s for s in stunden if s.id != stunden_id]
        if len(rest) == len(stunden):
            return False
        self.speichere_stunden(rest)
        return True

    def eigene_stunden(self) -> List[Stunde]:
        """Vom Nutzer selbst erstellte Stunden - Grundlage des Stil-Lernens."""
        return [s for s in self.stunden() if s.ist_eigene]

    # -- Einstellungen -----------------------------------------------------
    def einstellungen(self) -> Dict[str, Any]:
        daten = dict(STANDARD_EINSTELLUNGEN)
        daten.update(self._lies(self.einstellungen_datei, {}))
        return daten

    def speichere_einstellungen(self, einstellungen: Dict[str, Any]) -> None:
        self._schreib(self.einstellungen_datei, einstellungen)

    def setze_einstellung(self, schluessel: str, wert: Any) -> Dict[str, Any]:
        einstellungen = self.einstellungen()
        einstellungen[schluessel] = wert
        self.speichere_einstellungen(einstellungen)
        return einstellungen

    # -- Erstbefuellung ----------------------------------------------------
    def initialisiere_beispieldaten(self, ueberschreiben: bool = False) -> int:
        """Legt Beispielorte an, wenn noch keine Orte gespeichert sind."""
        if self.orte() and not ueberschreiben:
            return 0
        beispiele = Katalog.beispiel_orte()
        self.speichere_orte(beispiele)
        return len(beispiele)

    def pdf_pfad(self, dateiname: str) -> Path:
        self.pdf_verzeichnis.mkdir(parents=True, exist_ok=True)
        return self.pdf_verzeichnis / dateiname
