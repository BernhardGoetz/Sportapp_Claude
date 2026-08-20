import unittest

from sportstunden.katalog import Katalog
from sportstunden.planer import Planer, Planungsauftrag
from sportstunden.stil import Stillernen
from tests.hilfen import auftrag, eigene_stunde, planer, temp_speicher


TURN_STUNDE = {
    "aufwaermen": ["aufw_tierlauf"],
    "koordination": ["koo_bank_balancieren"],
    "hauptteil": ["st_purzelbaum", "st_reck_schwingen", "st_affenfelsen"],
    "abschluss": ["abs_fantasiereise"],
}

SPIEL_STUNDE = {
    "aufwaermen": ["aufw_versteinern", "aufw_farben_fangen"],
    "koordination": ["koo_farbsignal"],
    "hauptteil": ["spiel_fischer", "spiel_katz_maus_reifen"],
    "abschluss": ["abs_kleine_baelle"],
}


class StilTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.katalog = Katalog.laden()
        cls.speicher = temp_speicher()
        cls.ort = cls.speicher.ort("halle-grundschule")

    def _stunden(self, vorlage, gruppen_id, anzahl=4):
        return [
            eigene_stunde(self.katalog, self.ort, gruppen_id, vorlage)
            for _ in range(anzahl)
        ]

    def _plane(self, stunden, gruppen_id, seed):
        lernen = Stillernen(self.katalog, stunden)
        p = Planer(self.katalog, lernen.profil(self.katalog.altersgruppe(gruppen_id)))
        return p.plane(
            auftrag(self.ort, self.katalog, gruppen_id=gruppen_id, seed=seed)
        )

    def test_ohne_eigene_stunden_neutrales_profil(self):
        profil = Stillernen(self.katalog, []).profil(self.katalog.altersgruppe("grundschule_1"))
        self.assertEqual(profil.stichprobe, 0)
        self.assertAlmostEqual(sum(profil.anteile_fuer(["aufwaermen", "hauptteil"]).values()), 1.0)

    def test_eigene_stunden_veraendern_die_bewertung(self):
        stunden = self._stunden(TURN_STUNDE, "grundschule_1")
        profil = Stillernen(self.katalog, stunden).profil(self.katalog.altersgruppe("grundschule_1"))
        self.assertEqual(profil.stichprobe, 4)
        turnen = self.katalog.uebung("st_burgmauer")
        spiel = self.katalog.uebung("spiel_fischer")
        self.assertGreater(profil.bewerte(turnen), profil.bewerte(spiel))

    def test_gelernter_stil_praegt_die_planung(self):
        turn_treffer = 0
        spiel_treffer = 0
        for seed in range(8):
            turn_stunde = self._plane(self._stunden(TURN_STUNDE, "grundschule_1"), "grundschule_1", seed)
            spiel_stunde = self._plane(self._stunden(SPIEL_STUNDE, "grundschule_1"), "grundschule_1", seed)
            turn_tags = [t for u in turn_stunde.stunde.alle_uebungen() for t in u.tags]
            spiel_tags = [t for u in spiel_stunde.stunde.alle_uebungen() for t in u.tags]
            turn_treffer += turn_tags.count("turnen")
            spiel_treffer += spiel_tags.count("spielform")
        self.assertGreater(turn_treffer, 0)
        self.assertGreater(spiel_treffer, 0)

        # Der Turn-Stil plant deutlich mehr Turnen als der Spiel-Stil.
        turn_anteil = 0
        spiel_anteil = 0
        for seed in range(8):
            turn_plan = self._plane(self._stunden(TURN_STUNDE, "grundschule_1"), "grundschule_1", seed)
            spiel_plan = self._plane(self._stunden(SPIEL_STUNDE, "grundschule_1"), "grundschule_1", seed)
            turn_anteil += sum(
                "turnen" in u.tags for u in turn_plan.stunde.alle_uebungen()
            )
            spiel_anteil += sum(
                "turnen" in u.tags for u in spiel_plan.stunde.alle_uebungen()
            )
        self.assertGreater(turn_anteil, spiel_anteil)

    def test_stil_variiert_je_altersgruppe(self):
        """Ein Stil fuer die D-Jugend faerbt nicht voll auf die B-Jugend ab."""
        stunden = self._stunden(TURN_STUNDE, "grundschule_1") + self._stunden(SPIEL_STUNDE, "grundschule_2")
        lernen = Stillernen(self.katalog, stunden)
        profil_d = lernen.profil(self.katalog.altersgruppe("grundschule_1"))
        profil_b = lernen.profil(self.katalog.altersgruppe("grundschule_2"))
        turnen = self.katalog.uebung("st_purzelbaum")
        spiel = self.katalog.uebung("spiel_katz_maus_reifen")
        self.assertGreater(profil_d.bewerte(turnen), profil_b.bewerte(turnen))
        self.assertGreater(profil_b.bewerte(spiel), profil_d.bewerte(spiel))

    def test_neue_altersgruppe_erbt_den_gesamtstil(self):
        stunden = self._stunden(TURN_STUNDE, "grundschule_1")
        lernen = Stillernen(self.katalog, stunden)
        profil_c = lernen.profil(self.katalog.altersgruppe("vorschule"))
        neutral = Stillernen(self.katalog, []).profil(self.katalog.altersgruppe("vorschule"))
        turnen = self.katalog.uebung("st_purzelbaum")
        self.assertGreater(profil_c.bewerte(turnen), neutral.bewerte(turnen))
        # ... aber schwaecher als in der Gruppe, aus der gelernt wurde.
        self.assertGreaterEqual(
            lernen.profil(self.katalog.altersgruppe("grundschule_1")).bewerte(turnen),
            profil_c.bewerte(turnen),
        )

    def test_zeitaufteilung_wird_uebernommen(self):
        stunden = self._stunden(TURN_STUNDE, "grundschule_1", anzahl=6)
        # Aufwaermen kuenstlich verlaengern, Hauptteil kuerzen.
        for stunde in stunden:
            stunde.teil("aufwaermen").uebungen[0].dauer = 25
            for uebung in stunde.teil("hauptteil").uebungen:
                uebung.dauer = 10
        profil = Stillernen(self.katalog, stunden).profil(self.katalog.altersgruppe("grundschule_1"))
        neutral = Stillernen(self.katalog, []).profil(self.katalog.altersgruppe("grundschule_1"))
        self.assertGreater(
            profil.anteile_fuer(["aufwaermen", "koordination", "hauptteil", "abschluss"])[
                "aufwaermen"
            ],
            neutral.anteile_fuer(
                ["aufwaermen", "koordination", "hauptteil", "abschluss"]
            )["aufwaermen"],
        )

    def test_nur_eigene_stunden_werden_gelernt(self):
        stunden = self._stunden(TURN_STUNDE, "grundschule_1")
        for stunde in stunden:
            stunde.quelle = "geplant"
        profil = Stillernen(self.katalog, stunden).profil(self.katalog.altersgruppe("grundschule_1"))
        self.assertEqual(profil.stichprobe, 0)

    def test_stil_haelt_geraetegrenzen_ein(self):
        from sportstunden.planer import pruefe_bestand

        stunden = self._stunden(TURN_STUNDE, "grundschule_1", anzahl=6)
        for seed in range(5):
            ergebnis = self._plane(stunden, "grundschule_1", seed)
            self.assertEqual(
                pruefe_bestand(ergebnis.stunde, self.ort.ausstattung), []
            )


if __name__ == "__main__":
    unittest.main()
