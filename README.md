# Kinderturnen-Stundenplaner

Plant automatisch Stunden fuer das **Kinderturnen von 1 bis 10 Jahren** -
Freizeitsport, kein Leistungssport. Ergebnis ist ein **Stundenbild als PDF**:
Anfang, massstaeblicher Hallenplan mit nummerierten Stationen an ihren
tatsaechlichen Positionen, Stationsliste mit Material, Ende. Bedienbar ueber
die Kommandozeile oder eine grafische Oberflaeche, in der sich die Stationen
mit der Maus verschieben lassen. Reines Python ohne externe Abhaengigkeiten
(auch der PDF-Export).

## Was das Programm macht

* **Ort und Ausstattung zuerst.** Turnhallen, Gymnastikraeume, Wiesen und
  Sportplaetze werden mit ihrer Geraeteausstattung dauerhaft gespeichert. Vor
  jeder Planung werden Ort und die heute tatsaechlich verfuegbaren Geraete
  ausgewaehlt.
* **Stundenaufbau fuer das Kinderturnen.** Anfangsspiel, Bewegungslandschaft
  oder grosses Spiel als Hauptteil, Abschlussspiel. Ab einer einstellbaren
  Altersklasse (Standard: ab 6 Jahren) kommt direkt nach dem Aufwaermen ein
  **Koordinationsteil** dazu, abgestimmt auf die Schwerpunkte der Gruppe.
* **Bewegungslandschaft statt Trainingsplan.** Der Hauptteil besteht in der
  Regel aus mehreren Stationen mit kindgerechten Namen (Wackelberg,
  Pfuetzenspringen, Lianenschwingen). Wie viele Stationen aufgebaut werden,
  ergibt sich aus dem **Platz in der Halle** und dem Material; alle Stationen
  stehen gleichzeitig, gewechselt wird im Uhrzeigersinn.
* **Stationen an ihren tatsaechlichen Positionen.** Zu jedem Ort werden
  Hallenmasse und die festen Plaetze der ortsfesten Geraete gespeichert
  (Sprossenwand an der Wand, Reck und Barren in ihren Huelsen, Ringe und Tau an
  der Decke). Stationen mit diesen Geraeten stehen im Plan genau dort, alle
  uebrigen werden massstaeblich auf die freie Flaeche verteilt - ohne
  Ueberlappung und mit Laufwegen dazwischen.
* **Keine Teilnehmerzahl noetig.** Die Kinderzahl wird nirgends abgefragt.
  Material fuer die ganze Gruppe wird einmal gerechnet, Riegenmaterial je Riege,
  und was jedes Kind einzeln braucht (Baelle, Seilchen), steht ohne Stueckzahl
  als "fuer alle" im Plan.
* **Geraetegrenzen sind hart.** Der gleichzeitige Bedarf ueberschreitet nie den
  Bestand - die **Absicherung** (blaue Matten, Weichboden, Niedersprungmatte)
  zaehlt voll mit und wird automatisch ergaenzt (z. B. Niedersprungmatte je
  Minitrampolin, 2 Matten unter Reck, Barren und Tau).
* **Stundenbild als PDF - ohne Zeitangaben.** Seite 1 im Stil einer
  handgeschriebenen Stundenskizze mit frei waehlbarer Ueberschrift,
  Folgeseiten mit Ablauf, Beschreibungen, Aufbau und Sicherheitshinweisen.
  Minutenangaben stehen bewusst nirgends im PDF. Mit `--nur-stundenbild`
  bleibt es bei einer Seite.
* **Motto der Stunde.** Optional bekommt die Stunde ein Thema (Sommer, Wasser,
  Dschungel, Zirkus, Ritter, Baustelle, Bauernhof, Weltraum, Winter) - passende
  Spiele und Stationen werden dann bevorzugt.
* **Lernt den eigenen Stil.** Aus selbst erstellten Stunden lernt das Programm
  Zeitaufteilung, Inhalte, Stationszahl, Lieblingsstationen und Intensitaet -
  **pro Altersgruppe getrennt**.

## Installation

```bash
git clone <repo>
cd Sportapp_Claude
python3 -m sportstunden --help          # ohne Installation
pip install -e .                        # optional: Befehl 'sportstunden'
```

Getestet mit Python 3.9+, keine Fremdbibliotheken. Alle Daten liegen in
`~/.sportstunden` (aenderbar ueber `SPORTSTUNDEN_HOME` oder `--daten`).

## Schnellstart

```bash
python3 -m sportstunden init            # Beispielorte anlegen
python3 -m sportstunden gui             # grafische Oberflaeche
python3 -m sportstunden planen          # interaktiv auf der Kommandozeile
```

Der interaktive Ablauf fragt der Reihe nach:

