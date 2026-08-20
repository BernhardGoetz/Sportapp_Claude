/* Kinderturnen-Stundenplaner - laeuft ohne Installation im Browser.
 *
 * Aufbau:
 *   1. Hilfen            5. Planer
 *   2. Katalog           6. Zeichnen (Bildschirm und PDF)
 *   3. Bedarf            7. PDF
 *   4. Stil              8. Speicher und Oberflaeche
 *
 * Die Daten (Geraete, Gruppen, Uebungen, Orte) stehen in DATEN und stammen
 * aus denselben JSON-Dateien wie das Python-Programm.
 */
(function () {
  "use strict";

  // ==========================================================================
  // 1. Hilfen
  // ==========================================================================

  function zufallsfolge(seed) {
    let a = (seed >>> 0) || 1;
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const runde = (wert, stellen) => Math.round(wert * 10 ** stellen) / 10 ** stellen;

  function addiere(ziel, quelle) {
    for (const [schluessel, wert] of Object.entries(quelle || {})) {
      ziel[schluessel] = (ziel[schluessel] || 0) + wert;
    }
    return ziel;
  }

  function maximum(ziel, quelle) {
    for (const [schluessel, wert] of Object.entries(quelle || {})) {
      ziel[schluessel] = Math.max(ziel[schluessel] || 0, wert);
    }
    return ziel;
  }

  const heute = () => new Date().toISOString().slice(0, 10);

  function datumDeutsch(iso) {
    const teile = String(iso || "").split("-");
    return teile.length === 3 ? `${teile[2]}.${teile[1]}.${teile[0]}` : iso;
  }

  // ==========================================================================
  // 2. Katalog
  // ==========================================================================

  const GERAETE = {};
  DATEN.geraete.forEach((g) => (GERAETE[g.id] = g));
  const SICHERHEITSREGELN = DATEN.sicherheitsregeln;
  const SICHERHEITSHINWEISE = DATEN.sicherheitshinweise || {};
  const GRUPPEN = DATEN.altersgruppen;
  const UEBUNGEN = DATEN.uebungen;
  const KOORDINATION_AB_ALTER = DATEN.koordination_ab_alter || 6;

  const geraetName = (id) => (GERAETE[id] ? GERAETE[id].name : id);
  const geraetKurz = (id) => (GERAETE[id] ? GERAETE[id].kurz || GERAETE[id].name : id);
  const istAbsicherung = (id) => !!GERAETE[id] && GERAETE[id].kategorie === "absicherung";

  const THEMEN = Array.from(
    new Set(UEBUNGEN.map((u) => u.thema).filter(Boolean))
  ).sort();

  function brauchtKoordinationsteil(gruppe) {
    return gruppe.alter_max >= KOORDINATION_AB_ALTER;
  }

  function passtZuAlter(uebung, gruppe) {
    return !(uebung.alter_max < gruppe.alter_min || uebung.alter_min > gruppe.alter_max);
  }

  const dauerVorschlag = (u) => Math.round((u.dauer_min + u.dauer_max) / 2);
  const proKindUebung = (u) => (u.gruppengroesse || 0) === 1;

  // ==========================================================================
  // 3. Bedarf (Material inklusive Absicherung)
  // ==========================================================================

  function sicherheitsbedarf(geraete) {
    const bedarf = {};
    for (const [id, anzahl] of Object.entries(geraete)) {
      const regel = SICHERHEITSREGELN[id];
      if (!regel) continue;
      for (const [sicherung, faktor] of Object.entries(regel)) {
        bedarf[sicherung] = (bedarf[sicherung] || 0) + faktor * anzahl;
      }
    }
    return bedarf;
  }

  /** Material einer Uebung: fest, je Riege oder "fuer alle" (pro Kind). */
  function bedarf(uebung, riegen, bestand) {
    riegen = Math.max(1, riegen || 1);
    const proKind = proKindUebung(uebung);
    const gruppen = !uebung.gruppengroesse || proKind ? 1 : riegen;

    const geraete = Object.assign({}, uebung.geraete_fix || {});
    const fuerAlle = [];
    for (const [id, anzahl] of Object.entries(uebung.geraete_pro_gruppe || {})) {
      if (proKind) {
        fuerAlle.push(id);
        const vorhanden = (bestand && bestand[id]) || 0;
        geraete[id] = (geraete[id] || 0) + Math.max(anzahl, vorhanden);
      } else {
        geraete[id] = (geraete[id] || 0) + anzahl * gruppen;
      }
    }

    const absicherung = Object.assign({}, uebung.absicherung_fix || {});
    for (const [id, anzahl] of Object.entries(uebung.absicherung_pro_gruppe || {})) {
      absicherung[id] = (absicherung[id] || 0) + anzahl * (proKind ? 1 : gruppen);
    }
    for (const [id, anzahl] of Object.entries(sicherheitsbedarf(geraete))) {
      absicherung[id] = Math.max(absicherung[id] || 0, anzahl);
    }

    const sauber = (werte) =>
      Object.fromEntries(Object.entries(werte).filter(([, v]) => v > 0));
    return {
      geraete: sauber(geraete),
      absicherung: sauber(absicherung),
      proKind: Array.from(new Set(fuerAlle)).sort(),
      gruppen,
    };
  }

  const gesamtbedarf = (station) =>
    addiere(Object.assign({}, station.geraete), station.absicherung);

  function materialText(station, kurz) {
    const bedarfListe = gesamtbedarf(station);
    const namen = kurz ? geraetKurz : geraetName;
    const eintraege = Object.entries(bedarfListe).sort((a, b) =>
      namen(a[0]).localeCompare(namen(b[0]), "de")
    );
    if (!eintraege.length) return "kein Material";
    return eintraege
      .map(([id, anzahl]) => {
        if ((station.proKind || []).includes(id)) return `${namen(id)} fuer alle`;
        return anzahl > 1 ? `${anzahl}x ${namen(id)}` : namen(id);
      })
      .join(", ");
  }

  // ==========================================================================
  // 4. Stil - gelernt aus eigenen Stunden
  // ==========================================================================

  const NEUTRALE_ANTEILE = {
    aufwaermen: 0.2,
    koordination: 0.13,
    hauptteil: 0.52,
    abschluss: 0.15,
  };

  function basisfrequenz(merkmale) {
    const zaehler = {};
    UEBUNGEN.forEach((u) => {
      new Set(merkmale(u)).forEach((m) => (zaehler[m] = (zaehler[m] || 0) + 1));
    });
    const gesamt = Math.max(1, UEBUNGEN.length);
    return Object.fromEntries(
      Object.entries(zaehler).map(([k, v]) => [k, v / gesamt])
    );
  }

  const BASIS_TAGS = basisfrequenz((u) => u.tags || []);

  /** Tag-Gewichte aus den eigenen Stunden - gegen den Katalog normiert. */
  function stilprofil(eigeneStunden, gruppenId) {
    const passend = eigeneStunden.filter(
      (s) => !gruppenId || s.altersgruppe_id === gruppenId
    );
    const stichprobe = passend.length ? passend : eigeneStunden;
    if (!stichprobe.length) return { tags: {}, lieblinge: {}, stichprobe: 0 };

    const tagZaehler = {};
    const uebungsZaehler = {};
    let uebungen = 0;
    stichprobe.forEach((stunde) => {
      (stunde.teile || []).forEach((teil) => {
        (teil.uebungen || []).forEach((u) => {
          uebungen += 1;
          new Set(u.tags || []).forEach(
            (tag) => (tagZaehler[tag] = (tagZaehler[tag] || 0) + 1)
          );
          if (u.uebung_id) {
            uebungsZaehler[u.uebung_id] = (uebungsZaehler[u.uebung_id] || 0) + 1;
          }
        });
      });
    });

    const gewicht = (anteil, basis) => {
      const wert = Math.log((anteil + 0.02) / (basis + 0.02));
      return Math.max(-1.2, Math.min(1.2, wert));
    };
    const tags = {};
    for (const [tag, anzahl] of Object.entries(tagZaehler)) {
      tags[tag] = gewicht(anzahl / Math.max(1, uebungen), BASIS_TAGS[tag] || 0);
    }
    const lieblinge = {};
    for (const [id, anzahl] of Object.entries(uebungsZaehler)) {
      lieblinge[id] = anzahl / stichprobe.length;
    }
    return { tags, lieblinge, stichprobe: stichprobe.length };
  }

  // ==========================================================================
  // 5. Planer
  // ==========================================================================

  const MIN_STATIONEN = 3;
  const MAX_STATIONEN = 8;
  const WANDSTREIFEN = 1.0;
  const BELEGUNGSFAKTOR = 0.6;
  const MITTLERE_STATIONSFLAECHE = 22.0;
  const STANDARD_RIEGEN = 3;
  const MINDESTDAUER_TEIL = 4;

  const PHASEN_TITEL = {
    aufwaermen: "Aufwaermen",
    koordination: "Koordinationsteil",
    hauptteil: "Hauptteil",
    abschluss: "Abschluss",
  };

  function flaechenbudget(ort) {
    const laenge = Math.max(2, ort.laenge - 2 * WANDSTREIFEN);
    const breite = Math.max(2, ort.breite - 2 * WANDSTREIFEN);
    return laenge * breite * BELEGUNGSFAKTOR;
  }

  function stationszahl(auftrag) {
    if (auftrag.stationszahl) {
      return Math.max(1, Math.min(MAX_STATIONEN, auftrag.stationszahl));
    }
    const geschaetzt = Math.floor(flaechenbudget(auftrag.ort) / MITTLERE_STATIONSFLAECHE);
    return Math.max(MIN_STATIONEN, Math.min(MAX_STATIONEN, geschaetzt));
  }

  function kandidaten(phase, auftrag) {
    const gruppe = auftrag.gruppe;
    return UEBUNGEN.filter((u) => {
      if (u.phase !== phase) return false;
      if (!(u.orte || []).includes(auftrag.ort.art)) return false;
      if (!passtZuAlter(u, gruppe)) return false;
      if ((u.intensitaet || 3) > (gruppe.max_intensitaet || 5)) return false;
      if (phase === "koordination" && (gruppe.koordination_schwerpunkte || []).length) {
        const treffer = (u.koordination || []).some((k) =>
          gruppe.koordination_schwerpunkte.includes(k)
        );
        if (!treffer) return false;
      }
      return true;
    });
  }

  function bewertung(uebung, auftrag, phase, wuerfel, stil) {
    let punkte = 1.0;
    (uebung.tags || []).forEach((tag) => (punkte += stil.tags[tag] || 0));
    punkte += 1.5 * (stil.lieblinge[uebung.id] || 0);

    if (auftrag.schwerpunkt) {
      const schwerpunkt = auftrag.schwerpunkt.toLowerCase();
      if ((uebung.tags || []).some((t) => t.toLowerCase() === schwerpunkt)) punkte += 1.6;
      else if (uebung.name.toLowerCase().includes(schwerpunkt)) punkte += 0.8;
    }
    if (auftrag.thema) {
      if (uebung.thema === auftrag.thema) punkte += 1.2;
      else if (uebung.thema) punkte -= 0.3;
    }
    const gruppe = auftrag.gruppe;
    if (phase === "koordination") {
      const treffer = (uebung.koordination || []).filter((k) =>
        (gruppe.koordination_schwerpunkte || []).includes(k)
      ).length;
      punkte += 0.4 * treffer;
      const druck = (uebung.druckbedingungen || []).filter((d) =>
        (gruppe.druckbedingungen || []).includes(d)
      ).length;
      punkte += 0.2 * druck;
    }
    const ueberlappung =
      Math.min(uebung.alter_max, gruppe.alter_max) -
      Math.max(uebung.alter_min, gruppe.alter_min);
    if (ueberlappung >= gruppe.alter_max - gruppe.alter_min) punkte += 0.3;
    return punkte + wuerfel() * 0.35;
  }

  function phasendauern(gesamt, phasen) {
    const roh = {};
    phasen.forEach((p) => (roh[p] = gesamt * (NEUTRALE_ANTEILE[p] || 0.2)));
    const summe = phasen.reduce((s, p) => s + roh[p], 0) || 1;
    const dauern = {};
    phasen.forEach(
      (p) => (dauern[p] = Math.max(MINDESTDAUER_TEIL, Math.floor((roh[p] / summe) * gesamt)))
    );
    let differenz = gesamt - phasen.reduce((s, p) => s + dauern[p], 0);
    const reihenfolge = phasen.slice().sort((a, b) => roh[b] - roh[a]);
    let index = 0;
    while (differenz !== 0 && reihenfolge.length) {
      const phase = reihenfolge[index % reihenfolge.length];
      if (differenz > 0) {
        dauern[phase] += 1;
        differenz -= 1;
      } else if (dauern[phase] > MINDESTDAUER_TEIL) {
        dauern[phase] -= 1;
        differenz += 1;
      } else if (reihenfolge.every((p) => dauern[p] <= MINDESTDAUER_TEIL)) {
        break;
      }
      index += 1;
    }
    return dauern;
  }

  function verteileDauern(uebungen, ziel) {
    if (!uebungen.length) return [];
    const dauern = uebungen.map((u) => dauerVorschlag(u));
    const summe = () => dauern.reduce((s, d) => s + d, 0);

    while (summe() > ziel) {
      const kandidatenIndex = dauern
        .map((d, i) => i)
        .filter((i) => dauern[i] > uebungen[i].dauer_min);
      if (!kandidatenIndex.length) break;
      const groesster = kandidatenIndex.reduce((a, b) => (dauern[a] >= dauern[b] ? a : b));
      dauern[groesster] -= 1;
    }
    for (const grenze of [1.0, 1.3]) {
      while (summe() < ziel) {
        const frei = dauern
          .map((d, i) => i)
          .filter((i) => dauern[i] < Math.floor(uebungen[i].dauer_max * grenze));
        if (!frei.length) break;
        const kleinster = frei.reduce((a, b) => (dauern[a] <= dauern[b] ? a : b));
        dauern[kleinster] += 1;
      }
    }
    let ueberhang = summe() - ziel;
    while (ueberhang > 0) {
      let gekuerzt = false;
      for (let i = dauern.length - 1; i >= 0 && ueberhang > 0; i -= 1) {
        if (dauern[i] > 3) {
          dauern[i] -= 1;
          ueberhang -= 1;
          gekuerzt = true;
        }
      }
      if (!gekuerzt) break;
    }
    return dauern;
  }

  function alsStation(uebung, dauer, teil) {
    return {
      uebung_id: uebung.id,
      name: uebung.name,
      dauer,
      beschreibung: uebung.beschreibung,
      aufbau: uebung.aufbau || "",
      hinweise: uebung.hinweise || "",
      organisation: uebung.organisation || "ganze_gruppe",
      gruppen: teil.gruppen,
      tags: (uebung.tags || []).slice(),
      koordination: (uebung.koordination || []).slice(),
      intensitaet: uebung.intensitaet || 3,
      geraete: teil.geraete,
      absicherung: teil.absicherung,
      proKind: teil.proKind,
      x: 0,
      y: 0,
      stellLaenge: 0,
      stellBreite: 0,
    };
  }

  function planeTeil(phase, zielDauer, auftrag, rest, wuerfel, stil, optionen) {
    optionen = optionen || {};
    const warnungen = [];
    let auswahl = kandidaten(phase, auftrag);
    if (optionen.nurStationen !== undefined) {
      auswahl = auswahl.filter((u) => !!u.stationsbetrieb === optionen.nurStationen);
    }
    if (!auswahl.length) {
      warnungen.push(
        `Fuer den Teil '${PHASEN_TITEL[phase]}' gibt es keine passende Uebung.`
      );
      return { teil: { phase, uebungen: [], parallel: false, notiz: "", puffer: 0 }, warnungen };
    }

    const bewertet = auswahl
      .map((u) => ({ u, punkte: bewertung(u, auftrag, phase, wuerfel, stil) }))
      .sort((a, b) => b.punkte - a.punkte)
      .map((e) => e.u);

    const zielAnzahl = optionen.zielAnzahl || (phase === "hauptteil" ? 2 : 1);
    const riegen = optionen.nurStationen ? zielAnzahl : STANDARD_RIEGEN;
    const gewaehlt = [];
    const bedarfe = [];
    let uebersprungen = 0;
    let budget = optionen.nurStationen ? flaechenbudget(auftrag.ort) : Infinity;
    let flaecheKnapp = false;

    const zeitGedeckt = () =>
      gewaehlt.reduce((s, u) => s + u.dauer_max * 1.25, 0) >= zielDauer;

    for (const uebung of bewertet) {
      if (gewaehlt.length >= zielAnzahl && zeitGedeckt()) break;
      if (gewaehlt.length >= zielAnzahl + 3) break;

      const teil = bedarf(uebung, riegen, rest);
      const gesamt = addiere(Object.assign({}, teil.geraete), teil.absicherung);
      const passt = Object.entries(gesamt).every(
        ([id, anzahl]) => (rest[id] || 0) >= anzahl
      );
      if (!passt) {
        uebersprungen += 1;
        continue;
      }

      let platzbedarf = 0;
      if (optionen.nurStationen) {
        const probe = { geraete: teil.geraete, absicherung: teil.absicherung, proKind: [] };
        const [laenge, breite] = stellflaeche(probe);
        platzbedarf = laenge * breite * 1.15;
        if (gewaehlt.length && platzbedarf > budget) {
          flaecheKnapp = true;
          continue;
        }
      }
      for (const [id, anzahl] of Object.entries(gesamt)) rest[id] = (rest[id] || 0) - anzahl;
      budget -= platzbedarf;
      gewaehlt.push(uebung);
      bedarfe.push(teil);
    }

    if (!gewaehlt.length) {
      warnungen.push(`'${PHASEN_TITEL[phase]}': das Material reicht nicht aus.`);
      return { teil: { phase, uebungen: [], parallel: false, notiz: "", puffer: 0 }, warnungen };
    }
    if (flaecheKnapp) {
      warnungen.push(
        `${PHASEN_TITEL[phase]}: mehr Stationen haetten in ${auftrag.ort.name} keinen Platz.`
      );
    }
    if (uebersprungen) {
      warnungen.push(
        `${PHASEN_TITEL[phase]}: ${uebersprungen} Uebung(en) ohne passendes Material ausgelassen.`
      );
    }

    const dauern = verteileDauern(gewaehlt, zielDauer);
    const uebungen = gewaehlt.map((u, i) => alsStation(u, Math.max(3, dauern[i]), bedarfe[i]));
    const parallel = uebungen.length > 1;
    const puffer = Math.max(0, zielDauer - uebungen.reduce((s, u) => s + u.dauer, 0));
    return {
      teil: {
        phase,
        uebungen,
        parallel,
        notiz: parallel ? "Alle Aufbauten stehen gleichzeitig." : "",
        puffer,
      },
      warnungen,
    };
  }

  function planeHauptteil(zielDauer, auftrag, rest, wuerfel, stil) {
    let stationen = auftrag.stationsbetrieb;
    if (stationen === null || stationen === undefined) stationen = wuerfel() < 0.75;
    let letzte = null;
    for (const versuch of [stationen, !stationen]) {
      const sicherung = Object.assign({}, rest);
      const ergebnis = planeTeil("hauptteil", zielDauer, auftrag, rest, wuerfel, stil, {
        zielAnzahl: versuch ? stationszahl(auftrag) : 1,
        nurStationen: versuch,
      });
      if (ergebnis.teil.uebungen.length) {
        if (versuch) {
          ergebnis.teil.parallel = true;
          ergebnis.teil.notiz = `Bewegungslandschaft mit ${ergebnis.teil.uebungen.length} Stationen - Wechsel im Uhrzeigersinn.`;
        }
        return ergebnis;
      }
      Object.keys(rest).forEach((k) => delete rest[k]);
      Object.assign(rest, sicherung);
      letzte = ergebnis;
    }
    return letzte;
  }

  function plane(auftrag) {
    const wuerfel = zufallsfolge(auftrag.seed || 1);
    const stil = auftrag.stil || { tags: {}, lieblinge: {}, stichprobe: 0 };
    const bestand = Object.assign({}, auftrag.ausstattung || auftrag.ort.ausstattung);

    let phasen = ["aufwaermen"];
    const mitKoordination =
      auftrag.koordinationsteil === null || auftrag.koordinationsteil === undefined
        ? brauchtKoordinationsteil(auftrag.gruppe)
        : auftrag.koordinationsteil;
    if (mitKoordination) phasen.push("koordination");
    phasen = phasen.concat(["hauptteil", "abschluss"]);

    const planeAlle = (liste) => {
      const dauern = phasendauern(auftrag.dauer, liste);
      const teile = [];
      const warnungen = [];
      liste.forEach((phase) => {
        const rest = Object.assign({}, bestand); // zwischen den Teilen wird umgebaut
        const ergebnis =
          phase === "hauptteil"
            ? planeHauptteil(dauern[phase], auftrag, rest, wuerfel, stil)
            : planeTeil(phase, dauern[phase], auftrag, rest, wuerfel, stil, {});
        teile.push(ergebnis.teil);
        warnungen.push(...ergebnis.warnungen);
      });
      return { teile, warnungen };
    };

    let { teile, warnungen } = planeAlle(phasen);
    const gefuellt = teile.filter((t) => t.uebungen.length).map((t) => t.phase);
    if (gefuellt.length && gefuellt.length < phasen.length) {
      const leere = teile.filter((t) => !t.uebungen.length);
      ({ teile, warnungen } = planeAlle(gefuellt));
      leere.forEach((t) =>
        warnungen.push(
          `Der Teil '${PHASEN_TITEL[t.phase]}' liess sich nicht besetzen - die Zeit wurde verteilt.`
        )
      );
    }

    const stunde = {
      id: "stunde-" + Math.random().toString(36).slice(2, 10),
      titel: titelFuer(auftrag),
      ueberschrift: auftrag.ueberschrift || "Ki Tu",
      ort_id: auftrag.ort.id,
      ort_name: auftrag.ort.name,
      ortsart: auftrag.ort.art,
      altersgruppe_id: auftrag.gruppe.id,
      altersgruppe_name: auftrag.gruppe.name,
      dauer: auftrag.dauer,
      thema: auftrag.thema || "",
      schwerpunkt: auftrag.schwerpunkt || "",
      datum: auftrag.datum || heute(),
      quelle: "geplant",
      teile,
      ort_laenge: auftrag.ort.laenge,
      ort_breite: auftrag.ort.breite,
    };

    warnungen.push(...platziereStationen(stunde, auftrag.ort));
    return { stunde, warnungen, bestand };
  }

  function titelFuer(auftrag) {
    const teile = ["Kinderturnen", auftrag.gruppe.name.split(" (")[0]];
    if (auftrag.thema) {
      teile.push("Motto " + auftrag.thema[0].toUpperCase() + auftrag.thema.slice(1));
    } else if (auftrag.schwerpunkt) {
      teile.push("Schwerpunkt " + auftrag.schwerpunkt);
    }
    return teile.join(" - ");
  }

  function hauptteilVon(stunde) {
    return (stunde.teile || []).find((t) => t.phase === "hauptteil");
  }

  function stationenVon(stunde) {
    const teil = hauptteilVon(stunde);
    if (teil && teil.uebungen.length) return teil.uebungen;
    const anderer = (stunde.teile || []).find((t) => t.uebungen.length);
    return anderer ? anderer.uebungen : [];
  }

  function platziereStationen(stunde, ort) {
    const teil = hauptteilVon(stunde);
    if (!teil || !teil.uebungen.length) return [];
    const zielDauer = teil.uebungen.reduce((s, u) => s + u.dauer, 0) + teil.puffer;
    let hinweise = [];
    for (let runde = 0; runde < 4; runde += 1) {
      hinweise = platziere(teil.uebungen, ort);
      const streit = konflikte(teil.uebungen, ort);
      if (!streit.length || teil.uebungen.length <= 1) break;
      const namen = teil.uebungen.map((u) => u.name);
      const [erste, zweite] = streit[0];
      const weg =
        namen.indexOf(erste) > namen.indexOf(zweite) && namen.includes(erste)
          ? erste
          : zweite;
      const index = namen.indexOf(weg);
      if (index < 0) break;
      const entfernt = teil.uebungen.splice(index, 1)[0];
      hinweise.push(`'${entfernt.name}' hatte keinen Platz mehr und wurde weggelassen.`);
      const rest = Math.max(0, zielDauer - teil.puffer);
      const grund = Math.max(3, Math.floor(rest / teil.uebungen.length));
      teil.uebungen.forEach((u) => (u.dauer = grund));
      let fehlt = rest - grund * teil.uebungen.length;
      let i = 0;
      while (fehlt > 0 && teil.uebungen.length) {
        teil.uebungen[i % teil.uebungen.length].dauer += 1;
        fehlt -= 1;
        i += 1;
      }
      if (teil.uebungen.length) {
        teil.notiz = `Bewegungslandschaft mit ${teil.uebungen.length} Stationen - Wechsel im Uhrzeigersinn.`;
      }
    }
    return hinweise;
  }

  // ==========================================================================
  // 6. Platzierung in der Halle
  // ==========================================================================

  const GERAETEMASSE = DATEN.geraetemasse;
  const STANDARDMASS = [0.6, 0.6];
  const ORTSFESTE_GERAETE = DATEN.ortsfeste_geraete;
  const WANDABSTAND = 0.8;
  const SICHERHEITSRAND = 0.9;
  const SICHERHEITSRAND_SPRUNG = 1.4;
  const RASTER_SUCHE = 0.5;
  const RASTER_ZIEHEN = 0.25;
  const MAX_STATIONSLAENGE = 9.0;
  const MAX_STATIONSBREITE = 7.0;

  const mass = (id) => GERAETEMASSE[id] || STANDARDMASS;

  function ueberlappt(a, b) {
    return !(
      a[0] + a[2] <= b[0] ||
      b[0] + b[2] <= a[0] ||
      a[1] + a[3] <= b[1] ||
      b[1] + b[3] <= a[1]
    );
  }

  function geraetflaeche(id, anzahl) {
    const [laenge, breite] = mass(id);
    const spalten = Math.max(1, Math.ceil(Math.sqrt(Math.max(1, anzahl))));
    const zeilen = Math.max(1, Math.ceil(Math.max(1, anzahl) / spalten));
    return [laenge * spalten, breite * zeilen];
  }

  function ortsfestesGeraet(station) {
    const bedarfListe = gesamtbedarf(station);
    return ORTSFESTE_GERAETE.find((id) => bedarfListe[id]) || null;
  }

  function stellflaeche(station) {
    const bedarfListe = gesamtbedarf(station);
    const eintraege = Object.entries(bedarfListe);
    if (!eintraege.length) return [2.5, 2.5];

    let flaeche = 0;
    let laengstes = 0;
    let breitestes = 0;
    eintraege.forEach(([id, anzahl]) => {
      const [l, b] = geraetflaeche(id, anzahl);
      flaeche += l * b;
      const [el, eb] = mass(id);
      laengstes = Math.max(laengstes, el);
      breitestes = Math.max(breitestes, eb);
    });
    flaeche *= 1.6;
    let laenge = Math.max(laengstes, Math.sqrt(flaeche * 1.5));
    let breite = Math.max(breitestes, flaeche / laenge);
    const rand =
      Object.keys(station.absicherung || {}).length || ortsfestesGeraet(station)
        ? SICHERHEITSRAND_SPRUNG
        : SICHERHEITSRAND;
    laenge = Math.min(MAX_STATIONSLAENGE, laenge) + rand;
    breite = Math.min(MAX_STATIONSBREITE, breite) + rand;
    return [runde(laenge, 2), runde(breite, 2)];
  }

  function rasterpunkte(halle, flaeche) {
    const [hl, hb] = halle;
    const [laenge, breite] = flaeche;
    let maxX = hl - WANDABSTAND - laenge;
    let maxY = hb - WANDABSTAND - breite;
    if (maxX < WANDABSTAND) maxX = Math.max(0, (hl - laenge) / 2);
    if (maxY < WANDABSTAND) maxY = Math.max(0, (hb - breite) / 2);
    const punkte = [];
    for (let x = Math.min(WANDABSTAND, maxX); x <= maxX + 1e-6; x += RASTER_SUCHE) {
      for (let y = Math.min(WANDABSTAND, maxY); y <= maxY + 1e-6; y += RASTER_SUCHE) {
        punkte.push([runde(x, 2), runde(y, 2)]);
      }
    }
    if (!punkte.length) punkte.push([0, 0]);
    return punkte;
  }

  function naechsterFreierPlatz(ziel, flaeche, halle, belegt, hoechstabstand) {
    const [laenge, breite] = flaeche;
    let beste = null;
    let besterAbstand = Infinity;
    for (const [x, y] of rasterpunkte(halle, flaeche)) {
      const abstand = Math.hypot(x + laenge / 2 - ziel[0], y + breite / 2 - ziel[1]);
      if (abstand >= besterAbstand) continue;
      if (hoechstabstand !== undefined && abstand > hoechstabstand) continue;
      const kandidat = [x, y, laenge, breite];
      if (belegt.some((anderes) => ueberlappt(kandidat, anderes))) continue;
      beste = [x, y];
      besterAbstand = abstand;
    }
    return beste;
  }

  function ringziel(index, anzahl, halle) {
    const [hl, hb] = halle;
    const winkel = Math.PI / 2 + (2 * Math.PI * index) / Math.max(1, anzahl);
    return [hl / 2 + hl * 0.32 * Math.cos(winkel), hb / 2 + hb * 0.3 * Math.sin(winkel)];
  }

  const platzRechteck = (p) => [p.x, p.y, p.laenge, p.breite];

  function setzePosition(station, x, y, laenge, breite) {
    station.x = runde(x, 2);
    station.y = runde(y, 2);
    station.stellLaenge = runde(laenge, 2);
    station.stellBreite = runde(breite, 2);
  }

  function platziere(stationen, ort) {
    if (!stationen.length) return [];
    const halle = [ort.laenge, ort.breite];
    const hinweise = [];
    const belegt = [];
    const blockiert = (ort.geraeteplaetze || []).map(platzRechteck);
    const freie = {};
    (ort.geraeteplaetze || []).forEach((p) => {
      (freie[p.geraet] = freie[p.geraet] || []).push(p);
    });

    const verankert = [];
    const mobil = [];
    stationen.forEach((station) => {
      const geraet = ortsfestesGeraet(station);
      const plaetze = geraet ? freie[geraet] || [] : [];
      if (geraet && plaetze.length) verankert.push([station, plaetze.shift()]);
      else mobil.push(station);
    });

    verankert.forEach(([station, platz]) => {
      let [laenge, breite] = stellflaeche(station);
      laenge = Math.min(laenge, ort.laenge - 0.2);
      breite = Math.min(breite, ort.breite - 0.2);
      const mitteX = platz.x + platz.laenge / 2;
      const mitteY = platz.y + platz.breite / 2;
      let zielX = Math.min(Math.max(mitteX - laenge / 2, 0.1), ort.laenge - laenge - 0.1);
      let zielY = Math.min(Math.max(mitteY - breite / 2, 0.1), ort.breite - breite - 0.1);
      const eigen = platzRechteck(platz);
      const hindernisse = belegt.concat(
        blockiert.filter((r) => r.join() !== eigen.join())
      );
      if (hindernisse.some((r) => ueberlappt([zielX, zielY, laenge, breite], r))) {
        let ausweich = null;
        for (const radius of [2.5, 4.0]) {
          ausweich = naechsterFreierPlatz(
            [mitteX, mitteY], [laenge, breite], halle, hindernisse, radius
          );
          if (ausweich) break;
        }
        if (ausweich) [zielX, zielY] = ausweich;
        else hinweise.push(`'${station.name}' steht dicht an einer anderen Station.`);
      }
      setzePosition(station, zielX, zielY, laenge, breite);
      belegt.push([zielX, zielY, laenge, breite]);
    });

    mobil.forEach((station) => {
      let [laenge, breite] = stellflaeche(station);
      laenge = Math.min(laenge, Math.max(1, ort.laenge - 2 * WANDABSTAND));
      breite = Math.min(breite, Math.max(1, ort.breite - 2 * WANDABSTAND));
      const ziel = ringziel(stationen.indexOf(station), stationen.length, halle);
      let position = naechsterFreierPlatz(
        ziel, [laenge, breite], halle, belegt.concat(blockiert)
      );
      if (!position) {
        position = [
          Math.min(Math.max(ziel[0] - laenge / 2, 0.1), Math.max(0.1, ort.laenge - laenge - 0.1)),
          Math.min(Math.max(ziel[1] - breite / 2, 0.1), Math.max(0.1, ort.breite - breite - 0.1)),
        ];
        hinweise.push(`Fuer '${station.name}' ist die Flaeche knapp.`);
      }
      setzePosition(station, position[0], position[1], laenge, breite);
      belegt.push([position[0], position[1], laenge, breite]);
    });
    return hinweise;
  }

  function kollisionen(stationen) {
    const treffer = [];
    const liste = stationen.filter((s) => s.stellLaenge > 0);
    for (let i = 0; i < liste.length; i += 1) {
      for (let j = i + 1; j < liste.length; j += 1) {
        const a = liste[i];
        const b = liste[j];
        if (
          ueberlappt(
            [a.x, a.y, a.stellLaenge, a.stellBreite],
            [b.x, b.y, b.stellLaenge, b.stellBreite]
          )
        ) {
          treffer.push([a.name, b.name]);
        }
      }
    }
    return treffer;
  }

  function konflikte(stationen, ort) {
    const treffer = kollisionen(stationen);
    (ort.geraeteplaetze || []).forEach((platz) => {
      stationen.forEach((station) => {
        if (station.stellLaenge <= 0) return;
        if (ortsfestesGeraet(station) === platz.geraet) return;
        if (
          ueberlappt(
            [station.x, station.y, station.stellLaenge, station.stellBreite],
            platzRechteck(platz)
          )
        ) {
          treffer.push([platz.geraet, station.name]);
        }
      });
    });
    return treffer;
  }

  // ==========================================================================
  // 7. Zeichnen - gleiche Symbole fuer Bildschirm und PDF
  // ==========================================================================

  const FARBEN = {
    plan: [0.09, 0.34, 0.55],
    raster: [0.87, 0.91, 0.95],
    geraet: [0.13, 0.4, 0.62],
    fest: [0.62, 0.67, 0.72],
    flaeche: [0.95, 0.96, 0.98],
    text: [0.1, 0.1, 0.12],
    grau: [0.45, 0.47, 0.52],
    warn: [0.75, 0.2, 0.15],
  };

  const SYMBOLE = {
    matte: (z, x, y, b, h) => {
      z.rechteck(x, y, b, h, FARBEN.geraet, 0.8);
      z.linie(x + b * 0.08, y + h * 0.25, x + b * 0.92, y + h * 0.25, FARBEN.geraet, 0.35);
      z.linie(x + b * 0.08, y + h * 0.75, x + b * 0.92, y + h * 0.75, FARBEN.geraet, 0.35);
    },
    weichbodenmatte: (z, x, y, b, h) => {
      z.rechteck(x, y, b, h, FARBEN.geraet, 1);
      [0.3, 0.6, 0.9].forEach((a) =>
        z.linie(x + b * a, y, x + b * Math.max(0, a - 0.25), y + h, FARBEN.geraet, 0.45)
      );
    },
    kasten: (z, x, y, b, h) => {
      z.rechteck(x, y, b, h, FARBEN.geraet, 0.9);
      [0.33, 0.66].forEach((a) =>
        z.linie(x, y + h * a, x + b, y + h * a, FARBEN.geraet, 0.5)
      );
    },
    bank: (z, x, y, b, h) => {
      z.rechteck(x, y + h * 0.25, b, h * 0.5, FARBEN.geraet, 0.9);
      [0.1, 0.9].forEach((a) =>
        z.linie(x + b * a, y + h * 0.25, x + b * a, y, FARBEN.geraet, 0.6)
      );
    },
    reifen: (z, x, y, b, h) => {
      const r = Math.min(b, h) / 2.2;
      const spalten = Math.max(1, Math.min(3, Math.floor(b / (r * 2.2))));
      for (let i = 0; i < spalten; i += 1) {
        z.kreis(x + r * 1.1 + i * r * 2.2, y + h / 2, r, FARBEN.geraet, 0.8);
      }
    },
    reck: (z, x, y, b, h) => {
      z.linie(x + b * 0.1, y, x + b * 0.1, y + h, FARBEN.geraet, 0.9);
      z.linie(x + b * 0.9, y, x + b * 0.9, y + h, FARBEN.geraet, 0.9);
      z.linie(x, y + h * 0.5, x + b, y + h * 0.5, FARBEN.geraet, 1.2);
    },
    barren: (z, x, y, b, h) => {
      [0.3, 0.7].forEach((a) => z.linie(x, y + h * a, x + b, y + h * a, FARBEN.geraet, 1.1));
      [0.15, 0.85].forEach((a) =>
        z.linie(x + b * a, y + h * 0.3, x + b * a, y + h * 0.7, FARBEN.geraet, 0.6)
      );
    },
    ringe: (z, x, y, b, h) => {
      const r = Math.min(b, h) * 0.18;
      [0.3, 0.7].forEach((a) => z.kreis(x + b * a, y + h * 0.5, r, FARBEN.geraet, 0.9));
      z.linie(x + b * 0.3, y + h * 0.5, x + b * 0.7, y + h * 0.5, FARBEN.geraet, 0.4);
    },
    tau: (z, x, y, b, h) => {
      const punkte = [];
      for (let i = 0; i <= 6; i += 1) {
        punkte.push([x + b * (0.5 + 0.3 * Math.sin(i * 1.6)), y + (h * i) / 6]);
      }
      z.pfad(punkte, FARBEN.geraet, 0.9);
    },
    sprossenwand: (z, x, y, b, h) => {
      z.rechteck(x, y, b, h, FARBEN.geraet, 0.9);
      const schritte = h >= b ? 5 : 3;
      for (let i = 1; i < schritte; i += 1) {
        if (h >= b) z.linie(x, y + (h * i) / schritte, x + b, y + (h * i) / schritte, FARBEN.geraet, 0.45);
        else z.linie(x + (b * i) / schritte, y, x + (b * i) / schritte, y + h, FARBEN.geraet, 0.45);
      }
    },
    trampolin: (z, x, y, b, h) =>
      z.pfad(
        [
          [x + b * 0.05, y],
          [x + b * 0.95, y],
          [x + b * 0.75, y + h],
          [x + b * 0.25, y + h],
        ],
        FARBEN.geraet,
        0.9,
        true
      ),
    sprungbrett: (z, x, y, b, h) =>
      z.pfad([[x, y], [x + b, y + h * 0.8], [x + b, y]], FARBEN.geraet, 0.9, true),
    balken: (z, x, y, b, h) => {
      z.rechteck(x, y + h * 0.3, b, h * 0.4, FARBEN.geraet, 0.9);
      [0.2, 0.8].forEach((a) =>
        z.linie(x + b * a, y + h * 0.3, x + b * a, y, FARBEN.geraet, 0.6)
      );
    },
    schwungtuch: (z, x, y, b, h) => {
      const r = Math.min(b, h) * 0.45;
      const mx = x + b / 2;
      const my = y + h / 2;
      z.kreis(mx, my, r, FARBEN.geraet, 0.9);
      for (let i = 0; i < 6; i += 1) {
        const w = (i * Math.PI) / 3;
        z.linie(mx, my, mx + r * Math.cos(w), my + r * Math.sin(w), FARBEN.geraet, 0.35);
      }
    },
    rollbrett: (z, x, y, b, h) => {
      z.rechteck(x, y, b, h, FARBEN.geraet, 0.9);
      [0.2, 0.8].forEach((ax) =>
        [0.2, 0.8].forEach((ay) =>
          z.kreis(x + b * ax, y + h * ay, Math.min(b, h) * 0.1, FARBEN.geraet, 0.5, true)
        )
      );
    },
    baelle: (z, x, y, b, h) => {
      const r = Math.min(b / 4.5, h / 2.2);
      for (let i = 0; i < 3; i += 1) {
        z.kreis(x + r * 1.2 + i * r * 2.4, y + h / 2, r, FARBEN.geraet, 0.7);
      }
    },
    huetchen: (z, x, y, b, h) => {
      const breite = b / 3;
      for (let i = 0; i < 3; i += 1) {
        const links = x + i * breite;
        z.pfad(
          [
            [links + breite * 0.1, y],
            [links + breite * 0.5, y + h],
            [links + breite * 0.9, y],
          ],
          FARBEN.geraet,
          0.7,
          true
        );
      }
    },
    leiter: (z, x, y, b, h) => {
      z.rechteck(x, y, b, h, FARBEN.geraet, 0.8);
      for (let i = 1; i < 5; i += 1) {
        z.linie(x + (b * i) / 5, y, x + (b * i) / 5, y + h, FARBEN.geraet, 0.45);
      }
    },
    seil: (z, x, y, b, h) => {
      const punkte = [];
      for (let i = 0; i <= 8; i += 1) {
        punkte.push([x + (b * i) / 8, y + h * (0.5 + 0.4 * Math.sin(i * 1.3))]);
      }
      z.pfad(punkte, FARBEN.geraet, 0.8);
    },
    eimer: (z, x, y, b, h) =>
      z.pfad(
        [
          [x + b * 0.2, y],
          [x + b * 0.8, y],
          [x + b * 0.9, y + h],
          [x + b * 0.1, y + h],
        ],
        FARBEN.geraet,
        0.8,
        true
      ),
    bausteine: (z, x, y, b, h) => {
      z.rechteck(x, y, b * 0.45, h * 0.45, FARBEN.geraet, 0.7);
      z.rechteck(x + b * 0.55, y, b * 0.45, h * 0.45, FARBEN.geraet, 0.7);
      z.rechteck(x + b * 0.27, y + h * 0.55, b * 0.45, h * 0.45, FARBEN.geraet, 0.7);
    },
    tuecher: (z, x, y, b, h) => {
      for (let i = 0; i < 2; i += 1) {
        const links = x + i * b * 0.5;
        z.pfad(
          [
            [links + b * 0.05, y],
            [links + b * 0.2, y + h],
            [links + b * 0.4, y + h * 0.4],
          ],
          FARBEN.geraet,
          0.7,
          true
        );
      }
    },
    saeckchen: (z, x, y, b, h) => {
      for (let i = 0; i < 3; i += 1) {
        z.rechteck(x + i * b * 0.34, y + h * 0.25, b * 0.28, h * 0.5, FARBEN.geraet, 0.7);
      }
    },
    tor: (z, x, y, b, h) =>
      z.pfad([[x, y], [x, y + h], [x + b, y + h], [x + b, y]], FARBEN.geraet, 0.9),
    scheibe: (z, x, y, b, h) => {
      const r = Math.min(b, h) * 0.4;
      z.kreis(x + b / 2, y + h / 2, r, FARBEN.geraet, 0.9);
      z.kreis(x + b / 2, y + h / 2, r * 0.45, FARBEN.geraet, 0.5);
    },
    karten: (z, x, y, b, h) => {
      for (let i = 0; i < 2; i += 1) {
        z.rechteck(x + b * i * 0.3, y + h * i * 0.15, b * 0.6, h * 0.7, FARBEN.geraet, 0.7);
      }
    },
    pedalo: (z, x, y, b, h) => {
      z.rechteck(x, y + h * 0.3, b, h * 0.4, FARBEN.geraet, 0.8);
      [0.25, 0.75].forEach((a) =>
        z.kreis(x + b * a, y + h * 0.2, Math.min(b, h) * 0.14, FARBEN.geraet, 0.6)
      );
    },
    kreisel: (z, x, y, b, h) => {
      const r = Math.min(b, h) * 0.4;
      z.kreis(x + b / 2, y + h / 2, r, FARBEN.geraet, 0.9);
      z.kreis(x + b / 2, y + h / 2, r * 0.25, FARBEN.geraet, 0.6, true);
    },
  };

  const SYMBOL_FUER = {
    matte: "matte",
    weichbodenmatte: "weichbodenmatte",
    niedersprungmatte: "weichbodenmatte",
    kasten_gross: "kasten",
    kasten_klein: "kasten",
    kastenteil: "kasten",
    langbank: "bank",
    schwebebalken: "balken",
    reifen: "reifen",
    reck: "reck",
    barren: "barren",
    ringe: "ringe",
    tau: "tau",
    sprossenwand: "sprossenwand",
    klettergeruest: "sprossenwand",
    minitrampolin: "trampolin",
    sprungbrett: "sprungbrett",
    schwungtuch: "schwungtuch",
    rollbrett: "rollbrett",
    softball: "baelle",
    kleiner_ball: "baelle",
    grosser_ball: "baelle",
    luftballon: "baelle",
    huetchen: "huetchen",
    markierungsteller: "huetchen",
    huerde_klein: "huetchen",
    koordinationsleiter: "leiter",
    seil_lang: "seil",
    springseil: "seil",
    gummiband: "seil",
    eimer: "eimer",
    baustein: "bausteine",
    teppichfliese: "bausteine",
    jongliertuch: "tuecher",
    sandsaeckchen: "saeckchen",
    kleintor: "tor",
    wurfscheibe: "scheibe",
    bewegungskarten: "karten",
    pedalo: "pedalo",
    balancekreisel: "kreisel",
  };

  const KATEGORIE_RANG = {
    grossgeraet: 0,
    absicherung: 1,
    spielfeld: 2,
    kleingeraet: 3,
    sonstiges: 4,
  };

  function wichtigsteGeraete(station, hoechstens) {
    return Object.entries(gesamtbedarf(station))
      .sort((a, b) => {
        const symbolA = SYMBOL_FUER[a[0]] ? 0 : 1;
        const symbolB = SYMBOL_FUER[b[0]] ? 0 : 1;
        if (symbolA !== symbolB) return symbolA - symbolB;
        const katA = KATEGORIE_RANG[(GERAETE[a[0]] || {}).kategorie] ?? 5;
        const katB = KATEGORIE_RANG[(GERAETE[b[0]] || {}).kategorie] ?? 5;
        return katA - katB;
      })
      .slice(0, hoechstens || 4);
  }

  /** Rechnet Hallenmeter in Zeichenpunkte um.
   *
   * ``gedreht`` stellt die Halle quer - auf hochkant gehaltenen Geraeten
   * wird der Plan dadurch deutlich groesser.
   */
  function massstab(halle, x, y, breite, hoehe, gedreht) {
    const [planL, planB] = gedreht ? [halle[1], halle[0]] : [halle[0], halle[1]];
    const faktor = Math.min(breite / planL, hoehe / planB);
    const planBreite = planL * faktor;
    const planHoehe = planB * faktor;
    return {
      halleLaenge: halle[0],
      halleBreite: halle[1],
      gedreht: !!gedreht,
      faktor,
      planBreite,
      planHoehe,
      x: x + (breite - planBreite) / 2,
      y: y + (hoehe - planHoehe) / 2,
      punkt(mx, my) {
        if (this.gedreht) {
          return [
            this.x + (this.halleBreite - my) * this.faktor,
            this.y + mx * this.faktor,
          ];
        }
        return [this.x + mx * this.faktor, this.y + my * this.faktor];
      },
      /** Bildschirmrechteck eines Hallenrechtecks (Ecke links unten, Groesse). */
      rechteck(mx, my, ml, mb) {
        if (this.gedreht) {
          const ecke = this.punkt(mx, my + mb);
          return [ecke[0], ecke[1], mb * this.faktor, ml * this.faktor];
        }
        const ecke = this.punkt(mx, my);
        return [ecke[0], ecke[1], ml * this.faktor, mb * this.faktor];
      },
      laenge(m) {
        return m * this.faktor;
      },
      meter(px, py) {
        if (this.gedreht) {
          return [
            (py - this.y) / this.faktor,
            this.halleBreite - (px - this.x) / this.faktor,
          ];
        }
        return [(px - this.x) / this.faktor, (py - this.y) / this.faktor];
      },
    };
  }

  function zeichnePlan(z, stunde, ort, x, y, breite, hoehe, optionen) {
    optionen = optionen || {};
    const halle = [stunde.ort_laenge || 27, stunde.ort_breite || 15];
    // Hochkant-Flaeche und querliegende Halle: Plan drehen, dann wird er groesser.
    const gedreht =
      optionen.drehen === undefined
        ? hoehe / Math.max(1, breite) > 1.1 && halle[0] / Math.max(1, halle[1]) > 1.1
        : optionen.drehen;
    const ms = massstab(halle, x, y, breite, hoehe, gedreht);

    for (let m = 1; m < halle[0]; m += 1) {
      const a = ms.punkt(m, 0);
      const b = ms.punkt(m, halle[1]);
      z.linie(a[0], a[1], b[0], b[1], FARBEN.raster, 0.3);
    }
    for (let m = 1; m < halle[1]; m += 1) {
      const a = ms.punkt(0, m);
      const b = ms.punkt(halle[0], m);
      z.linie(a[0], a[1], b[0], b[1], FARBEN.raster, 0.3);
    }
    z.rechteck(ms.x, ms.y, ms.planBreite, ms.planHoehe, FARBEN.plan, 1.6);

    ((ort && ort.geraeteplaetze) || []).forEach((platz) => {
      const [px, py, pb, ph] = ms.rechteck(platz.x, platz.y, platz.laenge, platz.breite);
      z.rechteck(px, py, pb, ph, FARBEN.fest, 0.5);
    });
    z.text(`${halle[0]} x ${halle[1]} m`, ms.x + 3, ms.y - 9, 6.5, FARBEN.grau);

    const stationen = stationenVon(stunde);
    stationen.forEach((station, index) => {
      zeichneStation(z, station, index + 1, ms, optionen);
    });
    return ms;
  }

  function zeichneStation(z, station, nummer, ms, optionen) {
    if (!station.stellLaenge) return;
    const [eckeX, eckeY, breite, hoehe] = ms.rechteck(
      station.x,
      station.y,
      station.stellLaenge,
      station.stellBreite
    );
    const ecke = [eckeX, eckeY];

    if (optionen.mitFlaechen) z.flaeche(ecke[0], ecke[1], breite, hoehe, FARBEN.flaeche);
    if (optionen.markiert && optionen.markiert.includes(station.name)) {
      z.rechteck(ecke[0], ecke[1], breite, hoehe, FARBEN.warn, 2);
    }

    const rand = Math.min(0.4, station.stellLaenge * 0.08);
    let cursorX = station.x + rand;
    let zeileOben = station.y + station.stellBreite - rand;
    let zeileHoehe = 0;
    wichtigsteGeraete(station).forEach(([id, anzahl]) => {
      let [gl, gb] = mass(id);
      gl = Math.min(gl, station.stellLaenge - 2 * rand);
      gb = Math.min(gb, station.stellBreite - 2 * rand);
      if (cursorX + gl > station.x + station.stellLaenge - rand) {
        cursorX = station.x + rand;
        zeileOben -= zeileHoehe + 0.2;
        zeileHoehe = 0;
      }
      if (zeileOben - gb < station.y + rand) return;
      const [gx, gy, gbreite, ghoehe] = ms.rechteck(cursorX, zeileOben - gb, gl, gb);
      const zeichner = SYMBOLE[SYMBOL_FUER[id]];
      if (zeichner) zeichner(z, gx, gy, gbreite, ghoehe);
      else z.rechteck(gx, gy, gbreite, ghoehe, FARBEN.geraet, 0.6);
      cursorX += gl + 0.25;
      zeileHoehe = Math.max(zeileHoehe, gb);
    });

    const kreisX = ecke[0] + 9;
    const kreisY = ecke[1] + hoehe - 9;
    z.kreis(kreisX, kreisY, 8, FARBEN.plan, 1.1);
    z.text(String(nummer), kreisX, kreisY - 2.8, 8.5, FARBEN.plan, true, true);
    if (optionen.mitNamen) {
      z.text(station.name, ecke[0] + breite / 2, ecke[1] + 3, 7, FARBEN.text, false, true);
    }
  }

  function stationAnPunkt(stationen, ms, px, py) {
    const [mx, my] = ms.meter(px, py);
    for (let i = stationen.length - 1; i >= 0; i -= 1) {
      const s = stationen[i];
      if (!s.stellLaenge) continue;
      if (mx >= s.x && mx <= s.x + s.stellLaenge && my >= s.y && my <= s.y + s.stellBreite) {
        return s;
      }
    }
    return null;
  }

  /** Zeichenflaeche fuer das Bild auf dem Schirm (y zeigt nach oben wie im PDF). */
  function leinwandZeichner(ctx, hoehe, skalierung) {
    const farbe = (f) =>
      `rgb(${Math.round(f[0] * 255)},${Math.round(f[1] * 255)},${Math.round(f[2] * 255)})`;
    const y = (wert) => hoehe - wert;
    return {
      rechteck(x, yy, b, h, f, staerke) {
        ctx.strokeStyle = farbe(f || FARBEN.geraet);
        ctx.lineWidth = Math.max(0.7, staerke || 0.8) * skalierung;
        ctx.strokeRect(x, y(yy + h), b, h);
      },
      flaeche(x, yy, b, h, f) {
        ctx.fillStyle = farbe(f || FARBEN.flaeche);
        ctx.fillRect(x, y(yy + h), b, h);
      },
      linie(x1, y1, x2, y2, f, staerke) {
        ctx.strokeStyle = farbe(f || FARBEN.geraet);
        ctx.lineWidth = Math.max(0.5, staerke || 0.6) * skalierung;
        ctx.beginPath();
        ctx.moveTo(x1, y(y1));
        ctx.lineTo(x2, y(y2));
        ctx.stroke();
      },
      kreis(x, yy, r, f, staerke, fuellen) {
        ctx.beginPath();
        ctx.arc(x, y(yy), r, 0, Math.PI * 2);
        if (fuellen) {
          ctx.fillStyle = farbe(f || FARBEN.geraet);
          ctx.fill();
        } else {
          ctx.strokeStyle = farbe(f || FARBEN.geraet);
          ctx.lineWidth = Math.max(0.7, staerke || 0.8) * skalierung;
          ctx.stroke();
        }
      },
      pfad(punkte, f, staerke, schliessen, fuellen) {
        if (punkte.length < 2) return;
        ctx.beginPath();
        ctx.moveTo(punkte[0][0], y(punkte[0][1]));
        punkte.slice(1).forEach((p) => ctx.lineTo(p[0], y(p[1])));
        if (schliessen) ctx.closePath();
        if (fuellen) {
          ctx.fillStyle = farbe(f || FARBEN.geraet);
          ctx.fill();
        } else {
          ctx.strokeStyle = farbe(f || FARBEN.geraet);
          ctx.lineWidth = Math.max(0.7, staerke || 0.8) * skalierung;
          ctx.stroke();
        }
      },
      text(inhalt, x, yy, groesse, f, fett, zentriert) {
        ctx.fillStyle = farbe(f || FARBEN.text);
        ctx.font = `${fett ? "600 " : ""}${Math.max(9, (groesse || 7) * skalierung)}px system-ui, sans-serif`;
        ctx.textAlign = zentriert ? "center" : "left";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(inhalt, x, y(yy));
      },
    };
  }

  // ==========================================================================
  // 8. PDF
  // ==========================================================================

  const HELVETICA = DATEN.schriftbreiten.normal;
  const HELVETICA_FETT = DATEN.schriftbreiten.fett;
  const SONDERZEICHEN = {
    "ä": "a", "ö": "o", "ü": "u", "Ä": "A", "Ö": "O", "Ü": "U", "ß": "s",
    "é": "e", "è": "e", "à": "a", "ç": "c", "°": "o", "§": "s", "„": '"',
    "“": '"', "”": '"', "–": "-", "—": "-", "’": "'",
  };

  function zeichenbreite(zeichen, fett) {
    const tabelle = fett ? HELVETICA_FETT : HELVETICA;
    const code = zeichen.charCodeAt(0);
    if (code >= 32 && code <= 126) return tabelle[code - 32];
    const ersatz = SONDERZEICHEN[zeichen];
    if (ersatz) return tabelle[ersatz.charCodeAt(0) - 32];
    return tabelle["n".charCodeAt(0) - 32];
  }

  function textbreite(text, groesse, fett) {
    let summe = 0;
    for (const zeichen of String(text)) summe += zeichenbreite(zeichen, fett);
    return (summe * groesse) / 1000;
  }

  function umbrechen(text, breite, groesse, fett) {
    const zeilen = [];
    String(text)
      .split("\n")
      .forEach((absatz) => {
        const worte = absatz.split(/\s+/).filter(Boolean);
        if (!worte.length) {
          zeilen.push("");
          return;
        }
        let aktuell = worte[0];
        worte.slice(1).forEach((wort) => {
          const versuch = `${aktuell} ${wort}`;
          if (textbreite(versuch, groesse, fett) <= breite) aktuell = versuch;
          else {
            zeilen.push(aktuell);
            aktuell = wort;
          }
        });
        zeilen.push(aktuell);
      });
    return zeilen;
  }

  function pdfText(text) {
    let ausgabe = "";
    for (const zeichen of String(text)) {
      const code = zeichen.charCodeAt(0);
      let ziel = zeichen;
      if (code > 126) ziel = SONDERZEICHEN[zeichen] || "?";
      if (ziel === "(" || ziel === ")" || ziel === "\\") ausgabe += "\\";
      ausgabe += ziel;
    }
    return ausgabe;
  }

  function neuesPdf(fusstext) {
    const seiten = [];
    let inhalt = [];
    const breite = 595.28;
    const hoehe = 841.89;
    const rand = 48;

    const pdf = {
      breite,
      hoehe,
      rand,
      y: hoehe - rand,
      satzbreite: breite - 2 * rand,
      neueSeite() {
        if (inhalt.length) seiten.push(inhalt);
        inhalt = [];
        this.y = hoehe - rand;
      },
      _befehl(text) {
        inhalt.push(text);
      },
      text(wert, x, y, groesse, farbe, fett, zentriert) {
        const f = farbe || FARBEN.text;
        let stelle = x;
        if (zentriert) stelle = x - textbreite(wert, groesse, fett) / 2;
        inhalt.push(
          `BT ${f[0]} ${f[1]} ${f[2]} rg /${fett ? "F2" : "F1"} ${groesse} Tf ` +
            `1 0 0 1 ${stelle.toFixed(2)} ${y.toFixed(2)} Tm (${pdfText(wert)}) Tj ET`
        );
      },
      rechteck(x, y, b, h, farbe, staerke) {
        const f = farbe || FARBEN.geraet;
        inhalt.push(
          `${f[0]} ${f[1]} ${f[2]} RG ${(staerke || 0.8).toFixed(2)} w ` +
            `${x.toFixed(2)} ${y.toFixed(2)} ${b.toFixed(2)} ${h.toFixed(2)} re S`
        );
      },
      flaeche(x, y, b, h, farbe) {
        const f = farbe || FARBEN.flaeche;
        inhalt.push(
          `${f[0]} ${f[1]} ${f[2]} rg ${x.toFixed(2)} ${y.toFixed(2)} ` +
            `${b.toFixed(2)} ${h.toFixed(2)} re f`
        );
      },
      linie(x1, y1, x2, y2, farbe, staerke) {
        const f = farbe || FARBEN.geraet;
        inhalt.push(
          `${f[0]} ${f[1]} ${f[2]} RG ${(staerke || 0.6).toFixed(2)} w ` +
            `${x1.toFixed(2)} ${y1.toFixed(2)} m ${x2.toFixed(2)} ${y2.toFixed(2)} l S`
        );
      },
      kreis(x, y, r, farbe, staerke, fuellen) {
        const f = farbe || FARBEN.geraet;
        const k = r * 0.5523;
        const teile = [
          `${(x - r).toFixed(2)} ${y.toFixed(2)} m`,
          `${(x - r).toFixed(2)} ${(y + k).toFixed(2)} ${(x - k).toFixed(2)} ${(y + r).toFixed(2)} ${x.toFixed(2)} ${(y + r).toFixed(2)} c`,
          `${(x + k).toFixed(2)} ${(y + r).toFixed(2)} ${(x + r).toFixed(2)} ${(y + k).toFixed(2)} ${(x + r).toFixed(2)} ${y.toFixed(2)} c`,
          `${(x + r).toFixed(2)} ${(y - k).toFixed(2)} ${(x + k).toFixed(2)} ${(y - r).toFixed(2)} ${x.toFixed(2)} ${(y - r).toFixed(2)} c`,
          `${(x - k).toFixed(2)} ${(y - r).toFixed(2)} ${(x - r).toFixed(2)} ${(y - k).toFixed(2)} ${(x - r).toFixed(2)} ${y.toFixed(2)} c`,
        ];
        teile.push(
          fuellen
            ? `${f[0]} ${f[1]} ${f[2]} rg f`
            : `${f[0]} ${f[1]} ${f[2]} RG ${(staerke || 0.8).toFixed(2)} w S`
        );
        inhalt.push(teile.join(" "));
      },
      pfad(punkte, farbe, staerke, schliessen, fuellen) {
        if (punkte.length < 2) return;
        const f = farbe || FARBEN.geraet;
        const teile = [`${punkte[0][0].toFixed(2)} ${punkte[0][1].toFixed(2)} m`];
        punkte.slice(1).forEach((p) => teile.push(`${p[0].toFixed(2)} ${p[1].toFixed(2)} l`));
        if (schliessen) teile.push("h");
        if (fuellen) teile.push(`${f[0]} ${f[1]} ${f[2]} rg f`);
        else {
          teile.unshift(`${f[0]} ${f[1]} ${f[2]} RG ${(staerke || 0.8).toFixed(2)} w`);
          teile.push("S");
        }
        inhalt.push(teile.join(" "));
      },
      absatz(text, groesse, einzug, farbe, fett) {
        umbrechen(text, this.satzbreite - (einzug || 0), groesse, fett).forEach((zeile) => {
          if (this.y < rand + 40) this.neueSeite();
          this.y -= groesse * 1.35;
          if (zeile) this.text(zeile, rand + (einzug || 0), this.y, groesse, farbe, fett);
        });
      },
      bytes() {
        if (inhalt.length) seiten.push(inhalt);
        // Fusszeile auf jede Seite
        seiten.forEach((seite, nummer) => {
          const y = rand - 14;
          seite.push(
            `0.8 0.83 0.87 RG 0.8 w ${rand} ${y + 12} m ${breite - rand} ${y + 12} l S`
          );
          seite.push(
            `BT 0.45 0.47 0.52 rg /F1 8 Tf 1 0 0 1 ${rand} ${y} Tm (${pdfText(fusstext)}) Tj ET`
          );
          const zaehler = `Seite ${nummer + 1} von ${seiten.length}`;
          seite.push(
            `BT 0.45 0.47 0.52 rg /F1 8 Tf 1 0 0 1 ` +
              `${(breite - rand - textbreite(zaehler, 8)).toFixed(2)} ${y} Tm (${zaehler}) Tj ET`
          );
        });

        const objekte = [];
        const hinzu = (daten) => {
          objekte.push(daten);
          return objekte.length;
        };
        const f1 = hinzu("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
        const f2 = hinzu("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>");
        const inhaltIds = seiten.map((seite) => {
          const strom = seite.join("\n");
          return hinzu(`<< /Length ${strom.length} >>\nstream\n${strom}\nendstream`);
        });
        const seitenIds = [];
        const pagesId = objekte.length + seiten.length + 1;
        seiten.forEach((_, index) => {
          seitenIds.push(
            hinzu(
              `<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 ${breite} ${hoehe}] ` +
                `/Resources << /Font << /F1 ${f1} 0 R /F2 ${f2} 0 R >> >> ` +
                `/Contents ${inhaltIds[index]} 0 R >>`
            )
          );
        });
        const pages = hinzu(
          `<< /Type /Pages /Count ${seitenIds.length} /Kids [${seitenIds
            .map((id) => `${id} 0 R`)
            .join(" ")}] >>`
        );
        const katalog = hinzu(`<< /Type /Catalog /Pages ${pages} 0 R >>`);

        let ausgabe = "%PDF-1.4\n";
        const versatz = [];
        objekte.forEach((daten, index) => {
          versatz.push(ausgabe.length);
          ausgabe += `${index + 1} 0 obj\n${daten}\nendobj\n`;
        });
        const xref = ausgabe.length;
        ausgabe += `xref\n0 ${objekte.length + 1}\n0000000000 65535 f \n`;
        versatz.forEach((stelle) => {
          ausgabe += `${String(stelle).padStart(10, "0")} 00000 n \n`;
        });
        ausgabe += `trailer\n<< /Size ${objekte.length + 1} /Root ${katalog} 0 R >>\n`;
        ausgabe += `startxref\n${xref}\n%%EOF\n`;

        const bytes = new Uint8Array(ausgabe.length);
        for (let i = 0; i < ausgabe.length; i += 1) bytes[i] = ausgabe.charCodeAt(i) & 0xff;
        return bytes;
      },
    };
    return pdf;
  }

  function stundenPdf(stunde, ort, optionen) {
    optionen = optionen || {};
    const pdf = neuesPdf(`Kinderturnen - Stundenbild vom ${datumDeutsch(heute())}`);
    const akzent = [0.09, 0.34, 0.55];

    // Kopf
    const oben = pdf.hoehe - 42;
    pdf.text(stunde.ueberschrift || "Ki Tu", pdf.breite / 2, oben, 20, akzent, true, true);
    pdf.text(datumDeutsch(stunde.datum), pdf.breite - pdf.rand - 60, oben, 11, FARBEN.text);
    const kopfzeile = [stunde.altersgruppe_name, stunde.ort_name];
    if (stunde.thema) {
      kopfzeile.push("Motto: " + stunde.thema[0].toUpperCase() + stunde.thema.slice(1));
    }
    pdf.y = oben - 16;
    pdf.text(kopfzeile.join("   -   "), pdf.breite / 2, pdf.y, 9, FARBEN.grau, false, true);
    pdf.y -= 16;

    const eckzeile = (beschriftung, phase) => {
      const teil = (stunde.teile || []).find((t) => t.phase === phase);
      if (!teil || !teil.uebungen.length) return;
      pdf.y -= 14;
      pdf.text(beschriftung, pdf.rand, pdf.y, 11, akzent, true);
      const versatz = pdf.rand + 76;
      teil.uebungen.forEach((uebung, index) => {
        if (index) pdf.y -= 12;
        pdf.text(uebung.name, versatz, pdf.y, 10.5, FARBEN.text, true);
        const material = materialText(uebung, true);
        if (material !== "kein Material") {
          umbrechen(material, pdf.breite - pdf.rand - versatz, 8.5).forEach((zeile) => {
            pdf.y -= 11;
            pdf.text(zeile, versatz, pdf.y, 8.5, FARBEN.grau);
          });
        }
      });
      pdf.y -= 4;
    };

    eckzeile("Anfang:", "aufwaermen");
    eckzeile("Koordination:", "koordination");

    const hauptteil = hauptteilVon(stunde);
    const stationen = hauptteil ? hauptteil.uebungen : [];
    if (hauptteil && hauptteil.parallel && stationen.length) {
      pdf.y -= 13;
      pdf.text(
        `Hauptteil: ${stationen.length} Stationen, Wechsel im Uhrzeigersinn`,
        pdf.rand,
        pdf.y,
        9,
        FARBEN.grau
      );
    }

    const listenHoehe = 15 * Math.max(1, stationen.length) + 24;
    const verfuegbar = pdf.y - pdf.rand - listenHoehe - 46;
    const ausForm =
      (pdf.satzbreite * (stunde.ort_breite || 15)) / Math.max(1, stunde.ort_laenge || 27);
    const planHoehe = Math.max(140, Math.min(ausForm, verfuegbar));
    pdf.y -= planHoehe + 12;
    zeichnePlan(pdf, stunde, ort, pdf.rand, pdf.y, pdf.satzbreite, planHoehe, {});
    pdf.y -= 4;

    pdf.y -= 8;
    stationen.forEach((station, index) => {
      pdf.y -= 14;
      const kreisX = pdf.rand + 7;
      pdf.kreis(kreisX, pdf.y + 3, 7, akzent, 0.9);
      pdf.text(String(index + 1), kreisX, pdf.y, 8, akzent, true, true);
      const name = `${station.name}:`;
      pdf.text(name, pdf.rand + 19, pdf.y, 10, FARBEN.text, true);
      const textX = pdf.rand + 19 + textbreite(name, 10, true) + 5;
      umbrechen(materialText(station, true), pdf.breite - pdf.rand - textX, 9).forEach(
        (zeile, stelle) => {
          if (stelle) pdf.y -= 11;
          pdf.text(zeile, stelle === 0 ? textX : pdf.rand + 19, pdf.y, 9, FARBEN.text);
        }
      );
    });
    pdf.y -= 6;
    eckzeile("Ende:", "abschluss");

    if (optionen.mitDetails) detailseiten(pdf, stunde);
    return pdf.bytes();
  }

  function detailseiten(pdf, stunde) {
    pdf.neueSeite();
    pdf.y -= 6;
    pdf.text("Ablauf", pdf.rand, pdf.y, 13, [0.09, 0.34, 0.55], true);
    pdf.y -= 6;
    pdf.linie(pdf.rand, pdf.y, pdf.breite - pdf.rand, pdf.y, [0.9, 0.92, 0.95], 1);

    (stunde.teile || []).forEach((teil) => {
      pdf.y -= 16;
      if (pdf.y < pdf.rand + 60) pdf.neueSeite();
      pdf.text(PHASEN_TITEL[teil.phase] || teil.phase, pdf.rand, pdf.y, 10.5, FARBEN.text, true);
      if (teil.notiz) pdf.absatz(teil.notiz, 8.5, 0, FARBEN.grau);
      teil.uebungen.forEach((uebung) => {
        pdf.y -= 12;
        if (pdf.y < pdf.rand + 60) pdf.neueSeite();
        pdf.text(uebung.name, pdf.rand + 6, pdf.y, 9.5, FARBEN.text, true);
        pdf.absatz("Material: " + materialText(uebung, false), 8.5, 12, FARBEN.grau);
        pdf.absatz(uebung.beschreibung, 9, 12, FARBEN.text);
        if (uebung.aufbau) pdf.absatz("Aufbau: " + uebung.aufbau, 8.5, 12, FARBEN.grau);
        if (uebung.hinweise) pdf.absatz("Hinweis: " + uebung.hinweise, 8.5, 12, FARBEN.grau);
      });
    });

    // Sicherheit
    const hinweise = [];
    stunde.teile.forEach((teil) =>
      teil.uebungen.forEach((uebung) => {
        Object.keys(uebung.geraete || {}).forEach((id) => {
          const hinweis = SICHERHEITSHINWEISE[id];
          if (hinweis && !hinweise.includes(`${geraetName(id)}: ${hinweis}`)) {
            hinweise.push(`${geraetName(id)}: ${hinweis}`);
          }
        });
      })
    );
    if (hinweise.length) {
      pdf.y -= 18;
      if (pdf.y < pdf.rand + 80) pdf.neueSeite();
      pdf.text("Sicherheit und Absicherung", pdf.rand, pdf.y, 13, [0.09, 0.34, 0.55], true);
      hinweise.forEach((hinweis) => pdf.absatz("- " + hinweis, 9, 6, FARBEN.text));
    }
  }

  // ==========================================================================
  // 9. Speicher (auf dem Geraet) und Oberflaeche
  // ==========================================================================

  const SCHLUESSEL_ORTE = "kitu.orte";
  const SCHLUESSEL_STUNDEN = "kitu.stunden";
  const SCHLUESSEL_KOPF = "kitu.kopftitel";

  function ladeOrte() {
    try {
      const roh = localStorage.getItem(SCHLUESSEL_ORTE);
      if (roh) {
        const eigene = JSON.parse(roh);
        if (Array.isArray(eigene) && eigene.length) return eigene;
      }
    } catch (fehler) {
      /* Kein Speicher verfuegbar - dann eben die Vorlagen. */
    }
    return JSON.parse(JSON.stringify(DATEN.orte));
  }

  function sichereOrte(orte) {
    try {
      localStorage.setItem(SCHLUESSEL_ORTE, JSON.stringify(orte));
    } catch (fehler) {
      /* privater Modus - Aenderung gilt nur fuer diese Sitzung */
    }
  }

  function ladeStunden() {
    try {
      return JSON.parse(localStorage.getItem(SCHLUESSEL_STUNDEN) || "[]");
    } catch (fehler) {
      return [];
    }
  }

  function sichereStunden(stunden) {
    try {
      localStorage.setItem(SCHLUESSEL_STUNDEN, JSON.stringify(stunden.slice(-60)));
    } catch (fehler) {
      /* nichts zu tun */
    }
  }

  const $ = (id) => document.getElementById(id);

  const zustand = {
    orte: ladeOrte(),
    stunden: ladeStunden(),
    ergebnis: null,
    massstab: null,
    gezogen: null,
    versatz: [0, 0],
    seed: 1,
  };

  function aktuellerOrt() {
    return zustand.orte.find((o) => o.id === $("ort").value) || zustand.orte[0];
  }

  function aktuelleGruppe() {
    return GRUPPEN.find((g) => g.id === $("gruppe").value) || GRUPPEN[0];
  }

  function fuelleFelder() {
    $("ort").innerHTML = zustand.orte
      .map((o) => `<option value="${o.id}">${o.name}</option>`)
      .join("");
    $("gruppe").innerHTML = GRUPPEN.map(
      (g) => `<option value="${g.id}">${g.name}</option>`
    ).join("");
    $("gruppe").value = (GRUPPEN[2] || GRUPPEN[0]).id;
    $("thema").innerHTML =
      '<option value="">ohne Motto</option>' +
      THEMEN.map(
        (t) => `<option value="${t}">${t[0].toUpperCase() + t.slice(1)}</option>`
      ).join("");
    $("datum").value = heute();
    try {
      const kopf = localStorage.getItem(SCHLUESSEL_KOPF);
      if (kopf) $("ueberschrift").value = kopf;
    } catch (fehler) {
      /* egal */
    }
  }

  function planen(neuerSeed) {
    const ort = aktuellerOrt();
    if (!ort) return;
    if (neuerSeed) zustand.seed = Math.floor(Math.random() * 100000) + 1;
    const form = $("form").value;
    const stationszahlFeld = parseInt($("stationszahl").value, 10);
    const koordination = $("koordination").value;

    const auftrag = {
      ort,
      gruppe: aktuelleGruppe(),
      dauer: Math.max(20, parseInt($("dauer").value, 10) || 60),
      thema: $("thema").value,
      schwerpunkt: $("schwerpunkt").value.trim(),
      ueberschrift: $("ueberschrift").value.trim() || "Ki Tu",
      datum: $("datum").value || heute(),
      stationsbetrieb: form === "stationen" ? true : form === "spiel" ? false : null,
      stationszahl: Number.isFinite(stationszahlFeld) ? stationszahlFeld : null,
      koordinationsteil: koordination === "ja" ? true : koordination === "nein" ? false : null,
      seed: zustand.seed,
      stil: stilprofil(
        zustand.stunden.filter((s) => s.quelle === "eigene"),
        aktuelleGruppe().id
      ),
    };

    zustand.ergebnis = plane(auftrag);
    zeichneAlles();
    aktualisiereListe();
  }

  function zeichneAlles() {
    const leinwand = $("plan");
    const flaeche = $("planflaeche");
    if (!leinwand || !zustand.ergebnis) return;

    const skalierung = window.devicePixelRatio || 1;
    const kasten = leinwand.getBoundingClientRect();
    const breite = kasten.width || flaeche.clientWidth || 320;
    const hoehe = kasten.height || 240;
    leinwand.width = Math.max(200, Math.floor(breite * skalierung));
    leinwand.height = Math.max(150, Math.floor(hoehe * skalierung));

    const ctx = leinwand.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, leinwand.width, leinwand.height);

    const zeichner = leinwandZeichner(ctx, leinwand.height, skalierung);
    const stationen = stationenVon(zustand.ergebnis.stunde);
    const streit = konflikte(stationen, aktuellerOrt())
      .flat()
      .filter((name) => stationen.some((s) => s.name === name));

    const rand = 8 * skalierung;
    zustand.massstab = zeichnePlan(
      zeichner,
      zustand.ergebnis.stunde,
      aktuellerOrt(),
      rand,
      rand,
      leinwand.width - 2 * rand,
      leinwand.height - 2 * rand,
      { mitFlaechen: true, mitNamen: true, markiert: streit }
    );
    zustand.skalierung = skalierung;
  }

  function aktualisiereListe() {
    if (!zustand.ergebnis) return;
    const stunde = zustand.ergebnis.stunde;
    const textVon = (phase) => {
      const teil = (stunde.teile || []).find((t) => t.phase === phase);
      if (!teil || !teil.uebungen.length) return "-";
      return teil.uebungen
        .map((u) => {
          const material = materialText(u, true);
          return material === "kein Material" ? u.name : `${u.name} (${material})`;
        })
        .join("; ");
    };
    $("anfang").textContent = textVon("aufwaermen");
    const koordination = (stunde.teile || []).find((t) => t.phase === "koordination");
    $("koordination-zeile").hidden = !koordination || !koordination.uebungen.length;
    $("koordination-text").textContent = textVon("koordination");
    $("ende").textContent = textVon("abschluss");

    $("stationsliste").innerHTML = stationenVon(stunde)
      .map(
        (station) =>
          `<li><span><span class="name">${station.name}:</span> ` +
          `<span class="material">${materialText(station, true)}</span></span></li>`
      )
      .join("");

    $("warnungen").textContent = (zustand.ergebnis.warnungen || []).join(" ");
  }

  // -- Stationen verschieben -------------------------------------------------
  function zeigerPosition(ereignis) {
    const leinwand = $("plan");
    const kasten = leinwand.getBoundingClientRect();
    const skalierung = zustand.skalierung || window.devicePixelRatio || 1;
    const x = (ereignis.clientX - kasten.left) * (leinwand.width / kasten.width);
    const y = (ereignis.clientY - kasten.top) * (leinwand.height / kasten.height);
    return [x, leinwand.height - y, skalierung];
  }

  function zeigerStart(ereignis) {
    if (!zustand.massstab || !zustand.ergebnis) return;
    const [x, y] = zeigerPosition(ereignis);
    const station = stationAnPunkt(stationenVon(zustand.ergebnis.stunde), zustand.massstab, x, y);
    if (!station) return;
    zustand.gezogen = station;
    const [mx, my] = zustand.massstab.meter(x, y);
    zustand.versatz = [mx - station.x, my - station.y];
    $("plan").setPointerCapture(ereignis.pointerId);
    ereignis.preventDefault();
  }

  function zeigerBewegung(ereignis) {
    if (!zustand.gezogen) return;
    const [x, y] = zeigerPosition(ereignis);
    const [mx, my] = zustand.massstab.meter(x, y);
    const station = zustand.gezogen;
    // Fangraster - auch die Hallengrenze wird auf das Raster gelegt.
    const aufRaster = (wert) => Math.round(wert / RASTER_ZIEHEN) * RASTER_ZIEHEN;
    const maxX =
      Math.floor((zustand.massstab.halleLaenge - station.stellLaenge) / RASTER_ZIEHEN) *
      RASTER_ZIEHEN;
    const maxY =
      Math.floor((zustand.massstab.halleBreite - station.stellBreite) / RASTER_ZIEHEN) *
      RASTER_ZIEHEN;
    const neuX = Math.max(0, Math.min(aufRaster(mx - zustand.versatz[0]), maxX));
    const neuY = Math.max(0, Math.min(aufRaster(my - zustand.versatz[1]), maxY));
    station.x = runde(neuX, 2);
    station.y = runde(neuY, 2);
    zeichneAlles();
    ereignis.preventDefault();
  }

  function zeigerEnde(ereignis) {
    if (!zustand.gezogen) return;
    zustand.gezogen = null;
    try {
      $("plan").releasePointerCapture(ereignis.pointerId);
    } catch (fehler) {
      /* egal */
    }
  }

  // -- Geraete des Ortes -----------------------------------------------------
  function zeigeGeraete() {
    const ort = aktuellerOrt();
    if (!ort) return;
    const bekannt = DATEN.geraete.map((g) => g.id);
    const ids = Array.from(new Set(Object.keys(ort.ausstattung).concat(bekannt)));
    ids.sort((a, b) => geraetName(a).localeCompare(geraetName(b), "de"));
    $("geraete-liste").innerHTML = ids
      .map(
        (id) =>
          `<label>${geraetName(id)}<input type="number" min="0" data-geraet="${id}" ` +
          `value="${ort.ausstattung[id] || 0}"></label>`
      )
      .join("");
    $("geraete-dialog").showModal();
  }

  function uebernehmeGeraete() {
    const ort = aktuellerOrt();
    $("geraete-liste")
      .querySelectorAll("input[data-geraet]")
      .forEach((feld) => {
        const anzahl = parseInt(feld.value, 10) || 0;
        if (anzahl > 0) ort.ausstattung[feld.dataset.geraet] = anzahl;
        else delete ort.ausstattung[feld.dataset.geraet];
      });
    sichereOrte(zustand.orte);
    $("geraete-dialog").close();
  }

  // -- PDF -------------------------------------------------------------------
  function dateiname(stunde) {
    const roh = `${stunde.datum}_${stunde.altersgruppe_id}_${stunde.titel}`;
    return (
      roh
        .replace(/[äÄ]/g, "ae")
        .replace(/[öÖ]/g, "oe")
        .replace(/[üÜ]/g, "ue")
        .replace(/ß/g, "ss")
        .replace(/[^A-Za-z0-9_-]+/g, "_")
        .replace(/_+/g, "_")
        .slice(0, 80) + ".pdf"
    );
  }

  function pdfSpeichern() {
    if (!zustand.ergebnis) return;
    const stunde = zustand.ergebnis.stunde;
    stunde.ueberschrift = $("ueberschrift").value.trim() || "Ki Tu";
    stunde.datum = $("datum").value || stunde.datum;
    const bytes = stundenPdf(stunde, aktuellerOrt(), { mitDetails: $("details").checked });
    const blob = new Blob([bytes], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const verweis = document.createElement("a");
    verweis.href = url;
    verweis.download = dateiname(stunde);
    document.body.appendChild(verweis);
    verweis.click();
    document.body.removeChild(verweis);
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  function merken(alsEigene) {
    if (!zustand.ergebnis) return;
    const stunde = JSON.parse(JSON.stringify(zustand.ergebnis.stunde));
    stunde.quelle = alsEigene ? "eigene" : "geplant";
    stunde.ueberschrift = $("ueberschrift").value.trim() || "Ki Tu";
    zustand.stunden = zustand.stunden.filter((s) => s.id !== stunde.id).concat([stunde]);
    sichereStunden(zustand.stunden);
    $("warnungen").textContent = alsEigene
      ? "Als eigene Stunde gemerkt - sie praegt ab jetzt den Stil."
      : "Stunde auf diesem Geraet gemerkt.";
  }

  // -- Start -----------------------------------------------------------------
  function starte() {
    fuelleFelder();

    $("knopf-planen").addEventListener("click", () => planen(false));
    $("knopf-wuerfeln").addEventListener("click", () => planen(true));
    $("knopf-pdf").addEventListener("click", pdfSpeichern);
    $("knopf-speichern").addEventListener("click", () => merken(false));
    $("knopf-eigene").addEventListener("click", () => merken(true));
    $("knopf-geraete").addEventListener("click", zeigeGeraete);
    $("geraete-fertig").addEventListener("click", uebernehmeGeraete);
    $("geraete-zuruecksetzen").addEventListener("click", () => {
      zustand.orte = JSON.parse(JSON.stringify(DATEN.orte));
      sichereOrte(zustand.orte);
      fuelleFelder();
      $("geraete-dialog").close();
    });

    const einstellungen = $("einstellungen");
    $("knopf-einstellungen").addEventListener("click", () => {
      einstellungen.hidden = !einstellungen.hidden;
      $("knopf-einstellungen").setAttribute("aria-expanded", String(!einstellungen.hidden));
      requestAnimationFrame(zeichneAlles);
    });
    $("knopf-schliessen").addEventListener("click", () => {
      einstellungen.hidden = true;
      requestAnimationFrame(zeichneAlles);
    });

    $("ueberschrift").addEventListener("change", () => {
      try {
        localStorage.setItem(SCHLUESSEL_KOPF, $("ueberschrift").value);
      } catch (fehler) {
        /* egal */
      }
    });
    ["ort", "gruppe", "dauer", "thema", "form", "stationszahl", "koordination"].forEach(
      (id) => $(id).addEventListener("change", () => planen(false))
    );

    const leinwand = $("plan");
    leinwand.addEventListener("pointerdown", zeigerStart);
    leinwand.addEventListener("pointermove", zeigerBewegung);
    leinwand.addEventListener("pointerup", zeigerEnde);
    leinwand.addEventListener("pointercancel", zeigerEnde);

    if (window.ResizeObserver) {
      new ResizeObserver(() => zeichneAlles()).observe($("planflaeche"));
    }
    window.addEventListener("resize", zeichneAlles);
    window.addEventListener("orientationchange", () => setTimeout(zeichneAlles, 200));

    // Auf breiten Schirmen sind die Einstellungen gleich offen.
    if (window.innerWidth >= 900) einstellungen.hidden = false;
    planen(false);
  }

  // Fuer Tests und Erweiterungen zugaenglich machen.
  window.KiTu = {
    plane,
    platziere,
    stellflaeche,
    konflikte,
    kollisionen,
    bedarf,
    stundenPdf,
    stationenVon,
    zustand,
    planen,
    GRUPPEN,
    THEMEN,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", starte);
  } else {
    starte();
  }
})();
