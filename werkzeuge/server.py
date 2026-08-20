#!/usr/bin/env python3
"""Kleiner Server mit Konten fuer den Kinderturnen-Stundenplaner.

Die Browser-Fassung ist verschluesselt. Diesen Schluessel gibt der Server nur
an angemeldete Konten heraus (``/freischalten``) - ohne Anmeldung laeuft das
Programm nicht. Wer offline arbeiten muss, bekommt vom Verwalter zusaetzlich
einen Offline-Schluessel; damit laeuft dieselbe Datei ohne Verbindung.

Aufruf::

    python3 werkzeuge/server.py --port 8000
    python3 werkzeuge/server.py --port 8000 --https        # hinter nginx/Caddy
    python3 werkzeuge/server.py --verwalter mail@beispiel.de

Nur Standardbibliothek. Die Verschluesselung der Verbindung selbst uebernimmt
ein vorgeschalteter Webserver - dieses Skript spricht einfaches HTTP.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import re
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from werkzeuge import lizenzen  # noqa: E402
from werkzeuge.packen import normiere  # noqa: E402

SEITE = WURZEL / "web" / "kinderturnen.html"
COOKIE = "kitu_sitzung"
RUNDEN = 240000  # PBKDF2-Runden fuer die Kennwoerter
SITZUNGSDAUER = 30 * 24 * 3600
FEHLVERSUCHE = 10
SPERRZEIT = 15 * 60
MINDESTKENNWORT = 8


def jetzt() -> float:
    return time.time()


def zeitstempel() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Datenhaltung
# ---------------------------------------------------------------------------


class Anwendung:
    """Konten, Sitzungen und Schluessel - alles in einfachen JSON-Dateien."""

    def __init__(self, verzeichnis: Path, https: bool = False) -> None:
        self.verzeichnis = Path(verzeichnis)
        self.verzeichnis.mkdir(parents=True, exist_ok=True)
        self.https = https
        self.schloss = threading.Lock()
        self.konten_datei = self.verzeichnis / "konten.json"
        self.sitzungen_datei = self.verzeichnis / "sitzungen.json"
        self.protokoll_datei = self.verzeichnis / "zugriff.log"
        self.konten = self._lies(self.konten_datei, {"konten": []})["konten"]
        self.sitzungen = self._lies(self.sitzungen_datei, {})
        self.fehlversuche = {}
        self.geheim = self._geheim()
        self.lizenzen = lizenzen.lade()

    # -- Ablage ------------------------------------------------------------
    @staticmethod
    def _lies(datei: Path, standard):
        if not datei.exists():
            return standard
        try:
            return json.loads(datei.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return standard

    def _schreib(self, datei: Path, inhalt) -> None:
        vorlaeufig = datei.with_suffix(datei.suffix + ".neu")
        vorlaeufig.write_text(
            json.dumps(inhalt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        vorlaeufig.replace(datei)

    def _geheim(self) -> bytes:
        datei = self.verzeichnis / "geheim.txt"
        if not datei.exists():
            datei.write_text(secrets.token_hex(32), encoding="utf-8")
            try:
                datei.chmod(0o600)
            except OSError:  # pragma: no cover - Dateisystem ohne Rechte
                pass
        return bytes.fromhex(datei.read_text(encoding="utf-8").strip())

    def sichere_konten(self) -> None:
        self._schreib(self.konten_datei, {"konten": self.konten})

    def sichere_sitzungen(self) -> None:
        self._schreib(self.sitzungen_datei, self.sitzungen)

    def notiere(self, was: str, wer: str, mehr: str = "") -> None:
        zeile = f"{zeitstempel()}\t{was}\t{wer}\t{mehr}\n"
        with open(self.protokoll_datei, "a", encoding="utf-8") as datei:
            datei.write(zeile)

    # -- Konten ------------------------------------------------------------
    @staticmethod
    def _kennung(post: str) -> str:
        return (post or "").strip().lower()

    def konto(self, kennung: str):
        kennung = self._kennung(kennung)
        for eintrag in self.konten:
            if eintrag["kennung"] == kennung:
                return eintrag
        return None

    def lege_an(self, kennung: str, name: str, kennwort: str) -> dict:
        salz = secrets.token_hex(16)
        eintrag = {
            "kennung": self._kennung(kennung),
            "name": name.strip(),
            "salz": salz,
            "hash": self._hash(kennwort, salz),
            "runden": RUNDEN,
            "rolle": "verwalter" if not self.konten else "nutzer",
            "angelegt": zeitstempel(),
            "gesperrt": False,
            "offline": None,
        }
        self.konten.append(eintrag)
        self.sichere_konten()
        return eintrag

    @staticmethod
    def _hash(kennwort: str, salz: str, runden: int = RUNDEN) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", kennwort.encode("utf-8"), bytes.fromhex(salz), runden
        ).hex()

    def kennwort_stimmt(self, eintrag: dict, kennwort: str) -> bool:
        versuch = self._hash(kennwort, eintrag["salz"], eintrag.get("runden", RUNDEN))
        return hmac.compare_digest(versuch, eintrag["hash"])

    def setze_kennwort(self, eintrag: dict, kennwort: str) -> None:
        eintrag["salz"] = secrets.token_hex(16)
        eintrag["runden"] = RUNDEN
        eintrag["hash"] = self._hash(kennwort, eintrag["salz"])
        self.sichere_konten()

    # -- Sperre nach Fehlversuchen ----------------------------------------
    def zu_viele_versuche(self, merkmal: str) -> bool:
        versuche = [z for z in self.fehlversuche.get(merkmal, []) if jetzt() - z < SPERRZEIT]
        self.fehlversuche[merkmal] = versuche
        return len(versuche) >= FEHLVERSUCHE

    def fehlversuch(self, merkmal: str) -> None:
        self.fehlversuche.setdefault(merkmal, []).append(jetzt())

    # -- Sitzungen ---------------------------------------------------------
    def neue_sitzung(self, kennung=None) -> str:
        marke = secrets.token_urlsafe(32)
        self.sitzungen[marke] = {"kennung": kennung, "bis": jetzt() + SITZUNGSDAUER}
        self.raeume_auf()
        self.sichere_sitzungen()
        return marke

    def sitzung(self, marke: str):
        eintrag = self.sitzungen.get(marke or "")
        if not eintrag or eintrag["bis"] < jetzt():
            return None
        return eintrag

    def beende(self, marke: str) -> None:
        if marke in self.sitzungen:
            del self.sitzungen[marke]
            self.sichere_sitzungen()

    def raeume_auf(self) -> None:
        alt = [m for m, e in self.sitzungen.items() if e["bis"] < jetzt()]
        for marke in alt:
            del self.sitzungen[marke]

    def marke(self, sitzungsmarke: str) -> str:
        """CSRF-Marke, an die Sitzung gebunden."""
        return hmac.new(
            self.geheim, ("csrf:" + (sitzungsmarke or "")).encode("utf-8"), hashlib.sha256
        ).hexdigest()

    # -- Offline-Schluessel ------------------------------------------------
    def blockschluessel(self) -> str:
        return self.lizenzen["blockschluessel"]

    def freier_schluessel(self):
        belegt = {normiere(k["offline"]) for k in self.konten if k.get("offline")}
        for eintrag in self.lizenzen.get("vorrat", []):
            if eintrag.get("gesperrt"):
                continue
            if normiere(eintrag["schluessel"]) not in belegt:
                return eintrag["schluessel"]
        return None


# ---------------------------------------------------------------------------
# Seiten
# ---------------------------------------------------------------------------

STIL = """
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 system-ui,-apple-system,'Segoe UI',sans-serif;
background:#f3f5f8;color:#17334d}
.hut{background:#17568c;color:#fff;padding:14px 20px;display:flex;
justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.hut a{color:#cfe2f5;text-decoration:none;margin-left:14px}
.mitte{max-width:44rem;margin:28px auto;padding:0 1rem}
.karte{background:#fff;border-radius:14px;padding:24px;margin-bottom:18px;
box-shadow:0 6px 24px rgba(20,50,80,.09)}
h1{font-size:1.5rem;color:#17568c;margin:0 0 6px}
h2{font-size:1.15rem;color:#17568c;margin:0 0 10px}
label{display:block;margin:12px 0 4px;font-size:.95rem;color:#4a5b6b}
input[type=text],input[type=email],input[type=password]{width:100%;padding:11px;
font-size:1rem;border:1px solid #c3ced9;border-radius:9px}
button{margin-top:16px;padding:12px 18px;font-size:1rem;border:0;border-radius:9px;
background:#17568c;color:#fff;cursor:pointer}
button.leise{background:#e6ecf3;color:#17334d;margin-top:0;padding:7px 12px;font-size:.9rem}
table{width:100%;border-collapse:collapse;font-size:.95rem}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid #e6ecf3;vertical-align:top}
.fehler{background:#fbe9e6;color:#9c2f18;padding:11px 14px;border-radius:9px;margin:0 0 8px}
.gut{background:#e8f3ea;color:#1d6b32;padding:11px 14px;border-radius:9px;margin:0 0 8px}
.schluessel{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:1.1rem;
letter-spacing:.06em;background:#f3f5f8;padding:10px 12px;border-radius:9px;display:inline-block}
.klein{font-size:.9rem;color:#5d6f80}
"""


def seite(titel: str, inhalt: str, konto=None) -> bytes:
    anmeldung = ""
    if konto:
        anmeldung = (
            f'<span>{html.escape(konto["name"] or konto["kennung"])}'
            f'<a href="/konto">Konto</a>'
            + ('<a href="/verwaltung">Verwaltung</a>' if konto["rolle"] == "verwalter" else "")
            + '<a href="/">Planen</a></span>'
        )
    text = (
        "<!doctype html><html lang=de><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(titel)} - Ki Tu</title><style>{STIL}</style></head><body>"
        f'<div class=hut><strong>Ki Tu - Stundenplaner</strong>{anmeldung}</div>'
        f'<div class=mitte>{inhalt}</div></body></html>'
    )
    return text.encode("utf-8")


def feld(name: str, beschriftung: str, art: str = "text", wert: str = "") -> str:
    return (
        f'<label for="{name}">{html.escape(beschriftung)}</label>'
        f'<input id="{name}" name="{name}" type="{art}" value="{html.escape(wert)}"'
        f'{" required" if art != "text" else ""}>'
    )


# ---------------------------------------------------------------------------
# Anfragen
# ---------------------------------------------------------------------------


class Behandler(BaseHTTPRequestHandler):
    server_version = "KiTu"
    anwendung: Anwendung = None  # wird in baue_server gesetzt

    # -- Werkzeuge ---------------------------------------------------------
    def log_message(self, format, *args):  # noqa: A002 - Vorgabe der Basisklasse
        pass  # eigenes Protokoll in zugriff.log

    @property
    def app(self) -> Anwendung:
        return type(self).anwendung

    def sitzungsmarke(self):
        roh = self.headers.get("Cookie")
        if not roh:
            return None
        kekse = SimpleCookie()
        try:
            kekse.load(roh)
        except Exception:  # pragma: no cover - kaputte Cookies
            return None
        return kekse[COOKIE].value if COOKIE in kekse else None

    def angemeldet(self):
        eintrag = self.app.sitzung(self.sitzungsmarke())
        if not eintrag or not eintrag.get("kennung"):
            return None
        konto = self.app.konto(eintrag["kennung"])
        if not konto or konto.get("gesperrt"):
            return None
        return konto

    def keks(self, marke: str) -> list:
        """Kopfzeile fuer das Sitzungs-Cookie - leer, wenn nichts zu setzen ist."""
        if not marke:
            return []
        teile = [f"{COOKIE}={marke}", "Path=/", "HttpOnly", "SameSite=Lax",
                 f"Max-Age={SITZUNGSDAUER}"]
        if self.app.https:
            teile.append("Secure")
        return [("Set-Cookie", "; ".join(teile))]

    def antworte(self, koerper: bytes, art="text/html; charset=utf-8", status=200,
                 kopf=None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", art)
        self.send_header("Content-Length", str(len(koerper)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, wert in (kopf or []):
            self.send_header(name, wert)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(koerper)

    def weiter_zu(self, ziel: str, marke: str = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", ziel)
        for name, wert in self.keks(marke):
            self.send_header(name, wert)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def formulardaten(self) -> dict:
        laenge = int(self.headers.get("Content-Length") or 0)
        if laenge <= 0 or laenge > 100_000:
            return {}
        roh = self.rfile.read(laenge).decode("utf-8", "replace")
        return {k: v[0] for k, v in parse_qs(roh, keep_blank_values=True).items()}

    def merkmal(self, kennung: str) -> str:
        return f"{self.client_address[0]}|{kennung}"

    def gib_marke(self):
        """Sitzungsmarke fuer Formulare - notfalls eine neue (anonyme)."""
        marke = self.sitzungsmarke()
        if self.app.sitzung(marke):
            return marke, None
        neu = self.app.neue_sitzung()
        return neu, neu

    @staticmethod
    def sicheres_ziel(ziel: str) -> str:
        if ziel and ziel.startswith("/") and not ziel.startswith("//"):
            return ziel
        return "/"

    # -- GET ---------------------------------------------------------------
    def do_GET(self):  # noqa: N802 - Vorgabe der Basisklasse
        pfad = urlparse(self.path)
        wege = {
            "/": self.zeige_programm,
            "/anmelden": self.zeige_anmeldung,
            "/registrieren": self.zeige_registrierung,
            "/konto": self.zeige_konto,
            "/verwaltung": self.zeige_verwaltung,
            "/freischalten": self.freischalten,
            "/kinderturnen.html": self.gib_datei,
        }
        behandeln = wege.get(pfad.path)
        if not behandeln:
            self.antworte(seite("Nicht gefunden", "<div class=karte><h1>Nicht gefunden</h1>"
                                "<p><a href=/>Zum Stundenplaner</a></p></div>"),
                          status=HTTPStatus.NOT_FOUND)
            return
        behandeln(parse_qs(pfad.query))

    def do_HEAD(self):  # noqa: N802
        self.do_GET()

    def zeige_programm(self, abfrage=None):
        if not self.angemeldet():
            self.weiter_zu("/anmelden")
            return
        if not SEITE.exists():
            self.antworte(seite("Fehlt", "<div class=karte><h1>Programm fehlt</h1>"
                                "<p>Bitte <code>python3 werkzeuge/baue_web.py</code> "
                                "ausfuehren.</p></div>"), status=HTTPStatus.NOT_FOUND)
            return
        self.antworte(SEITE.read_bytes())

    def zeige_anmeldung(self, abfrage=None, fehler: str = ""):
        marke, neu = self.gib_marke()
        ziel = self.sicheres_ziel((abfrage or {}).get("weiter", ["/"])[0])
        inhalt = (
            "<div class=karte><h1>Anmelden</h1>"
            + (f'<p class=fehler>{html.escape(fehler)}</p>' if fehler else "")
            + '<form method=post action="/anmelden">'
            + f'<input type=hidden name=marke value="{self.app.marke(marke)}">'
            + f'<input type=hidden name=weiter value="{html.escape(ziel)}">'
            + feld("kennung", "E-Mail", "email")
            + feld("kennwort", "Kennwort", "password")
            + '<button id="knopf-anmelden">Anmelden</button></form>'
            + '<p class=klein>Noch kein Konto? <a href="/registrieren">Hier registrieren</a>.</p>'
            + "</div>"
        )
        self.antworte(seite("Anmelden", inhalt), kopf=self.keks(neu))

    def zeige_registrierung(self, abfrage=None, fehler: str = "", werte=None):
        marke, neu = self.gib_marke()
        werte = werte or {}
        inhalt = (
            "<div class=karte><h1>Konto anlegen</h1>"
            "<p class=klein>Mit dem Konto planst du Stunden im Browser - "
            "auf dem Handy wie am Rechner.</p>"
            + (f'<p class=fehler>{html.escape(fehler)}</p>' if fehler else "")
            + '<form method=post action="/registrieren">'
            + f'<input type=hidden name=marke value="{self.app.marke(marke)}">'
            + feld("name", "Name", "text", werte.get("name", ""))
            + feld("kennung", "E-Mail", "email", werte.get("kennung", ""))
            + feld("kennwort", "Kennwort (mindestens 8 Zeichen)", "password")
            + feld("kennwort2", "Kennwort wiederholen", "password")
            + '<button id="knopf-registrieren">Konto anlegen</button></form>'
            + '<p class=klein>Schon ein Konto? <a href="/anmelden">Anmelden</a>.</p>'
            + "</div>"
        )
        self.antworte(seite("Registrieren", inhalt), kopf=self.keks(neu))

    def zeige_konto(self, abfrage=None, meldung: str = "", fehler: str = ""):
        konto = self.angemeldet()
        if not konto:
            self.weiter_zu("/anmelden?weiter=/konto")
            return
        marke = self.app.marke(self.sitzungsmarke())
        if konto.get("offline"):
            offline = (
                "<p>Mit diesem Schluessel laeuft der Stundenplaner auch ohne "
                "Verbindung - Datei speichern, oeffnen, Schluessel eingeben:</p>"
                f'<p class=schluessel>{html.escape(konto["offline"])}</p>'
                '<p><a href="/kinderturnen.html">Datei herunterladen</a> - '
                'einmal speichern, danach genuegt ein Doppelklick.</p>'
            )
        else:
            offline = (
                "<p class=klein>Fuer diesen Zugang ist kein Offline-Schluessel "
                "freigegeben. Solange laeuft das Programm nur ueber den Server.</p>"
            )
        inhalt = (
            (f'<p class=gut>{html.escape(meldung)}</p>' if meldung else "")
            + (f'<p class=fehler>{html.escape(fehler)}</p>' if fehler else "")
            + "<div class=karte><h1>Konto</h1>"
            + f"<p>{html.escape(konto['name'] or '-')}<br>"
            + f"<span class=klein>{html.escape(konto['kennung'])} - "
            + f"{html.escape(konto['rolle'])}</span></p>"
            + '<form method=post action="/abmelden">'
            + f'<input type=hidden name=marke value="{marke}">'
            + '<button class=leise id="knopf-abmelden">Abmelden</button></form></div>'
            + f"<div class=karte><h2>Offline arbeiten</h2>{offline}</div>"
            + "<div class=karte><h2>Kennwort aendern</h2>"
            + '<form method=post action="/konto">'
            + f'<input type=hidden name=marke value="{marke}">'
            + feld("alt", "Bisheriges Kennwort", "password")
            + feld("neu", "Neues Kennwort", "password")
            + feld("neu2", "Neues Kennwort wiederholen", "password")
            + '<button id="knopf-kennwort">Aendern</button></form></div>'
        )
        self.antworte(seite("Konto", inhalt, konto))

    def zeige_verwaltung(self, abfrage=None, meldung: str = ""):
        konto = self.angemeldet()
        if not konto:
            self.weiter_zu("/anmelden?weiter=/verwaltung")
            return
        if konto["rolle"] != "verwalter":
            self.antworte(seite("Kein Zutritt", "<div class=karte><h1>Kein Zutritt</h1>"
                                "<p>Diese Seite ist der Verwaltung vorbehalten.</p></div>",
                                konto), status=HTTPStatus.FORBIDDEN)
            return
        marke = self.app.marke(self.sitzungsmarke())

        def knopf(tat, kennung, beschriftung):
            return (
                '<form method=post action="/verwaltung" style="display:inline">'
                f'<input type=hidden name=marke value="{marke}">'
                f'<input type=hidden name=tat value="{tat}">'
                f'<input type=hidden name=konto value="{html.escape(kennung)}">'
                f"<button class=leise>{beschriftung}</button></form> "
            )

        zeilen = []
        for eintrag in self.app.konten:
            kennung = eintrag["kennung"]
            taten = ""
            if eintrag.get("gesperrt"):
                taten += knopf("entsperren", kennung, "Entsperren")
            else:
                taten += knopf("sperren", kennung, "Sperren")
            if eintrag.get("offline"):
                taten += knopf("offline_nehmen", kennung, "Offline entziehen")
            else:
                taten += knopf("offline_geben", kennung, "Offline freigeben")
            if eintrag["rolle"] != "verwalter":
                taten += knopf("verwalter", kennung, "Zum Verwalter")
            zeilen.append(
                "<tr><td>{}<br><span class=klein>{}</span></td><td>{}</td>"
                "<td class=klein>{}</td><td>{}</td></tr>".format(
                    html.escape(eintrag["name"] or "-"),
                    html.escape(kennung),
                    "gesperrt" if eintrag.get("gesperrt") else eintrag["rolle"],
                    html.escape(eintrag.get("offline") or "-"),
                    taten,
                )
            )
        frei = len(
            [
                e
                for e in self.app.lizenzen.get("vorrat", [])
                if not e.get("gesperrt")
            ]
        ) - len([k for k in self.app.konten if k.get("offline")])
        inhalt = (
            (f'<p class=gut>{html.escape(meldung)}</p>' if meldung else "")
            + "<div class=karte><h1>Verwaltung</h1>"
            + f"<p class=klein>{len(self.app.konten)} Konten, "
            + f"{max(0, frei)} Offline-Schluessel noch frei.</p>"
            + "<table><tr><th>Konto</th><th>Zustand</th><th>Offline</th><th></th></tr>"
            + "".join(zeilen)
            + "</table></div>"
        )
        self.antworte(seite("Verwaltung", inhalt, konto))

    def gib_datei(self, abfrage=None):
        """Die Datei zum Mitnehmen - laeuft danach mit dem Offline-Schluessel."""
        konto = self.angemeldet()
        if not konto:
            self.weiter_zu("/anmelden?weiter=/kinderturnen.html")
            return
        if not SEITE.exists():
            self.antworte(seite("Fehlt", "<div class=karte><h1>Programm fehlt</h1></div>",
                                konto), status=HTTPStatus.NOT_FOUND)
            return
        self.app.notiere("datei-geladen", konto["kennung"])
        self.antworte(
            SEITE.read_bytes(),
            kopf=[("Content-Disposition", 'attachment; filename="kinderturnen.html"')],
        )

    def freischalten(self, abfrage=None):
        konto = self.angemeldet()
        if not konto:
            self.app.notiere("freischalten-abgelehnt", self.client_address[0])
            self.antworte(
                json.dumps({"fehler": "nicht angemeldet"}).encode("utf-8"),
                art="application/json; charset=utf-8",
                status=HTTPStatus.UNAUTHORIZED,
            )
            return
        self.app.notiere("freischalten", konto["kennung"])
        self.antworte(
            json.dumps({"schluessel": self.app.blockschluessel()}).encode("utf-8"),
            art="application/json; charset=utf-8",
        )

    # -- POST --------------------------------------------------------------
    def do_POST(self):  # noqa: N802
        pfad = urlparse(self.path).path
        daten = self.formulardaten()
        erwartet = self.app.marke(self.sitzungsmarke())
        if not hmac.compare_digest(daten.get("marke", ""), erwartet):
            self.antworte(
                seite("Abgelaufen", "<div class=karte><h1>Bitte noch einmal</h1>"
                      "<p>Das Formular war zu alt. "
                      '<a href="/anmelden">Zurueck zur Anmeldung</a></p></div>'),
                status=HTTPStatus.FORBIDDEN,
            )
            return

        wege = {
            "/anmelden": self.melde_an,
            "/registrieren": self.registriere,
            "/abmelden": self.melde_ab,
            "/konto": self.aendere_kennwort,
            "/verwaltung": self.verwalte,
        }
        behandeln = wege.get(pfad)
        if not behandeln:
            self.antworte(seite("Nicht gefunden", "<div class=karte><h1>Nicht gefunden</h1></div>"),
                          status=HTTPStatus.NOT_FOUND)
            return
        with self.app.schloss:
            behandeln(daten)

    def melde_an(self, daten):
        kennung = (daten.get("kennung") or "").strip().lower()
        ziel = self.sicheres_ziel(daten.get("weiter", "/"))
        if self.app.zu_viele_versuche(self.merkmal(kennung)):
            self.app.notiere("anmeldung-gesperrt", kennung, self.client_address[0])
            self.zeige_anmeldung(
                fehler="Zu viele Fehlversuche. Bitte in einer Viertelstunde erneut."
            )
            return
        konto = self.app.konto(kennung)
        if not konto or not self.app.kennwort_stimmt(konto, daten.get("kennwort", "")):
            self.app.fehlversuch(self.merkmal(kennung))
            self.app.notiere("anmeldung-falsch", kennung, self.client_address[0])
            self.zeige_anmeldung(fehler="E-Mail oder Kennwort stimmt nicht.")
            return
        if konto.get("gesperrt"):
            self.app.notiere("anmeldung-gesperrtes-konto", kennung)
            self.zeige_anmeldung(fehler="Dieses Konto ist gesperrt.")
            return
        self.app.beende(self.sitzungsmarke())  # Marke wechseln
        self.app.notiere("anmeldung", kennung)
        self.weiter_zu(ziel, self.app.neue_sitzung(konto["kennung"]))

    def registriere(self, daten):
        name = (daten.get("name") or "").strip()
        kennung = (daten.get("kennung") or "").strip().lower()
        kennwort = daten.get("kennwort", "")
        werte = {"name": name, "kennung": kennung}
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", kennung):
            self.zeige_registrierung(fehler="Bitte eine gueltige E-Mail angeben.", werte=werte)
            return
        if len(kennwort) < MINDESTKENNWORT:
            self.zeige_registrierung(
                fehler=f"Das Kennwort braucht mindestens {MINDESTKENNWORT} Zeichen.",
                werte=werte,
            )
            return
        if kennwort != daten.get("kennwort2", ""):
            self.zeige_registrierung(fehler="Die Kennwoerter stimmen nicht ueberein.",
                                     werte=werte)
            return
        if self.app.konto(kennung):
            self.zeige_registrierung(
                fehler="Zu dieser E-Mail gibt es schon ein Konto.", werte=werte
            )
            return
        konto = self.app.lege_an(kennung, name, kennwort)
        self.app.beende(self.sitzungsmarke())
        self.app.notiere("registrierung", kennung, konto["rolle"])
        self.weiter_zu("/", self.app.neue_sitzung(konto["kennung"]))

    def melde_ab(self, daten):
        konto = self.angemeldet()
        self.app.beende(self.sitzungsmarke())
        if konto:
            self.app.notiere("abmeldung", konto["kennung"])
        self.weiter_zu("/anmelden")

    def aendere_kennwort(self, daten):
        konto = self.angemeldet()
        if not konto:
            self.weiter_zu("/anmelden")
            return
        if not self.app.kennwort_stimmt(konto, daten.get("alt", "")):
            self.zeige_konto(fehler="Das bisherige Kennwort stimmt nicht.")
            return
        neu = daten.get("neu", "")
        if len(neu) < MINDESTKENNWORT:
            self.zeige_konto(fehler=f"Mindestens {MINDESTKENNWORT} Zeichen, bitte.")
            return
        if neu != daten.get("neu2", ""):
            self.zeige_konto(fehler="Die Kennwoerter stimmen nicht ueberein.")
            return
        self.app.setze_kennwort(konto, neu)
        self.app.notiere("kennwort-geaendert", konto["kennung"])
        self.zeige_konto(meldung="Das Kennwort ist geaendert.")

    def verwalte(self, daten):
        konto = self.angemeldet()
        if not konto or konto["rolle"] != "verwalter":
            self.antworte(seite("Kein Zutritt", "<div class=karte><h1>Kein Zutritt</h1></div>"),
                          status=HTTPStatus.FORBIDDEN)
            return
        ziel = self.app.konto(daten.get("konto", ""))
        if not ziel:
            self.zeige_verwaltung(meldung="Dieses Konto gibt es nicht.")
            return
        tat = daten.get("tat", "")
        meldung = ""
        if tat == "sperren":
            ziel["gesperrt"] = True
            meldung = f"{ziel['kennung']} ist gesperrt."
        elif tat == "entsperren":
            ziel["gesperrt"] = False
            meldung = f"{ziel['kennung']} ist wieder frei."
        elif tat == "offline_geben":
            schluessel = self.app.freier_schluessel()
            if not schluessel:
                self.zeige_verwaltung(
                    meldung="Kein freier Offline-Schluessel mehr - Vorrat auffuellen "
                    "und neu bauen."
                )
                return
            ziel["offline"] = schluessel
            meldung = f"{ziel['kennung']} kann jetzt offline arbeiten."
        elif tat == "offline_nehmen":
            ziel["offline"] = None
            meldung = f"{ziel['kennung']} arbeitet wieder nur ueber den Server."
        elif tat == "verwalter":
            ziel["rolle"] = "verwalter"
            meldung = f"{ziel['kennung']} ist jetzt Verwalter."
        self.app.sichere_konten()
        self.app.notiere("verwaltung:" + tat, konto["kennung"], ziel["kennung"])
        self.zeige_verwaltung(meldung=meldung)


def baue_server(port: int = 8000, verzeichnis: Path = None, https: bool = False,
                host: str = "") -> ThreadingHTTPServer:
    """Fertiger Server - die Tests starten ihn in einem eigenen Faden."""
    anwendung = Anwendung(verzeichnis or (WURZEL / "server"), https=https)
    behandler = type("KiTuBehandler", (Behandler,), {"anwendung": anwendung})
    server = ThreadingHTTPServer((host, port), behandler)
    server.anwendung = anwendung
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="", help="Vorgabe: alle Adressen")
    parser.add_argument("--daten", default=str(WURZEL / "server"),
                        help="Verzeichnis fuer Konten, Sitzungen, Protokoll")
    parser.add_argument("--https", action="store_true",
                        help="Cookies als 'Secure' markieren (hinter nginx/Caddy)")
    parser.add_argument("--verwalter", metavar="E-MAIL",
                        help="dieses Konto zum Verwalter machen und beenden")
    args = parser.parse_args()

    server = baue_server(args.port, Path(args.daten), args.https, args.host)
    anwendung = server.anwendung

    if args.verwalter:
        konto = anwendung.konto(args.verwalter)
        if not konto:
            print(f"Kein Konto zu {args.verwalter}.")
            return 1
        konto["rolle"] = "verwalter"
        anwendung.sichere_konten()
        print(f"{args.verwalter} ist jetzt Verwalter.")
        return 0

    if not SEITE.exists():
        print("Hinweis: web/kinderturnen.html fehlt - bitte "
              "'python3 werkzeuge/baue_web.py' ausfuehren.")
    print(f"Ki Tu laeuft auf http://{args.host or 'localhost'}:{args.port}/")
    print(f"Konten: {anwendung.konten_datei}")
    if not anwendung.konten:
        print("Das erste angelegte Konto wird automatisch Verwalter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEnde.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
