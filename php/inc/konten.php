<?php
/**
 * Konten: anlegen, finden, Kennwoerter, Rollen, Mailcodes.
 */

declare(strict_types=1);

const MINDESTKENNWORT   = 8;
const CODEVERSUCHE      = 5;   // danach hilft nur ein neuer Code
const UNBESTAETIGT_TAGE = 7;   // so lange wartet ein Konto auf den Code
const ROLLEN            = ['nutzer', 'wartung', 'verwalter'];

function kennung_normiert(?string $roh): string
{
    return mb_strtolower(trim((string) $roh));
}

function konto(?string $kennung): ?array
{
    $kennung = kennung_normiert($kennung);
    if ($kennung === '') {
        return null;
    }
    return db_zeile('SELECT * FROM konten WHERE kennung = ?', [$kennung]);
}

function konten_alle(): array
{
    return db_zeilen('SELECT * FROM konten ORDER BY angelegt');
}

function konten_zahl(): int
{
    return db_zahl('SELECT COUNT(*) FROM konten');
}

/** Nie bestaetigte Konten nach einer Woche wieder freigeben. */
function konten_aufraeumen(): int
{
    $grenze = in_tagen(-UNBESTAETIGT_TAGE);
    $alte = db_zeilen(
        'SELECT kennung FROM konten WHERE bestaetigt = 0 AND SUBSTR(angelegt, 1, 10) < ?',
        [$grenze]
    );
    foreach ($alte as $zeile) {
        db_tue('DELETE FROM konten WHERE kennung = ?', [$zeile['kennung']]);
        db_tue('DELETE FROM codes WHERE kennung = ?', [$zeile['kennung']]);
        notiere('konto-verfallen', $zeile['kennung']);
    }
    return count($alte);
}

/**
 * Neues Konto - kostenlos, dauerhaft, noch unbestaetigt.
 * Das erste Konto ueberhaupt wird Verwalter.
 */
function konto_anlegen(string $kennung, string $name, string $kennwort): array
{
    konten_aufraeumen();
    $kennung = kennung_normiert($kennung);
    $rolle = konten_zahl() === 0 ? 'verwalter' : 'nutzer';
    db_tue(
        'INSERT INTO konten
            (kennung, name, kennwort, rolle, angelegt, bestaetigt, gesperrt,
             abo_art, abo_seit, abo_bis, probe_zuletzt, offline)
         VALUES (?, ?, ?, ?, ?, 0, 0, \'frei\', ?, \'\', \'\', \'\')',
        [$kennung, trim($name), kennwort_hash($kennwort), $rolle, zeitstempel(), heute()]
    );
    notiere('registrierung', $kennung, $rolle);
    return konto($kennung);
}

function kennwort_hash(string $kennwort): string
{
    return password_hash($kennwort, PASSWORD_DEFAULT);
}

function kennwort_stimmt(array $konto, string $kennwort): bool
{
    return password_verify($kennwort, $konto['kennwort']);
}

function kennwort_setzen(string $kennung, string $kennwort): void
{
    db_tue('UPDATE konten SET kennwort = ? WHERE kennung = ?',
        [kennwort_hash($kennwort), kennung_normiert($kennung)]);
}

function konto_feld_setzen(string $kennung, string $feld, $wert): void
{
    $erlaubt = ['name', 'rolle', 'bestaetigt', 'gesperrt', 'abo_art', 'abo_seit',
                'abo_bis', 'probe_zuletzt', 'offline'];
    if (!in_array($feld, $erlaubt, true)) {
        throw new InvalidArgumentException("Unbekanntes Feld: $feld");
    }
    db_tue("UPDATE konten SET $feld = ? WHERE kennung = ?",
        [$wert, kennung_normiert($kennung)]);
}

/**
 * Dienstkonto (Verwaltung oder Wartung) - fertig bestaetigt.
 *
 * @return array [Konto, Kennwort] - das Kennwort nur beim ersten Anlegen.
 */
function dienstkonto(string $kennung, string $name, string $rolle): array
{
    $vorhanden = konto($kennung);
    if ($vorhanden) {
        konto_feld_setzen($kennung, 'rolle', $rolle);
        konto_feld_setzen($kennung, 'bestaetigt', 1);
        return [konto($kennung), ''];
    }
    $zeichen = 'abcdefghijkmnpqrstuvwxyz23456789';
    $teile = [];
    for ($i = 0; $i < 4; $i++) {
        $stueck = '';
        for ($j = 0; $j < 5; $j++) {
            $stueck .= $zeichen[random_int(0, strlen($zeichen) - 1)];
        }
        $teile[] = $stueck;
    }
    $kennwort = implode('-', $teile);
    konto_anlegen($kennung, $name, $kennwort);
    konto_feld_setzen($kennung, 'rolle', $rolle);
    konto_feld_setzen($kennung, 'bestaetigt', 1);
    notiere('dienstkonto', kennung_normiert($kennung), $rolle);
    return [konto($kennung), $kennwort];
}

// ---------------------------------------------------------------------------
// Mailcodes
// ---------------------------------------------------------------------------

function code_hash(string $art, string $code): string
{
    return hash_hmac('sha256', $art . ':' . $code, konfig()['geheim']);
}

/** Neuen sechsstelligen Code anlegen und zurueckgeben. */
function code_neu(string $kennung, string $art): string
{
    $code = str_pad((string) random_int(0, 999999), 6, '0', STR_PAD_LEFT);
    db_tue('DELETE FROM codes WHERE kennung = ?', [$kennung]);
    db_tue(
        'INSERT INTO codes (kennung, art, hash, bis, versuche) VALUES (?, ?, ?, ?, 0)',
        [$kennung, $art, code_hash($art, $code), time() + CODEDAUER]
    );
    return $code;
}

/** Code pruefen; stimmt er, ist er danach verbraucht. */
function code_stimmt(string $kennung, string $art, string $eingabe): bool
{
    $zeile = db_zeile('SELECT * FROM codes WHERE kennung = ?', [$kennung]);
    if (!$zeile || $zeile['art'] !== $art || (int) $zeile['bis'] < time()) {
        return false;
    }
    if ((int) $zeile['versuche'] >= CODEVERSUCHE) {
        return false;
    }
    $eingabe = preg_replace('/\D/', '', $eingabe);
    if (hash_equals($zeile['hash'], code_hash($art, $eingabe))) {
        db_tue('DELETE FROM codes WHERE kennung = ?', [$kennung]);
        return true;
    }
    db_tue('UPDATE codes SET versuche = versuche + 1 WHERE kennung = ?', [$kennung]);
    return false;
}

/** Code anlegen und als Mail hinausschicken. */
function code_senden(array $konto, string $art): void
{
    $code = code_neu($konto['kennung'], $art);
    [$betreff, $text] = $art === 'bestaetigung'
        ? text_bestaetigung($konto['name'], $code, konfig()['adresse'])
        : text_kennwort($konto['name'], $code, konfig()['adresse']);
    mail_senden($konto['kennung'], $betreff, $text);
    notiere('mail:' . $art, $konto['kennung']);
}
