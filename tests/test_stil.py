import unittest

from sportstunden.katalog import Katalog
from sportstunden.planer import Planer, Planungsauftrag
from sportstunden.stil import Stillernen
from tests.hilfen import auftrag, eigene_stunde, planer, temp_speicher


TURN_STUNDE = {
    "aufwaermen": ["aufw_bankspiel"],
    "koordination": ["koo_gleichgewicht_bank"],
    "hauptteil": ["haupt_turnen_rolle", "haupt_klettern_tau"],
    "abschluss": ["abs_dehnen_matte"],
}

SPIEL_STUNDE = {
    "aufwaermen": ["aufw_kettenfangen", "aufw_zombieball"],
    "koordination": ["koo_reaktion_farbsignal"],
    "hauptteil": ["haupt_kleine_spiele_ball", "haupt_hockey_klein"],
    "abschluss": ["abs_koenigsspiel_ruhig"],
}


class StilTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.katalog = Katalog.laden()
        cls.speicher = temp_speicher()
        cls.ort = cls.speicher.ort("halle-schulzentrum")

    def _stunden(self, vorlage, gruppen_id, anzahl=4):
        return [
            eigene_stunde(self.katalog, self.ort, gruppen_id, vorlage)
            for _ in range(anzahl)
        ]

    def _plane(self, stunden, gruppen_id, seed):
        lernen = Stillernen(self.katalog, stunden)
        p = Planer(self.katalog, lernen.profil(self.katalog.altersgruppe(gruppen_id)))
        return p.plane(
            auftrag(self.ort, self.katalog, gruppen_id=gruppen_id, seed=seed, teilnehmer=16)
        )

    def test_ohne_eigene_stunden_neutrales_profil(self):
        profil = Stillernen(self.katalog, []).profil(self.katalog.altersgruppe("d"))
        self.assertEqual(profil.stichprobe, 0)
        self.assertAlmostEqual(sum(profil.anteile_fuer(["aufwaermen", "hauptteil"]).values()), 1.0)

    def test_eigene_stunden_veraendern_die_bewertung(self):
        stunden = self._stunden(TURN_STUNDE, "d")
        profil = Stillernen(self.katalog, stunden).profil(self.katalog.altersgruppe("d"))
        self.assertEqual(profil.stichprobe, 4)
        turnen = self.katalog.uebung("haupt_sprung_kasten")
        spiel = self.katalog.uebung("haupt_kleine_spiele_ball")
        self.assertGreater(profil.bewerte(turnen), profil.bewerte(spiel))

    def test_gelernter_stil_praegt_die_planung(self):
        turn_treffer = 0
        spiel_treffer = 0
        for seed in range(8):
            turn_stunde = self._plane(self._stunden(TURN_STUNDE, "d"), "d", seed)
            spiel_stunde = self._plane(self._stunden(SPIEL_STUNDE, "d"), "d", seed)
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
            turn_plan = self._plane(self._stunden(TURN_STUNDE, "d"), "d", seed)
            spiel_plan = self._plane(self._stunden(SPIEL_STUNDE, "d"), "d", seed)
            turn_anteil += sum(
                "turnen" in u.tags for u in turn_plan.stunde.alle_uebungen()
            )
            spiel_anteil += sum(
                "turnen" in u.tags for u in spiel_plan.stunde.alle_uebungen()
            )
        self.assertGreater(turn_anteil, spiel_anteil)

    def test_stil_variiert_je_altersgruppe(self):
        """Ein Stil fuer die D-Jugend faerbt nicht voll auf die B-Jugend ab."""
        stunden = self._stunden(TURN_STUNDE, "d") + self._stunden(SPIEL_STUNDE, "b")
        lernen = Stillernen(self.katalog, stunden)
        profil_d = lernen.profil(self.katalog.altersgruppe("d"))
        profil_b = lernen.profil(self.katalog.altersgruppe("b"))
        turnen = self.katalog.uebung("haupt_turnen_rolle")
        spiel = self.katalog.uebung("haupt_hockey_klein")
        self.assertGreater(profil_d.bewerte(turnen), profil_b.bewerte(turnen))
        self.assertGreater(profil_b.bewerte(spiel), profil_d.bewerte(spiel))

    def test_neue_altersgruppe_erbt_den_gesamtstil(self):
        stunden = self._stunden(TURN_STUNDE, "d")
        lernen = Stillernen(self.katalog, stunden)
        profil_c = lernen.profil(self.katalog.altersgruppe("c"))
        neutral = Stillernen(self.katalog, []).profil(self.katalog.altersgruppe("c"))
        turnen = self.katalog.uebung("haupt_turnen_rolle")
        self.assertGreater(profil_c.bewerte(turnen), neutral.bewerte(turnen))
        # ... aber schwaecher als in der Gruppe, aus der gelernt wurde.
        self.assertGreaterEqual(
            lernen.profil(self.katalog.altersgruppe("d")).bewerte(turnen),
            profil_c.bewerte(turnen),
        )

    def test_zeitaufteilung_wird_uebernommen(self):
        stunden = self._stunden(TURN_STUNDE, "d", anzahl=6)
        # Aufwaermen kuenstlich verlaengern, Hauptteil kuerzen.
        for stunde in stunden:
            stunde.teil("aufwaermen").uebungen[0].dauer = 25
            for uebung in stunde.teil("hauptteil").uebungen:
                uebung.dauer = 10
        profil = Stillernen(self.katalog, stunden).profil(self.katalog.altersgruppe("d"))
        neutral = Stillernen(self.katalog, []).profil(self.katalog.altersgruppe("d"))
        self.assertGreater(
            profil.anteile_fuer(["aufwaermen", "koordination", "hauptteil", "abschluss"])[
                "aufwaermen"
            ],
            neutral.anteile_fuer(
                ["aufwaermen", "koordination", "hauptteil", "abschluss"]
            )["aufwaermen"],
        )

    def test_nur_eigene_stunden_werden_gelernt(self):
        stunden = self._stunden(TURN_STUNDE, "d")
        for stunde in stunden:
            stunde.quelle = "geplant"
        profil = Stillernen(self.katalog, stunden).profil(self.katalog.altersgruppe("d"))
        self.assertEqual(profil.stichprobe, 0)

    def test_stil_haelt_geraetegrenzen_ein(self):
        from sportstunden.planer import pruefe_bestand

        stunden = self._stunden(TURN_STUNDE, "d", anzahl=6)
        for seed in range(5):
            ergebnis = self._plane(stunden, "d", seed)
            self.assertEqual(
                pruefe_bestand(ergebnis.stunde, self.ort.ausstattung), []
            )


if __name__ == "__main__":
    unittest.main()
