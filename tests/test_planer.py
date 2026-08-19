import unittest

from sportstunden.katalog import Katalog
from sportstunden.models import Ort
from sportstunden.planer import Planungsauftrag, pruefe_bestand
from tests.hilfen import auftrag, planer, temp_speicher


class PlanerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.katalog = Katalog.laden()
        cls.speicher = temp_speicher()
        cls.orte = {o.id: o for o in cls.speicher.orte()}

    def _plane(self, ort_id: str, gruppen_id: str, **kwargs):
        ort = self.orte[ort_id]
        p = planer(self.katalog, gruppen_id=gruppen_id)
        return p.plane(auftrag(ort, self.katalog, gruppen_id=gruppen_id, **kwargs))

    # -- Struktur ----------------------------------------------------------
    def test_phasenreihenfolge_mit_koordinationsteil(self):
        ergebnis = self._plane("halle-schulzentrum", "d", seed=1)
        self.assertEqual(
            ergebnis.stunde.phasen,
            ["aufwaermen", "koordination", "hauptteil", "abschluss"],
        )

    def test_kein_koordinationsteil_fuer_junge_gruppen(self):
        for gruppen_id in ("bambini", "f"):
            ergebnis = self._plane("halle-schulzentrum", gruppen_id, seed=2)
            self.assertNotIn("koordination", ergebnis.stunde.phasen, gruppen_id)

    def test_koordinationsteil_erzwingbar(self):
        ort = self.orte["halle-schulzentrum"]
        p = planer(self.katalog, gruppen_id="f")
        ergebnis = p.plane(
            auftrag(ort, self.katalog, gruppen_id="f", seed=3, koordinationsteil=True)
        )
        self.assertIn("koordination", ergebnis.stunde.phasen)

    def test_koordinationsteil_passt_zur_altersgruppe(self):
        for gruppen_id in ("e", "d", "c", "b", "senioren"):
            ergebnis = self._plane("halle-schulzentrum", gruppen_id, seed=4)
            teil = ergebnis.stunde.teil("koordination")
            self.assertIsNotNone(teil, gruppen_id)
            schwerpunkte = set(
                self.katalog.altersgruppe(gruppen_id).koordination_schwerpunkte
            )
            for uebung in teil.uebungen:
                self.assertTrue(
                    set(uebung.koordination) & schwerpunkte,
                    f"{gruppen_id}: {uebung.name} passt nicht zu {schwerpunkte}",
                )

    def test_dauer_wird_exakt_eingehalten(self):
        for dauer in (30, 45, 60, 75, 90, 120):
            for gruppen_id in ("bambini", "e", "c", "erwachsene"):
                ergebnis = self._plane(
                    "halle-schulzentrum", gruppen_id, dauer=dauer, seed=dauer
                )
                self.assertEqual(
                    ergebnis.stunde.gesamtdauer, dauer, f"{gruppen_id}/{dauer}"
                )

    def test_uebungen_haben_beschreibung_und_aufbau(self):
        ergebnis = self._plane("halle-schulzentrum", "d", seed=5)
        for uebung in ergebnis.stunde.alle_uebungen():
            self.assertTrue(uebung.beschreibung)
            self.assertTrue(uebung.name)

    # -- Geraetebestand ----------------------------------------------------
    def test_bestand_wird_nie_ueberschritten(self):
        for ort_id, ort in self.orte.items():
            for gruppen_id in ("bambini", "f", "e", "d", "c", "b", "a", "erwachsene", "senioren"):
                for teilnehmer in (6, 14, 24, 40):
                    for seed in (1, 2, 3):
                        ergebnis = self._plane(
                            ort_id,
                            gruppen_id,
                            teilnehmer=teilnehmer,
                            seed=seed,
                        )
                        verstoesse = pruefe_bestand(ergebnis.stunde, ort.ausstattung)
                        self.assertEqual(
                            verstoesse,
                            [],
                            f"{ort_id}/{gruppen_id}/{teilnehmer}/{seed}: {verstoesse}",
                        )

    def test_absicherung_zaehlt_zum_bestand(self):
        """Matten reichen nur fuer wenige Geraete - das muss die Planung merken."""
        ort = Ort(
            id="test-halle",
            name="Testhalle",
            art="halle",
            ausstattung={
                "minitrampolin": 4,
                "niedersprungmatte": 1,
                "matte": 2,
                "softball": 10,
                "huetchen": 10,
                "langbank": 2,
                "reifen": 10,
                "markierungsteller": 10,
            },
        )
        p = planer(self.katalog, gruppen_id="d")
        ergebnis = p.plane(auftrag(ort, self.katalog, gruppen_id="d", teilnehmer=24, seed=7))
        self.assertEqual(pruefe_bestand(ergebnis.stunde, ort.ausstattung), [])
        for uebung in ergebnis.stunde.alle_uebungen():
            trampoline = uebung.geraete.get("minitrampolin", 0)
            if trampoline:
                self.assertGreaterEqual(
                    uebung.absicherung.get("niedersprungmatte", 0), trampoline
                )
                self.assertLessEqual(
                    uebung.absicherung.get("niedersprungmatte", 0), 1
                )

    def test_gemeinsames_material_summiert_ueber_alle_teile(self):
        ort = self.orte["halle-schulzentrum"]
        p = planer(self.katalog, gruppen_id="c")
        ergebnis = p.plane(
            auftrag(
                ort,
                self.katalog,
                gruppen_id="c",
                teilnehmer=20,
                seed=9,
                umbau_zwischen_teilen=False,
            )
        )
        summe = {}
        for teil in ergebnis.stunde.teile:
            for geraet, anzahl in teil.bedarf().items():
                summe[geraet] = summe.get(geraet, 0) + anzahl
        for geraet, anzahl in summe.items():
            self.assertLessEqual(
                anzahl, ort.bestand(geraet), f"{geraet}: {anzahl} > {ort.bestand(geraet)}"
            )

    def test_eingeschraenkte_ausstattung_wird_beachtet(self):
        ort = self.orte["halle-schulzentrum"]
        p = planer(self.katalog, gruppen_id="d")
        beschraenkt = {"huetchen": 6, "softball": 8, "leibchen": 6}
        ergebnis = p.plane(
            auftrag(
                ort,
                self.katalog,
                gruppen_id="d",
                teilnehmer=18,
                seed=11,
                ausstattung=beschraenkt,
            )
        )
        for teil in ergebnis.stunde.teile:
            for geraet, anzahl in teil.bedarf().items():
                self.assertIn(geraet, beschraenkt)
                self.assertLessEqual(anzahl, beschraenkt[geraet])

    def test_schwerpunkt_wird_beruecksichtigt(self):
        treffer = 0
        for seed in range(6):
            ergebnis = self._plane(
                "halle-schulzentrum", "d", seed=seed, schwerpunkt="turnen"
            )
            tags = [tag for u in ergebnis.stunde.alle_uebungen() for tag in u.tags]
            if "turnen" in tags:
                treffer += 1
        self.assertGreaterEqual(treffer, 5)

    def test_teilnehmerzahl_erhoeht_bedarf(self):
        klein = self._plane("halle-schulzentrum", "d", teilnehmer=8, seed=21)
        gross = self._plane("halle-schulzentrum", "d", teilnehmer=32, seed=21)
        summe = lambda stunde: sum(stunde.materialliste().values())
        self.assertGreater(summe(gross.stunde), summe(klein.stunde))

    def test_planung_ohne_ausstattung_scheitert(self):
        ort = Ort(id="leer", name="Leere Halle", art="halle", ausstattung={})
        p = planer(self.katalog, gruppen_id="d")
        with self.assertRaises(Exception):
            p.plane(auftrag(ort, self.katalog, gruppen_id="d"))

    def test_leerer_teil_wird_umverteilt(self):
        """Fehlt fuer einen Teil das Material, bleibt die Gesamtdauer erhalten."""
        ort = Ort(
            id="karg",
            name="Karge Wiese",
            art="freien",
            ausstattung={"huetchen": 4},
        )
        p = planer(self.katalog, gruppen_id="d")
        ergebnis = p.plane(
            auftrag(ort, self.katalog, gruppen_id="d", dauer=60, teilnehmer=12, seed=13)
        )
        self.assertEqual(ergebnis.stunde.gesamtdauer, 60)
        self.assertEqual(pruefe_bestand(ergebnis.stunde, ort.ausstattung), [])

    def test_seed_liefert_reproduzierbare_planung(self):
        erste = self._plane("halle-schulzentrum", "c", seed=42)
        zweite = self._plane("halle-schulzentrum", "c", seed=42)
        self.assertEqual(
            [u.uebung_id for u in erste.stunde.alle_uebungen()],
            [u.uebung_id for u in zweite.stunde.alle_uebungen()],
        )

    def test_intensitaet_passt_zur_altersgruppe(self):
        for gruppen_id in ("bambini", "senioren"):
            gruppe = self.katalog.altersgruppe(gruppen_id)
            ergebnis = self._plane("halle-schulzentrum", gruppen_id, seed=17)
            for uebung in ergebnis.stunde.alle_uebungen():
                self.assertLessEqual(uebung.intensitaet, gruppe.max_intensitaet)

    def test_ortsart_wird_eingehalten(self):
        for ort_id, ort in self.orte.items():
            ergebnis = self._plane(ort_id, "d", seed=23)
            for uebung in ergebnis.stunde.alle_uebungen():
                katalog_uebung = self.katalog.uebung(uebung.uebung_id)
                self.assertIn(ort.art, katalog_uebung.orte, uebung.name)


if __name__ == "__main__":
    unittest.main()
