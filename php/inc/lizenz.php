<?php
/**
 * Blockschluessel und Offline-Schluessel.
 *
 * Die ausgelieferte Datei ist mit einem 32-Byte-Blockschluessel
 * verschluesselt. Angemeldete Konten bekommen ihn ueber ``freischalten.php``.
 * Fuer den Offline-Betrieb verdeckt ihn eine **Huelle**, die aus Kontokennung
 * *und* Offline-Schluessel abgeleitet wird - jede Huelle passt damit auf genau
 * ein Konto. Dieselbe Rechnung steht in ``werkzeuge/packen.py`` und
 * ``web/quelle/lader.js``.
 */

declare(strict_types=1);

const ABLEITUNGSRUNDEN = 20000;

function lizenzdatei(): array
{
    $pfad = konfig()['lizenzen'];
    if (!is_file($pfad)) {
        throw new RuntimeException("Lizenzdatei fehlt: $pfad");
    }
    return json_decode(file_get_contents($pfad), true);
}

function blockschluessel(): string
{
    return lizenzdatei()['blockschluessel'];
}

/** Schluessel ohne Bindestriche, Leerzeichen und Kleinschreibung. */
function schluessel_normiert(?string $roh): string
{
    return preg_replace('/[^A-Z0-9]/', '', mb_strtoupper((string) $roh));
}

function schluessel_paar(string $kennung, string $schluessel): string
{
    return kennung_normiert($kennung) . ':' . schluessel_normiert($schluessel);
}

/** Kurzes, oeffentliches Merkmal eines Konto-Schluessel-Paares. */
function paarkennung(string $kennung, string $schluessel): string
{
    return substr(hash('sha256', 'kitu2-kennung:' . schluessel_paar($kennung, $schluessel)), 0, 8);
}

/** Ableitung aus Konto und Schluessel - 20000 Runden SHA-256. */
function ableitung(string $kennung, string $schluessel): string
{
    $h = hash('sha256', 'kitu2:' . schluessel_paar($kennung, $schluessel), true);
    for ($i = 0; $i < ABLEITUNGSRUNDEN; $i++) {
        $h = hash('sha256', $h . 'kitu2', true);
    }
    return $h;
}

/** Blockschluessel, verdeckt mit der Ableitung - als Hex. */
function huelle(string $kennung, string $schluessel): string
{
    $block = hex2bin(blockschluessel());
    $deckel = ableitung($kennung, $schluessel);
    $aus = '';
    for ($i = 0; $i < strlen($block); $i++) {
        $aus .= chr(ord($block[$i]) ^ ord($deckel[$i]));
    }
    return bin2hex($aus);
}

/** Neuer Offline-Schluessel in der Form KITU-XXXX-XXXX-XXXX-XXXX. */
function schluessel_neu(): string
{
    $zeichen = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';  // ohne I, O, 0, 1
    $bloecke = [];
    for ($i = 0; $i < 4; $i++) {
        $stueck = '';
        for ($j = 0; $j < 4; $j++) {
            $stueck .= $zeichen[random_int(0, strlen($zeichen) - 1)];
        }
        $bloecke[] = $stueck;
    }
    return 'KITU-' . implode('-', $bloecke);
}

/** Offline-Schluessel fuer genau dieses Konto vergeben. */
function offline_geben(array $konto): string
{
    $schluessel = schluessel_neu();
    konto_feld_setzen($konto['kennung'], 'offline', $schluessel);
    notiere('offline-vergeben', $konto['kennung'], $konto['abo_bis']);
    return $schluessel;
}

/** Der Eintrag, der in die persoenliche Kopie der Datei kommt. */
function huelleneintrag(array $konto): array
{
    if ($konto['offline'] === '') {
        return [];
    }
    return [
        'k'   => paarkennung($konto['kennung'], $konto['offline']),
        'h'   => huelle($konto['kennung'], $konto['offline']),
        'bis' => $konto['abo_bis'],
    ];
}

/**
 * Die Datei mit der Huelle dieses Kontos - sonst unveraendert.
 * Ohne Offline-Schluessel bleibt sie, wie sie gebaut wurde.
 */
function persoenliche_datei(array $konto): string
{
    $pfad = konfig()['anwendung'];
    if (!is_file($pfad)) {
        throw new RuntimeException('Die Anwendung fehlt: ' . $pfad);
    }
    $text = file_get_contents($pfad);
    $eintrag = huelleneintrag($konto);
    if (!$eintrag) {
        return $text;
    }
    return preg_replace(
        '/var HUELLEN = \[\];/',
        'var HUELLEN = ' . json_encode([$eintrag]) . ';',
        $text,
        1
    );
}
