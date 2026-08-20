"""Grafische Oberflaeche (Tkinter) fuer den Kinderturnen-Stundenplaner.

Links werden Ort, Gruppe und Wuensche eingestellt, in der Mitte steht der
Hallenplan: Die Stationen lassen sich mit der Maus an ihren tatsaechlichen
Platz schieben. Unten stehen Anfang, Stationsliste und Ende, dazu die
Schaltflaechen zum Speichern und fuer das PDF.

Tkinter gehoert zur Standardbibliothek; unter Linux muss es teilweise mit
``sudo apt install python3-tk`` nachinstalliert werden.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from .export import dateiname_fuer, stunden_pdf
from .hallenplan import (
    BESCHRIFTUNG,
    GERAET_FARBE,
    STATIONSFLAECHE,
    Zeichner,
    station_an_punkt,
    zeichne_hallenplan,
)
from .katalog import Katalog
from .pdf import Farbe
from .planer import Planer, Planungsauftrag, Planungsergebnis, Planungsfehler
from .platzierung import kollisionen
from .speicher import Speicher
from .stil import Stillernen

RASTER = 0.25  # Fangraster beim Verschieben, in Metern
WARNFARBE = Farbe(0.75, 0.2, 0.15)


def _hex(farbe: Farbe) -> str:
    return "#%02x%02x%02x" % (
        int(max(0.0, min(1.0, farbe.r)) * 255),
        int(max(0.0, min(1.0, farbe.g)) * 255),
        int(max(0.0, min(1.0, farbe.b)) * 255),
    )


class CanvasZeichner(Zeichner):
    """Zeichnet den Hallenplan auf eine Tk-Leinwand.

    Die Zeichenflaeche rechnet wie das PDF mit dem Ursprung links unten,
    die Leinwand mit dem Ursprung links oben - deshalb wird y gespiegelt.
    """

    def __init__(self, canvas: tk.Canvas, hoehe: float) -> None:
        self.canvas = canvas
        self.hoehe = hoehe

    def _y(self, wert: float) -> float:
        return self.hoehe - wert

    def rechteck(self, x, y, breite, hoehe, farbe=GERAET_FARBE, staerke=0.8) -> None:
        self.canvas.create_rectangle(
            x, self._y(y + hoehe), x + breite, self._y(y),
            outline=_hex(farbe), width=max(1.0, staerke),
        )

    def flaeche(self, x, y, breite, hoehe, farbe=STATIONSFLAECHE) -> None:
        self.canvas.create_rectangle(
            x, self._y(y + hoehe), x + breite, self._y(y),
            outline="", fill=_hex(farbe),
        )

    def linie(self, x1, y1, x2, y2, farbe=GERAET_FARBE, staerke=0.6) -> None:
        self.canvas.create_line(
            x1, self._y(y1), x2, self._y(y2), fill=_hex(farbe), width=max(1.0, staerke)
        )

    def kreis(self, x, y, radius, farbe=GERAET_FARBE, staerke=0.8, fuellen=False) -> None:
        self.canvas.create_oval(
            x - radius, self._y(y + radius), x + radius, self._y(y - radius),
            outline=_hex(farbe),
            width=max(1.0, staerke),
            fill=_hex(farbe) if fuellen else "",
        )

    def pfad(self, punkte, farbe=GERAET_FARBE, staerke=0.8, schliessen=False, fuellen=False) -> None:
        flach: List[float] = []
        for punkt_x, punkt_y in punkte:
            flach.extend([punkt_x, self._y(punkt_y)])
        if schliessen and len(punkte) > 2:
            self.canvas.create_polygon(
                flach,
                outline=_hex(farbe),
                width=max(1.0, staerke),
                fill=_hex(farbe) if fuellen else "",
            )
        else:
            self.canvas.create_line(flach, fill=_hex(farbe), width=max(1.0, staerke))

    def text(self, inhalt, x, y, groesse=7.0, farbe=BESCHRIFTUNG, fett=False, zentriert=False) -> None:
        self.canvas.create_text(
            x,
            self._y(y),
            text=inhalt,
            anchor="center" if zentriert else "w",
            fill=_hex(farbe),
            font=("TkDefaultFont", max(6, int(groesse)), "bold" if fett else "normal"),
        )


class Planerfenster(tk.Tk):
    def __init__(self, speicher: Speicher) -> None:
        super().__init__()
        self.speicher = speicher
        self.katalog = Katalog.laden()
        einstellungen = speicher.einstellungen()
        self.katalog.koordination_ab_alter = int(
            einstellungen.get("koordination_ab_alter", self.katalog.koordination_ab_alter)
        )
        self.orte = speicher.orte()
        self.ergebnis: Optional[Planungsergebnis] = None
        self.massstab = None
        self.gezogen = None
        self.zieh_versatz = (0.0, 0.0)

        self.title("Kinderturnen - Stundenplaner")
        self.geometry("1180x820")
        self._baue_oberflaeche(einstellungen)
        if not self.orte:
            messagebox.showinfo(
                "Keine Orte",
                "Es sind noch keine Orte gespeichert. Bitte einmal "
                "'sportstunden init' ausfuehren oder Orte anlegen.",
            )

    # -- Aufbau ------------------------------------------------------------
    def _baue_oberflaeche(self, einstellungen: Dict[str, object]) -> None:
        links = ttk.Frame(self, padding=10)
        links.pack(side="left", fill="y")
        rechts = ttk.Frame(self, padding=(0, 10, 10, 10))
        rechts.pack(side="right", fill="both", expand=True)

        ttk.Label(links, text="Stunde planen", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        self.ort_var = tk.StringVar()
        self._feld(links, "Ort", self.ort_var, [o.name for o in self.orte])

        self.gruppe_var = tk.StringVar()
        self._feld(
            links, "Gruppe", self.gruppe_var, [g.name for g in self.katalog.altersgruppen]
        )
        if len(self.katalog.altersgruppen) > 2:
            self.gruppe_var.set(self.katalog.altersgruppen[2].name)

        self.dauer_var = tk.StringVar(value=str(einstellungen.get("standard_dauer", 60)))
        self._eingabe(links, "Dauer (Minuten)", self.dauer_var)

        self.thema_var = tk.StringVar(value="ohne Motto")
        self._feld(
            links,
            "Motto",
            self.thema_var,
            ["ohne Motto"] + [t.capitalize() for t in self.katalog.themen()],
        )

        self.schwerpunkt_var = tk.StringVar()
        self._eingabe(links, "Schwerpunkt (optional)", self.schwerpunkt_var)

        self.ueberschrift_var = tk.StringVar(
            value=str(einstellungen.get("kopftitel", "Ki Tu"))
        )
        self._eingabe(links, "Ueberschrift", self.ueberschrift_var)

        self.form_var = tk.StringVar(value="Bewegungslandschaft")
        self._feld(
            links,
            "Hauptteil",
            self.form_var,
            ["Bewegungslandschaft", "Grosses Spiel", "automatisch"],
        )

        self.stationen_var = tk.StringVar()
        self._eingabe(links, "Stationen (leer = nach Platz)", self.stationen_var)

        self.details_var = tk.BooleanVar(value=False)
        self.koordination_var = tk.StringVar(value="automatisch")
        self._feld(
            links, "Koordinationsteil", self.koordination_var, ["automatisch", "ja", "nein"]
        )

        ttk.Checkbutton(
            links,
            text="PDF mit Detailseiten",
            variable=self.details_var,
        ).pack(anchor="w", pady=(8, 0))

        knopfleiste = ttk.Frame(links)
        knopfleiste.pack(fill="x", pady=(12, 4))
        ttk.Button(knopfleiste, text="Planen", command=self.planen).pack(
            side="left", expand=True, fill="x"
        )
        ttk.Button(knopfleiste, text="Neu wuerfeln", command=self.neu_wuerfeln).pack(
            side="left", expand=True, fill="x", padx=(6, 0)
        )

        ttk.Separator(links).pack(fill="x", pady=10)
        ttk.Button(links, text="Stunde speichern", command=self.speichern).pack(fill="x")
        ttk.Button(
            links, text="Als eigene Stunde uebernehmen", command=self.als_eigene
        ).pack(fill="x", pady=4)
        ttk.Button(links, text="PDF speichern ...", command=self.pdf_speichern).pack(
            fill="x"
        )

        self.hinweis = ttk.Label(links, text="", wraplength=240, foreground="#555")
        self.hinweis.pack(anchor="w", pady=(12, 0))

        self.canvas = tk.Canvas(rechts, background="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.zeichne())
        self.canvas.bind("<ButtonPress-1>", self.zieh_start)
        self.canvas.bind("<B1-Motion>", self.zieh_bewegung)
        self.canvas.bind("<ButtonRelease-1>", self.zieh_ende)

        self.liste = tk.Text(rechts, height=12, wrap="word", relief="flat")
        self.liste.pack(fill="x", pady=(8, 0))
        self.liste.configure(state="disabled")

    def _feld(self, eltern, beschriftung: str, variable: tk.StringVar, werte) -> None:
        ttk.Label(eltern, text=beschriftung).pack(anchor="w", pady=(6, 0))
        box = ttk.Combobox(eltern, textvariable=variable, values=werte, state="readonly")
        box.pack(fill="x")
        if werte and not variable.get():
            variable.set(werte[0])

    def _eingabe(self, eltern, beschriftung: str, variable: tk.StringVar) -> None:
        ttk.Label(eltern, text=beschriftung).pack(anchor="w", pady=(6, 0))
        ttk.Entry(eltern, textvariable=variable).pack(fill="x")

    # -- Planung -----------------------------------------------------------
    def _gewaehlter_ort(self):
        for ort in self.orte:
            if ort.name == self.ort_var.get():
                return ort
        return self.orte[0] if self.orte else None

    def _gewaehlte_gruppe(self):
        for gruppe in self.katalog.altersgruppen:
            if gruppe.name == self.gruppe_var.get():
                return gruppe
        return self.katalog.altersgruppen[0]

    def _auftrag(self, seed: Optional[int] = None) -> Optional[Planungsauftrag]:
        ort = self._gewaehlter_ort()
        if not ort:
            messagebox.showerror("Kein Ort", "Bitte zuerst einen Ort anlegen.")
            return None
        try:
            dauer = int(self.dauer_var.get())
        except ValueError:
            messagebox.showerror("Dauer", "Bitte eine Zahl als Dauer eingeben.")
            return None

        stationszahl: Optional[int] = None
        if self.stationen_var.get().strip():
            try:
                stationszahl = int(self.stationen_var.get())
            except ValueError:
                messagebox.showerror("Stationen", "Bitte eine Zahl oder nichts eingeben.")
                return None

        form = self.form_var.get()
        stationsbetrieb: Optional[bool] = None
        if form == "Bewegungslandschaft":
            stationsbetrieb = True
        elif form == "Grosses Spiel":
            stationsbetrieb = False

        koordination: Optional[bool] = None
        if self.koordination_var.get() == "ja":
            koordination = True
        elif self.koordination_var.get() == "nein":
            koordination = False

        thema = self.thema_var.get()
        thema = "" if thema == "ohne Motto" else thema.lower()

        return Planungsauftrag(
            ort=ort,
            altersgruppe=self._gewaehlte_gruppe(),
            dauer=dauer,
            schwerpunkt=self.schwerpunkt_var.get().strip(),
            ueberschrift=self.ueberschrift_var.get().strip(),
            thema=thema,
            stationsbetrieb=stationsbetrieb,
            stationszahl=stationszahl,
            koordinationsteil=koordination,
            seed=seed,
        )

    def planen(self, seed: Optional[int] = 1) -> None:
        auftrag = self._auftrag(seed)
        if not auftrag:
            return
        lernen = Stillernen(self.katalog, self.speicher.stunden())
        planer = Planer(self.katalog, lernen.profil(auftrag.altersgruppe))
        try:
            self.ergebnis = planer.plane(auftrag)
        except Planungsfehler as fehler:
            messagebox.showerror("Planung nicht moeglich", str(fehler))
            return
        self.zeichne()
        self.aktualisiere_liste()

    def neu_wuerfeln(self) -> None:
        import random

        self.planen(seed=random.randint(1, 10_000))

    # -- Zeichnen ----------------------------------------------------------
    def zeichne(self) -> None:
        self.canvas.delete("all")
        if not self.ergebnis:
            return
        breite = max(200, self.canvas.winfo_width())
        hoehe = max(150, self.canvas.winfo_height())
        zeichner = CanvasZeichner(self.canvas, hoehe)
        rand = 16
        self.massstab = zeichne_hallenplan(
            zeichner,
            self.ergebnis.stunde,
            self.katalog,
            rand,
            rand,
            breite - 2 * rand,
            hoehe - 2 * rand,
            ort=self._gewaehlter_ort(),
            mit_flaechen=True,
            mit_namen=True,
        )
        # Ueberlappungen deutlich machen
        stationen = self._stationen()
        streit = {name for paar in kollisionen(stationen) for name in paar}
        for station in stationen:
            if station.name in streit and station.hat_position:
                ecke = self.massstab.punkt(station.x, station.y)
                zeichner.rechteck(
                    ecke[0],
                    ecke[1],
                    self.massstab.laenge(station.stell_laenge),
                    self.massstab.laenge(station.stell_breite),
                    WARNFARBE,
                    2.0,
                )
        self.hinweis.configure(
            text="Stationen lassen sich mit der Maus verschieben."
            + ("  Rot = Ueberlappung." if streit else "")
        )

    def _stationen(self):
        if not self.ergebnis:
            return []
        teil = self.ergebnis.stunde.teil("hauptteil")
        return list(teil.uebungen) if teil else []

    def aktualisiere_liste(self) -> None:
        if not self.ergebnis:
            return
        stunde = self.ergebnis.stunde
        zeilen: List[str] = [stunde.titel, ""]
        for beschriftung, phase in (("Anfang", "aufwaermen"), ("Koordination", "koordination")):
            teil = stunde.teil(phase)
            if teil and teil.uebungen:
                namen = ", ".join(u.name for u in teil.uebungen)
                zeilen.append(f"{beschriftung}: {namen}")
        for nummer, station in enumerate(self._stationen(), start=1):
            material = ", ".join(
                (
                    f"{self.katalog.geraet_kurz(g)} fuer alle"
                    if g in station.pro_kind
                    else f"{a}x {self.katalog.geraet_kurz(g)}"
                )
                for g, a in sorted(station.gesamtbedarf.items())
            )
            zeilen.append(f"{nummer}. {station.name}: {material or 'kein Material'}")
        abschluss = stunde.teil("abschluss")
        if abschluss and abschluss.uebungen:
            zeilen.append(
                "Ende: " + ", ".join(u.name for u in abschluss.uebungen)
            )
        for warnung in self.ergebnis.warnungen:
            zeilen.append(f"Hinweis: {warnung}")

        self.liste.configure(state="normal")
        self.liste.delete("1.0", "end")
        self.liste.insert("1.0", "\n".join(zeilen))
        self.liste.configure(state="disabled")

    # -- Stationen verschieben --------------------------------------------
    def zieh_start(self, ereignis) -> None:
        if not self.massstab:
            return
        punkt_y = self.canvas.winfo_height() - ereignis.y
        station = station_an_punkt(self._stationen(), self.massstab, ereignis.x, punkt_y)
        if station:
            self.gezogen = station
            meter = self.massstab.meter(ereignis.x, punkt_y)
            self.zieh_versatz = (meter[0] - station.x, meter[1] - station.y)

    def zieh_bewegung(self, ereignis) -> None:
        if not self.gezogen or not self.massstab:
            return
        punkt_y = self.canvas.winfo_height() - ereignis.y
        meter_x, meter_y = self.massstab.meter(ereignis.x, punkt_y)
        neu_x = meter_x - self.zieh_versatz[0]
        neu_y = meter_y - self.zieh_versatz[1]
        # Fangraster und Hallengrenzen
        neu_x = round(neu_x / RASTER) * RASTER
        neu_y = round(neu_y / RASTER) * RASTER
        neu_x = max(0.0, min(neu_x, self.massstab.halle_laenge - self.gezogen.stell_laenge))
        neu_y = max(0.0, min(neu_y, self.massstab.halle_breite - self.gezogen.stell_breite))
        self.gezogen.x = round(neu_x, 2)
        self.gezogen.y = round(neu_y, 2)
        self.zeichne()

    def zieh_ende(self, _ereignis) -> None:
        self.gezogen = None

    # -- Speichern ---------------------------------------------------------
    def speichern(self) -> None:
        if not self.ergebnis:
            return
        self.speicher.speichere_stunde(self.ergebnis.stunde)
        messagebox.showinfo(
            "Gespeichert", f"Stunde gespeichert (ID {self.ergebnis.stunde.id})."
        )

    def als_eigene(self) -> None:
        if not self.ergebnis:
            return
        self.ergebnis.stunde.quelle = "eigene"
        self.speicher.speichere_stunde(self.ergebnis.stunde)
        messagebox.showinfo(
            "Uebernommen",
            "Die Stunde zaehlt jetzt als eigene Stunde und fliesst in den "
            "gelernten Stil ein.",
        )

    def pdf_speichern(self) -> None:
        if not self.ergebnis:
            return
        stunde = self.ergebnis.stunde
        stunde.ueberschrift = self.ueberschrift_var.get().strip() or stunde.ueberschrift
        ziel = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=dateiname_fuer(stunde),
            filetypes=[("PDF", "*.pdf")],
        )
        if not ziel:
            return
        einstellungen = self.speicher.einstellungen()
        pfad = stunden_pdf(
            stunde,
            self.katalog,
            ziel,
            bestand=self.ergebnis.bestand,
            trainer=str(einstellungen.get("trainer", "")),
            verein=str(einstellungen.get("verein", "")),
            mit_details=bool(self.details_var.get()),
            ort=self._gewaehlter_ort(),
        )
        messagebox.showinfo("PDF", f"PDF geschrieben:\n{pfad}")


def starte(speicher: Optional[Speicher] = None) -> int:
    """Startet die Oberflaeche - Rueckgabewert wie bei den CLI-Befehlen."""
    fenster = Planerfenster(speicher or Speicher())
    fenster.mainloop()
    return 0