1. Halle, im Freien oder Sportplatz?
2. Welcher Ort?
3. Welche Ausstattung steht heute zur Verfuegung? (alles / einzelne Geraete
   ausschliessen / Anzahlen anpassen / nur bestimmte Geraete)
4. Welche Gruppe, wie lang, Schwerpunkt, Ueberschrift, Motto

Danach steht die Stunde auf dem Bildschirm und kann gespeichert, als PDF
abgelegt, neu gewuerfelt oder als eigene Stunde uebernommen werden.

Nicht interaktiv (z. B. fuer Skripte):

```bash
python3 -m sportstunden planen \
    --ort halle-grundschule --altersgruppe vorschule \
    --dauer 60 --thema sommer --stationen --ueberschrift "Ki Tu" \
    --ohne minitrampolin --speichern --pdf ~/Stunden/
```

## Grafische Oberflaeche

```bash
python3 -m sportstunden gui     # oder nach 'pip install -e .': sportstunden-gui
```

Links werden Ort, Gruppe, Dauer, Motto, Schwerpunkt und Ueberschrift
eingestellt, in der Mitte steht der massstaebliche Hallenplan. **Stationen
lassen sich mit der Maus an ihren Platz schieben** (Fangraster 25 cm,
Ueberlappungen werden rot umrandet), darunter stehen Anfang, Stationsliste und
Ende. Die Schaltflaechen speichern die Stunde, uebernehmen sie in den
gelernten Stil oder schreiben das PDF.

Tkinter gehoert zur Standardbibliothek. Windows und macOS bringen es mit der
Python-Installation mit; unter Linux gegebenenfalls
`sudo apt install python3-tk` nachinstallieren.

## Gruppen und Koordinationsteil

| Gruppe | Alter | Koordinationsteil | Schwerpunkte |
| --- | --- | --- | --- |
| `eltern_kind` | 1-3 | nein | Gleichgewicht, Orientierung |
| `kleinkind` | 3-4 | nein | Gleichgewicht, Orientierung |
| `vorschule` | 5-6 | ja | Gleichgewicht, Orientierung, Reaktion, Rhythmus |
| `grundschule_1` | 7-8 | ja | Reaktion, Rhythmus, Gleichgewicht, Orientierung |
| `grundschule_2` | 9-10 | ja | Rhythmus, Differenzierung, Kopplung, Orientierung, Reaktion |

Die Altersgrenze fuer den Koordinationsteil laesst sich verschieben:

```bash
python3 -m sportstunden einstellungen --setzen koordination_ab_alter=7
```

Je Stunde geht auch `--mit-koordination` / `--ohne-koordination`.

## Befehlsuebersicht

| Befehl | Zweck |
| --- | --- |
| `init` | Beispielorte und Datenverzeichnis anlegen |
| `orte`, `ort <id>` | Orte und ihre Ausstattung anzeigen |
| `ort-neu`, `ort-bearbeiten`, `ort-loeschen` | Orte und Geraetebestand pflegen |
| `geraete [--suche]` | Geraetekatalog inkl. Pflicht-Absicherung |
| `altersgruppen` | Gruppen, Koordinationsschwerpunkte, Hinweise |
| `planen` | Stunde planen (interaktiv oder per Flags) |
| `stunden`, `zeigen <id>`, `loeschen <id>` | Gespeicherte Stunden verwalten |
| `pdf <id> [--datei] [--ueberschrift] [--nur-stundenbild]` | Stundenbild als PDF speichern |
| `gui` | Grafische Oberflaeche starten |
| `erfassen` | Eigene Stunde erfassen (Stil-Vorlage) |
| `markieren <id>` | Stunde als eigene Stunde werten |
| `importieren <datei>` / `exportieren <id> <datei>` | JSON-Austausch |
| `stil [--altersgruppe]` | Gelernten Planungsstil anzeigen |
| `einstellungen [--setzen k=v]` | Standardwerte, Name, Verein, Kopftitel |

Wichtige Flags von `planen`:

| Flag | Wirkung |
| --- | --- |
| `--ort`, `--art` | Ort bzw. Ortsart waehlen |
| `--altersgruppe`, `--alter` | Gruppe direkt oder ueber das Alter waehlen |
| `--dauer` | Stundenlaenge in Minuten |
| `--ueberschrift "Ki Tu"` | Ueberschrift auf dem Stundenbild |
| `--thema sommer` / `--thema auto` | Motto der Stunde |
| `--stationen [ANZAHL]` / `--spiel` | Bewegungslandschaft (mit Zahl: feste Stationszahl, ohne: nach Platz) oder grosses Spiel |
| `--geraete`, `--ohne` | Ausstattung fuer heute einschraenken |
| `--gemeinsames-material` | Kein Umbau zwischen den Teilen |
| `--seed` | Reproduzierbare Planung |
| `--pdf [pfad]`, `--nur-stundenbild` | PDF schreiben |
| `--speichern`, `--eigene` | Stunde ablegen (und als eigenen Stil werten) |

