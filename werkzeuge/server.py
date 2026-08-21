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
import os
import re
import secrets
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from werkzeuge import lizenzen  # noqa: E402
from werkzeuge import post as postfach  # noqa: E402
from werkzeuge.packen import huelle, kennung as paarkennung  # noqa: E402
from werkzeuge.packen import neuer_lizenzschluessel  # noqa: E402

SEITE = WURZEL / "web" / "kinderturnen.html"
COOKIE = "kitu_sitzung"
RUNDEN = 240000  # PBKDF2-Runden fuer die Kennwoerter
SITZUNGSDAUER = 30 * 24 * 3600
FEHLVERSUCHE = 10
SPERRZEIT = 15 * 60
MINDESTKENNWORT = 8
CODEDAUER = postfach.CODE_MINUTEN * 60  # Gueltigkeit der Mailcodes
CODEVERSUCHE = 5                        # danach hilft nur ein neuer Code
UNBESTAETIGT_TAGE = 7                   # so lange wartet ein Konto auf den Code
ABOZEITEN = {"abo_monat": (31, "Monatsabo"), "abo_jahr": (365, "Jahresabo")}
PROBETAGE = 14      # Probeabo: das Kaufabo zum Ausprobieren
PROBESPERRE = 365   # danach erst im naechsten Jahr wieder
ROLLEN = ("nutzer", "wartung", "verwalter")


def jetzt() -> float:
    return time.time()


