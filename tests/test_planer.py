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
        ergebnis = self._plane("halle-grundschule", "grundschule_1", seed=1)
        self.assertEqual(
            ergebnis.stunde.phasen,
            ["aufwaermen", "koordination", "hauptteil", "abschluss"],
        )

    def test_kein_koordinationsteil_fuer_junge_gruppen(self):
        for gruppen_id in ("eltern_kind", "kleinkind"):
            ergebnis = self._plane("halle-grundschule", gruppen_id, seed=2)
            self.assertNotIn("koordination", ergebnis.stunde.phasen, gruppen_id)

    def test_koordinationsteil_erzwingbar(self):
        ort = self.orte["halle-grundschule"]
        p = planer(self.katalog, gruppen_id="kleinkind")
        ergebnis = p.plane(
            auftrag(
                ort,
                self.katalog,
                gruppen_id="kleinkind",
                seed=3,
                koordinationsteil=True,
            )
        )
        self.assertIn("koordination", ergebnis.stunde.phasen)

    def test_koordinationsteil_passt_zur_altersgruppe(self):
        for gruppen_id in ("vorschule", "grundschule_1", "grundschule_2"):
            ergebnis = self._plane("halle-grundschule", gruppen_id, seed=4)
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
            for gruppen_id in ("eltern_kind", "vorschule", "grundschule_2"):
                ergebnis = self._plane(
                    "halle-grundschule", gruppen_id, dauer=dauer, seed=dauer
                )
                self.assertEqual(
                    ergebnis.stunde.gesamtdauer, dauer, f"{gruppen_id}/{dauer}"
                )

    def test_uebungen_haben_beschreibung_und_aufbau(self):
        ergebnis = self._plane("halle-grundschule", "grundschule_1", seed=5)
        for uebung in ergebnis.stunde.alle_uebungen():
            self.assertTrue(uebung.beschreibung)
            self.assertTrue(uebung.name)

    # -- Geraetebestand ----------------------------------------------------
    def test_bestand_wird_nie_ueberschritten(self):
        for ort_id, ort in self.orte.items():
            for gruppen_id in (
                "eltern_kind", "kleinkind", "vorschule", "grundschule_1", "grundschule_2"
            ):
                for seed in (1, 2, 3, 4, 5):
                    ergebnis = self._plane(ort_id, gruppen_id, seed=seed)
                    verstoesse = pruefe_bestand(ergebnis.stunde, ort.ausstattung)
                    self.assertEqual(
                        verstoesse, [], f"{ort_id}/{gruppen_id}/{seed}: {verstoesse}"
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
        p = planer(self.katalog, gruppen_id="grundschule_1")
        ergebnis = p.plane(auftrag(ort, self.katalog, gruppen_id="grundschule_1", seed=7))
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
        ort = self.orte["halle-grundschule"]
        p = planer(self.katalog, gruppen_id="grundschule_2")
        ergebnis = p.plane(
            auftrag(
                ort,
                self.katalog,
                gruppen_id="grundschule_2",
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
        ort = self.orte["halle-grundschule"]
        p = planer(self.katalog, gruppen_id="grundschule_1")
        beschraenkt = {"huetchen": 6, "softball": 8, "leibchen": 6}
        ergebnis = p.plane(
            auftrag(
                ort,
                self.katalog,
                gruppen_id="grundschule_1",
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
                "halle-grundschule", "grundschule_1", seed=seed, schwerpunkt="turnen"
            )
            tags = [tag for u in ergebnis.stunde.alle_uebungen() for tag in u.tags]
            if "turnen" in tags:
                treffer += 1
        self.assertGreaterEqual(treffer, 4)

    def test_planung_kennt_keine_teilnehmerzahl(self):
        """Die Kinderzahl ist kein Planungsparameter mehr."""
        import inspect

        from sportstunden.planer import Planungsauftrag

        self.assertNotIn("teilnehmer", inspect.signature(Planungsauftrag).parameters)
        ergebnis = self._plane("halle-grundschule", "grundschule_1", seed=21)
        self.assertEqual(ergebnis.stunde.teilnehmer, 0)

    def test_planung_ohne_ausstattung_scheitert(self):
        ort = Ort(id="leer", name="Leere Halle", art="halle", ausstattung={})
        p = planer(self.katalog, gruppen_id="grundschule_1")
        with self.assertRaises(Exception):
            p.plane(auftrag(ort, self.katalog, gruppen_id="grundschule_1"))

    def test_leerer_teil_wird_umverteilt(self):
        """Fehlt fuer einen Teil das Material, bleibt die Gesamtdauer erhalten."""
        ort = Ort(
            id="karg",
            name="Karge Wiese",
            art="freien",
            ausstattung={"huetchen": 4},
        )
        p = planer(self.katalog, gruppen_id="grundschule_1")
        ergebnis = p.plane(
            auftrag(ort, self.katalog, gruppen_id="grundschule_1", dauer=60, seed=13)
        )
        self.assertEqual(ergebnis.stunde.gesamtdauer, 60)
        self.assertEqual(pruefe_bestand(ergebnis.stunde, ort.ausstattung), [])

    def test_seed_liefert_reproduzierbare_planung(self):
        erste = self._plane("halle-grundschule", "grundschule_2", seed=42)
        zweite = self._plane("halle-grundschule", "grundschule_2", seed=42)
        self.assertEqual(
            [u.uebung_id for u in erste.stunde.alle_uebungen()],
            [u.uebung_id for u in zweite.stunde.alle_uebungen()],
        )

    def test_intensitaet_passt_zur_altersgruppe(self):
        for gruppen_id in ("eltern_kind", "kleinkind", "vorschule"):
            gruppe = self.katalog.altersgruppe(gruppen_id)
            ergebnis = self._plane("halle-grundschule", gruppen_id, seed=17)
            for uebung in ergebnis.stunde.alle_uebungen():
                self.assertLessEqual(uebung.intensitaet, gruppe.max_intensitaet)

    def test_ortsart_wird_eingehalten(self):
        for ort_id, ort in self.orte.items():
            ergebnis = self._plane(ort_id, "grundschule_1", seed=23)
            for uebung in ergebnis.stunde.alle_uebungen():
                katalog_uebung = self.katalog.uebung(uebung.uebung_id)
                self.assertIn(ort.art, katalog_uebung.orte, uebung.name)

    # -- Kinderturnen: Bewegungslandschaft ---------------------------------
    def test_stationsbetrieb_erzeugt_bewegungslandschaft(self):
        ergebnis = self._plane(
            "halle-grundschule", "vorschule", seed=8, stationsbetrieb=True
        )
        teil = ergebnis.stunde.teil("hauptteil")
        self.assertTrue(teil.parallel)
        self.assertGreaterEqual(len(teil.uebungen), 3)
        for uebung in teil.uebungen:
            katalog_uebung = self.katalog.uebung(uebung.uebung_id)
            self.assertTrue(katalog_uebung.stationsbetrieb, uebung.name)
        # Alle Stationen laufen gleich lang (Wechsel im Uhrzeigersinn).
        dauern = {u.dauer for u in teil.uebungen}
        self.assertLessEqual(max(dauern) - min(dauern), 1)
        self.assertIn("Stationen", teil.notiz)

    def test_stationszahl_richtet_sich_nach_der_halle(self):
        """Grosse Halle - mehr Stationen; kleiner Raum - weniger."""
        gross = self._plane(
            "halle-grundschule", "grundschule_1", seed=3, stationsbetrieb=True
        )
        klein = self._plane(
            "halle-vereinsheim", "grundschule_1", seed=3, stationsbetrieb=True
        )
        self.assertLess(
            len(klein.stunde.teil("hauptteil").uebungen),
            len(gross.stunde.teil("hauptteil").uebungen),
        )
        self.assertLessEqual(len(gross.stunde.teil("hauptteil").uebungen), 8)
        self.assertGreaterEqual(len(klein.stunde.teil("hauptteil").uebungen), 1)

    def test_stationszahl_laesst_sich_vorgeben(self):
        ergebnis = self._plane(
            "halle-grundschule",
            "grundschule_1",
            seed=3,
            stationsbetrieb=True,
            stationszahl=4,
        )
        self.assertEqual(len(ergebnis.stunde.teil("hauptteil").uebungen), 4)

    def test_spielmodus_plant_grosses_spiel(self):
        ergebnis = self._plane(
            "halle-grundschule", "grundschule_1", seed=6, stationsbetrieb=False
        )
        teil = ergebnis.stunde.teil("hauptteil")
        self.assertTrue(teil.uebungen)
        for uebung in teil.uebungen:
            self.assertFalse(self.katalog.uebung(uebung.uebung_id).stationsbetrieb)

    def test_stationen_summieren_material(self):
        ergebnis = self._plane(
            "halle-grundschule", "vorschule", seed=12, stationsbetrieb=True
        )
        teil = ergebnis.stunde.teil("hauptteil")
        summe = {}
        for uebung in teil.uebungen:
            for geraet, anzahl in uebung.gesamtbedarf.items():
                summe[geraet] = summe.get(geraet, 0) + anzahl
        self.assertEqual(teil.bedarf(), summe)
        ort = self.orte["halle-grundschule"]
        for geraet, anzahl in summe.items():
            self.assertLessEqual(anzahl, ort.bestand(geraet), geraet)

    def test_thema_praegt_die_auswahl(self):
        mit_thema = 0
        ohne_thema = 0
        for seed in range(6):
            passend = self._plane(
                "halle-grundschule", "vorschule", seed=seed, thema="dschungel",
                stationsbetrieb=True,
            )
            neutral = self._plane(
                "halle-grundschule", "vorschule", seed=seed, stationsbetrieb=True
            )
            mit_thema += sum(
                self.katalog.uebung(u.uebung_id).thema == "dschungel"
                for u in passend.stunde.alle_uebungen()
            )
            ohne_thema += sum(
                self.katalog.uebung(u.uebung_id).thema == "dschungel"
                for u in neutral.stunde.alle_uebungen()
            )
        self.assertGreater(mit_thema, ohne_thema)
        self.assertGreater(mit_thema, 0)

    def test_thema_wird_in_der_stunde_gespeichert(self):
        ergebnis = self._plane("halle-grundschule", "vorschule", seed=2, thema="zirkus")
        self.assertEqual(ergebnis.stunde.thema, "zirkus")
        self.assertIn("Zirkus", ergebnis.stunde.titel)


if __name__ == "__main__":
    unittest.main()
