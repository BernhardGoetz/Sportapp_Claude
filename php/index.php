<?php
/**
 * Startseite: Wer angemeldet und bestaetigt ist, bekommt den Stundenplaner.
 * Alle anderen landen bei der Anmeldung bzw. bei der Bestaetigung.
 */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$konto = angemeldet();
$grund = darf_planen($konto);

if ($grund === 'anmeldung') {
    weiter_zu('anmelden.php');
}
if ($grund === 'bestaetigung') {
    weiter_zu('bestaetigen.php');
}

$pfad = konfig()['anwendung'];
if (!is_file($pfad)) {
    meldeseite('Programm fehlt',
        'Bitte <code>python3 werkzeuge/baue_web.py</code> ausfuehren und '
        . '<code>web/kinderturnen.html</code> auf den Server legen.', 404, $konto);
}

header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
readfile($pfad);
