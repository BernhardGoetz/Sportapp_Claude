# Sportstunden-Planer

Plant automatisch komplette Sportstunden fuer verschiedene Kurse und
Altersklassen - in der Turnhalle, im Freien oder auf dem Sportplatz.
Reines Python ohne externe Abhaengigkeiten (auch der PDF-Export).

## Was das Programm macht

* **Ort und Ausstattung zuerst.** Turnhallen, Sportplaetze und Aussengelaende
  werden mit ihrer Geraeteausstattung dauerhaft gespeichert. Vor jeder Planung
  werden Ort und die heute tatsaechlich verfuegbaren Geraete ausgewaehlt.
* **Stundenaufbau nach Altersklasse.** Jede Stunde besteht aus Aufwaermen,
  Hauptteil und Abschluss. Ab einer einstellbaren Altersklasse (Standard: ab
  8 Jahren) kommt direkt nach dem Aufwaermen ein **Koordinationsteil** dazu,
  der auf die koordinativen Schwerpunkte und Druckbedingungen der jeweiligen
  Altersgruppe abgestimmt ist.
* **Geraetegrenzen sind hart.** Der gleichzeitige Bedarf einer Stunde
  ueberschreitet nie den Bestand - die **Absicherung** (Matten, Weichboden,
  Niedersprungmatten) zaehlt dabei voll mit und wird bei Bedarf automatisch
  ergaenzt (z. B. eine Niedersprungmatte je Minitrampolin).
* **PDF mit Aufbau-Informationen.** Fertige Stunden lassen sich als PDF
  speichern: Ablauf mit Zeiten, Materialliste inklusive Absicherung, Aufbau je
  Stundenteil und Sicherheitshinweise.
* **Lernt den eigenen Stil.** Aus selbst erstellten Stunden lernt das Programm
  Zeitaufteilung, Inhalte, Organisationsformen, Lieblingsuebungen und
  Intensitaet - **pro Altersgruppe getrennt**. Fuer Altersgruppen ohne eigene
  Beispiele wird weich auf den Gesamtstil zurueckgegriffen.

## Installation

```bash
git clone <repo>
cd Sportapp_Claude
python3 -m sportstunden --help          # ohne Installation
pip install -e .                        # optional: Befehl 'sportstunden'
```

Getestet mit Python 3.9+. Es werden keine Fremdbibliotheken benoetigt.

Alle Daten liegen in `~/.sportstunden` (aenderbar ueber die Umgebungsvariable
`SPORTSTUNDEN_HOME` oder `--daten <verzeichnis>`).

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
4. Altersgruppe, Dauer, Teilnehmerzahl, optionaler Schwerpunkt

Danach steht die Stunde auf dem Bildschirm und kann gespeichert, als PDF
abgelegt, neu gewuerfelt oder als eigene Stunde uebernommen werden.

Nicht interaktiv (z. B. fuer Skripte):

```bash
python3 -m sportstunden planen \
    --ort halle-schulzentrum --altersgruppe d \
    --dauer 75 --teilnehmer 18 --schwerpunkt turnen \
    --ohne minitrampolin,tau --speichern --pdf ~/Stunden/
```

## Befehlsuebersicht

| Befehl | Zweck |
| --- | --- |
| `init` | Beispielorte und Datenverzeichnis anlegen |
| `orte`, `ort <id>` | Orte und ihre Ausstattung anzeigen |
| `ort-neu`, `ort-bearbeiten`, `ort-loeschen` | Orte und Geraetebestand pflegen |
| `geraete [--suche]` | Geraetekatalog inkl. Pflicht-Absicherung |
| `altersgruppen` | Altersklassen, Koordinationsschwerpunkte, Hinweise |
| `planen` | Stunde planen (interaktiv oder per Flags) |
| `stunden`, `zeigen <id>`, `loeschen <id>` | Gespeicherte Stunden verwalten |
| `pdf <id> [--datei]` | Stunde als PDF speichern |
| `erfassen` | Eigene Stunde erfassen (Stil-Vorlage) |
| `markieren <id>` | Stunde als eigene Stunde werten |
| `importieren <datei>` / `exportieren <id> <datei>` | JSON-Austausch |
| `stil [--altersgruppe]` | Gelernten Planungsstil anzeigen |
| `einstellungen [--setzen k=v]` | Standardwerte, Trainername, Verein |

