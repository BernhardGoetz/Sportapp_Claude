# Kinderturnen-Stundenplaner

Plant automatisch Stunden fuer das **Kinderturnen von 1 bis 10 Jahren** -
Freizeitsport, kein Leistungssport. Ergebnis ist ein **einseitiges Stundenbild
als PDF**: Anfang, massstaeblicher Hallenplan mit nummerierten Stationen an
ihren tatsaechlichen Positionen, Stationsliste mit Material, Ende. Detailseiten
gibt es auf Wunsch.

Bedient wird das Programm im Browser: **`web/kinderturnen.html`** - eine
einzige Datei fuer Handy, Tablet und Rechner, der Plan laesst sich mit dem
Finger verschieben. Mehr als ein Browser wird nicht gebraucht; eine
Kommandozeilen- oder Fensterfassung gibt es nicht.

Die Datei ist **verschluesselt**. Sie oeffnet sich auf zwei Wegen:

| Weg | Was passiert |
| --- | --- |
| **Angemeldet** | Der eigene Server (`werkzeuge/server.py`) gibt den Schluessel an jedes bestaetigte Konto heraus - **kostenlos und dauerhaft**. Registrierung mit Mailbestaetigung, Anmeldung und Verwaltung inbegriffen. |
| **Offline-Schluessel** | Die Zugabe im **Abo**: ein vom Verwalter freigegebener Schluessel oeffnet dieselbe Datei ohne jede Verbindung - fuer Hallen ohne Empfang. Er passt auf **genau ein Konto** und gilt bis zum Ende des Abos. |

Reines JavaScript, keine Fremdbibliotheken - auch nicht fuer den PDF-Export.
Das Python-Paket im Projekt liefert die Stammdaten, baut die Browser-Fassung
und stellt den Server; ausgeliefert wird allein die eine HTML-Datei.

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

## Eine Datei fuer alle Geraete

`web/kinderturnen.html` ist **eine einzige Datei** mit Katalog, Oberflaeche und
PDF-Erzeugung darin. Installiert wird nichts:

* **Rechner:** Adresse des Servers aufrufen - oder die heruntergeladene Datei
  doppelklicken.
* **Handy und Tablet:** In Safari und Chrome laesst sich die Seite ueber "Zum
  Home-Bildschirm" wie eine App ablegen. Die heruntergeladene Datei tut es
  genauso, sobald ein Offline-Schluessel freigegeben ist.

Die Oberflaeche passt sich der Bildschirmgroesse an: Der Plan bekommt immer den
groessten Teil des Fensters, auf hochkant gehaltenen Geraeten wird er passend
gedreht. Stationen werden mit dem Finger oder der Maus verschoben (Fangraster
25 cm), Ort und Geraetezahlen bleiben auf dem Geraet gespeichert.

## Konten, Anmeldung und Offline-Schluessel

Der Server (`werkzeuge/server.py`) haelt die Konten und gibt den Schluessel
zur Datei heraus. Der Weg fuer eine neue Uebungsleiterin:

1. **Registrieren** unter `/registrieren` (Name, E-Mail, Kennwort).
2. **Bestaetigen**: Es geht sofort ein sechsstelliger Code per Mail hinaus;
   erst wer ihn unter `/bestaetigen` eingibt, kommt ins Programm. Der Code
   gilt 30 Minuten, vertraegt fuenf Fehlversuche und laesst sich erneut
   anfordern. Nie bestaetigte Konten verfallen nach einer Woche von selbst.
   Das **erste angelegte Konto wird Verwalter**.
3. **Planen**: Nach der Anmeldung liefert `/` die Datei, sie holt sich den
   Schluessel ueber `/freischalten` und entschluesselt sich selbst.
4. **Offline arbeiten** (mit Abo): Der Verwalter gibt unter `/verwaltung`
   einen Offline-Schluessel frei. Er steht danach im Konto der Person
   (`KITU-XXXX-XXXX-XXXX-XXXX`), dazu ein Verweis auf die **persoenliche
   Kopie** der Datei. Einmal gespeichert, laeuft sie ueberall ohne
   Verbindung - beim ersten Oeffnen fragt sie nach **E-Mail und Schluessel**
   und merkt sich beides.

**Ein Schluessel, ein Konto.** Die Huelle, die den Blockschluessel verdeckt,
wird aus Kontokennung *und* Offline-Schluessel abgeleitet und steckt nur in
der persoenlichen Kopie. Ein weitergereichter Schluessel nuetzt ohne die
zugehoerige E-Mail nichts - und in einer fremden Kopie der Datei ebenso wenig.

