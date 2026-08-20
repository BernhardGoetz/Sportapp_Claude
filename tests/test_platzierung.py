import unittest

from sportstunden.katalog import Katalog
from sportstunden.models import Geraeteplatz, Ort
from sportstunden.platzierung import (
    braucht_ortsfestes_geraet,
    kollisionen,
    masse_der_stunde,
    passt_in_halle,
    platziere,
    stelle_sicher,
    stellflaeche,
)
from tests.hilfen import auftrag, planer, temp_speicher


class PlatzierungTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.katalog = Katalog.laden()
        cls.speicher = temp_speicher()
        cls.orte = {o.id: o for o in cls.speicher.orte()}

    def _plane(self, ort_id: str, gruppen_id: str = "vorschule", **kwargs):
        ort = self.orte[ort_id]
        p = planer(self.katalog, gruppen_id=gruppen_id)
        return p.plane(
            auftrag(ort, self.katalog, gruppen_id=gruppen_id, stationsbetrieb=True, **kwargs)
        )

    # -- Grunddaten --------------------------------------------------------
    def test_beispielorte_haben_masse(self):
        for ort in self.orte.values():
            self.assertGreater(ort.laenge, 5)
            self.assertGreater(ort.breite, 5)

    def test_hallen_haben_feste_geraeteplaetze(self):
        halle = self.orte["halle-grundschule"]
        self.assertTrue(halle.plaetze_fuer("sprossenwand"))
        self.assertTrue(halle.plaetze_fuer("reck"))
        for platz in halle.geraeteplaetze:
            self.assertLessEqual(platz.x + platz.laenge, halle.laenge + 0.01)
            self.assertLessEqual(platz.y + platz.breite, halle.breite + 0.01)

    def test_stellflaeche_waechst_mit_dem_material(self):
        klein = self.katalog.uebung("st_slalomwald")
        gross = self.katalog.uebung("st_burgmauer")
        geraete_k, absicherung_k, _, _ = self.katalog.bedarf(klein)
        geraete_g, absicherung_g, _, _ = self.katalog.bedarf(gross)

        from sportstunden.models import StundenUebung

        a = StundenUebung(
            uebung_id=klein.id, name=klein.name, dauer=5, beschreibung="",
            geraete=geraete_k, absicherung=absicherung_k,
        )
        b = StundenUebung(
            uebung_id=gross.id, name=gross.name, dauer=5, beschreibung="",
            geraete=geraete_g, absicherung=absicherung_g,
        )
        flaeche = lambda u: stellflaeche(u, self.katalog)[0] * stellflaeche(u, self.katalog)[1]
        self.assertGreater(flaeche(b), flaeche(a))

    # -- Platzierung -------------------------------------------------------
    def test_stationen_liegen_in_der_halle_und_ueberlappen_nicht(self):
        for ort_id in self.orte:
            for seed in (1, 2, 3):
                ergebnis = self._plane(ort_id, seed=seed)
                stationen = ergebnis.stunde.teil("hauptteil").uebungen
                halle = masse_der_stunde(ergebnis.stunde)
                for station in stationen:
                    self.assertTrue(station.hat_position, station.name)
                    self.assertTrue(
                        passt_in_halle(station, halle),
                        f"{ort_id}/{seed}: {station.name} liegt ausserhalb",
                    )
                self.assertEqual(
                    kollisionen(stationen), [], f"{ort_id}/{seed}: Ueberlappung"
                )

    def test_ortsfeste_station_steht_am_geraeteplatz(self):
        halle = self.orte["halle-grundschule"]
        for seed in range(6):
            ergebnis = self._plane("halle-grundschule", seed=seed)
            for station in ergebnis.stunde.teil("hauptteil").uebungen:
                geraet_id = braucht_ortsfestes_geraet(station)
                if not geraet_id:
                    continue
                plaetze = halle.plaetze_fuer(geraet_id)
                if not plaetze:
                    continue
                mitte = station.mitte
                abstand = min(
                    max(abs(mitte[0] - p.mitte[0]), abs(mitte[1] - p.mitte[1]))
                    for p in plaetze
                )
                self.assertLess(
                    abstand,
                    6.0,
                    f"{station.name} steht zu weit von seinem {geraet_id} entfernt",
                )

    def test_platzierung_ist_reproduzierbar(self):
        erste = self._plane("halle-grundschule", seed=9)
        zweite = self._plane("halle-grundschule", seed=9)
        self.assertEqual(
            [(u.name, u.x, u.y) for u in erste.stunde.teil("hauptteil").uebungen],
            [(u.name, u.x, u.y) for u in zweite.stunde.teil("hauptteil").uebungen],
        )

    def test_enge_halle_liefert_hinweis_statt_absturz(self):
        winzig = Ort(
            id="winzig",
            name="Winziger Raum",
            art="halle",
            laenge=6.0,
            breite=5.0,
            ausstattung={"matte": 6, "langbank": 2, "reifen": 8, "softball": 6},
        )
        p = planer(self.katalog, gruppen_id="kleinkind")
        ergebnis = p.plane(
            auftrag(winzig, self.katalog, gruppen_id="kleinkind", seed=2, stationsbetrieb=True)
        )
        stationen = ergebnis.stunde.teil("hauptteil").uebungen
        self.assertEqual(kollisionen(stationen), [])
        self.assertEqual(ergebnis.stunde.gesamtdauer, 60)

    def test_stelle_sicher_platziert_nachtraeglich(self):
        ergebnis = self._plane("halle-grundschule", seed=4)
        stunde = ergebnis.stunde
        for station in stunde.teil("hauptteil").uebungen:
            station.x = station.y = 0.0
            station.stell_laenge = station.stell_breite = 0.0
        stelle_sicher(stunde, self.orte["halle-grundschule"], self.katalog)
        stationen = stunde.teil("hauptteil").uebungen
        self.assertTrue(all(s.hat_position for s in stationen))
        self.assertEqual(kollisionen(stationen), [])

    def test_platzierung_merkt_sich_die_hallenmasse(self):
        ergebnis = self._plane("halle-vereinsheim", seed=1)
        self.assertEqual(
            masse_der_stunde(ergebnis.stunde),
            (self.orte["halle-vereinsheim"].laenge, self.orte["halle-vereinsheim"].breite),
        )

    def test_feste_geraeteplaetze_bleiben_frei(self):
        """Mobile Stationen stellen sich nicht auf Reck oder Barren."""
        halle = self.orte["halle-grundschule"]
        ergebnis = self._plane("halle-grundschule", seed=7)
        for station in ergebnis.stunde.teil("hauptteil").uebungen:
            if braucht_ortsfestes_geraet(station):
                continue
            for platz in halle.geraeteplaetze:
                ueberlappt = not (
                    station.x + station.stell_laenge <= platz.x
                    or platz.x + platz.laenge <= station.x
                    or station.y + station.stell_breite <= platz.y
                    or platz.y + platz.breite <= station.y
                )
                self.assertFalse(
                    ueberlappt, f"{station.name} steht auf dem Platz von {platz.geraet}"
                )


if __name__ == "__main__":
    unittest.main()
