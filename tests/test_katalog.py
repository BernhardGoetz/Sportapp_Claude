import unittest

from sportstunden.katalog import Katalog


class KatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.katalog = Katalog.laden()

    def test_katalog_ist_konsistent(self):
        self.katalog.pruefe_konsistenz()
        self.assertGreater(len(self.katalog.uebungen), 50)
        for phase in ("aufwaermen", "koordination", "hauptteil", "abschluss"):
            self.assertTrue(
                [u for u in self.katalog.uebungen if u.phase == phase],
                f"keine Uebungen fuer {phase}",
            )

    def test_uebungs_ids_sind_eindeutig(self):
        ids = [u.id for u in self.katalog.uebungen]
        self.assertEqual(len(ids), len(set(ids)))

    def test_koordinationsuebungen_haben_faehigkeiten(self):
        for uebung in self.katalog.uebungen:
            if uebung.phase == "koordination":
                self.assertTrue(
                    uebung.koordination, f"{uebung.id} ohne koordinative Faehigkeit"
                )

    def test_sicherheitsregel_wird_ergaenzt(self):
        uebung = self.katalog.uebung("haupt_minitramp_sprung")
        geraete, absicherung, gruppen = self.katalog.bedarf(uebung, 16)
        self.assertEqual(gruppen, 2)
        self.assertEqual(geraete["minitrampolin"], 2)
        # Pro Minitrampolin ist eine Niedersprungmatte Pflicht.
        self.assertGreaterEqual(absicherung["niedersprungmatte"], 2)

    def test_absicherung_auch_ohne_deklaration(self):
        uebung = self.katalog.uebung("haupt_reck_huefaufschwung")
        uebung.absicherung_fix = {}
        uebung.absicherung_pro_gruppe = {}
        geraete, absicherung, _ = self.katalog.bedarf(uebung, 12)
        self.assertEqual(absicherung["matte"], 2 * geraete["reck"])

    def test_koordinationsteil_ab_altersklasse(self):
        self.assertFalse(
            self.katalog.braucht_koordinationsteil(self.katalog.altersgruppe("bambini"))
        )
        self.assertFalse(
            self.katalog.braucht_koordinationsteil(self.katalog.altersgruppe("f"))
        )
        for gruppen_id in ("e", "d", "c", "b", "a", "erwachsene", "senioren"):
            self.assertTrue(
                self.katalog.braucht_koordinationsteil(
                    self.katalog.altersgruppe(gruppen_id)
                ),
                gruppen_id,
            )

    def test_altersgruppe_fuer_alter(self):
        self.assertEqual(self.katalog.altersgruppe_fuer_alter(11).id, "d")
        self.assertEqual(self.katalog.altersgruppe_fuer_alter(4).id, "bambini")
        self.assertEqual(self.katalog.altersgruppe_fuer_alter(75).id, "senioren")


if __name__ == "__main__":
    unittest.main()