## Ausstattung pflegen

```bash
python3 -m sportstunden ort-neu --name "Halle Nord" --art halle \
    --geraete "matte=14,kasten_gross=2,minitrampolin=1,langbank=6,softball=12"

python3 -m sportstunden ort-bearbeiten halle-nord --geraete "matte=16,tau=0"
python3 -m sportstunden ort halle-nord
```

`ort-bearbeiten` ohne `--geraete` startet am Terminal die gefuehrte Eingabe
(`liste` zeigt alle Geraete-IDs, `fertig` beendet).

## Absicherung und Geraetegrenzen

Jede Uebung nennt ihren Geraetebedarf getrennt nach *fix* und *pro Gruppe*.
Aus der Teilnehmerzahl ergibt sich die Zahl der Stationen, daraus der Bedarf.
Zusaetzlich gelten Sicherheitsregeln, z. B.

| Geraet | Pflicht-Absicherung |
| --- | --- |
| Minitrampolin | 1 Niedersprungmatte |
| Kasten (gross) | 2 Turnmatten |
| Reck, Barren, Tau, Schwebebalken | 2 Turnmatten |
| Ringe | 1 Weichbodenmatte |

Der Planer bucht Geraete **inklusive** dieser Absicherung. Passt eine Uebung
nicht in den Bestand, wird sie nicht eingeplant und im Ergebnis als Hinweis
ausgewiesen. Innerhalb eines Stundenteils stehen alle Aufbauten gleichzeitig,
deshalb wird dort summiert. Zwischen den Teilen wird umgebaut; wer ohne Umbau
arbeiten will, plant mit `--gemeinsames-material` - dann gilt der Bestand fuer
die gesamte Stunde.

## Koordinationsteil

Ab der eingestellten Altersgrenze (Standard 8 Jahre, aenderbar mit
`einstellungen --setzen koordination_ab_alter=10`) enthaelt jede Stunde nach
dem Aufwaermen einen Koordinationsteil. Ausgewaehlt werden nur Uebungen, die zu
den Schwerpunkten der Altersgruppe passen:

| Altersgruppe | Schwerpunkte |
| --- | --- |
| E-Jugend (8-9) | Reaktion, Orientierung, Gleichgewicht, Rhythmus |
| D-Jugend (10-11) | Rhythmus, Differenzierung, Kopplung, Orientierung |
| C-Jugend (12-13) | Kopplung, Umstellung, Differenzierung |
| B-/A-Jugend (14-18) | Umstellung, Differenzierung, Kopplung, Reaktion |
| Erwachsene | Gleichgewicht, Kopplung, Rhythmus, Differenzierung |
| Senioren | Gleichgewicht, Reaktion, Orientierung (Sturzprophylaxe) |

Mit `--mit-koordination` / `--ohne-koordination` laesst sich das je Stunde
uebersteuern.

## Stil lernen

Es zaehlen ausschliesslich Stunden mit der Quelle `eigene`:

```bash
python3 -m sportstunden erfassen                 # Stunde selbst zusammenstellen
python3 -m sportstunden markieren stunde-1a2b3c  # geplante Stunde uebernehmen
python3 -m sportstunden importieren meine.json   # aus JSON einlesen
python3 -m sportstunden stil                     # gelernten Stil ansehen
```

Gelernt werden Zeitaufteilung der Teile, Anzahl der Uebungen je Teil,
bevorzugte Inhalte (Tags), Organisationsformen, Geraete, Lieblingsuebungen und
die typische Intensitaet. Die Gewichte werden gegen die Haeufigkeit im Katalog
normiert, damit nicht einfach das Uebliche gewinnt.