**Kennwort vergessen** laeuft ueber denselben Mailweg: `/kennwort-vergessen`
schickt einen Code, `/kennwort-neu` nimmt Code und neues Kennwort entgegen.
Ob es zu einer Adresse ein Konto gibt, verraet die Seite dabei nicht.

Der Verwalter kann Konten **sperren**, Offline-Schluessel **entziehen**, das
**Abo verlaengern** und weitere Verwalter ernennen. `?lizenz=neu` in der
Adresse loescht einen gemerkten Schluessel wieder vom Geraet.

```bash
python3 werkzeuge/baue_web.py                # Datei bauen (verschluesselt)
python3 werkzeuge/server.py --port 8000 \
    --adresse https://kitu.mein-verein.de    # Adresse fuer die Verweise in den Mails
```

### Kostenlos und Abo

**Der kostenlose Zugang laeuft nie ab.** Wer ein Konto anlegt und bestaetigt,
plant damit dauerhaft: Ort und Gruppe waehlen, Stunde planen, Stundenbild als
PDF - alles dabei, ohne Ablaufdatum und ohne Nachfragen.

Ein **Abo** kommt nur dazu, wer die Datei **offline** mitnehmen will. Es laeuft
nach der gewaehlten Zeit ab:

| Knopf in der Verwaltung | Wirkung |
| --- | --- |
| **+1 Monat** | Monatsabo, 31 Tage - haengt an ein laufendes Abo hinten an |
| **+1 Jahr** | Jahresabo, 365 Tage - ebenso |
| **Abo beenden** | zurueck auf kostenlos; der Offline-Schluessel faellt weg |

Laeuft ein Abo aus, **bleibt das Konto offen** und plant kostenlos weiter -
nur die Offline-Kopie macht zu, denn sie traegt das Enddatum des Abos in sich.
Bezahlung ist bewusst nicht eingebaut: Die Mechanik steht, angebunden wird sie,
wenn ein Anbieter feststeht.

### Mail

Ohne `--smtp` landet jede Mail als lesbare Textdatei in `<daten>/postfach/` -
gut zum Ausprobieren und fuer die Tests. Mit Mailserver:

```bash
export KITU_SMTP_KENNWORT="..."
python3 werkzeuge/server.py --smtp mail.mein-verein.de:587 \
    --smtp-nutzer kitu@mein-verein.de \
    --absender "Ki Tu <kitu@mein-verein.de>" \
    --adresse https://kitu.mein-verein.de
```

Die beiden Texte stehen in `werkzeuge/post.py` (`text_bestaetigung`,
`text_kennwort`): Anrede mit Namen, der Code gut lesbar als `792 681`, die
Gueltigkeit, der passende Verweis und je ein Satz fuer den Fall, dass die
Mail unerwartet kam.

### Server betreiben

* **Verschluesselte Verbindung:** Das Skript spricht einfaches HTTP. Fuer den
  echten Betrieb gehoert nginx oder Caddy davor, der HTTPS beendet; dann
  `--https` mitgeben, damit das Sitzungs-Cookie als `Secure` markiert wird.
* **Sichern:** `server/konten.json` (Konten, Abo, Offline-Zuteilung),
  `server/geheim.txt` und `web/lizenzen.json` gehoeren ins Backup.
  `server/zugriff.log` protokolliert Registrierung, Bestaetigung, Anmeldung,
  Mailversand, Freischaltung und jede Verwaltungshandlung.
* **Kennwoerter** liegen als PBKDF2-HMAC-SHA256 mit 240000 Runden und eigenem
  Salz, die Mailcodes als HMAC. Nach zehn Fehlversuchen in einer
  Viertelstunde ist Ruhe. Jedes Formular traegt eine an die Sitzung gebundene
  Marke gegen fremde Absender.
* **Verwalter nachtragen:** `--verwalter mail@beispiel.de` macht ein
  bestehendes Konto zum Verwalter.
* **`Content-Security-Policy`:** Wird die Datei ueber einen eigenen Webserver
  ausgeliefert, darf `script-src` nicht ohne `'unsafe-eval'` gesetzt sein -
  der Lader startet das entschluesselte Programm ueber `new Function`.

## Der Quelltext bleibt zu

Die ausgelieferte Datei enthaelt **keinen lesbaren Quelltext**. Aufbau (HTML),
Gestaltung (CSS), Katalog und Programm liegen in einem verschluesselten Block
(Schluesselstrom aus SHA-256 im Zaehlerbetrieb, 32-Byte-Schluessel); sichtbar
ist nur der Lader, der ihn nach Anmeldung oder mit dem Offline-Schluessel
entschluesselt. "Seitenquelltext anzeigen" zeigt nichts Verwertbares - weder
Uebungen und Sicherheitsregeln noch die Planungslogik. Zusaetzlich:

* Aus **Kontokennung und Offline-Schluessel** wird ueber 20000 Runden
  SHA-256 die Huelle abgeleitet, die den Blockschluessel verdeckt. Die
  allgemeine Datei traegt gar keine Huelle (`var HUELLEN = [];`), die
  persoenliche Kopie genau eine - mit dem Ablaufdatum des Abos.
* Die Innereien (`window.KiTu`) reicht die Seite nur mit `?pruefung=1` in der
  Adresse heraus - im Normalbetrieb gibt es keinen Einstiegspunkt.
* Kommentare und Einrueckung sind vor dem Verschluesseln entfernt.
* `<meta name="robots" content="noarchive">` haelt Suchmaschinen-Archive fern.
* Die lesbaren Quellen liegen unter `web/quelle/`, die Schluessel in
  `web/lizenzen.json`. Beides bleibt im Projekt; weitergegeben wird allein
  `web/kinderturnen.html`.

**Grenzen, die ehrlich benannt sein wollen:** Ohne Schluessel ist der Block
nicht zu oeffnen - so weit haelt die Verschluesselung. Wer aber einen
Schluessel hat (angemeldet oder offline freigegeben), kann ihn aufheben und
weitergeben: Was der Browser ausfuehrt, muss der Browser entschluesseln
koennen. Die Bindung an ein Konto und das Ablaufdatum erhoehen die Huerde,
sind aber kein Bann fuer alle Zeiten - eine einmal heruntergeladene
persoenliche Kopie laeuft bis zum Ende ihres Abos weiter, auch wenn der
Schluessel danach entzogen wird, und die Datumspruefung glaubt der Uhr des
Geraets. (Beim kostenlosen Zugang stellt sich die Frage nicht: Der laeuft
ohnehin dauerhaft, nur eben ueber den Server.) Die fertig aufgebaute Seite ist in den Entwicklerwerkzeugen ausserdem
als Elementbaum sichtbar. Der Serverbetrieb ist damit vor allem eine
abschaltbare, protokollierte Nutzungsschranke. Wirklich beim Betreiber bliebe
die Planungslogik nur, wenn sie auf dem Server liefe und der Browser nur das
Ergebnis bekaeme; dann gaebe es aber keinen Offline-Betrieb mehr.

## Bedienung

Oben stehen Ueberschrift und Datum, hinter **"Einstellungen"** Ort, Gruppe,
Dauer, Motto, Schwerpunkt, Hauptteil, Stationszahl und Koordinationsteil. Den
groessten Teil des Fensters nimmt der massstaebliche Hallenplan ein:
**Stationen lassen sich mit dem Finger oder der Maus an ihren Platz schieben**
(Fangraster 25 cm, Ueberlappungen werden rot umrandet). Daneben - auf dem Handy
darunter - stehen Anfang, Koordinationsteil, Stationsliste und Ende.

Die Leiste unten plant eine Stunde, wuerfelt sie neu, schreibt das PDF, merkt
sich die Stunde auf dem Geraet oder uebernimmt sie als **eigene Stunde** in den
gelernten Stil.

## Neu bauen und weiterentwickeln

```bash
git clone <repo>
cd Sportapp_Claude
python3 werkzeuge/lizenzen.py --vorrat 50           # einmalig
python3 werkzeuge/baue_web.py --oeffnen             # bauen und anschauen
python3 werkzeuge/server.py --port 8000             # Konten und Freischaltung
```

Gearbeitet wird in `web/quelle/` (Oberflaeche) und `sportstunden/data/`
(Katalog); `werkzeuge/baue_web.py` setzt daraus die auslieferbare Datei
zusammen. Getestet mit Python 3.9+, keine Fremdbibliotheken.

Zum Ausprobieren ohne Server hilft `--server ""`: Dann fragt die Datei
gleich nach einem Offline-Schluessel aus `web/lizenzen.json`.

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

Unter "Einstellungen" fuehrt die Schaltflaeche **"Geraete des Ortes"** zu den
Stueckzahlen: anpassen oder auf 0 setzen, wenn heute etwas fehlt. Die Seite
merkt sich das auf dem Geraet, ohne dass etwas nach draussen geht.

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

Es zaehlen ausschliesslich Stunden, die mit **"Eigene Stunde"** uebernommen
wurden. Gelernt werden
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
web/
  kinderturnen.html   das Programm: eine Datei, verschluesselt, zum Weitergeben
  quelle/             deren Quellen (vorlage.html, inhalt.html, stil.css,
                      app.js und lader.js - der sichtbare Teil)
  lizenzen.json       Blockschluessel und Serveradresse
