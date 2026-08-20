# Kinderturnen-Stundenplaner

Plant automatisch Stunden fuer das **Kinderturnen von 1 bis 10 Jahren** -
Freizeitsport, kein Leistungssport. Ergebnis ist ein **einseitiges Stundenbild
als PDF**: Anfang, massstaeblicher Hallenplan mit nummerierten Stationen an
ihren tatsaechlichen Positionen, Stationsliste mit Material, Ende. Detailseiten
gibt es auf Wunsch.

Zwei Wege zur Bedienung, beide mit demselben Katalog und derselben Logik:

| Weg | Wofuer | Voraussetzung |
| --- | --- | --- |
| **`web/kinderturnen.html`** | Handy, Tablet, Rechner - Plan mit dem Finger verschieben | ein Browser, sonst nichts |
| `python3 -m sportstunden` | Fenster-Oberflaeche am Rechner | Python 3.9+ mit tkinter |

Eine Kommandozeilenfassung gibt es nicht (mehr). Reines Python beziehungsweise
reines JavaScript - keine Fremdbibliotheken, auch nicht fuer den PDF-Export.

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
  handgeschriebenen Stundenskizze mit frei waehlbarer Ueberschrift. Der Haken
  "PDF mit Detailseiten" haengt Ablauf, Beschreibungen, Aufbau und
  Sicherheitshinweise an. Minutenangaben stehen bewusst nirgends im PDF.
* **Motto der Stunde.** Optional bekommt die Stunde ein Thema (Sommer, Wasser,
  Dschungel, Zirkus, Ritter, Baustelle, Bauernhof, Weltraum, Winter) - passende
  Spiele und Stationen werden dann bevorzugt.
* **Lernt den eigenen Stil.** Aus selbst erstellten Stunden lernt das Programm
  Zeitaufteilung, Inhalte, Stationszahl, Lieblingsstationen und Intensitaet -
  **pro Altersgruppe getrennt**.

## Ohne Installation: die Browser-Fassung

`web/kinderturnen.html` ist **eine einzige Datei** mit Katalog, Oberflaeche und
PDF-Erzeugung darin. Sie braucht keine Installation und keine Internetverbindung:

* **Rechner:** Datei doppelklicken - sie oeffnet sich im Browser.
* **Handy und Tablet:** Datei per Mail, Messenger oder Cloud aufs Geraet legen
  und antippen. In Safari und Chrome laesst sie sich ueber "Zum Home-Bildschirm"
  wie eine App ablegen.
* **Verein:** Datei auf eine Webseite legen - dann genuegt der Link.

Die Oberflaeche passt sich der Bildschirmgroesse an: Der Plan bekommt immer den
groessten Teil des Fensters, auf hochkant gehaltenen Geraeten wird er passend
gedreht. Stationen werden mit dem Finger oder der Maus verschoben (Fangraster
25 cm), Ort und Geraetezahlen bleiben auf dem Geraet gespeichert.

```bash
python3 werkzeuge/baue_web.py           # baut die Datei neu aus den Quellen
```

## Veroeffentlichen: der Quelltext bleibt zu

Die ausgelieferte Datei enthaelt **keinen lesbaren Quelltext**. Aufbau
(HTML), Gestaltung (CSS), Katalog und Programm liegen in einem einzigen,
verwuerfelten Base64-Block; sichtbar ist nur ein kurzer Lader, der den Block
zur Laufzeit zusammensetzt und ausfuehrt. "Seitenquelltext anzeigen" zeigt
damit nichts Verwertbares mehr - weder Uebungen und Sicherheitsregeln noch die
Planungslogik. Zusaetzlich:

* Die Innereien (`window.KiTu`) reicht die Seite nur mit `?pruefung=1` in der
  Adresse heraus - im Normalbetrieb gibt es keinen Einstiegspunkt.
