"""Minimaler PDF-Generator ohne externe Abhaengigkeiten.

Es werden nur die 14 Standardschriften (Helvetica) verwendet, damit die
erzeugten Dateien ohne eingebettete Fonts auskommen und in jedem Viewer
lesbar sind. Der Textumbruch nutzt die echten Zeichenbreiten der Schrift.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

A4 = (595.28, 841.89)

_HELVETICA = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]

_HELVETICA_BOLD = [
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
]

# Sonderzeichen (WinAnsi) auf die Breite eines aehnlichen Grundzeichens legen.
_SONDERBREITEN_BASIS = {
    0xC4: "A", 0xD6: "O", 0xDC: "U", 0xE4: "a", 0xF6: "o", 0xFC: "u", 0xDF: "s",
    0xC9: "E", 0xE9: "e", 0xE8: "e", 0xEA: "e", 0xE0: "a", 0xE2: "a", 0xF4: "o",
    0xE7: "c", 0xF1: "n", 0xB0: "o", 0xA7: "s", 0x80: "E", 0x92: "'", 0x93: '"',
    0x94: '"', 0x96: "-", 0x97: "-",
}


def _breite(zeichen: str, fett: bool) -> float:
    tabelle = _HELVETICA_BOLD if fett else _HELVETICA
    code = ord(zeichen)
    if 32 <= code <= 126:
        return tabelle[code - 32]
    ersatz = _SONDERBREITEN_BASIS.get(code)
    if ersatz:
        return tabelle[ord(ersatz) - 32]
    return tabelle[ord("n") - 32]


def textbreite(text: str, groesse: float, fett: bool = False) -> float:
    return sum(_breite(z, fett) for z in text) * groesse / 1000.0


def umbrechen(text: str, breite: float, groesse: float, fett: bool = False) -> List[str]:
    """Bricht Text auf die angegebene Breite (in Punkt) um."""
    zeilen: List[str] = []
    for absatz in text.split("\n"):
        worte = absatz.split()
        if not worte:
            zeilen.append("")
            continue
        aktuell = worte[0]
        for wort in worte[1:]:
            versuch = f"{aktuell} {wort}"
            if textbreite(versuch, groesse, fett) <= breite:
                aktuell = versuch
            else:
                zeilen.append(aktuell)
                aktuell = wort
        zeilen.append(aktuell)
    return zeilen


def _kodieren(text: str) -> bytes:
    roh = text.encode("cp1252", errors="replace")
    ausgabe = bytearray()
    for byte in roh:
        if byte in (0x28, 0x29, 0x5C):  # ( ) \
            ausgabe.append(0x5C)
        ausgabe.append(byte)
    return bytes(ausgabe)


@dataclass
class Farbe:
    r: float
    g: float
    b: float

    def pdf(self) -> str:
        return f"{self.r:.3f} {self.g:.3f} {self.b:.3f}"


SCHWARZ = Farbe(0.10, 0.10, 0.12)
GRAU = Farbe(0.42, 0.44, 0.48)
HELLGRAU = Farbe(0.92, 0.93, 0.95)
AKZENT = Farbe(0.09, 0.34, 0.55)
AKZENT_HELL = Farbe(0.87, 0.92, 0.96)
WARNROT = Farbe(0.70, 0.18, 0.14)


class Seite:
    def __init__(self) -> None:
        self.inhalt: List[str] = []

    def anhaengen(self, befehl: str) -> None:
        self.inhalt.append(befehl)

    def stream(self) -> bytes:
        return "\n".join(self.inhalt).encode("latin-1", errors="replace")


class PDF:
    """Sehr einfacher Seitensatz: Fliesstext, Ueberschriften, Tabellen."""

    def __init__(
        self,
        titel: str = "",
        format: Tuple[float, float] = A4,
        rand: float = 48.0,
        fusstext: str = "",
    ) -> None:
        self.breite, self.hoehe = format
        self.rand = rand
        self.titel = titel
        self.fusstext = fusstext
        self.seiten: List[Seite] = []
        self.seite: Optional[Seite] = None
        self.y = 0.0
        self.neue_seite()

    # -- Grundlagen --------------------------------------------------------
    @property
    def satzbreite(self) -> float:
        return self.breite - 2 * self.rand

    def neue_seite(self) -> None:
        self.seite = Seite()
        self.seiten.append(self.seite)
        self.y = self.hoehe - self.rand

    def platz_pruefen(self, benoetigt: float) -> None:
        if self.y - benoetigt < self.rand + 28:
            self.neue_seite()

    def abstand(self, hoehe: float) -> None:
        self.y -= hoehe

    # -- Zeichenbefehle ----------------------------------------------------
    def _text(
        self,
        text: str,
        x: float,
        y: float,
        groesse: float,
        fett: bool = False,
        farbe: Farbe = SCHWARZ,
        kursiv: bool = False,
    ) -> None:
        schrift = "F2" if fett else ("F3" if kursiv else "F1")
        self.seite.anhaengen(
            f"BT {farbe.pdf()} rg /{schrift} {groesse:.2f} Tf "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ({_kodieren(text).decode('latin-1')}) Tj ET"
        )

    def rechteck(
        self, x: float, y: float, breite: float, hoehe: float, farbe: Farbe
    ) -> None:
        self.seite.anhaengen(
            f"{farbe.pdf()} rg {x:.2f} {y:.2f} {breite:.2f} {hoehe:.2f} re f"
        )

    def linie(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        farbe: Farbe = GRAU,
        staerke: float = 0.6,
    ) -> None:
        self.seite.anhaengen(
            f"{farbe.pdf()} RG {staerke:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"
        )

    # -- Textbausteine -----------------------------------------------------
    def kopfzeile(self, titel: str, untertitel: str = "") -> None:
        hoehe = 54.0
        self.rechteck(0, self.hoehe - hoehe, self.breite, hoehe, AKZENT)
        self._text(titel, self.rand, self.hoehe - 32, 17, fett=True, farbe=Farbe(1, 1, 1))
        if untertitel:
            self._text(
                untertitel, self.rand, self.hoehe - 46, 9.5, farbe=Farbe(0.88, 0.92, 0.97)
            )
        self.y = self.hoehe - hoehe - 22

    def ueberschrift(self, text: str, groesse: float = 13.0, farbe: Farbe = AKZENT) -> None:
        self.platz_pruefen(groesse + 16)
        self.abstand(groesse + 4)
        self._text(text, self.rand, self.y, groesse, fett=True, farbe=farbe)
        self.abstand(4)
        self.linie(self.rand, self.y, self.breite - self.rand, self.y, HELLGRAU, 1.0)
        self.abstand(8)

    def zwischentitel(self, text: str, groesse: float = 10.5) -> None:
        self.platz_pruefen(groesse + 8)
        self.abstand(groesse + 3)
        self._text(text, self.rand, self.y, groesse, fett=True)
        self.abstand(3)

    def absatz(
        self,
        text: str,
        groesse: float = 9.5,
        einzug: float = 0.0,
        farbe: Farbe = SCHWARZ,
        fett: bool = False,
        kursiv: bool = False,
        zeilenabstand: float = 1.35,
    ) -> None:
        if not text:
            return
        breite = self.satzbreite - einzug
        for zeile in umbrechen(text, breite, groesse, fett):
            self.platz_pruefen(groesse * zeilenabstand)
            self.abstand(groesse * zeilenabstand)
            if zeile:
                self._text(
                    zeile, self.rand + einzug, self.y, groesse, fett=fett, farbe=farbe,
                    kursiv=kursiv,
                )

    def aufzaehlung(
        self, eintraege: Iterable[str], groesse: float = 9.5, zeichen: str = "-"
    ) -> None:
        for eintrag in eintraege:
            zeilen = umbrechen(eintrag, self.satzbreite - 14, groesse)
            for index, zeile in enumerate(zeilen):
                self.platz_pruefen(groesse * 1.35)
                self.abstand(groesse * 1.35)
                if index == 0:
                    self._text(zeichen, self.rand, self.y, groesse, farbe=GRAU)
                self._text(zeile, self.rand + 14, self.y, groesse)

    def hinweiskasten(
        self, titel: str, zeilen: Sequence[str], farbe: Farbe = AKZENT_HELL,
        textfarbe: Farbe = SCHWARZ, groesse: float = 9.0,
    ) -> None:
        umbrochen: List[str] = []
        for zeile in zeilen:
            umbrochen.extend(umbrechen(zeile, self.satzbreite - 24, groesse))
        hoehe = 18 + len(umbrochen) * groesse * 1.35 + 8
        self.platz_pruefen(hoehe + 10)
        self.abstand(hoehe)
        self.rechteck(self.rand, self.y, self.satzbreite, hoehe, farbe)
        y = self.y + hoehe - 13
        self._text(titel, self.rand + 10, y, groesse + 0.5, fett=True, farbe=textfarbe)
        for zeile in umbrochen:
            y -= groesse * 1.35
            self._text(zeile, self.rand + 10, y, groesse, farbe=textfarbe)
        self.abstand(6)

    # -- Tabelle -----------------------------------------------------------
    def tabelle(
        self,
        kopf: Sequence[str],
        zeilen: Sequence[Sequence[str]],
        breiten: Sequence[float],
        groesse: float = 9.0,
    ) -> None:
        """Tabelle mit automatischem Umbruch und Seitenwechsel."""
        spalten = [self.satzbreite * anteil for anteil in breiten]

        def kopf_zeichnen() -> None:
            hoehe = groesse * 1.7
            self.platz_pruefen(hoehe + 6)
            self.abstand(hoehe)
            self.rechteck(self.rand, self.y, self.satzbreite, hoehe, AKZENT)
            x = self.rand + 5
            for index, zelle in enumerate(kopf):
                self._text(
                    zelle, x, self.y + 5, groesse, fett=True, farbe=Farbe(1, 1, 1)
                )
                x += spalten[index]

        kopf_zeichnen()
        for nummer, zeile in enumerate(zeilen):
            zellen = [
                umbrechen(str(zelle), spalten[index] - 10, groesse)
                for index, zelle in enumerate(zeile)
            ]
            zeilenzahl = max(len(z) for z in zellen) or 1
            hoehe = zeilenzahl * groesse * 1.32 + 6
            if self.y - hoehe < self.rand + 28:
                self.neue_seite()
                kopf_zeichnen()
            self.abstand(hoehe)
            if nummer % 2 == 0:
                self.rechteck(self.rand, self.y, self.satzbreite, hoehe, HELLGRAU)
            x = self.rand + 5
            for index, inhalt in enumerate(zellen):
                y = self.y + hoehe - groesse - 1
                for text in inhalt:
                    self._text(text, x, y, groesse)
                    y -= groesse * 1.32
                x += spalten[index]
        self.abstand(6)

    # -- Ausgabe -----------------------------------------------------------
    def _fusszeilen_setzen(self) -> None:
        gesamt = len(self.seiten)
        for nummer, seite in enumerate(self.seiten, start=1):
            self.seite = seite
            y = self.rand - 14
            self.linie(self.rand, y + 12, self.breite - self.rand, y + 12, HELLGRAU, 0.8)
            if self.fusstext:
                self._text(self.fusstext, self.rand, y, 8, farbe=GRAU)
            text = f"Seite {nummer} von {gesamt}"
            self._text(
                text,
                self.breite - self.rand - textbreite(text, 8),
                y,
                8,
                farbe=GRAU,
            )

    def bytes(self) -> bytes:
        self._fusszeilen_setzen()

        objekte: List[bytes] = []

        def objekt(daten: bytes) -> int:
            objekte.append(daten)
            return len(objekte)

        schriften = {}
        for name, basis in (("F1", "Helvetica"), ("F2", "Helvetica-Bold"), ("F3", "Helvetica-Oblique")):
            schriften[name] = objekt(
                f"<< /Type /Font /Subtype /Type1 /BaseFont /{basis} "
                f"/Encoding /WinAnsiEncoding >>".encode("latin-1")
            )

        seiten_ids: List[int] = []
        inhalt_ids: List[int] = []
        for seite in self.seiten:
            komprimiert = zlib.compress(seite.stream())
            inhalt_ids.append(
                objekt(
                    b"<< /Length "
                    + str(len(komprimiert)).encode()
                    + b" /Filter /FlateDecode >>\nstream\n"
                    + komprimiert
                    + b"\nendstream"
                )
            )
            seiten_ids.append(0)  # Platzhalter, wird unten ersetzt

        pages_id = len(objekte) + len(self.seiten) + 1
        for index, _ in enumerate(self.seiten):
            ressourcen = " ".join(
                f"/{name} {nummer} 0 R" for name, nummer in schriften.items()
            )
            seiten_ids[index] = objekt(
                (
                    f"<< /Type /Page /Parent {pages_id} 0 R "
                    f"/MediaBox [0 0 {self.breite:.2f} {self.hoehe:.2f}] "
                    f"/Resources << /Font << {ressourcen} >> >> "
                    f"/Contents {inhalt_ids[index]} 0 R >>"
                ).encode("latin-1")
            )

        kinder = " ".join(f"{nummer} 0 R" for nummer in seiten_ids)
        pages = objekt(
            f"<< /Type /Pages /Count {len(seiten_ids)} /Kids [{kinder}] >>".encode(
                "latin-1"
            )
        )
        assert pages == pages_id
        info = objekt(
            f"<< /Title ({_kodieren(self.titel).decode('latin-1')}) "
            f"/Producer (Sportstunden-Planer) >>".encode("latin-1")
        )
        katalog = objekt(f"<< /Type /Catalog /Pages {pages} 0 R >>".encode("latin-1"))

        ausgabe = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        versatz: List[int] = []
        for nummer, daten in enumerate(objekte, start=1):
            versatz.append(len(ausgabe))
            ausgabe += f"{nummer} 0 obj\n".encode("latin-1") + daten + b"\nendobj\n"

        xref_start = len(ausgabe)
        ausgabe += f"xref\n0 {len(objekte) + 1}\n".encode("latin-1")
        ausgabe += b"0000000000 65535 f \n"
        for stelle in versatz:
            ausgabe += f"{stelle:010d} 00000 n \n".encode("latin-1")
        ausgabe += (
            f"trailer\n<< /Size {len(objekte) + 1} /Root {katalog} 0 R "
            f"/Info {info} 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
        ).encode("latin-1")
        return bytes(ausgabe)

    def speichern(self, pfad: Path | str) -> Path:
        pfad = Path(pfad)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_bytes(self.bytes())
        return pfad