def zeitstempel() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def heute() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def in_tagen(tage: int, ab: str = "") -> str:
    """Datum in ``tage`` Tagen - gerechnet ab heute oder ab ``ab``."""
    start = datetime.now(timezone.utc)
    if ab:
        gesetzt = datetime.strptime(ab, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start = max(start, gesetzt)
    return (start + timedelta(days=tage)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Datenhaltung
# ---------------------------------------------------------------------------


class Anwendung:
    """Konten, Sitzungen und Schluessel - alles in einfachen JSON-Dateien."""

    def __init__(self, verzeichnis: Path, https: bool = False,
                 postausgang=None, adresse: str = "") -> None:
        self.verzeichnis = Path(verzeichnis)
        self.verzeichnis.mkdir(parents=True, exist_ok=True)
        self.https = https
        self.adresse = adresse
        self.postausgang = postausgang or postfach.Dateipost(
            self.verzeichnis / "postfach"
        )
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

    def raeume_konten_auf(self) -> int:
        """Nie bestaetigte Konten nach einer Woche wieder freigeben."""
        grenze = in_tagen(-UNBESTAETIGT_TAGE)
        alt = [
            k for k in self.konten
            if not k.get("bestaetigt") and k.get("angelegt", "")[:10] < grenze
        ]
        for konto in alt:
            self.konten.remove(konto)
            self.notiere("konto-verfallen", konto["kennung"])
        if alt:
            self.sichere_konten()
        return len(alt)

    def lege_an(self, kennung: str, name: str, kennwort: str) -> dict:
        self.raeume_konten_auf()
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
            "bestaetigt": False,
            "code": None,
            # Kostenlos und dauerhaft - ein Abo kommt nur auf Wunsch dazu.
            "abo": {"seit": heute(), "bis": "", "art": "frei"},
            "probe_zuletzt": "",  # wann zuletzt ein Probeabo lief
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

    def gib_offline(self, konto: dict) -> str:
        """Neuer Offline-Schluessel fuer genau dieses Konto."""
        konto["offline"] = neuer_lizenzschluessel()
        self.sichere_konten()
        return konto["offline"]

    def huelle_fuer(self, konto: dict) -> dict:
        """Der Eintrag, der in die persoenliche Kopie der Datei kommt."""
        schluessel = konto.get("offline")
        if not schluessel:
            return {}
        return {
            "k": paarkennung(konto["kennung"], schluessel),
            "h": huelle(
                bytes.fromhex(self.blockschluessel()), konto["kennung"], schluessel
            ),
            "bis": konto.get("abo", {}).get("bis", ""),
        }

    def persoenliche_seite(self, konto: dict) -> bytes:
        """Die Datei mit der Huelle dieses Kontos - sonst unveraendert."""
        text = SEITE.read_text(encoding="utf-8")
        eintrag = self.huelle_fuer(konto)
        if not eintrag:
            return text.encode("utf-8")
        neu = "var HUELLEN = " + json.dumps([eintrag], separators=(",", ":")) + ";"
        return re.sub(r"var HUELLEN = \[\];", neu, text, count=1).encode("utf-8")

    # -- Abo ---------------------------------------------------------------
    # Der kostenlose Zugang gilt dauerhaft. Nur ein gebuchtes Abo hat ein
    # Ende - je nach gewaehlter Laufzeit. Laeuft es ab, faellt das Konto auf
    # den kostenlosen Zugang zurueck; verschlossen wird nichts.
    @staticmethod
    def abo_laeuft(konto: dict) -> bool:
        abo = konto.get("abo", {})
        return bool(abo.get("bis")) and abo["bis"] >= heute()

    @staticmethod
    def abo_gelaufen(konto: dict) -> bool:
        """Ein gebuchtes Abo, dessen Zeit um ist."""
        abo = konto.get("abo", {})
        return bool(abo.get("bis")) and abo["bis"] < heute()

    def verlaengere(self, konto: dict, tage: int, art: str = "Abo") -> str:
        abo = konto.setdefault("abo", {"seit": heute()})
        abo["bis"] = in_tagen(tage, abo.get("bis", ""))
        abo["art"] = art
        abo.setdefault("seit", heute())
        self.sichere_konten()
        return abo["bis"]

    def lege_dienstkonto_an(self, kennung: str, name: str, rolle: str) -> tuple:
        """Konto fuer Verwaltung oder Wartung - fertig bestaetigt.

        Gibt (Konto, Kennwort) zurueck; das Kennwort steht nur hier einmal
        im Klartext und wird sonst nirgends abgelegt.
        """
        vorhanden = self.konto(kennung)
        if vorhanden:
            vorhanden["rolle"] = rolle
            vorhanden["bestaetigt"] = True
            self.sichere_konten()
            return vorhanden, ""
        kennwort = "-".join(
            "".join(secrets.choice("abcdefghijkmnpqrstuvwxyz23456789") for _ in range(5))
            for _ in range(4)
        )
        konto = self.lege_an(kennung, name, kennwort)
        konto["rolle"] = rolle
        konto["bestaetigt"] = True
        self.sichere_konten()
        self.notiere("dienstkonto", kennung, rolle)
        return konto, kennwort

    def probe_moeglich(self, konto: dict) -> bool:
        """Ein Probeabo je Konto und Jahr - und nur ohne laufendes Abo."""
        if self.abo_laeuft(konto):
            return False
        zuletzt = konto.get("probe_zuletzt", "")
        return not zuletzt or zuletzt <= in_tagen(-PROBESPERRE)

    def probe_wieder_ab(self, konto: dict) -> str:
        """Datum, ab dem das naechste Probeabo moeglich ist."""
        zuletzt = konto.get("probe_zuletzt", "")
        return in_tagen(PROBESPERRE, zuletzt) if zuletzt else heute()

    def starte_probe(self, konto: dict) -> str:
        konto["abo"] = {
            "seit": heute(),
            "bis": in_tagen(PROBETAGE),
            "art": "Probeabo",
        }
        konto["probe_zuletzt"] = heute()
        self.sichere_konten()
        self.notiere("probeabo", konto["kennung"], konto["abo"]["bis"])
        return konto["abo"]["bis"]

    def beende_abo(self, konto: dict) -> None:
        """Zurueck auf den kostenlosen Zugang - der bleibt dauerhaft offen."""
        konto["abo"] = {"seit": heute(), "bis": "", "art": "frei"}
        konto["offline"] = None  # offline gibt es nur mit laufendem Abo
        self.sichere_konten()

    # -- Codes fuer Mail ---------------------------------------------------
    def _codehash(self, art: str, code: str) -> str:
        return hmac.new(
            self.geheim, (art + ":" + code).encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def neuer_code(self, konto: dict, art: str) -> str:
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        konto["code"] = {
            "art": art,
            "hash": self._codehash(art, code),
            "bis": jetzt() + CODEDAUER,
            "versuche": 0,
        }
        self.sichere_konten()
        return code

    def code_stimmt(self, konto: dict, art: str, code: str) -> bool:
        eintrag = konto.get("code") or {}
        if eintrag.get("art") != art or eintrag.get("bis", 0) < jetzt():
            return False
        if eintrag.get("versuche", 0) >= CODEVERSUCHE:
            return False
        code = "".join(z for z in (code or "") if z.isdigit())
        if hmac.compare_digest(eintrag.get("hash", ""), self._codehash(art, code)):
            konto["code"] = None
            self.sichere_konten()
            return True
        eintrag["versuche"] = eintrag.get("versuche", 0) + 1
        self.sichere_konten()
        return False

    def sende_code(self, konto: dict, art: str) -> None:
        code = self.neuer_code(konto, art)
        bauer = (
            postfach.text_bestaetigung if art == "bestaetigung" else postfach.text_kennwort
        )
        betreff, text = bauer(konto.get("name", ""), code, self.adresse)
        self.postausgang.sende(konto["kennung"], betreff, text)
        self.notiere("mail:" + art, konto["kennung"])


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
            + ('<a href="/verwaltung">Verwaltung</a>'
               if konto["rolle"] == "verwalter" else "")
            + ('<a href="/wartung">Wartung</a>'
               if konto["rolle"] in ("verwalter", "wartung") else "")
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

    def darf_planen(self, konto):
        """Leer, wenn alles passt - sonst der Grund als Wort."""
        if not konto:
            return "anmeldung"
        if not konto.get("bestaetigt"):
            return "bestaetigung"
        return ""

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
            "/wartung": self.zeige_wartung,
            "/freischalten": self.freischalten,
            "/kinderturnen.html": self.gib_datei,
            "/bestaetigen": self.zeige_bestaetigung,
            "/kennwort-vergessen": self.zeige_kennwort_vergessen,
            "/kennwort-neu": self.zeige_kennwort_neu,
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
        konto = self.angemeldet()
        grund = self.darf_planen(konto)
        if grund == "anmeldung":
            self.weiter_zu("/anmelden")
            return
        if grund == "bestaetigung":
            self.weiter_zu("/bestaetigen")
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
            + '<p class=klein>Noch kein Konto? <a href="/registrieren">Hier registrieren</a>.'
            + ' Kennwort weg? <a href="/kennwort-vergessen">Neues anfordern</a>.</p>'
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
                "<p>Dieser Schluessel gehoert zu <strong>genau diesem Konto</strong>: "
                "Datei herunterladen, oeffnen, E-Mail und Schluessel eingeben - "
                "danach laeuft der Stundenplaner ohne Verbindung.</p>"
                f'<p class=schluessel>{html.escape(konto["offline"])}</p>'
                '<p><a href="/kinderturnen.html">Datei herunterladen</a> - '
                "einmal speichern, danach genuegt ein Doppelklick. Ohne die "
                "E-Mail des Kontos ist der Schluessel wertlos.</p>"
            )
        else:
            offline = (
                "<p class=klein>Fuer dieses Konto ist kein Offline-Schluessel "
                "freigegeben. Solange laeuft das Programm nur ueber den Server.</p>"
            )
        abo = konto.get("abo", {})
        if self.app.abo_laeuft(konto):
            abotext = (
                f"<p><strong>{html.escape(abo.get('art', 'Abo'))}</strong> - "
                f"laeuft bis {html.escape(abo['bis'])}.</p>"
                "<p class=klein>Danach geht es kostenlos weiter; nur der "
                "Offline-Schluessel braucht ein laufendes Abo.</p>"
            )
        elif self.app.abo_gelaufen(konto):
            abotext = (
                f"<p>Das Abo lief bis {html.escape(abo['bis'])} - seitdem ist "
                "dieses Konto wieder <strong>kostenlos</strong> unterwegs.</p>"
                "<p class=klein>Planen geht damit dauerhaft weiter. Fuer den "
                "Offline-Betrieb bitte beim Verwalter ein Abo anfragen.</p>"
            )
        else:
            abotext = (
                "<p><strong>Kostenlos</strong> - dauerhaft, ohne Ablaufdatum.</p>"
                "<p class=klein>Planen, Stundenbild als PDF, alles dabei. Ein Abo "
                "braucht nur, wer die Datei offline mitnehmen will.</p>"
            )
        if self.app.probe_moeglich(konto):
            abotext += (
                f"<p class=klein>Zum Ausprobieren: {PROBETAGE} Tage Probeabo mit "
                "allem, was das Kaufabo kann - einmal im Jahr.</p>"
                '<form method=post action="/probeabo">'
                + f'<input type=hidden name=marke value="{marke}">'
                + f'<button id="knopf-probeabo">Probeabo starten '
                + f"({PROBETAGE} Tage)</button></form>"
            )
        elif konto.get("probe_zuletzt"):
            wieder = self.app.probe_wieder_ab(konto)
            abotext += (
                "<p class=klein>Das Probeabo lief zuletzt am "
                f"{html.escape(konto['probe_zuletzt'])}"
                + (
                    f" - ein neues gibt es ab {html.escape(wieder)}.</p>"
                    if not self.app.abo_laeuft(konto)
                    else ".</p>"
                )
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
            + f"<div class=karte><h2>Abo</h2>{abotext}</div>"
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
            taten += knopf("abo_monat", kennung, "+1 Monat")
            taten += knopf("abo_jahr", kennung, "+1 Jahr")
            if self.app.abo_laeuft(eintrag):
                taten += knopf("abo_stop", kennung, "Abo beenden")
            taten += knopf("probe", kennung, "Probeabo geben")
            if eintrag["rolle"] != "verwalter":
                taten += knopf("verwalter", kennung, "Zum Verwalter")
            if eintrag["rolle"] == "nutzer":
                taten += knopf("wartung", kennung, "Zur Wartung")
            zustand = "gesperrt" if eintrag.get("gesperrt") else eintrag["rolle"]
            if not eintrag.get("bestaetigt"):
                zustand += " (unbestaetigt)"
            abo = eintrag.get("abo", {})
            if self.app.abo_laeuft(eintrag):
                abospalte = "{} bis {}".format(
                    html.escape(abo.get("art", "Abo")), html.escape(abo["bis"])
                )
            elif self.app.abo_gelaufen(eintrag):
                abospalte = "kostenlos (Abo lief bis {})".format(html.escape(abo["bis"]))
            else:
                abospalte = "kostenlos"
            if eintrag.get("probe_zuletzt"):
                abospalte += "<br>Probe: " + html.escape(eintrag["probe_zuletzt"])
            zeilen.append(
                "<tr><td>{}<br><span class=klein>{}</span></td><td>{}</td>"
                "<td class=klein>{}</td><td class=klein>{}</td><td>{}</td></tr>".format(
                    html.escape(eintrag["name"] or "-"),
                    html.escape(kennung),
                    zustand,
                    abospalte,
                    html.escape(eintrag.get("offline") or "-"),
                    taten,
                )
            )
        laufend = len([k for k in self.app.konten if self.app.abo_laeuft(k)])
        inhalt = (
            (f'<p class=gut>{html.escape(meldung)}</p>' if meldung else "")
            + "<div class=karte><h1>Verwaltung</h1>"
            + f"<p class=klein>{len(self.app.konten)} Konten, davon {laufend} mit "
            + "laufendem Abo. Planen geht fuer alle dauerhaft und kostenlos; "
            + "das Abo bringt den Offline-Schluessel und laeuft nach der "
            + "gewaehlten Zeit ab. Jeder Schluessel gehoert zu genau einem Konto "
            + "und gilt bis zum Ende des Abos.</p>"
            + "<table><tr><th>Konto</th><th>Zustand</th><th>Abo</th>"
            + "<th>Offline</th><th></th></tr>"
            + "".join(zeilen)
            + "</table></div>"
        )
        self.antworte(seite("Verwaltung", inhalt, konto))

    def gib_datei(self, abfrage=None):
        """Die persoenliche Datei zum Mitnehmen - mit der eigenen Huelle."""
        konto = self.angemeldet()
        grund = self.darf_planen(konto)
        if grund == "anmeldung":
            self.weiter_zu("/anmelden?weiter=/kinderturnen.html")
            return
        if grund == "bestaetigung":
            self.weiter_zu("/bestaetigen")
            return
        if not SEITE.exists():
            self.antworte(seite("Fehlt", "<div class=karte><h1>Programm fehlt</h1></div>",
                                konto), status=HTTPStatus.NOT_FOUND)
            return
        self.app.notiere("datei-geladen", konto["kennung"])
        self.antworte(
            self.app.persoenliche_seite(konto),
            kopf=[("Content-Disposition", 'attachment; filename="kinderturnen.html"')],
        )

    def _codeformular(self, titel: str, ziel: str, text: str, felder: str,
                      fehler: str = "", meldung: str = "") -> None:
        marke, keks = self.gib_marke()
        inhalt = (
            (f'<p class=gut>{html.escape(meldung)}</p>' if meldung else "")
            + (f'<p class=fehler>{html.escape(fehler)}</p>' if fehler else "")
            + f"<div class=karte><h1>{html.escape(titel)}</h1>"
            + f"<p class=klein>{text}</p>"
            + f'<form method=post action="{ziel}">'
            + f'<input type=hidden name=marke value="{self.app.marke(marke)}">'
            + felder
            + "</form></div>"
        )
        self.antworte(seite(titel, inhalt), kopf=self.keks(keks))

    def zeige_bestaetigung(self, abfrage=None, fehler: str = "", meldung: str = ""):
        """Code aus der Mail eingeben - erst danach geht es ins Programm."""
        konto = self.angemeldet()
        if konto and konto.get("bestaetigt"):
            self.weiter_zu("/")
            return
        wohin = konto["kennung"] if konto else ""
        marke, keks = self.gib_marke()
        inhalt = (
            (f'<p class=gut>{html.escape(meldung)}</p>' if meldung else "")
            + (f'<p class=fehler>{html.escape(fehler)}</p>' if fehler else "")
            + "<div class=karte><h1>Konto bestaetigen</h1>"
            + "<p class=klein>Wir haben einen sechsstelligen Code an "
            + (f"<strong>{html.escape(wohin)}</strong>" if wohin else "deine E-Mail")
            + f" geschickt. Er gilt {postfach.CODE_MINUTEN} Minuten.</p>"
            + '<form method=post action="/bestaetigen">'
            + f'<input type=hidden name=marke value="{self.app.marke(marke)}">'
            + ("" if wohin else feld("kennung", "E-Mail", "email"))
            + feld("code", "Code aus der Mail", "text")
            + '<button id="knopf-bestaetigen">Bestaetigen</button></form>'
            + '<form method=post action="/code-neu" style="margin-top:10px">'
            + f'<input type=hidden name=marke value="{self.app.marke(marke)}">'
            + ("" if wohin else '<input type=hidden name=kennung value="">')
            + '<button class=leise id="knopf-code-neu">Code erneut senden</button>'
            + "</form></div>"
        )
        self.antworte(seite("Konto bestaetigen", inhalt), kopf=self.keks(keks))

    def zeige_kennwort_vergessen(self, abfrage=None, fehler: str = "", meldung: str = ""):
        self._codeformular(
            "Kennwort vergessen",
            "/kennwort-vergessen",
            "Gib deine E-Mail an - wenn es dazu ein Konto gibt, ist gleich ein "
            "Code unterwegs.",
            feld("kennung", "E-Mail", "email")
            + '<button id="knopf-code">Code anfordern</button>',
            fehler,
            meldung,
        )

    def zeige_kennwort_neu(self, abfrage=None, fehler: str = "", meldung: str = "",
                           kennung: str = ""):
        vorgabe = kennung or (abfrage or {}).get("kennung", [""])[0]
        self._codeformular(
            "Neues Kennwort",
            "/kennwort-neu",
            "Code aus der Mail eingeben und das neue Kennwort zweimal.",
            feld("kennung", "E-Mail", "email", vorgabe)
            + feld("code", "Code aus der Mail", "text")
            + feld("kennwort", f"Neues Kennwort (mindestens {MINDESTKENNWORT} Zeichen)",
                   "password")
            + feld("kennwort2", "Neues Kennwort wiederholen", "password")
            + '<button id="knopf-kennwort-neu">Kennwort setzen</button>',
            fehler,
            meldung,
        )

    def zeige_wartung(self, abfrage=None):
        """Schaufenster fuer die Wartung: schauen ja, anfassen nein."""
        konto = self.angemeldet()
        if not konto:
            self.weiter_zu("/anmelden?weiter=/wartung")
            return
        if konto["rolle"] not in ("verwalter", "wartung"):
            self.antworte(seite("Kein Zutritt", "<div class=karte><h1>Kein Zutritt</h1>"
                                "<p>Diese Seite ist fuer die Wartung.</p></div>", konto),
                          status=HTTPStatus.FORBIDDEN)
            return

        konten = self.app.konten
        zeilen = [
            ("Konten", str(len(konten))),
            ("davon bestaetigt", str(len([k for k in konten if k.get("bestaetigt")]))),
            ("davon gesperrt", str(len([k for k in konten if k.get("gesperrt")]))),
            ("laufende Abos", str(len([k for k in konten if self.app.abo_laeuft(k)]))),
            ("davon Probeabos",
             str(len([k for k in konten
                      if self.app.abo_laeuft(k)
                      and k.get("abo", {}).get("art") == "Probeabo"]))),
            ("Offline-Schluessel", str(len([k for k in konten if k.get("offline")]))),
            ("offene Sitzungen", str(len(self.app.sitzungen))),
        ]
        datei = "fehlt"
        if SEITE.exists():
            groesse = SEITE.stat().st_size // 1024
            stand = datetime.fromtimestamp(
                SEITE.stat().st_mtime, timezone.utc
            ).strftime("%Y-%m-%d %H:%M UTC")
            datei = f"{groesse} KB, gebaut am {stand}"
        zeilen.append(("kinderturnen.html", datei))
        zeilen.append(("Blockschluessel", self.app.blockschluessel()[:8] + "..."))
        zeilen.append(("Postfach", str(self.app.verzeichnis / "postfach")))

        letzte = ""
        if self.app.protokoll_datei.exists():
            with open(self.app.protokoll_datei, encoding="utf-8") as datei_offen:
                letzte = "".join(datei_offen.readlines()[-15:])

        inhalt = (
            "<div class=karte><h1>Wartung</h1>"
            + "<table>"
            + "".join(
                f"<tr><td>{html.escape(name)}</td><td>{html.escape(wert)}</td></tr>"
                for name, wert in zeilen
            )
            + "</table></div>"
            + "<div class=karte><h2>Letzte Zugriffe</h2>"
            + f"<pre class=klein>{html.escape(letzte) or 'noch nichts'}</pre></div>"
        )
        self.antworte(seite("Wartung", inhalt, konto))

    def freischalten(self, abfrage=None):
        konto = self.angemeldet()
        grund = self.darf_planen(konto)
        if grund:
            wer = konto["kennung"] if konto else self.client_address[0]
            self.app.notiere("freischalten-abgelehnt", wer, grund)
            self.antworte(
                json.dumps({"fehler": grund}).encode("utf-8"),
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
            "/probeabo": self.starte_probeabo,
            "/bestaetigen": self.bestaetige,
            "/code-neu": self.code_erneut,
            "/kennwort-vergessen": self.sende_kennwortcode,
            "/kennwort-neu": self.setze_kennwort_neu,
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
        if not konto.get("bestaetigt"):
            self.app.sende_code(konto, "bestaetigung")
            ziel = "/bestaetigen"
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
        self.app.sende_code(konto, "bestaetigung")
        self.app.beende(self.sitzungsmarke())
        self.app.notiere("registrierung", kennung, konto["rolle"])
        # Angemeldet ist das Konto schon - ins Programm kommt es erst nach
        # dem Code aus der Mail.
        self.weiter_zu("/bestaetigen", self.app.neue_sitzung(konto["kennung"]))

    def bestaetige(self, daten):
        """Code aus der Bestaetigungsmail pruefen."""
        konto = self.angemeldet() or self.app.konto(daten.get("kennung", ""))
        if not konto:
            self.zeige_bestaetigung(fehler="Zu dieser E-Mail gibt es kein Konto.")
            return
        if konto.get("bestaetigt"):
            self.weiter_zu("/")
            return
        if self.app.zu_viele_versuche(self.merkmal(konto["kennung"])):
            self.zeige_bestaetigung(fehler="Zu viele Versuche. Bitte spaeter erneut.")
            return
        if not self.app.code_stimmt(konto, "bestaetigung", daten.get("code", "")):
            self.app.fehlversuch(self.merkmal(konto["kennung"]))
            self.app.notiere("bestaetigung-falsch", konto["kennung"])
            self.zeige_bestaetigung(
                fehler="Dieser Code stimmt nicht oder ist abgelaufen."
            )
            return
        konto["bestaetigt"] = True
        self.app.sichere_konten()
        self.app.notiere("bestaetigt", konto["kennung"])
        self.app.beende(self.sitzungsmarke())
        self.weiter_zu("/", self.app.neue_sitzung(konto["kennung"]))

    def code_erneut(self, daten):
        konto = self.angemeldet() or self.app.konto(daten.get("kennung", ""))
        if konto and not konto.get("bestaetigt"):
            self.app.sende_code(konto, "bestaetigung")
        self.zeige_bestaetigung(meldung="Ein neuer Code ist unterwegs.")

    def sende_kennwortcode(self, daten):
        """Code fuer ein neues Kennwort - ohne zu verraten, wer ein Konto hat."""
        kennung = (daten.get("kennung") or "").strip().lower()
        konto = self.app.konto(kennung)
        if konto and not konto.get("gesperrt"):
            self.app.sende_code(konto, "kennwort")
        else:
            self.app.notiere("kennwortcode-ins-leere", kennung or "-")
        self.zeige_kennwort_neu(
            meldung="Wenn es zu dieser E-Mail ein Konto gibt, ist ein Code unterwegs.",
            kennung=kennung,
        )

    def setze_kennwort_neu(self, daten):
        kennung = (daten.get("kennung") or "").strip().lower()
        konto = self.app.konto(kennung)
        kennwort = daten.get("kennwort", "")
        if len(kennwort) < MINDESTKENNWORT:
            self.zeige_kennwort_neu(
                fehler=f"Das Kennwort braucht mindestens {MINDESTKENNWORT} Zeichen.",
                kennung=kennung,
            )
            return
        if kennwort != daten.get("kennwort2", ""):
            self.zeige_kennwort_neu(fehler="Die Kennwoerter stimmen nicht ueberein.",
                                    kennung=kennung)
            return
        if self.app.zu_viele_versuche(self.merkmal(kennung)):
            self.zeige_kennwort_neu(fehler="Zu viele Versuche. Bitte spaeter erneut.",
                                    kennung=kennung)
            return
        if not konto or not self.app.code_stimmt(konto, "kennwort", daten.get("code", "")):
            self.app.fehlversuch(self.merkmal(kennung))
            self.app.notiere("kennwortcode-falsch", kennung or "-")
            self.zeige_kennwort_neu(
                fehler="Dieser Code stimmt nicht oder ist abgelaufen.", kennung=kennung
            )
            return
        self.app.setze_kennwort(konto, kennwort)
        konto["bestaetigt"] = True  # der Code kam ja an die Mailadresse
        self.app.sichere_konten()
        self.app.notiere("kennwort-neu", konto["kennung"])
        self.app.beende(self.sitzungsmarke())
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

    def starte_probeabo(self, daten):
        """Der Nutzer bestellt sein Probeabo selbst - einmal im Jahr."""
        konto = self.angemeldet()
        if not konto:
            self.weiter_zu("/anmelden?weiter=/konto")
            return
        if not self.app.probe_moeglich(konto):
            self.zeige_konto(
                fehler="Ein Probeabo gibt es einmal im Jahr - und nur, wenn "
                "gerade kein Abo laeuft."
            )
            return
        bis = self.app.starte_probe(konto)
        self.zeige_konto(
            meldung=f"Probeabo laeuft bis {bis}. Fuer den Offline-Betrieb bitte "
            "beim Verwalter den Schluessel anfordern."
        )

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
            if not self.app.abo_laeuft(ziel):
                self.zeige_verwaltung(
                    meldung=f"{ziel['kennung']} hat kein laufendes Abo - offline "
                    "geht nur mit Abo. Erst verlaengern, dann freigeben."
                )
                return
            schluessel = self.app.gib_offline(ziel)
            meldung = (
                f"{ziel['kennung']} kann jetzt offline arbeiten: {schluessel} "
                f"(steht auch im Konto der Person, gilt bis {ziel['abo']['bis']})."
            )
        elif tat == "offline_nehmen":
            ziel["offline"] = None
            meldung = (
                f"{ziel['kennung']} arbeitet wieder nur ueber den Server. "
                "Eine schon heruntergeladene Datei laeuft bis zum Ende des Abos weiter."
            )
        elif tat in ABOZEITEN:
            tage, art = ABOZEITEN[tat]
            bis = self.app.verlaengere(ziel, tage, art)
            meldung = f"{art} von {ziel['kennung']} laeuft bis {bis}."
        elif tat == "abo_stop":
            self.app.beende_abo(ziel)
            meldung = (
                f"Abo von {ziel['kennung']} ist beendet - das Konto plant "
                "kostenlos weiter, der Offline-Schluessel ist weg."
            )
        elif tat in ("verwalter", "wartung"):
            ziel["rolle"] = tat
            meldung = f"{ziel['kennung']} hat jetzt die Rolle {tat}."
        elif tat == "probe":
            if not self.app.probe_moeglich(ziel):
                self.zeige_verwaltung(
                    meldung=f"{ziel['kennung']} hatte im letzten Jahr schon ein "
                    "Probeabo (oder hat gerade ein laufendes Abo)."
                )
                return
            meldung = (
                f"Probeabo fuer {ziel['kennung']} laeuft bis "
                f"{self.app.starte_probe(ziel)}."
            )
        self.app.sichere_konten()
        self.app.notiere("verwaltung:" + tat, konto["kennung"], ziel["kennung"])
        self.zeige_verwaltung(meldung=meldung)


def baue_server(port: int = 8000, verzeichnis: Path = None, https: bool = False,
                host: str = "", postausgang=None,
                adresse: str = "") -> ThreadingHTTPServer:
    """Fertiger Server - die Tests starten ihn in einem eigenen Faden."""
    anwendung = Anwendung(
        verzeichnis or (WURZEL / "server"),
        https=https,
        postausgang=postausgang,
        adresse=adresse,
    )
    behandler = type("KiTuBehandler", (Behandler,), {"anwendung": anwendung})
    server = ThreadingHTTPServer((host, port), behandler)
    server.anwendung = anwendung
    return server


VERWALTUNGSKONTO = os.environ.get("KITU_VERWALTER", "verwaltung@kitu.local")
WARTUNGSKONTO = os.environ.get("KITU_WARTUNG", "wartung@kitu.local")


def zeige_zugang(konto: dict, kennwort: str) -> None:
    """Zugangsdaten einmalig auf die Konsole - nirgends sonst hin."""
    print(f"  {konto['rolle']:<10} {konto['kennung']}")
    if kennwort:
        print(f"  {'Kennwort':<10} {kennwort}")
    else:
        print(f"  {'Kennwort':<10} (unveraendert - Konto gab es schon)")
    print()


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
    parser.add_argument("--konto-anlegen", metavar="E-MAIL",
                        help="Konto anlegen (fertig bestaetigt) und beenden")
    parser.add_argument("--rolle", default="nutzer", choices=list(ROLLEN),
                        help="Rolle fuer --konto-anlegen (Vorgabe: nutzer)")
    parser.add_argument("--name", default="", help="Name fuer --konto-anlegen")
    parser.add_argument("--einrichten", action="store_true",
                        help="Verwaltungs- und Wartungskonto anlegen und beenden")
    parser.add_argument("--adresse", default="",
                        help="oeffentliche Adresse fuer die Verweise in den Mails, "
                             "z. B. https://kitu.mein-verein.de")
    parser.add_argument("--smtp", metavar="WIRT[:PORT]",
                        help="Mailserver; ohne Angabe landen die Mails als "
                             "Textdateien in <daten>/postfach/")
    parser.add_argument("--smtp-nutzer", default="")
    parser.add_argument("--absender", default=postfach.ABSENDER)
    args = parser.parse_args()

    versand = None
    if args.smtp:
        wirt, _, port = args.smtp.partition(":")
        versand = postfach.SMTPPost(
            wirt,
            int(port or 587),
            args.smtp_nutzer,
            os.environ.get("KITU_SMTP_KENNWORT", ""),
            args.absender,
        )
        if args.smtp_nutzer and not os.environ.get("KITU_SMTP_KENNWORT"):
            print("Hinweis: KITU_SMTP_KENNWORT ist nicht gesetzt.")

    server = baue_server(args.port, Path(args.daten), args.https, args.host,
                         versand, args.adresse)
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

    if args.konto_anlegen:
        konto, kennwort = anwendung.lege_dienstkonto_an(
            args.konto_anlegen, args.name or args.konto_anlegen, args.rolle
        )
        zeige_zugang(konto, kennwort)
        return 0

    if args.einrichten:
        print("Zwei Dienstkonten - Kennwoerter bitte gleich notieren, sie "
              "stehen nirgends sonst:\n")
        for kennung, name, rolle in (
            (VERWALTUNGSKONTO, "Verwaltung", "verwalter"),
            (WARTUNGSKONTO, "Wartung", "wartung"),
        ):
            konto, kennwort = anwendung.lege_dienstkonto_an(kennung, name, rolle)
            zeige_zugang(konto, kennwort)
        print("Nach der ersten Anmeldung bitte unter /konto ein eigenes "
              "Kennwort setzen.")
        return 0

    if not SEITE.exists():
        print("Hinweis: web/kinderturnen.html fehlt - bitte "
              "'python3 werkzeuge/baue_web.py' ausfuehren.")
    print(f"Ki Tu laeuft auf http://{args.host or 'localhost'}:{args.port}/")
    print(f"Konten: {anwendung.konten_datei}")
    if not args.smtp:
        print(f"Mails: {anwendung.verzeichnis / 'postfach'} (kein Mailserver "
              "angegeben - Codes stehen dort als Textdatei)")
    if not anwendung.konten:
        print("Das erste angelegte Konto wird automatisch Verwalter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEnde.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
