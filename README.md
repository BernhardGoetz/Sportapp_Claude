# Kinderturnen-Stundenplaner

Plant automatisch Stunden fuer das **Kinderturnen von 1 bis 10 Jahren** -
Freizeitsport, kein Leistungssport. Ergebnis ist ein **Stundenbild als PDF**:
Anfang, Hallenplan mit nummerierten Stationen, Stationsliste mit Material,
Ende. Reines Python ohne externe Abhaengigkeiten (auch der PDF-Export).

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
  Pfuetzenspringen, Lianenschwingen). Die Zahl der Stationen richtet sich nach
  der Kinderzahl, alle Stationen stehen gleichzeitig, gewechselt wird im
  Uhrzeigersinn.
* **Geraetegrenzen sind hart.** Der gleichzeitige Bedarf ueberschreitet nie den
  Bestand - die **Absicherung** (blaue Matten, Weichboden, Niedersprungmatte)
  zaehlt voll mit und wird automatisch ergaenzt (z. B. Niedersprungmatte je
  Minitrampolin, 2 Matten unter Reck, Barren und Tau).
* **Stundenbild als PDF.** Seite 1 im Stil einer handgeschriebenen
  Stundenskizze, Folgeseiten mit Ablauf, Beschreibungen, Aufbau und
  Sicherheitshinweisen. Mit `--nur-stundenbild` bleibt es bei einer Seite.
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
python3 -m sportstunden planen          # interaktiv planen
```

Der interaktive Ablauf fragt der Reihe nach:

1. Halle, im Freien oder Sportplatz?
2. Welcher Ort?
3. Welche Ausstattung steht heute zur Verfuegung? (alles / einzelne Geraete
   ausschliessen / Anzahlen anpassen / nur bestimmte Geraete)
4. Welche Gruppe, wie lang, wie viele Kinder, Schwerpunkt, Motto

Danach steht die Stunde auf dem Bildschirm und kann gespeichert, als PDF
abgelegt, neu gewuerfelt oder als eigene Stunde uebernommen werden.

Nicht interaktiv (z. B. fuer Skripte):

```bash
python3 -m sportstunden planen \
    --ort halle-grundschule --altersgruppe vorschule \
    --dauer 60 --teilnehmer 18 --thema sommer --stationen \
    --ohne minitrampolin --speichern --pdf ~/Stunden/
```

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
| `pdf <id> [--datei] [--nur-stundenbild]` | Stundenbild als PDF speichern |
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
| `--dauer`, `--teilnehmer` | Stundenlaenge und Kinderzahl |
| `--thema sommer` / `--thema auto` | Motto der Stunde |
| `--stationen` / `--spiel` | Hauptteil als Bewegungslandschaft oder als grosses Spiel |
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

Aus der Kinderzahl ergibt sich, wie viele Stationen oder Kleingruppen noetig
sind, daraus der Materialbedarf. Zusaetzlich gelten Sicherheitsregeln:

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

**Seite 1 - Stundenbild:** Kopfzeile (`Ki Tu` und Datum), Zeile `Anfang:` mit
Spiel und Material, optional `Koordination:`, der Hallenplan mit nummerierten
Stationen und Geraetesymbolen, darunter die nummerierte Stationsliste mit
Material in Kurzform (`LB`, `WB`, `kl. Kasten`), zum Schluss `Ende:`.

**Folgeseiten:** Ablauf mit Zeiten, Beschreibung jeder Station, Materialliste
mit Bedarf und Bestand, Aufbau je Stundenteil und die Sicherheitshinweise.

Kopfzeile, Name und Verein kommen aus den Einstellungen:

```bash
python3 -m sportstunden einstellungen \
    --setzen "trainer=B. Goetz" --setzen "verein=TSV Beispiel" --setzen "kopftitel=Ki Tu"
```

## Projektstruktur

```
sportstunden/
  models.py      Datenmodelle (Ort, Uebung, Stunde, Stundenteil ...)
  katalog.py     Stammdaten, Bedarfsrechnung inkl. Sicherheitsregeln
  speicher.py    JSON-Speicherung von Orten, Stunden, Einstellungen
  stil.py        Stil-Lernen je Altersgruppe
  planer.py      Auswahl, Stationszahl, Zeitverteilung, Geraetebuchung
  hallenplan.py  Schematischer Hallenplan mit Geraetesymbolen
  pdf.py         Minimaler PDF-Generator (Text, Tabellen, Grafik)
  export.py      Layout des Stundenbilds und der Detailseiten
  ansicht.py     Textausgabe fuer das Terminal
  cli.py         Kommandozeile
  data/          Geraete, Sicherheitsregeln, Gruppen, Uebungen, Beispielorte
tests/           82 Tests (unittest)
```

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

Abgedeckt sind unter anderem: der Geraetebestand wird in ueber 300
Planungsvarianten nie ueberschritten, die Absicherung wird automatisch
ergaenzt, der Koordinationsteil erscheint genau ab der richtigen Altersklasse,
die Stationszahl waechst mit der Kinderzahl, das Motto praegt die Auswahl, die
Stundendauer stimmt exakt, der gelernte Stil veraendert die Auswahl und
variiert je Gruppe, und das Stundenbild enthaelt Plan, Stationsnummern und
Material in Kurzform.

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
aufgebaut, unabhaengig von der Kinderzahl. Spiele fuer die ganze Gruppe haben
`"stationsbetrieb": false`; skalierendes Material gehoert dann nach
`geraete_pro_gruppe` mit passender `gruppengroesse`. Neue Geraete kommen in
`data/geraete.json` (dort stehen auch Kurzform und Sicherheitsregeln); ein
neues Symbol fuer den Hallenplan wird in `hallenplan.py` unter `SYMBOLE`
eingetragen. Der Katalog wird beim Laden geprueft - unbekannte Geraete-IDs
fuehren sofort zu einer Fehlermeldung.