* Kommentare und Einrueckung sind vor dem Packen entfernt.
* `<meta name="robots" content="noarchive">` haelt Suchmaschinen-Archive fern.
* Die lesbaren Quellen liegen unter `web/quelle/` und werden **nicht**
  mit veroeffentlicht - weitergegeben wird allein `web/kinderturnen.html`.

**Grenze, die ehrlich benannt sein will:** Was der Browser ausfuehrt, muss der
Browser entpacken koennen - der Lader steht in der Datei. Wer sich hinsetzt,
kann den Block darueber zurueckrechnen; und die fertig aufgebaute Seite ist in
den Entwicklerwerkzeugen als Elementbaum sichtbar, weil sie dort ja dargestellt
wird. Das hier ist eine wirksame Huerde gegen Mitlesen und Abkupfern, keine
Verschluesselung. Wirklich geheim bleibt nur, was auf einem Server liegt und nie
ausgeliefert wird - das widerspricht aber dem Ziel, ohne Installation und ohne
Netz zu laufen.

Wird die Datei auf einen Webserver gelegt, darf dessen `Content-Security-Policy`
`script-src` nicht ohne `'unsafe-eval'` gesetzt sein: der Lader startet das
entpackte Programm ueber `new Function`.

## Fenster-Oberflaeche am Rechner

```bash
git clone <repo>
cd Sportapp_Claude
python3 -m sportstunden            # oder nach 'pip install -e .': sportstunden-gui
```

Links werden Ort, Gruppe, Dauer, Motto, Schwerpunkt und Ueberschrift
eingestellt, in der Mitte steht der massstaebliche Hallenplan. **Stationen
lassen sich mit der Maus an ihren Platz schieben** (Fangraster 25 cm,
Ueberlappungen werden rot umrandet), darunter stehen Anfang, Stationsliste und
Ende. Die Schaltflaechen speichern die Stunde, uebernehmen sie in den
gelernten Stil oder schreiben das PDF.

Tkinter gehoert zur Standardbibliothek. Windows und macOS bringen es mit der
Python-Installation mit; unter Linux gegebenenfalls
`sudo apt install python3-tk` nachinstallieren. Die Daten liegen in
`~/.sportstunden` (aenderbar ueber `SPORTSTUNDEN_HOME`).

## Gruppen und Koordinationsteil

| Gruppe | Alter | Koordinationsteil | Schwerpunkte |
| --- | --- | --- | --- |
| `eltern_kind` | 1-3 | nein | Gleichgewicht, Orientierung |
| `kleinkind` | 3-4 | nein | Gleichgewicht, Orientierung |
| `vorschule` | 5-6 | ja | Gleichgewicht, Orientierung, Reaktion, Rhythmus |
| `grundschule_1` | 7-8 | ja | Reaktion, Rhythmus, Gleichgewicht, Orientierung |
| `grundschule_2` | 9-10 | ja | Rhythmus, Differenzierung, Kopplung, Orientierung, Reaktion |

Je Stunde laesst sich der Koordinationsteil auf "ja", "nein" oder
"automatisch" stellen. Die Altersgrenze fuer "automatisch" steht in
`sportstunden/data/altersgruppen.json` unter `koordination_ab_alter`; nach einer
Aenderung `python3 werkzeuge/baue_web.py` ausfuehren, damit die Browser-Fassung
sie uebernimmt.

## Ausstattung pflegen

In beiden Oberflaechen fuehrt die Schaltflaeche **"Geraete des Ortes"** zu den
Stueckzahlen: anpassen oder auf 0 setzen, wenn heute etwas fehlt. Der Browser
merkt sich das auf dem Geraet, die Fenster-Oberflaeche in `~/.sportstunden`.

Neue Orte und ihre festen Geraeteplaetze kommen in
`sportstunden/data/orte.json` (siehe unten) und stehen nach
`python3 werkzeuge/baue_web.py` auch im Browser zur Verfuegung.

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
deshalb wird dort summiert. Zwischen den Teilen wird umgebaut.

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
verteilt - mit Wandabstand, Sicherheitsrand und ohne Ueberlappung. Danach laesst
sich jede Station noch von Hand verschieben; die Position landet im PDF.