## Ausstattung pflegen

```bash
python3 -m sportstunden ort-neu --name "Halle Nord" --art halle \
    --geraete "matte=12,kastenteil=6,langbank=6,reifen=16,schwungtuch=1"

python3 -m sportstunden ort-bearbeiten halle-nord --geraete "matte=14,tau=0"
python3 -m sportstunden ort halle-nord
```

`ort-bearbeiten` ohne `--geraete` startet am Terminal die gefuehrte Eingabe
(`liste` zeigt alle Geraete-IDs, `fertig` beendet).

## Absicherung und Geraetegrenzen

Material fuer die ganze Gruppe wird einmal gerechnet, Riegenmaterial je Riege.
Was jedes Kind einzeln braucht, wird als "fuer alle" gefuehrt und mit dem
Bestand des Ortes gebucht. Zusaetzlich gelten Sicherheitsregeln:

| Geraet | Pflicht-Absicherung |
| --- | --- |
| Minitrampolin | 1 Niedersprungmatte |
| Grosser Kasten | 2 blaue Matten |
| Reck, Barren, Tau, Schwebebalken, Klettergeruest | 2 blaue Matten |
| Schaukelringe | 1 Weichbodenmatte |
| Kleiner Kasten, Kastenteil, Sprungbrett, Sprossenwand | 1 blaue Matte |

Der Planer bucht Geraete **inklusive** dieser Absicherung. Passt eine Station
nicht in den Bestand, wird sie nicht eingeplant und im Ergebnis als Hinweis
ausgewiesen. Innerhalb eines Stundenteils stehen alle Aufbauten gleichzeitig,
deshalb wird dort summiert. Zwischen den Teilen wird umgebaut; wer ohne Umbau
arbeiten will, plant mit `--gemeinsames-material`.


## Hallenmasse und Geraeteplaetze

Damit die Stationen an ihren tatsaechlichen Platz kommen, kennt jeder Ort seine
Masse und die festen Standorte der ortsfesten Geraete. In
`sportstunden/data/orte.json` sieht das so aus:

```json
{
  "id": "halle-grundschule",
  "laenge": 27.0,
  "breite": 15.0,
  "geraeteplaetze": [
    {"geraet": "sprossenwand", "x": 0.3, "y": 2.0, "laenge": 0.4, "breite": 2.5},
    {"geraet": "reck", "x": 18.5, "y": 3.0, "laenge": 2.4, "breite": 0.8},
    {"geraet": "tau", "x": 23.5, "y": 6.0, "laenge": 1.2, "breite": 1.2}
  ]
}
```

Koordinaten sind Meter, Ursprung ist die linke untere Ecke der Flaeche; `laenge`
liegt in x-Richtung. Orte ohne Angaben rechnen mit 27 x 15 m. Stationen mit
Sprossenwand, Reck, Barren, Ringen, Tau, Klettergeruest oder Balken werden an
diesen Plaetzen verankert, alle anderen im Uhrzeigersinn auf der freien Flaeche
verteilt - mit Wandabstand, Sicherheitsrand und ohne Ueberlappung. In der
grafischen Oberflaeche laesst sich jede Station danach noch mit der Maus
verschieben; die Position landet im PDF.

## Stil lernen

Es zaehlen ausschliesslich Stunden mit der Quelle `eigene`:

```bash
python3 -m sportstunden erfassen                 # Stunde selbst zusammenstellen
python3 -m sportstunden markieren stunde-1a2b3c  # geplante Stunde uebernehmen
python3 -m sportstunden importieren meine.json   # aus JSON einlesen
python3 -m sportstunden stil                     # gelernten Stil ansehen
```

Gelernt werden Zeitaufteilung, Zahl der Stationen bzw. Spiele je Teil,
bevorzugte Inhalte, Organisationsformen, Geraete, Lieblingsstationen, die
typische Intensitaet und wie oft mit Stationsbetrieb gearbeitet wird. Die
Gewichte werden gegen die Haeufigkeit im Katalog normiert, damit nicht einfach
das Uebliche gewinnt. Das Profil wird in drei Stufen gemischt:

```
neutrales Profil  ->  Gesamtstil des Nutzers  ->  Stil dieser Altersgruppe
```

Je mehr eigene Stunden fuer eine Gruppe vorliegen, desto staerker schlaegt
deren eigener Stil durch (`n / (n + 2)`). So kann das Eltern-Kind-Turnen anders
geplant werden als die dritte Klasse, ohne dass eine neue Gruppe bei null
anfaengt.