Das Profil wird in drei Stufen gemischt:

```
neutrales Profil  ->  Gesamtstil des Nutzers  ->  Stil dieser Altersgruppe
```

Je mehr eigene Stunden fuer eine Altersgruppe vorliegen, desto staerker
schlaegt deren eigener Stil durch (`n / (n + 2)`). So kann der Stil fuer die
Bambini ein anderer sein als fuer die B-Jugend, ohne dass eine neue
Altersgruppe bei null anfaengt.

## PDF-Export

```bash
python3 -m sportstunden planen --ort halle-schulzentrum --altersgruppe d --pdf
python3 -m sportstunden pdf stunde-1a2b3c --datei ~/Stunden/
```

Das PDF enthaelt Stundenuebersicht, Materialliste (Bedarf und Bestand,
Absicherung gekennzeichnet), den Ablauf mit Zeiten und Beschreibungen, den
Aufbau je Stundenteil inklusive Umbauhinweisen sowie die Sicherheitshinweise.
Name und Verein der Uebungsleitung kommen aus den Einstellungen:

```bash
python3 -m sportstunden einstellungen --setzen "trainer=B. Goetz" --setzen "verein=TSV Beispiel"
```

## Projektstruktur

```
sportstunden/
  models.py     Datenmodelle (Ort, Uebung, Stunde, Stundenteil ...)
  katalog.py    Stammdaten, Bedarfsrechnung inkl. Sicherheitsregeln
  speicher.py   JSON-Speicherung von Orten, Stunden, Einstellungen
  stil.py       Stil-Lernen je Altersgruppe
  planer.py     Auswahl, Zeitverteilung, Geraetebuchung, Aufbauplan
  pdf.py        Minimaler PDF-Generator (Helvetica, Umbruch, Tabellen)
  export.py     Layout der Stunden-PDF
  ansicht.py    Textausgabe fuer das Terminal
  cli.py        Kommandozeile
  data/         Geraete, Sicherheitsregeln, Altersgruppen, Uebungen, Beispielorte
tests/          63 Tests (unittest)
```

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

Abgedeckt sind unter anderem: der Geraetebestand wird in ueber 400
Planungsvarianten nie ueberschritten, die Absicherung wird automatisch
ergaenzt, der Koordinationsteil erscheint genau ab der richtigen Altersklasse
und passt zu deren Schwerpunkten, die Stundendauer stimmt exakt, der gelernte
Stil veraendert die Auswahl und variiert je Altersgruppe, und das erzeugte PDF
ist strukturell gueltig und bleibt im Satzspiegel.

## Uebungskatalog erweitern

Die Uebungen liegen in `sportstunden/data/uebungen.json`. Ein Eintrag:

```json
{
  "id": "haupt_beispiel",
  "name": "Beispieluebung",
  "phase": "hauptteil",
  "orte": ["halle"],
  "alter_min": 10, "alter_max": 14,
  "dauer_min": 15, "dauer_max": 25,
  "tags": ["turnen", "technik"],
  "organisation": "riegen",
  "gruppengroesse": 6,
  "geraete_pro_gruppe": {"kasten_gross": 1, "sprungbrett": 1},
  "absicherung_pro_gruppe": {"weichbodenmatte": 1},
  "intensitaet": 4,
  "koordination": [],
  "beschreibung": "...",
  "aufbau": "...",
  "hinweise": "..."
}
```

`gruppengroesse` steuert, wie viele Stationen bei welcher Teilnehmerzahl
gebraucht werden. Neue Geraete werden in `data/geraete.json` ergaenzt, dort
stehen auch die Sicherheitsregeln. Der Katalog wird beim Laden geprueft -
unbekannte Geraete-IDs fuehren sofort zu einer Fehlermeldung.
