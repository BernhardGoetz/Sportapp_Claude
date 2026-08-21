/* Lader der Browser-Fassung - das einzige Stueck, das offen in der Seite steht.
 *
 * Er entschluesselt das eigentliche Programm und startet es. Den Schluessel
 * dafuer bekommt er auf zwei Wegen:
 *
 *   1. Aus einem Lizenzschluessel. Der wird auf dem Geraet gemerkt; danach
 *      laeuft die Seite ohne jede Verbindung.
 *   2. Vom Lizenzserver. Ohne Lizenzschluessel fragt die Seite bei jedem
 *      Start dort nach und merkt sich nichts - ohne Verbindung geht nichts.
 *
 * Ohne beides bleibt der Block verschluesselt und die Seite zeigt nur die
 * Abfrage.
 */
(function () {
  "use strict";

  var BLOCK = "__BLOCK__"; // verschluesseltes Programm (Base64)
  var HUELLEN = __HUELLEN__; // je Lizenz: Kennung und verdeckter Blockschluessel
  var SERVER = "__SERVER__"; // Adresse des Lizenzservers ("" = keiner)
  var ABLAGE = "kitu.lizenz";
  var MARKE = "/*KITU1*/\n";
  var RUNDEN = 20000;

  // -------------------------------------------------------------- SHA-256
  var K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];

  function dreh(wert, zahl) {
    return ((wert >>> zahl) | (wert << (32 - zahl))) >>> 0;
  }

  function sha256(bytes) {
    var laenge = bytes.length;
    var voll = new Uint8Array(((((laenge + 8) >> 6) + 1) << 6));
    voll.set(bytes);
    voll[laenge] = 0x80;
    var sicht = new DataView(voll.buffer);
    sicht.setUint32(voll.length - 8, Math.floor((laenge * 8) / 4294967296));
    sicht.setUint32(voll.length - 4, (laenge * 8) >>> 0);

    var h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
    var h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
    var w = new Uint32Array(64);

    for (var i = 0; i < voll.length; i += 64) {
      for (var t = 0; t < 16; t++) w[t] = sicht.getUint32(i + t * 4);
      for (t = 16; t < 64; t++) {
        var x = w[t - 15], y = w[t - 2];
        var s0 = (dreh(x, 7) ^ dreh(x, 18) ^ (x >>> 3)) >>> 0;
        var s1 = (dreh(y, 17) ^ dreh(y, 19) ^ (y >>> 10)) >>> 0;
        w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0;
      }
      var a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, hh = h7;
      for (t = 0; t < 64; t++) {
        var S1 = (dreh(e, 6) ^ dreh(e, 11) ^ dreh(e, 25)) >>> 0;
        var wahl = ((e & f) ^ (~e & g)) >>> 0;
        var t1 = (hh + S1 + wahl + K[t] + w[t]) >>> 0;
        var S0 = (dreh(a, 2) ^ dreh(a, 13) ^ dreh(a, 22)) >>> 0;
        var mehrheit = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
        var t2 = (S0 + mehrheit) >>> 0;
        hh = g; g = f; f = e; e = (d + t1) >>> 0;
        d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0;
      h3 = (h3 + d) >>> 0; h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0;
      h6 = (h6 + g) >>> 0; h7 = (h7 + hh) >>> 0;
    }

    var aus = new Uint8Array(32);
    var av = new DataView(aus.buffer);
    var teile = [h0, h1, h2, h3, h4, h5, h6, h7];
    for (i = 0; i < 8; i++) av.setUint32(i * 4, teile[i]);
    return aus;
  }

  // --------------------------------------------------------------- Hilfen
  function bytes(text) {
    return new TextEncoder().encode(text);
  }

  function verbinde(a, b) {
    var aus = new Uint8Array(a.length + b.length);
    aus.set(a);
    aus.set(b, a.length);
    return aus;
  }

  function ausHex(hex) {
    var aus = new Uint8Array(hex.length / 2);
    for (var i = 0; i < aus.length; i++) {
      aus[i] = parseInt(hex.substr(i * 2, 2), 16);
    }
    return aus;
  }

  function zuHex(roh) {
    var aus = "";
    for (var i = 0; i < roh.length; i++) {
      aus += (roh[i] < 16 ? "0" : "") + roh[i].toString(16);
    }
    return aus;
  }

  function normiere(lizenz) {
    return (lizenz || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  }

  // ------------------------------------------------------------ Schluessel
  function normiereKonto(konto) {
    return (konto || "").trim().toLowerCase();
  }

  function paar(konto, lizenz) {
    return normiereKonto(konto) + ":" + normiere(lizenz);
  }

  function kennung(konto, lizenz) {
    return zuHex(sha256(bytes("kitu2-kennung:" + paar(konto, lizenz)))).slice(0, 8);
  }

  function ausLizenz(konto, lizenz) {
    var h = sha256(bytes("kitu2:" + paar(konto, lizenz)));
    var marke = bytes("kitu2");
    for (var i = 0; i < RUNDEN; i++) h = sha256(verbinde(h, marke));
    return h;
  }

  /* Huelle zu diesem Konto-Schluessel-Paar: {schluessel, bis} oder null. */
  function blockschluessel(konto, lizenz) {
    var gesucht = kennung(konto, lizenz);
    for (var i = 0; i < HUELLEN.length; i++) {
      if (HUELLEN[i].k !== gesucht) continue;
      var verdeckt = ausHex(HUELLEN[i].h);
      var ableitung = ausLizenz(konto, lizenz);
      var schluessel = new Uint8Array(32);
      for (var j = 0; j < 32; j++) schluessel[j] = verdeckt[j] ^ ableitung[j];
      return { schluessel: schluessel, bis: HUELLEN[i].bis || "" };
    }
    return null;
  }

  /* Abo abgelaufen? Vergleicht das Datum "JJJJ-MM-TT" mit dem heutigen Tag. */
  function abgelaufen(bis) {
    if (!bis) return false;
    var heute = new Date();
    var tag =
      heute.getFullYear() +
      "-" + ("0" + (heute.getMonth() + 1)).slice(-2) +
      "-" + ("0" + heute.getDate()).slice(-2);
    return bis < tag;
  }

  function entschluessele(schluessel) {
    var roh = atob(BLOCK);
    var n = roh.length;
    var aus = new Uint8Array(n);
    var zaehler = new Uint8Array(4);
    var zv = new DataView(zaehler.buffer);
    for (var block = 0; block * 32 < n; block++) {
      zv.setUint32(0, block);
      var strom = sha256(verbinde(schluessel, zaehler));
      for (var j = 0; j < 32 && block * 32 + j < n; j++) {
        aus[block * 32 + j] = roh.charCodeAt(block * 32 + j) ^ strom[j];
      }
    }
    var text;
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(aus);
    } catch (fehler) {
      return null;
    }
    return text.slice(0, MARKE.length) === MARKE ? text.slice(MARKE.length) : null;
  }

  // -------------------------------------------------------------- Ablage
  function gemerkt() {
    try {
      var roh = localStorage.getItem(ABLAGE);
      return roh ? JSON.parse(roh) : null;
    } catch (fehler) {
      return null;
    }
  }

  function merke(konto, lizenz) {
    try {
      localStorage.setItem(
        ABLAGE, JSON.stringify({ konto: konto, schluessel: lizenz })
      );
      return true;
    } catch (fehler) {
      return false;
    }
  }

  function vergiss() {
    try {
      localStorage.removeItem(ABLAGE);
    } catch (fehler) {
      /* dann eben nicht */
    }
  }

  // -------------------------------------------------------------- Abfrage
  function abfrage(meldung, vorgabe) {
    var stil = document.createElement("style");
    stil.textContent =
      "body{margin:0;font:16px/1.5 system-ui,-apple-system,'Segoe UI',sans-serif;" +
      "background:#f3f5f8;color:#17334d;display:flex;min-height:100vh;" +
      "align-items:center;justify-content:center}" +
      ".karte{background:#fff;border-radius:14px;padding:28px;max-width:26rem;" +
      "width:calc(100% - 2rem);box-shadow:0 8px 30px rgba(0,0,0,.12)}" +
      ".karte h1{margin:0 0 4px;font-size:1.5rem;color:#17568c}" +
      ".karte p{margin:0 0 16px;color:#4a5b6b}" +
      ".karte input{width:100%;margin-bottom:8px;padding:12px;font-size:1.05rem;" +
      "letter-spacing:.04em;border:1px solid #c3ced9;border-radius:9px;" +
      "box-sizing:border-box;text-align:center}" +
      ".karte button{margin-top:12px;width:100%;padding:13px;font-size:1.05rem;" +
      "border:0;border-radius:9px;background:#17568c;color:#fff;cursor:pointer}" +
      ".hinweis{margin-top:12px;min-height:1.4em;font-size:.95rem;color:#a4341f}" +
      ".fuss{margin:14px 0 0;font-size:.85rem;color:#7b8a99}";
    document.head.appendChild(stil);

    var karte = document.createElement("div");
    karte.className = "karte";
    var titel = document.createElement("h1");
    titel.textContent = "Ki Tu - Stundenplaner";
    var text = document.createElement("p");
    text.textContent =
      meldung || "Bitte E-Mail und Offline-Schluessel des Kontos eingeben.";

    var kontofeld = document.createElement("input");
    kontofeld.setAttribute("placeholder", "E-Mail des Kontos");
    kontofeld.setAttribute("type", "email");
    kontofeld.setAttribute("autocapitalize", "none");
    kontofeld.setAttribute("spellcheck", "false");
    kontofeld.id = "kontofeld";

    var feld = document.createElement("input");
    feld.setAttribute("placeholder", "KITU-XXXX-XXXX-XXXX-XXXX");
    feld.setAttribute("autocapitalize", "characters");
    feld.setAttribute("spellcheck", "false");
    feld.id = "lizenzfeld";

    var knopf = document.createElement("button");
    knopf.textContent = "Freischalten";
    knopf.id = "lizenzknopf";
    var hinweis = document.createElement("div");
    hinweis.className = "hinweis";
    hinweis.id = "lizenzhinweis";
    var fuss = document.createElement("p");
    fuss.className = "fuss";
    fuss.textContent =
      "Der Schluessel gehoert zu genau einem Konto und steht dort unter "
      + "„Konto“. Ohne Schluessel geht es online ueber die Anmeldung.";

    karte.appendChild(titel);
    karte.appendChild(text);
    karte.appendChild(kontofeld);
    karte.appendChild(feld);
    karte.appendChild(knopf);
    karte.appendChild(hinweis);
    karte.appendChild(fuss);
    document.body.innerHTML = "";
    document.body.appendChild(karte);
    (vorgabe && vorgabe.konto ? feld : kontofeld).focus();
    if (vorgabe && vorgabe.konto) kontofeld.value = vorgabe.konto;

    function pruefe() {
      hinweis.textContent = "";
      knopf.disabled = true;
      knopf.textContent = "Pruefe ...";
      setTimeout(function () {
        var konto = kontofeld.value;
        var lizenz = feld.value;
        var treffer = konto && lizenz ? blockschluessel(konto, lizenz) : null;
        var programm = treffer ? entschluessele(treffer.schluessel) : null;
        knopf.disabled = false;
        knopf.textContent = "Freischalten";
        if (!programm) {
          hinweis.textContent = "E-Mail und Schluessel passen nicht zusammen.";
          feld.select();
          return;
        }
        if (abgelaufen(treffer.bis)) {
          hinweis.textContent =
            "Das Abo ist am " + treffer.bis + " abgelaufen. Bitte online anmelden.";
          return;
        }
        if (!merke(konto, lizenz)) {
          hinweis.textContent =
            "Hinweis: Dieses Geraet kann den Schluessel nicht speichern.";
        }
        starte(programm);
      }, 30);
    }

    knopf.addEventListener("click", pruefe);
    [kontofeld, feld].forEach(function (eingabe) {
      eingabe.addEventListener("keydown", function (ereignis) {
        if (ereignis.key === "Enter") pruefe();
      });
    });
  }

  function warte(meldung) {
    document.body.innerHTML =
      '<p style="font:16px system-ui,sans-serif;color:#4a5b6b;' +
      'text-align:center;margin:25vh 1rem">' + meldung + "</p>";
  }

  // -------------------------------------------------------------- Ablauf
  function starte(programm) {
    document.body.innerHTML = "";
    new Function(programm)();
  }

  function vomServer() {
    warte("Verbindung zum Server ...");
    fetch(SERVER, { cache: "no-store", credentials: "same-origin" })
      .then(function (antwort) {
        // Nicht angemeldet: zur Anmeldung, sofern wir vom Server kommen.
        if (antwort.status === 401 && location.protocol !== "file:") {
          location.href = "anmelden.php?weiter=" + encodeURIComponent(
            location.pathname.replace(/^.*\//, "") || "index.php"
          );
          throw new Error("nicht angemeldet");
        }
        return antwort.json();
      })
      .then(function (daten) {
        var programm = daten.schluessel
          ? entschluessele(ausHex(daten.schluessel))
          : null;
        if (!programm) throw new Error("keine Freigabe");
        starte(programm);
      })
      .catch(function (fehler) {
        if (String(fehler.message) === "nicht angemeldet") return;
        abfrage(
          "Der Server hat nicht freigegeben. Mit einem Offline-Schluessel " +
            "laeuft das Programm auch ohne Verbindung."
        );
      });
  }

  function ausDerAdresse() {
    var adresse = location.hash + location.search;
    var schluessel = adresse.match(/lizenz=([^&]+)/);
    var konto = adresse.match(/konto=([^&]+)/);
    if (!schluessel) return null;
    return {
      schluessel: decodeURIComponent(schluessel[1]),
      konto: konto ? decodeURIComponent(konto[1]) : "",
    };
  }

  function los() {
    var adresse = ausDerAdresse();
    var zugang = adresse || gemerkt();
    if (zugang && zugang.schluessel === "neu") {
      vergiss();
      abfrage("");
      return;
    }
    if (zugang && zugang.schluessel && zugang.konto) {
      // Das Ableiten dauert einen Augenblick - erst die Meldung zeigen.
      warte("Einen Moment ...");
      setTimeout(function () {
        var treffer = blockschluessel(zugang.konto, zugang.schluessel);
        var programm = treffer ? entschluessele(treffer.schluessel) : null;
        if (programm && abgelaufen(treffer.bis)) {
          abfrage(
            "Das Abo ist am " + treffer.bis + " abgelaufen. Bitte online "
              + "anmelden und verlaengern.",
            zugang
          );
          return;
        }
        if (programm) {
          merke(zugang.konto, zugang.schluessel);
          starte(programm);
          return;
        }
        vergiss();
        abfrage("Der gespeicherte Offline-Schluessel gilt nicht mehr.", zugang);
      }, 30);
      return;
    }
    if (zugang && zugang.schluessel) {
      abfrage("Zu diesem Schluessel fehlt die E-Mail des Kontos.", zugang);
      return;
    }
    // Eine Adresse wie "freischalten.php" fuehrt von einer geoeffneten Datei
    // aus ins Leere - dann gleich nach dem Offline-Schluessel fragen.
    var ausDatei = location.protocol === "file:" && !/^https?:/i.test(SERVER);
    if (SERVER && !ausDatei) {
      vomServer();
      return;
    }
    abfrage("");
  }

  los();
})();
