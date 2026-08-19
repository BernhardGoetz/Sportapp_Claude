"""Gemeinsame Testhilfen."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from sportstunden.katalog import Katalog
from sportstunden.models import Ort, Stunde, StundenUebung, Stundenteil
from sportstunden.planer import Planer, Planungsauftrag
from sportstunden.speicher import Speicher
from sportstunden.stil import Stillernen


def temp_speicher() -> Speicher:
    speicher = Speicher(Path(tempfile.mkdtemp(prefix="sportstunden-test-")))
    speicher.initialisiere_beispieldaten()
    return speicher


def planer(katalog: Katalog, stunden: Optional[List[Stunde]] = None, gruppen_id: str = "d") -> Planer:
    lernen = Stillernen(katalog, stunden or [])
    return Planer(katalog, lernen.profil(katalog.altersgruppe(gruppen_id)))


def eigene_stunde(
    katalog: Katalog,
    ort: Ort,
    gruppen_id: str,
    uebungs_ids: Dict[str, List[str]],
    teilnehmer: int = 12,
) -> Stunde:
    """Baut eine 'eigene' Stunde aus Katalog-Uebungen (fuer Stil-Tests)."""
    gruppe = katalog.altersgruppe(gruppen_id)
    teile: List[Stundenteil] = []
    for phase, ids in uebungs_ids.items():
        uebungen = []
        for uebung_id in ids:
            uebung = katalog.uebung(uebung_id)
            assert uebung is not None, uebung_id
            geraete, absicherung, gruppen = katalog.bedarf(uebung, teilnehmer)
            uebungen.append(
                StundenUebung(
                    uebung_id=uebung.id,
                    name=uebung.name,
                    dauer=uebung.dauer_vorschlag(),
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
                )
            )
        teile.append(Stundenteil(phase=phase, uebungen=uebungen, parallel=len(uebungen) > 1))
    return Stunde(
        id=f"stunde-test-{gruppen_id}-{len(teile)}-{abs(hash(str(uebungs_ids))) % 10000}",
        titel=f"Eigene Stunde {gruppen_id}",
        ort_id=ort.id,
        ort_name=ort.name,
        ortsart=ort.art,
        altersgruppe_id=gruppe.id,
        altersgruppe_name=gruppe.name,
        dauer=sum(t.dauer for t in teile),
        teilnehmer=teilnehmer,
        teile=teile,
        quelle="eigene",
    )


def auftrag(
    ort: Ort,
    katalog: Katalog,
    gruppen_id: str = "d",
    dauer: int = 60,
    teilnehmer: int = 16,
    **kwargs,
) -> Planungsauftrag:
    return Planungsauftrag(
        ort=ort,
        altersgruppe=katalog.altersgruppe(gruppen_id),
        dauer=dauer,
        teilnehmer=teilnehmer,
        **kwargs,
    )
