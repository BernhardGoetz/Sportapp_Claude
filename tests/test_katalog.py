import unittest

from sportstunden.katalog import Katalog


class KatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.katalog = Katalog.laden()

    def test_katalog_ist_konsistent(self):
        self.katalog.pruefe_konsistenz()
        self.assertGreater(len(self.katalog.uebungen), 60)
        for phase in ("aufwaermen", "koordination", "hauptteil", "abschluss"):
            self.assertTrue(
                [u for u in self.katalog.uebungen if u.phase == phase],
                f"keine Uebungen fuer {phase}",
            )

    def test_uebungs_ids_sind_eindeutig(self):
        ids = [u.id for u in self.katalog.uebungen]
        self.assertEqual(len(ids), len(set(ids)))

    def test_katalog_ist_auf_kinderturnen_zugeschnitten(self):
        """Alle Inhalte liegen im Altersbereich 1 bis 10 Jahre."""
        for uebung in self.katalog.uebungen:
            self.assertGreaterEqual(uebung.alter_min, 1, uebung.id)
            self.assertLessEqual(uebung.alter_max, 10, uebung.id)
            self.assertLessEqual(uebung.intensitaet, 4, uebung.id)

    def test_altersgruppen_decken_eins_bis_zehn_ab(self):
        gruppen = self.katalog.altersgruppen
        self.assertEqual(gruppen[0].alter_min, 1)
        self.assertEqual(gruppen[-1].alter_max, 10)
        for alter in range(1, 11):
            gruppe = self.katalog.altersgruppe_fuer_alter(alter)
            self.assertLessEqual(gruppe.alter_min, alter)
            self.assertGreaterEqual(gruppe.alter_max, alter)

    def test_jede_uebung_hat_beschreibung_und_aufbau(self):
        for uebung in self.katalog.uebungen:
            self.assertTrue(uebung.beschreibung, uebung.id)
            self.assertTrue(uebung.aufbau, uebung.id)

    def test_stationen_sind_unabhaengig_von_der_kindergruppe(self):
        """Eine Station wird einmal aufgebaut - ihr Material skaliert nicht."""
        for uebung in self.katalog.uebungen:
            if uebung.phase == "hauptteil" and uebung.stationsbetrieb:
                self.assertEqual(uebung.gruppengroesse, 0, uebung.id)
                self.assertFalse(uebung.geraete_pro_gruppe, uebung.id)

    def test_koordinationsuebungen_haben_faehigkeiten(self):
        for uebung in self.katalog.uebungen:
            if uebung.phase == "koordination":
                self.assertTrue(
                    uebung.koordination, f"{uebung.id} ohne koordinative Faehigkeit"
                )

    def test_sicherheitsregel_wird_ergaenzt(self):
        uebung = self.katalog.uebung("st_trampolin_artist")
        geraete, absicherung, _ = self.katalog.bedarf(uebung, 16)
        self.assertEqual(geraete["minitrampolin"], 1)
        self.assertGreaterEqual(absicherung["niedersprungmatte"], 1)

    def test_absicherung_auch_ohne_deklaration(self):
        uebung = self.katalog.uebung("st_reck_schwingen")
        uebung.absicherung_fix = {}
        uebung.absicherung_pro_gruppe = {}
        geraete, absicherung, _ = self.katalog.bedarf(uebung, 12)
        self.assertEqual(absicherung["matte"], 2 * geraete["reck"])

    def test_koordinationsteil_ab_altersklasse(self):
        for gruppen_id in ("eltern_kind", "kleinkind"):
            self.assertFalse(
                self.katalog.braucht_koordinationsteil(
                    self.katalog.altersgruppe(gruppen_id)
                ),
                gruppen_id,
            )
        for gruppen_id in ("vorschule", "grundschule_1", "grundschule_2"):
            self.assertTrue(
                self.katalog.braucht_koordinationsteil(
                    self.katalog.altersgruppe(gruppen_id)
                ),
                gruppen_id,
            )

    def test_geraete_haben_kurzform(self):
        self.assertEqual(self.katalog.geraet_kurz("langbank"), "LB")
        self.assertEqual(self.katalog.geraet_kurz("weichbodenmatte"), "WB")
        self.assertEqual(self.katalog.geraet_kurz("kasten_klein"), "kl. Kasten")

    def test_themen_vorhanden(self):
        themen = self.katalog.themen()
        for thema in ("sommer", "dschungel", "zirkus"):
            self.assertIn(thema, themen)


if __name__ == "__main__":
    unittest.main()