## Das PDF

```bash
python3 -m sportstunden planen --ort halle-grundschule --altersgruppe vorschule --pdf
python3 -m sportstunden pdf stunde-1a2b3c --datei ~/Stunden/ --nur-stundenbild
```

**Seite 1 - Stundenbild:** Kopfzeile (frei waehlbare Ueberschrift und Datum),
Zeile `Anfang:` mit Spiel und Material, optional `Koordination:`, der
massstaebliche Hallenplan mit nummerierten Stationen an ihren Positionen,
darunter die nummerierte Stationsliste mit Material in Kurzform (`LB`, `WB`,
`kl. Kasten`), zum Schluss `Ende:`. Zeitangaben stehen nicht im PDF.

**Folgeseiten:** Ablauf mit Zeiten, Beschreibung jeder Station, Materialliste
mit Bedarf und Bestand, Aufbau je Stundenteil und die Sicherheitshinweise.

Kopfzeile, Name und Verein kommen aus den Einstellungen:

```bash
python3 -m sportstunden einstellungen \
    --setzen "trainer=B. Goetz" --setzen "verein=TSV Beispiel" --setzen "kopftitel=Ki Tu"
```

`kopftitel` ist die Vorgabe fuer die Ueberschrift, `standard_stationen` eine
feste Stationszahl (0 = nach Platz in der Halle), `standard_dauer` die
uebliche Stundenlaenge.

## Projektstruktur

```
sportstunden/
  models.py       Datenmodelle (Ort, Geraeteplatz, Uebung, Stunde ...)
  katalog.py      Stammdaten, Bedarfsrechnung inkl. Sicherheitsregeln
  speicher.py     JSON-Speicherung von Orten, Stunden, Einstellungen
  stil.py         Stil-Lernen je Altersgruppe
  planer.py       Auswahl, Flaechenbudget, Zeitverteilung, Geraetebuchung
  platzierung.py  Geraetemasse und Positionen der Stationen in der Halle
  hallenplan.py   Massstaeblicher Plan mit Geraetesymbolen (PDF und Bildschirm)
  pdf.py          Minimaler PDF-Generator (Text, Tabellen, Grafik)
  export.py       Layout des Stundenbilds und der Detailseiten
  ansicht.py      Textausgabe fuer das Terminal
  cli.py          Kommandozeile
  gui.py          Grafische Oberflaeche (Tkinter)
  data/           Geraete, Sicherheitsregeln, Gruppen, Uebungen, Beispielorte
tests/            109 Tests (unittest)
```

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

Abgedeckt sind unter anderem: der Geraetebestand wird in ueber 100
Planungsvarianten nie ueberschritten, die Absicherung wird automatisch
ergaenzt, der Koordinationsteil erscheint genau ab der richtigen Altersklasse,
die Stationszahl richtet sich nach der Hallenflaeche, alle Stationen liegen
ohne Ueberlappung in der Halle und Stationen mit ortsfesten Geraeten stehen an
deren Platz, das PDF enthaelt weder Minuten noch eine Kinderzahl, die
Ueberschrift ist frei waehlbar, der gelernte Stil veraendert die Auswahl - und
die Oberflaeche laesst sich bedienen und verschiebt Stationen im Raster (diese
Tests werden ohne tkinter uebersprungen).

## Uebungskatalog erweitern

Die Inhalte liegen in `sportstunden/data/uebungen.json`. Eine Station:

```json
{
  "id": "st_beispiel",
  "name": "Wackelberg",
  "phase": "hauptteil",
  "orte": ["halle"],
  "alter_min": 4, "alter_max": 10,
  "dauer_min": 4, "dauer_max": 8,
  "tags": ["turnen", "mut", "gleichgewicht"],
  "organisation": "stationen",
  "stationsbetrieb": true,
  "geraete_fix": {"weichbodenmatte": 3, "reck": 1, "ringe": 1},
  "intensitaet": 3,
  "koordination": ["gleichgewicht", "orientierung"],
  "thema": "",
  "beschreibung": "...",
  "aufbau": "...",
  "hinweise": "..."
}
```

Stationen bekommen ihr Material unter `geraete_fix` - sie werden einmal
aufgebaut. Spiele fuer die ganze Gruppe haben
`"stationsbetrieb": false`; skalierendes Material gehoert dann nach
`geraete_pro_gruppe` mit passender `gruppengroesse`. Neue Geraete kommen in
`data/geraete.json` (dort stehen auch Kurzform und Sicherheitsregeln); ein
neues Symbol fuer den Hallenplan wird in `hallenplan.py` unter `SYMBOLE`
eingetragen. Der Katalog wird beim Laden geprueft - unbekannte Geraete-IDs
fuehren sofort zu einer Fehlermeldung.