## Stil lernen

Es zaehlen ausschliesslich Stunden, die als **"Eigene Stunde"** uebernommen
wurden - die Schaltflaeche gibt es in beiden Oberflaechen. Gelernt werden
Zeitaufteilung, Zahl der Stationen bzw. Spiele je Teil, bevorzugte Inhalte,
Organisationsformen, Geraete, Lieblingsstationen, die typische Intensitaet und
wie oft mit Stationsbetrieb gearbeitet wird. Die Gewichte werden gegen die
Haeufigkeit im Katalog normiert, damit nicht einfach das Uebliche gewinnt. Das
Profil wird in drei Stufen gemischt:

```
neutrales Profil  ->  Gesamtstil des Nutzers  ->  Stil dieser Altersgruppe
```

Je mehr eigene Stunden fuer eine Gruppe vorliegen, desto staerker schlaegt
deren eigener Stil durch (`n / (n + 2)`). So kann das Eltern-Kind-Turnen anders
geplant werden als die dritte Klasse, ohne dass eine neue Gruppe bei null
anfaengt.

## Das PDF

Standardmaessig besteht das PDF nur aus dem Stundenbild; der Haken "PDF mit
Detailseiten" haengt Ablauf, Beschreibungen, Aufbau und Sicherheitshinweise an.

**Seite 1 - Stundenbild:** Kopfzeile (frei waehlbare Ueberschrift und Datum),
Zeile `Anfang:` mit Spiel und Material, optional `Koordination:`, der
massstaebliche Hallenplan mit nummerierten Stationen an ihren Positionen,
darunter die nummerierte Stationsliste mit Material in Kurzform (`LB`, `WB`,
`kl. Kasten`), zum Schluss `Ende:`. Zeitangaben stehen nicht im PDF.

**Folgeseiten:** Ablauf, Beschreibung jeder Station, Materialliste mit Bedarf
und Bestand, Aufbau je Stundenteil und die Sicherheitshinweise.

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
  gui.py          Fenster-Oberflaeche (Tkinter)
  data/           Geraete, Sicherheitsregeln, Gruppen, Uebungen, Beispielorte
web/
  kinderturnen.html   fertige Browser-Fassung (eine Datei, gepackt)
  quelle/             deren Quellen (vorlage.html, inhalt.html, stil.css, app.js)
werkzeuge/
  baue_web.py     baut web/kinderturnen.html aus Quellen und Katalogdaten
  packen.py       entfernt Kommentare und verpackt Aufbau, Stil, Daten, Programm
tests/            104 Tests (unittest)
```

Die Browser-Fassung traegt dieselbe Logik wie das Python-Paket in JavaScript;
die Stammdaten kommen in beiden Faellen aus `sportstunden/data/`.

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
die Fenster-Oberflaeche laesst sich bedienen und verschiebt Stationen im Raster
(diese Tests werden ohne tkinter uebersprungen).

Die Browser-Fassung wird zusaetzlich im echten Chromium geprueft: sie baut sich
aus dem gepackten Block selbst auf, plant ohne Fehler, alle Stationen liegen in
der Halle, Ziehen funktioniert auch im gedrehten Plan, der Plan nimmt auf Handy,
Tablet und Rechner den groessten Teil des Fensters ein, und das erzeugte PDF hat
genau eine Seite (mit Details mehr) und keine Zeitangaben. Geprueft wird auch,
dass im Seitenquelltext nichts Lesbares steht und ohne `?pruefung=1` keine
Innereien zugaenglich sind. Diese Tests brauchen Playwright und werden sonst
uebersprungen. Nach Aenderungen an `web/quelle/` bitte
`python3 werkzeuge/baue_web.py` ausfuehren - ein Test prueft, dass die abgelegte
Datei dazu passt.

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
fuehren sofort zu einer Fehlermeldung. Nach jeder Aenderung an den Daten
`python3 werkzeuge/baue_web.py` ausfuehren.