werkzeuge/
  baue_web.py     baut und verschluesselt web/kinderturnen.html
  packen.py       Kommentare entfernen, verschluesseln, Schluessel ableiten
  lizenzen.py     Blockschluessel und Serveradresse pflegen
  server.py       Konten, Registrierung, Bestaetigung, Abo, Freischaltung
  post.py         Mailtexte (Bestaetigung, Kennwort) und Versand
server/           Laufzeitdaten des Servers (nicht im Projektstand)
  konten.json, sitzungen.json, geheim.txt, zugriff.log, postfach/
sportstunden/     Stammdaten und Vergleichsfassung in Python (wird nicht ausgeliefert)
  data/           Geraete, Sicherheitsregeln, Gruppen, Uebungen, Beispielorte
  models.py       Datenmodelle (Ort, Geraeteplatz, Uebung, Stunde ...)
  katalog.py      Stammdaten, Bedarfsrechnung inkl. Sicherheitsregeln
  speicher.py     JSON-Speicherung von Orten, Stunden, Einstellungen
  stil.py         Stil-Lernen je Altersgruppe
  planer.py       Auswahl, Flaechenbudget, Zeitverteilung, Geraetebuchung
  platzierung.py  Geraetemasse und Positionen der Stationen in der Halle
  hallenplan.py   Massstaeblicher Plan mit Geraetesymbolen
  pdf.py          Minimaler PDF-Generator (Text, Tabellen, Grafik)
  export.py       Layout des Stundenbilds und der Detailseiten
tests/            191 Tests (unittest)
```

`web/quelle/app.js` traegt dieselbe Logik wie das Python-Paket in JavaScript.
Das Python-Paket bleibt als Quelle der Stammdaten und als geprueftes
Gegenstueck bestehen: Bedarfsrechnung, Absicherung, Flaechenbudget und
Platzierung lassen sich dort mit vollem Testumfang nachrechnen. Wer die
Planungsregeln aendert, aendert sie an beiden Stellen.

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
Ueberschrift ist frei waehlbar, der gelernte Stil veraendert die Auswahl.

Die Browser-Fassung wird im echten Chromium geprueft: sie baut sich aus dem
entschluesselten Block selbst auf, plant ohne Fehler, alle Stationen liegen in
der Halle, Ziehen funktioniert auch im gedrehten Plan, der Plan nimmt auf Handy,
Tablet und Rechner den groessten Teil des Fensters ein, und das erzeugte PDF hat
genau eine Seite (mit Details mehr) und keine Zeitangaben. Zur Verschluesselung:
im Seitenquelltext steht nichts Lesbares, ohne Schluessel bleibt es bei der
Abfrage, ein falscher Schluessel wird abgewiesen, derselbe Schluessel mit
einer fremden E-Mail ebenfalls, ein abgelaufenes Abo haelt die Datei zu, und
ein richtiges Paar wird gemerkt.

Der Server hat eigene Tests: Registrierung, Bestaetigung per Mailcode
(falscher, abgelaufener und verbrauchter Code, neuer Code auf Wunsch),
Anmeldung, Sperre nach zehn Fehlversuchen, Kennwoerter und Codes nur als
Hash, Kennwort-Zuruecksetzen ueber die Mail (einmalig, ohne zu verraten wer
ein Konto hat), Abolaufzeiten und Verlaengerung, kein Zutritt zur Verwaltung ohne
Rolle, Vergabe und Entzug der Offline-Schluessel, Formulare ohne gueltige
Marke werden abgewiesen. Eigene Tests halten fest, dass der kostenlose Zugang
dauerhaft offen bleibt - auch nach Jahren und nach einem abgelaufenen Abo -
und dass es einen Offline-Schluessel nur mit laufendem Abo gibt. Ein Test rechnet nach, dass die Huelle eines Kontos
mit einer anderen Kennung nichts hergibt.

Die Mailtexte pruefen `tests/test_post.py`: Anrede, gruppierter Code,
Gueltigkeit, der richtige Verweis, keine offenen Platzhalter - und dass sich
die beiden Texte nicht verwechseln lassen.

Drei Tests gehen den ganzen Weg im Browser: im leeren Chromium registrieren,
Code aus dem Postfach eingeben, das Programm erscheint und plant eine Stunde;
ein gesperrtes Konto fliegt wieder heraus; und die persoenliche Datei
oeffnet sich per `file://` mit E-Mail und Schluessel. Damit ist auch belegt,
dass das SHA-256 im Lader exakt zu Python passt.

Die Browsertests brauchen Playwright und werden sonst uebersprungen. Nach
Aenderungen an `web/quelle/` bitte `python3 werkzeuge/baue_web.py` ausfuehren -
ein Test prueft, dass die abgelegte Datei dazu passt.

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
